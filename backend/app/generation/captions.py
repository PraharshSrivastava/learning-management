"""Validated forced-alignment captions; never estimate timing from word counts."""

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
import unicodedata
import wave
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from app.core.settings import settings
from app.core.storage import resolve_public_asset_path
from app.generation.tts_normalization import clean_text_for_tts

VERSION = 1


class CaptionsUnavailable(RuntimeError):
    pass


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


def record_narration_source(audio: Path, script: str) -> None:
    atomic_json(
        audio.with_suffix(".narration.json"),
        {
            "version": VERSION,
            "audio_sha256": digest(audio),
            "spoken_sha256": hashlib.sha256(clean_text_for_tts(script).encode()).hexdigest(),
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


def _balanced_pieces(words: list[dict]) -> list[list[dict]]:
    """Halve an over-long phrase at its most even word boundary, so no word is left alone."""
    text = " ".join(word["text"] for word in words)
    if len(words) < 2 or (len(text) <= 78 and words[-1]["end"] - words[0]["start"] <= 6):
        return [words]

    def cost(split: int) -> float:
        left = len(" ".join(word["text"] for word in words[:split]))
        balance = max(left, len(text) - left - 1)
        # Prefer a natural break after a comma or colon when it is nearly as even.
        return balance - (10 if words[split - 1]["text"].endswith((",", ":")) else 0)

    split = min(range(1, len(words)), key=cost)
    return _balanced_pieces(words[:split]) + _balanced_pieces(words[split:])


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


def generate_module_captions(
    video: Path, slides: list[dict], *, already_locked: bool = False
) -> str:
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
            provenance.get("version") != VERSION
            or provenance.get("video_sha256") != video_hash
            or provenance.get("inputs") != inputs
        ):
            raise CaptionsUnavailable(
                "Video and saved narration provenance do not match; regenerate video"
            )
        durations = provenance["clip_durations"]
        if len(durations) != len(slides) or any(not math.isfinite(t) or t <= 0 for t in durations):
            raise CaptionsUnavailable("Invalid rendered clip durations")
        metadata_path = video.with_suffix(".captions.json")
        vtt_path = video.with_suffix(".vtt")
        if metadata_path.is_file() and vtt_path.is_file():
            try:
                existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            except ValueError:
                existing = {}
            if (
                existing.get("version") == VERSION
                and existing.get("video_sha256") == video_hash
                and existing.get("inputs") == inputs
                and existing.get("vtt_sha256") == digest(vtt_path)
            ):
                return "skipped_valid_captions"
        items, narration = [], []
        for slide, clip_duration in zip(slides, durations, strict=True):
            audio = resolve_public_asset_path(slide["audio_path"], settings)
            duration = audio_duration(str(audio))
            if duration > clip_duration + 0.05:
                raise CaptionsUnavailable("Narration exceeds rendered clip")
            items.append((audio, display_words(slide["script"])[0]))
            narration.append(duration)
        cues, offset = [], 0.0
        for slide, words, duration, clip_duration in zip(
            slides, align_slides(items), narration, durations, strict=True
        ):
            cues.extend(group_cues(slide["script"], words, duration, offset))
            offset += clip_duration
        final_duration = audio_duration(str(video))
        if abs(offset - final_duration) > 0.1 or cues[-1]["end"] > final_duration:
            raise CaptionsUnavailable("Caption timeline differs from rendered video")
        if digest(video) != video_hash or source_inputs(slides) != inputs:
            raise CaptionsUnavailable("Video or narration changed during alignment")
        content = serialize_vtt(cues)
        fingerprint = hashlib.sha256(content.encode()).hexdigest()
        stat = video.stat()
        atomic_text(vtt_path, content)
        atomic_json(
            metadata_path,
            {
                "version": VERSION,
                "language": "en",
                "method": "forced-alignment",
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
    """Cut the video's soundtrack into per-slide narration, refusing unverifiable layouts."""
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
        items.append((segment, display_words(script)[0]))
        starts.append(start)
        expected = start + duration + pause
    return {
        "items": items,
        "narration": narration,
        "starts": starts,
        "pause": pause,
        "video_duration": video_duration,
    }


def _valid_existing_captions(video: Path, video_hash: str) -> bool:
    metadata_path, vtt_path = video.with_suffix(".captions.json"), video.with_suffix(".vtt")
    if not (metadata_path.is_file() and vtt_path.is_file()):
        return False
    try:
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return (
        existing.get("version") == VERSION
        and existing.get("video_sha256") == video_hash
        and existing.get("vtt_sha256") == digest(vtt_path)
    )


def generate_legacy_module_captions(
    video: Path, slides: list[dict], *, already_locked: bool = False
) -> str:
    """Caption a video that has no render-time provenance, from its own soundtrack."""
    if not already_locked:
        with module_lock(video):
            return generate_legacy_module_captions(video, slides, already_locked=True)
    if video.with_suffix(".srt").exists():
        raise CaptionsUnavailable("Video Generator videos already show burned-in subtitles")
    video_hash = digest(video)
    if _valid_existing_captions(video, video_hash):
        return "skipped_valid_captions"
    with tempfile.TemporaryDirectory() as directory:
        layout = prepare_legacy_slides(video, slides, Path(directory))
        aligned = align_slides(layout["items"])
    words = [word for slide in aligned for word in slide]
    # A script edited after rendering aligns badly: most words collapse to zero length.
    if words and sum(float(w["end"]) - float(w["start"]) < 0.02 for w in words) > len(words) / 2:
        raise CaptionsUnavailable("Narration script does not match the spoken audio")
    cues = []
    for slide, slide_words, duration, start in zip(
        slides, aligned, layout["narration"], layout["starts"], strict=True
    ):
        cues.extend(group_cues(slide["script"], slide_words, duration, start))
    if not cues or cues[-1]["end"] > layout["video_duration"]:
        raise CaptionsUnavailable("Caption timeline differs from the video")
    if digest(video) != video_hash:
        raise CaptionsUnavailable("Video changed during alignment")
    content = serialize_vtt(cues)
    fingerprint = hashlib.sha256(content.encode()).hexdigest()
    stat = video.stat()
    atomic_text(video.with_suffix(".vtt"), content)
    atomic_json(
        video.with_suffix(".captions.json"),
        {
            "version": VERSION,
            "language": "en",
            "method": LEGACY_METHOD,
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
    """Inspect or caption one module video; local video mode only."""
    number = module.get("module_number")
    if (module.get("video_service") or {}).get("run_id"):
        return {"status": "skipped_video_generator", "module": number}
    video = resolve_public_asset_path(str(module.get("video_path") or ""), settings)
    if not module.get("video_path") or not video.is_file():
        return {"status": "skipped_no_video", "module": number}
    if video.with_suffix(".srt").exists():
        return {"status": "skipped_video_generator", "module": number}
    slides = module.get("slides") or []
    legacy = not video.with_suffix(".source.json").is_file()
    method = LEGACY_METHOD if legacy else "forced-alignment"
    try:
        if not apply:
            if legacy:
                with tempfile.TemporaryDirectory() as directory:
                    layout = prepare_legacy_slides(video, slides, Path(directory))
                return {"status": "dry_run", "module": number, "method": method,
                        "slides": len(slides), "pause_seconds": round(layout["pause"], 3)}
            check_video_source(video, slides)
            return {"status": "dry_run", "module": number, "method": method, "slides": len(slides)}
        generate = generate_legacy_module_captions if legacy else generate_module_captions
        return {"status": generate(video, slides), "module": number, "method": method}
    except (CaptionsUnavailable, OSError, subprocess.SubprocessError) as error:
        return {"status": "unavailable", "module": number, "reason": str(error)}
