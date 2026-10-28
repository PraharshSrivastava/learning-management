"""Captions for locally rendered module videos, timed one of two ways (``CAPTION_TIMING``).

- Forced alignment (``forced-alignment``): a local aligner times every word.
- Narration timing (``narration-timing``): no aligner. Slide spans are exact (measured clip
  lengths and narration WAVs, with edge silence trimmed). Inside a slide, phrases share the
  speech time by spoken length, pinned to audible pauses at phrase ends where one is found.
  In ``auto`` mode a failed alignment falls back to narration timing.

Both publish the same ``.vtt`` and ``.captions.json`` the player validates.
"""

from __future__ import annotations

import array
import hashlib
import html
import json
import math
import os
import re
import subprocess
import tempfile
import textwrap
import unicodedata
import wave
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from app.core.logging import generation_logger
from app.core.settings import settings
from app.core.storage import resolve_public_asset_path
from app.generation.tts_normalization import clean_text_for_tts

logger = generation_logger(__name__)
VERSION = 1
ALIGNED_METHOD = "forced-alignment"
NARRATION_METHOD = "narration-timing"
NARRATION_LEGACY_METHOD = "narration-timing-legacy"
NARRATION_METHODS = {NARRATION_METHOD, NARRATION_LEGACY_METHOD}


class CaptionsUnavailable(RuntimeError):
    pass


class ScriptMismatch(CaptionsUnavailable):
    """The script is not what was spoken; no timing method can caption it correctly."""


def caption_timing() -> str:
    """Resolve CAPTION_TIMING to "aligned", "narration" or "off"."""
    if settings.caption_timing == "auto":
        return "aligned" if settings.caption_align_command else "narration"
    return settings.caption_timing


def _keep_existing(existing: dict, timing: str) -> bool:
    """Valid captions are kept, except estimated ones once an aligner can do better."""
    return timing != "aligned" or existing.get("method") not in NARRATION_METHODS


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_inputs(slides: list[dict]) -> list[dict]:
    return [
        {
            "script_sha256": hashlib.sha256(str(slide.get("script") or "").encode()).hexdigest(),
            "audio_sha256": digest(
                resolve_public_asset_path(str(slide.get("audio_path") or ""), settings)
            ),
        }
        for slide in slides
    ]


def narration_pace() -> str:
    """Audio made under different speed settings must be re-synthesized."""
    return f"speed={settings.tts_speed};max_wpm={settings.tts_max_words_per_minute}"


def record_narration_source(audio: Path, script: str) -> None:
    atomic_json(
        audio.with_suffix(".narration.json"),
        {
            "version": VERSION,
            "audio_sha256": digest(audio),
            "spoken_sha256": hashlib.sha256(clean_text_for_tts(script).encode()).hexdigest(),
            "pace": narration_pace(),
        },
    )


def narration_matches(audio: Path, script: str) -> bool:
    try:
        source = json.loads(audio.with_suffix(".narration.json").read_text(encoding="utf-8"))
        return (
            source.get("version") == VERSION
            and source.get("audio_sha256") == digest(audio)
            and source.get("spoken_sha256")
            == hashlib.sha256(clean_text_for_tts(script).encode()).hexdigest()
            and source.get("pace") == narration_pace()
        )
    except (OSError, ValueError, TypeError):
        return False


def atomic_json(path: Path, data: dict) -> None:
    atomic_text(path, json.dumps(data, ensure_ascii=False, allow_nan=False))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def record_video_source(
    video: Path, slides: list[dict], durations: list[float], inputs: list[dict] | None = None
) -> None:
    """Record provenance at render time; historical audio is not assumed to match."""
    if not all(
        narration_matches(
            resolve_public_asset_path(str(slide.get("audio_path") or ""), settings),
            str(slide.get("script") or ""),
        )
        for slide in slides
    ):
        raise CaptionsUnavailable(
            "Narration script/audio provenance missing; regenerate narration before captions"
        )
    current_inputs = source_inputs(slides)
    if inputs is not None and current_inputs != inputs:
        raise CaptionsUnavailable("Narration changed during video rendering")
    atomic_json(
        video.with_suffix(".source.json"),
        {
            "version": VERSION,
            "video_sha256": digest(video),
            "inputs": current_inputs,
            "clip_durations": durations,
        },
    )


def _tokens(text: str) -> list[str]:
    # Match the Qwen English tokenizer: punctuation is removed inside each token.
    return [
        cleaned
        for token in text.lower().split()
        if (
            cleaned := "".join(
                char for char in token if char == "'" or unicodedata.category(char)[0] in {"L", "N"}
            )
        )
    ]


def display_words(script: str) -> tuple[str, list[tuple[str, int]]]:
    """Map normalized speech tokens back to readable script words, failing closed."""
    original = re.sub(r"<[^>]*>", "", script).split()
    normalized = clean_text_for_tts(script)
    expected = _tokens(normalized)

    @lru_cache(maxsize=None)
    def match(index: int, consumed: int):
        if index == len(original):
            return () if consumed == len(expected) else None
        # Financial-year/currency expressions can span more than one script word.
        for end in range(index + 1, min(len(original), index + 8) + 1):
            text = " ".join(original[index:end])
            tokens = _tokens(clean_text_for_tts(text))
            if tokens and expected[consumed : consumed + len(tokens)] == tokens:
                tail = match(end, consumed + len(tokens))
                if tail is not None:
                    return ((text, len(tokens)),) + tail
        return None

    mapping = match(0, 0)
    if not mapping:
        raise CaptionsUnavailable("Narration contains unalignable tokens")
    return normalized, list(mapping)


def align_slide(audio: Path, transcript: str) -> list[dict]:
    return align_slides([(audio, transcript)])[0]


def align_slides(items: list[tuple[Path, str]]) -> list[list[dict]]:
    """Run an explicitly configured local worker with no shell or audio upload.

    All slides of a module go to one worker run, so the model loads once per module.
    """
    command = list(settings.caption_align_command)
    if not command:
        raise CaptionsUnavailable(
            "Configure CAPTION_ALIGN_COMMAND with a local forced-alignment worker"
        )
    with tempfile.TemporaryDirectory() as directory:
        request = Path(directory) / "request.json"
        result = Path(directory) / "result.json"
        request.write_text(
            json.dumps(
                {
                    "items": [
                        {"audio": str(audio.resolve()), "text": transcript}
                        for audio, transcript in items
                    ],
                    "language": "English",
                }
            ),
            encoding="utf-8",
        )
        subprocess.run(
            command + [str(request), str(result)],
            check=True,
            timeout=600 + 120 * len(items),
            capture_output=True,
            text=True,
            shell=False,
            env={
                **os.environ,
                "CAPTION_ALIGN_MODEL_PATH": settings.caption_align_model_path,
                "CAPTION_ALIGN_DEVICE": settings.caption_align_device,
            },
        )  # nosec B603
        results = json.loads(result.read_text(encoding="utf-8"))["results"]
        if len(results) != len(items):
            raise CaptionsUnavailable("Aligner returned a different number of slides")
        return [entry["words"] for entry in results]


def group_cues(script: str, words: list[dict], duration: float, offset: float = 0) -> list[dict]:
    transcript, mapping = display_words(script)
    if len(words) != len(_tokens(transcript)) or [
        _tokens(str(word.get("text", ""))) for word in words
    ] != [[token] for token in _tokens(transcript)]:
        raise CaptionsUnavailable("Aligner did not return the complete expected transcript")
    previous = 0.0
    for word in words:
        start, end = float(word["start"]), float(word["end"])
        if (
            not all(math.isfinite(t) for t in (start, end))
            or start < previous
            # Aligner frames are ~80 ms, so short function words can be zero-length.
            or end < start
            or end > duration + 0.05
        ):
            raise CaptionsUnavailable("Invalid word timing")
        previous = end
    readable = []
    index = 0
    for text, count in mapping:
        readable.append(
            {
                "text": text,
                "start": float(words[index]["start"]),
                "end": min(duration, float(words[index + count - 1]["end"])),
            }
        )
        index += count
    # Phrases end at sentence punctuation or audible pauses; long phrases are then balanced.
    phrases, batch = [], []
    for word in readable:
        if batch and word["start"] - batch[-1]["end"] > 0.4:
            phrases.append(batch)
            batch = []
        batch.append(word)
        if word["text"].endswith((".", "!", "?", ";")):
            phrases.append(batch)
            batch = []
    if batch:
        phrases.append(batch)
    return [
        {
            "start": round(offset + piece[0]["start"], 3),
            "end": round(offset + piece[-1]["end"], 3),
            "text": " ".join(word["text"] for word in piece),
        }
        for phrase in phrases
        for piece in _balanced_pieces(phrase)
    ]


CUE_MAX_CHARS = 78  # About two lines; stricter than the Video Generator's 2 x 42.
CUE_LINE_CHARS = 42
# From the Video Generator: a cue should not end on a word that leads into the next phrase.
WEAK_ENDINGS = frozenset("a an the of to by in on at for with and or its their from as".split())


def _balanced_pieces(words: list[dict], *, timed: bool = True) -> list[list[dict]]:
    """Halve an over-long phrase at its most even word boundary, so no word is left alone.

    Aligned words also cap a piece at 6 s. Untimed (narration) pieces must wrap into two
    42-character lines, and avoid ending on a weak word or stranding a single word.
    """
    text = " ".join(word["text"] for word in words)
    if timed:
        fits = len(text) <= CUE_MAX_CHARS and words[-1]["end"] - words[0]["start"] <= 6
    else:
        fits = len(text) <= CUE_MAX_CHARS and len(textwrap.wrap(text, CUE_LINE_CHARS)) <= 2
    if len(words) < 2 or fits:
        return [words]

    def cost(split: int) -> tuple:
        left = len(" ".join(word["text"] for word in words[:split]))
        balance = max(left, len(text) - left - 1)
        # Prefer a natural break after a comma or colon when it is nearly as even.
        balance -= 10 if words[split - 1]["text"].endswith((",", ":")) else 0
        if timed:
            return (0, 0, balance)
        weak = words[split - 1]["text"].lower().lstrip("([\"'‘“") in WEAK_ENDINGS
        return (weak, split in (1, len(words) - 1), balance)

    split = min(range(1, len(words)), key=cost)
    return _balanced_pieces(words[:split], timed=timed) + _balanced_pieces(
        words[split:], timed=timed
    )


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{ms:03}"


def serialize_vtt(cues: list[dict]) -> str:
    previous = 0.0
    blocks = ["WEBVTT\n"]
    for cue in cues:
        start, end = cue["start"], cue["end"]
        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < previous
            or end <= start
            or not cue["text"].strip()
        ):
            raise CaptionsUnavailable("Invalid caption cue")
        blocks.append(f"{timestamp(start)} --> {timestamp(end)}\n{html.escape(cue['text'])}\n")
        previous = end
    if not cues:
        raise CaptionsUnavailable("No caption cues")
    return "\n".join(blocks)


@contextmanager
def module_lock(video: Path):
    lock = video.with_suffix(".media.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise CaptionsUnavailable("Video or caption generation is already running") from error
    os.close(descriptor)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


# Narration timing: the Video Generator's method (measured speech span, shared between
# phrases by length), plus edge trimming and sentence anchors from audible pauses.
MIN_CUE_SECONDS = 0.8
LOUD_PERCENTILE = 0.95  # The slide's own speech level, robust to a few loud clicks.
SPEECH_EDGE_RATIO = 0.03  # About -30 dB below it: soft consonants still count as speech.
# About -20 dB: breaths and room tone inside a pause count as silence. Measured on real
# narration, 0.06 missed shallow sentence pauses; 0.08-0.15 all found them.
PAUSE_RATIO = 0.10
SPEECH_MARGIN_SECONDS = 0.05  # Show a phrase slightly before its first sound.
MIN_PAUSE_FRAMES = 25  # 0.25 s; stops between words are much shorter.
ANCHOR_TOLERANCE_SECONDS = 1.5
RATE_VARIATION = 0.15  # Speaking rate varies by about this share of a stretch.
TIMING_NOISE_SECONDS = 0.25  # Plus this much for pause detection and short stretches.
# Squared-error units: a sentence end nearly always pauses, a comma or colon often does,
# and a pause seldom falls anywhere else.
UNPAIRED_SENTENCE = 4.0
UNPAIRED_PHRASE = 1.0
UNPAIRED_PAUSE = 2.0
# Search limits that keep long slides fast. On real narration a pair never skipped more than
# 3 phrase ends or 2 pauses since the last one, and a matched pause never sat more than 6% of
# the speech from its plain proportional estimate.
MAX_SKIPPED_PHRASES = 10
MAX_SKIPPED_PAUSES = 6
SEARCH_WINDOW_SECONDS = 4.0
SEARCH_WINDOW_SHARE = 0.08


def _speech_layout(samples: array.array, duration: float) -> tuple[float, float, list]:
    """Speech start, end and inner pauses of one slide's narration, in seconds.

    Any failure to find speech falls back to the whole narration with no pauses.
    """
    envelope = _envelope(samples)
    loud = sorted(envelope)[int(LOUD_PERCENTILE * (len(envelope) - 1))] if envelope else 0.0
    if loud <= 0:
        return 0.0, duration, []
    voiced = [index for index, level in enumerate(envelope) if level >= loud * SPEECH_EDGE_RATIO]
    start = max(0.0, voiced[0] / 100 - SPEECH_MARGIN_SECONDS)
    end = min(duration, (voiced[-1] + 1) / 100 + SPEECH_MARGIN_SECONDS)
    if end - start < 0.1:
        return 0.0, duration, []
    # A pause is a long enough run of quiet frames between two clearly spoken ones.
    spoken = [index for index, level in enumerate(envelope) if level >= loud * PAUSE_RATIO]
    pauses = [
        ((before + 1) / 100 + SPEECH_MARGIN_SECONDS, after / 100 - SPEECH_MARGIN_SECONDS)
        for before, after in zip(spoken, spoken[1:])
        if after - before - 1 >= MIN_PAUSE_FRAMES
    ]
    return start, end, pauses


def _spoken_words(script: str) -> list[dict]:
    """Written words, weighted by the length of what the voice says for them."""
    try:
        transcript, mapping = display_words(script)
    except (CaptionsUnavailable, RecursionError):
        return [
            {"text": word, "weight": len(word) + 1}
            for word in re.sub(r"<[^>]*>", "", script).split()
        ]
    tokens, words, index = _tokens(transcript), [], 0
    for text, count in mapping:
        words.append({"text": text, "weight": len(" ".join(tokens[index : index + count])) + 1})
        index += count
    return words


CLOSERS = "\"')]”’"
# Abbreviations that end in a full stop without ending the sentence ("etc." often does).
ABBREVIATIONS = frozenset({"mr.", "mrs.", "ms.", "dr.", "e.g.", "i.e.", "vs."})


def _ends_sentence(text: str) -> bool:
    bare = text.rstrip(CLOSERS)
    return bare.endswith((".", "!", "?", ";")) and bare.lower().lstrip("([\"'") not in ABBREVIATIONS


def _ends_phrase(text: str) -> bool:
    """A sentence end, or a comma or colon where the voice may pause."""
    return _ends_sentence(text) or text.rstrip(CLOSERS).endswith((",", ":"))


def _match_pauses(
    positions: list[float],
    unpaired: list[float],
    pauses: list[tuple[float, float]],
    start: float,
    end: float,
    total: float,
) -> dict:
    """Pair phrase ends with pauses, in order and one each; returns {phrase index: pause}.

    ``positions`` are the spoken-length positions of the phrase ends (of ``total``). Each
    pause start is predicted from the previous pinned phrase end at the slide's own speaking
    rate, plus any pauses in between, so estimates do not drift across a long slide. A pair
    scores its error relative to the predicted stretch (speaking rate varies by a share of
    it), and only within ANCHOR_TOLERANCE_SECONDS. A phrase end left without a pause costs
    its ``unpaired`` penalty and a pause left without a phrase end costs UNPAIRED_PAUSE.
    """
    silent = [0.0]
    for pause_start, pause_end in pauses:
        silent.append(silent[-1] + pause_end - pause_start)
    rate = (end - start - silent[-1]) / total if total else 0.0
    if not positions or not pauses or rate <= 0:
        return {}
    skipped = [0.0]
    for penalty in unpaired:
        skipped.append(skipped[-1] + penalty)

    def score(state: tuple[int, int], weight: float, before: int, actual: float) -> float:
        """Cost of the stretch from the pinned state to ``actual``, ahead of pause ``before``."""
        phrase, pause = state
        time = pauses[pause - 1][1] if pause else start
        stretch = rate * (weight - (positions[phrase - 1] if phrase else 0.0))
        stretch += silent[before] - silent[pause]
        error = abs(actual - time - stretch)
        if error > ANCHOR_TOLERANCE_SECONDS:
            return math.inf
        return (error / (RATE_VARIATION * stretch + TIMING_NOISE_SECONDS)) ** 2

    # States are (phrase ends used, pauses used), the last of each pinned together. Only pauses
    # near a phrase end's proportional estimate are tried, and only recent states (or the
    # start) precede a pair; see the search limits above.
    window = SEARCH_WINDOW_SECONDS + SEARCH_WINDOW_SHARE * (end - start)
    cost, back = {(0, 0): 0.0}, {}
    for phrase in range(1, len(positions) + 1):
        estimate = start + (end - start) * positions[phrase - 1] / total
        for pause in range(1, len(pauses) + 1):
            if abs(pauses[pause - 1][0] - estimate) > window:
                continue
            states = [(0, 0)] + [
                (used_phrases, used_pauses)
                for used_phrases in range(max(1, phrase - MAX_SKIPPED_PHRASES), phrase)
                for used_pauses in range(max(1, pause - MAX_SKIPPED_PAUSES), pause)
                if (used_phrases, used_pauses) in cost
            ]
            for state in states:
                base = cost[state]
                total_cost = (
                    base
                    + score(state, positions[phrase - 1], pause - 1, pauses[pause - 1][0])
                    + skipped[phrase - 1] - skipped[state[0]]
                    + UNPAIRED_PAUSE * (pause - state[1] - 1)
                )
                if total_cost < cost.get((phrase, pause), math.inf):
                    cost[(phrase, pause)] = total_cost
                    back[(phrase, pause)] = state
    finish = {
        state: base
        + score(state, total, len(pauses), end)
        + skipped[-1] - skipped[state[0]]
        + UNPAIRED_PAUSE * (len(pauses) - state[1])
        for state, base in cost.items()
    }
    state, anchors = min(finish, key=finish.get), {}
    while state != (0, 0):
        anchors[state[0] - 1] = pauses[state[1] - 1]
        state = back[state]
    return anchors


def _share(weights: list[float], start: float, end: float) -> list[float]:
    """Boundaries dividing start..end by weight, each piece at least MIN_CUE_SECONDS if it fits."""
    span, count = end - start, len(weights)
    durations = [span / count] * count
    if span >= MIN_CUE_SECONDS * count:
        pinned: set[int] = set()
        while True:
            free = span - MIN_CUE_SECONDS * len(pinned)
            total = sum(weight for i, weight in enumerate(weights) if i not in pinned)
            if total <= 0:  # Rounding pinned every piece: the span is exactly the minimum.
                durations = [span / count] * count
                break
            durations = [
                MIN_CUE_SECONDS if i in pinned else free * weight / total
                for i, weight in enumerate(weights)
            ]
            short = {i for i, length in enumerate(durations) if length < MIN_CUE_SECONDS}
            if short <= pinned:
                break
            pinned |= short
    boundaries = [start]
    for length in durations[:-1]:
        boundaries.append(boundaries[-1] + length)
    return boundaries + [end]


def _phrases(words: list[dict]) -> list[list[dict]]:
    """Cue pieces: sentences, with long ones balanced into two-line phrases."""
    pieces, sentence = [], []
    for word in words:
        sentence.append(word)
        if _ends_sentence(word["text"]):
            pieces.extend(_balanced_pieces(sentence, timed=False))
            sentence = []
    if sentence:
        pieces.extend(_balanced_pieces(sentence, timed=False))
    return pieces


def narration_cues(
    script: str, start: float, end: float, pauses: list | None = None, offset: float = 0.0
) -> list[dict]:
    """Time one slide's written phrases across its measured speech start..end.

    Speech time follows spoken length, pinned at every phrase end matched to a pause: the
    phrase ends where the pause starts and the next begins where it ends.
    """
    words = _spoken_words(script)
    if not words or end <= start:
        return []
    positions, done = [], 0.0
    for word in words:
        done += word["weight"]
        positions.append(done)
    candidates = [index for index, word in enumerate(words[:-1]) if _ends_phrase(word["text"])]
    matched = _match_pauses(
        [positions[i] for i in candidates],
        [UNPAIRED_SENTENCE if _ends_sentence(words[i]["text"]) else UNPAIRED_PHRASE for i in candidates],
        pauses or [],
        start,
        end,
        done,
    )
    knots = [(0.0, start, start)]
    knots += [(positions[candidates[i]], *matched[i]) for i in sorted(matched)]
    knots.append((done, end, end))

    def time_at(weight: float, starting: bool) -> float:
        """Map a spoken-length position to time; at a pinned pause, before or after it."""
        for (left, _, after), (right, before, resume) in zip(knots, knots[1:]):
            if weight == right:
                return resume if starting else before
            if left <= weight < right:
                return after + (before - after) * (weight - left) / (right - left)
        return end

    cues, first = [], 0.0
    for piece in _phrases(words):
        last = first + sum(word["weight"] for word in piece)
        text = " ".join(word["text"] for word in piece)
        cues.append({"start": time_at(first, True), "end": time_at(last, False), "text": text})
        first = last
    # Contiguous runs of cues (no pinned pause between them) get their minimum time here.
    runs, run = [], [cues[0]]
    for cue in cues[1:]:
        if cue["start"] > run[-1]["end"]:
            runs.append(run)
            run = []
        run.append(cue)
    runs.append(run)
    for run in runs:
        bounds = _share(
            [cue["end"] - cue["start"] for cue in run], run[0]["start"], run[-1]["end"]
        )
        for cue, (first_time, last_time) in zip(run, zip(bounds, bounds[1:]), strict=True):
            cue["start"], cue["end"] = first_time, last_time
    for cue, following in zip(cues, [*cues[1:], None], strict=True):
        limit = following["start"] if following else end
        cue["end"] = max(cue["end"], min(cue["start"] + MIN_CUE_SECONDS, limit))
    return [
        {
            "start": round(offset + cue["start"], 3),
            "end": round(offset + cue["end"], 3),
            "text": cue["text"],
        }
        for cue in cues
    ]


# What a failed alignment can raise: no command, worker error or timeout, bad worker output,
# or a transcript the aligner cannot handle.
ALIGNMENT_FAILURES = (
    CaptionsUnavailable,
    OSError,
    subprocess.SubprocessError,
    ValueError,
    KeyError,
    TypeError,
)


def _after_failed_alignment(video: Path, error: Exception, upgrading: bool) -> str | None:
    """In auto mode, keep existing narration captions or fall back to narration timing.

    Explicit ``aligned`` mode re-raises. Returns a status when nothing should be written.
    """
    if settings.caption_timing != "auto" or isinstance(error, ScriptMismatch):
        raise error
    logger.warning(
        "caption_alignment_failed video=%s fallback=%s reason=%s",
        video,
        "kept_narration_captions" if upgrading else "narration_timing",
        error,
    )
    return "kept_narration_captions" if upgrading else None


def _aligned_cues(slides: list[dict], audios: list, durations: list, offsets: list) -> list:
    items = [
        (audio, display_words(slide["script"])[0]) for slide, audio in zip(slides, audios, strict=True)
    ]
    cues = []
    for slide, words, duration, offset in zip(
        slides, align_slides(items), durations, offsets, strict=True
    ):
        cues.extend(group_cues(slide["script"], words, duration, offset))
    return cues


def generate_module_captions(
    video: Path, slides: list[dict], *, already_locked: bool = False
) -> str:
    timing = caption_timing()
    if timing == "off":
        return "skipped_captions_off"
    if not already_locked:
        with module_lock(video):
            return generate_module_captions(video, slides, already_locked=True)
    from app.generation.video import audio_duration

    try:
        if not slides:
            raise CaptionsUnavailable("No narration slides")
        provenance = json.loads(video.with_suffix(".source.json").read_text(encoding="utf-8"))
        inputs = source_inputs(slides)
        video_hash = digest(video)
        if (
            not isinstance(provenance, dict)
            or provenance.get("version") != VERSION
            or provenance.get("video_sha256") != video_hash
            or provenance.get("inputs") != inputs
        ):
            raise CaptionsUnavailable(
                "Video and saved narration provenance do not match; regenerate video"
            )
        durations = provenance["clip_durations"]
        if len(durations) != len(slides) or any(not math.isfinite(t) or t <= 0 for t in durations):
            raise CaptionsUnavailable("Invalid rendered clip durations")
        existing = _existing_captions(video, video_hash)
        upgrading = existing is not None and existing.get("inputs") == inputs
        if upgrading and _keep_existing(existing, timing):
            return "skipped_valid_captions"
        audios, narration = [], []
        for slide, clip_duration in zip(slides, durations, strict=True):
            audio = resolve_public_asset_path(slide["audio_path"], settings)
            duration = audio_duration(str(audio))
            if duration > clip_duration + 0.05:
                raise CaptionsUnavailable("Narration exceeds rendered clip")
            audios.append(audio)
            narration.append(duration)
        # Slide n starts after the measured clips before it; its transition pause gets no cue.
        offsets = [sum(durations[:index]) for index in range(len(slides))]
        if timing == "aligned":
            try:
                cues = _aligned_cues(slides, audios, narration, offsets)
            except ALIGNMENT_FAILURES as error:
                kept = _after_failed_alignment(video, error, upgrading)
                if kept:
                    return kept
                timing = "narration"
        if timing == "narration":
            cues = []
            with tempfile.TemporaryDirectory() as directory:
                for index, (slide, audio, duration, clip_duration, offset) in enumerate(
                    zip(slides, audios, narration, durations, offsets, strict=True)
                ):
                    samples = _to_pcm(audio, Path(directory) / f"slide_{index}.wav")
                    # Never past the slide's own clip, even within the 0.05 s slack above.
                    start, end, pauses = _speech_layout(samples, min(duration, clip_duration))
                    script = str(slide["script"] or "")
                    cues.extend(narration_cues(script, start, end, pauses, offset))
        final_duration = audio_duration(str(video))
        if abs(sum(durations) - final_duration) > 0.1 or not cues:
            raise CaptionsUnavailable("Caption timeline differs from rendered video")
        if cues[-1]["end"] > final_duration:
            raise CaptionsUnavailable("Caption timeline differs from rendered video")
        if digest(video) != video_hash or source_inputs(slides) != inputs:
            raise CaptionsUnavailable("Video or narration changed during caption timing")
        content = serialize_vtt(cues)
        fingerprint = hashlib.sha256(content.encode()).hexdigest()
        stat = video.stat()
        atomic_text(video.with_suffix(".vtt"), content)
        atomic_json(
            video.with_suffix(".captions.json"),
            {
                "version": VERSION,
                "language": "en",
                "method": ALIGNED_METHOD if timing == "aligned" else NARRATION_METHOD,
                "video_sha256": video_hash,
                "inputs": inputs,
                "video_size": stat.st_size,
                "video_mtime": int(stat.st_mtime),
                "duration": final_duration,
                "fingerprint": fingerprint,
                "vtt_sha256": fingerprint,
                "cue_count": len(cues),
            },
        )
        return "generated"
    except (FileNotFoundError, KeyError, ValueError, TypeError) as error:
        raise CaptionsUnavailable(f"Caption source data unavailable: {error}") from error


def check_video_source(video: Path, slides: list[dict]) -> None:
    """Read-only preflight for a selected backfill; does not create assets or locks."""
    try:
        source = json.loads(video.with_suffix(".source.json").read_text(encoding="utf-8"))
        if (
            not slides
            or source.get("version") != VERSION
            or source.get("video_sha256") != digest(video)
            or source.get("inputs") != source_inputs(slides)
        ):
            raise CaptionsUnavailable("Video/narration provenance mismatch; regenerate video")
    except (OSError, ValueError, TypeError) as error:
        raise CaptionsUnavailable(f"Video provenance unavailable: {error}") from error


# Videos rendered before render-time provenance existed. Each slide clip is the slide's
# narration padded with a silent transition pause. Encoding shifts each clip's sound by a
# few hundredths of a second, so every slide is located in the video's own soundtrack by
# matching its narration's loudness pattern near the expected position.
LEGACY_METHOD = "forced-alignment-legacy"
LEGACY_MAX_PAUSE_SECONDS = 3.0
LEGACY_SAMPLE_RATE = 16000
LEGACY_FRAME = LEGACY_SAMPLE_RATE // 100  # 10 ms loudness frames
LEGACY_SEARCH_FRAMES = 60  # Look up to 0.6 s either side of the expected start.
LEGACY_MAX_MISMATCH = 0.25


def _to_pcm(source: Path, destination: Path) -> array.array:
    import imageio_ffmpeg

    subprocess.run(  # nosec B603
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", str(source), "-vn",
         "-ac", "1", "-ar", str(LEGACY_SAMPLE_RATE), "-c:a", "pcm_s16le", str(destination)],
        check=True,
        capture_output=True,
        timeout=600,
    )
    return _read_pcm(destination)


def _envelope(samples: array.array) -> list[float]:
    return [
        _rms(samples[index : index + LEGACY_FRAME])
        for index in range(0, len(samples) - LEGACY_FRAME + 1, LEGACY_FRAME)
    ]


def _locate(track: list[float], template: list[float], expected: int) -> tuple[int, float]:
    """Best start frame for template near expected, and its relative loudness mismatch."""
    total = sum(template) or 1.0
    best = (expected, math.inf)
    for start in range(max(0, expected - LEGACY_SEARCH_FRAMES), expected + LEGACY_SEARCH_FRAMES + 1):
        window = track[start : start + len(template)]
        if len(window) < len(template):
            break
        mismatch = sum(abs(a - b) for a, b in zip(window, template)) / total
        if mismatch < best[1]:
            best = (start, mismatch)
    return best


def _read_pcm(path: Path) -> array.array:
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getnchannels() != 1:
            raise CaptionsUnavailable("Unexpected soundtrack format")
        samples = array.array("h")
        samples.frombytes(stream.readframes(stream.getnframes()))
    return samples


def _rms(samples: array.array) -> float:
    return math.sqrt(sum(value * value for value in samples) / len(samples)) if samples else 0.0


def _write_pcm(path: Path, samples: array.array) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(LEGACY_SAMPLE_RATE)
        stream.writeframes(samples.tobytes())


def prepare_legacy_slides(video: Path, slides: list[dict], directory: Path) -> dict:
    """Cut the video's soundtrack into per-slide narration, refusing unverifiable layouts.

    ``items`` pair each slide's piece of soundtrack with its script.
    """
    from app.generation.video import audio_duration

    try:
        if not slides:
            raise CaptionsUnavailable("No narration slides")
        scripts = [str(slide["script"] or "") for slide in slides]
        if not all(script.strip() for script in scripts):
            raise CaptionsUnavailable("A slide has no narration script")
        narration = [
            audio_duration(str(resolve_public_asset_path(str(slide["audio_path"]), settings)))
            for slide in slides
        ]
        video_duration = audio_duration(str(video))
    except (FileNotFoundError, KeyError, TypeError, RuntimeError) as error:
        raise CaptionsUnavailable(f"Caption source data unavailable: {error}") from error
    pause = (video_duration - sum(narration)) / len(slides)
    if not 0 <= pause <= LEGACY_MAX_PAUSE_SECONDS:
        raise CaptionsUnavailable(
            "Slide narration does not add up to the video length; regenerate video"
        )
    samples = _to_pcm(video, directory / "soundtrack.wav")
    track = _envelope(samples)
    if not any(track):
        raise CaptionsUnavailable("Video has no audible narration")
    # The silent pause belongs to the pattern, so each slide's end is matched too.
    silence = [0.0] * int(min(pause, 1.0) * 100)
    items, starts, expected = [], [], 0.0
    for index, (slide, script, duration) in enumerate(zip(slides, scripts, narration), start=1):
        audio = resolve_public_asset_path(str(slide["audio_path"]), settings)
        template = _envelope(_to_pcm(audio, directory / f"narration_{index}.wav")) + silence
        frame, mismatch = _locate(track, template, round(expected * 100))
        if mismatch > LEGACY_MAX_MISMATCH:
            raise CaptionsUnavailable(
                f"Slide {index} narration does not match the video soundtrack; regenerate video"
            )
        start = frame / 100
        segment = directory / f"slide_{index}.wav"
        first = frame * LEGACY_FRAME
        _write_pcm(segment, samples[first : first + round(duration * LEGACY_SAMPLE_RATE)])
        items.append((segment, script))
        starts.append(start)
        expected = start + duration + pause
    return {
        "items": items,
        "narration": narration,
        "starts": starts,
        "pause": pause,
        "video_duration": video_duration,
    }


def _existing_captions(video: Path, video_hash: str) -> dict | None:
    """Metadata of caption assets that still match this exact video, if any."""
    metadata_path, vtt_path = video.with_suffix(".captions.json"), video.with_suffix(".vtt")
    if not (metadata_path.is_file() and vtt_path.is_file()):
        return None
    try:
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    valid = (
        isinstance(existing, dict)
        and existing.get("version") == VERSION
        and existing.get("video_sha256") == video_hash
        and existing.get("vtt_sha256") == digest(vtt_path)
    )
    return existing if valid else None


# Spoken characters per second of trimmed speech. Real narration measured 13.9-18.6; the
# bounds leave a wide margin (about 0.6x and 1.5x) for other voices and speed settings.
SPOKEN_CHARS_PER_SECOND = (8.0, 28.0)
SHORT_SLIDE_CHARS, SHORT_SLIDE_SECONDS = 40, 3.0  # Too short to judge a rate.


def _check_narration_length(number: int, script: str, seconds: float) -> None:
    """Refuse a script that cannot be what was spoken; old videos have no script hash."""
    spoken = sum(word["weight"] for word in _spoken_words(script))
    if spoken < SHORT_SLIDE_CHARS and seconds < SHORT_SLIDE_SECONDS:
        return
    low, high = SPOKEN_CHARS_PER_SECOND
    if seconds <= 0 or not low <= spoken / seconds <= high:
        raise ScriptMismatch(
            f"Slide {number} script does not match its narration length; regenerate narration"
        )


def _legacy_aligned_cues(slides: list[dict], layout: dict) -> list[dict]:
    items = [
        (segment, display_words(script)[0]) for segment, script in layout["items"]
    ]
    aligned = align_slides(items)
    words = [word for slide in aligned for word in slide]
    collapsed = sum(float(w["end"]) - float(w["start"]) < 0.02 for w in words)
    # A script edited after rendering aligns badly: most words collapse to zero length.
    if words and collapsed > len(words) / 2:
        raise ScriptMismatch("Narration script does not match the spoken audio")
    cues = []
    for slide, slide_words, duration, start in zip(
        slides, aligned, layout["narration"], layout["starts"], strict=True
    ):
        cues.extend(group_cues(slide["script"], slide_words, duration, start))
    return cues


def _legacy_narration_cues(layout: dict) -> list[dict]:
    cues = []
    # Each slide's piece of the soundtrack starts at its located slide start.
    for number, ((segment, script), duration, start) in enumerate(
        zip(layout["items"], layout["narration"], layout["starts"], strict=True), start=1
    ):
        speech_start, speech_end, pauses = _speech_layout(_read_pcm(segment), duration)
        _check_narration_length(number, script, speech_end - speech_start)
        cues.extend(narration_cues(script, speech_start, speech_end, pauses, start))
    return cues


def generate_legacy_module_captions(
    video: Path, slides: list[dict], *, already_locked: bool = False
) -> str:
    """Caption a video that has no render-time provenance, from its own soundtrack."""
    timing = caption_timing()
    if timing == "off":
        return "skipped_captions_off"
    if not already_locked:
        with module_lock(video):
            return generate_legacy_module_captions(video, slides, already_locked=True)
    if video.with_suffix(".srt").exists():
        raise CaptionsUnavailable("Video Generator videos already show burned-in subtitles")
    video_hash = digest(video)
    existing = _existing_captions(video, video_hash)
    if existing is not None and _keep_existing(existing, timing):
        return "skipped_valid_captions"
    with tempfile.TemporaryDirectory() as directory:
        layout = prepare_legacy_slides(video, slides, Path(directory))
        if timing == "aligned":
            try:
                cues = _legacy_aligned_cues(slides, layout)
            except ALIGNMENT_FAILURES as error:
                kept = _after_failed_alignment(video, error, existing is not None)
                if kept:
                    return kept
                timing = "narration"
        if timing == "narration":
            cues = _legacy_narration_cues(layout)
    if not cues or cues[-1]["end"] > layout["video_duration"]:
        raise CaptionsUnavailable("Caption timeline differs from the video")
    if digest(video) != video_hash:
        raise CaptionsUnavailable("Video changed during caption timing")
    content = serialize_vtt(cues)
    fingerprint = hashlib.sha256(content.encode()).hexdigest()
    stat = video.stat()
    atomic_text(video.with_suffix(".vtt"), content)
    atomic_json(
        video.with_suffix(".captions.json"),
        {
            "version": VERSION,
            "language": "en",
            "method": LEGACY_METHOD if timing == "aligned" else NARRATION_LEGACY_METHOD,
            "video_sha256": video_hash,
            "pause_seconds": round(layout["pause"], 3),
            "video_size": stat.st_size,
            "video_mtime": int(stat.st_mtime),
            "duration": layout["video_duration"],
            "fingerprint": fingerprint,
            "vtt_sha256": fingerprint,
            "cue_count": len(cues),
        },
    )
    return "generated"


def backfill_module_captions(module: dict, *, apply: bool) -> dict:
    """Inspect or caption one module video; local video mode only.

    ``method`` is the method of the captions on disk afterwards, or the one that would be
    used; a dry run also says whether existing narration captions would be upgraded.
    """
    number = module.get("module_number")
    if (module.get("video_service") or {}).get("run_id"):
        return {"status": "skipped_video_generator", "module": number}
    video = resolve_public_asset_path(str(module.get("video_path") or ""), settings)
    if not module.get("video_path") or not video.is_file():
        return {"status": "skipped_no_video", "module": number}
    if video.with_suffix(".srt").exists():
        return {"status": "skipped_video_generator", "module": number}
    timing = caption_timing()
    if timing == "off":
        return {"status": "skipped_captions_off", "module": number}
    slides = module.get("slides") or []
    legacy = not video.with_suffix(".source.json").is_file()
    if timing == "aligned":
        method = LEGACY_METHOD if legacy else ALIGNED_METHOD
    else:
        method = NARRATION_LEGACY_METHOD if legacy else NARRATION_METHOD
    try:
        existing = _existing_captions(video, digest(video))
        if not apply:
            report = {
                "status": "dry_run",
                "module": number,
                "method": method,
                "slides": len(slides),
                "existing_method": existing.get("method") if existing else None,
                "would_upgrade": existing is not None and not _keep_existing(existing, timing),
            }
            if legacy:
                with tempfile.TemporaryDirectory() as directory:
                    layout = prepare_legacy_slides(video, slides, Path(directory))
                report["pause_seconds"] = round(layout["pause"], 3)
            else:
                check_video_source(video, slides)
            return report
        generate = generate_legacy_module_captions if legacy else generate_module_captions
        status = generate(video, slides)
        written = _existing_captions(video, digest(video))
        return {
            "status": status,
            "module": number,
            "method": written.get("method") if written else method,
        }
    except (CaptionsUnavailable, OSError, subprocess.SubprocessError) as error:
        return {"status": "unavailable", "module": number, "reason": str(error)}
