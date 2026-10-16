"""Validated forced-alignment captions; never estimate timing from word counts."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import subprocess
import tempfile
import unicodedata
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
    """Run an explicitly configured local worker with no shell or audio upload."""
    command = list(settings.caption_align_command)
    if not command:
        raise CaptionsUnavailable(
            "Configure CAPTION_ALIGN_COMMAND with a local forced-alignment worker"
        )
    with tempfile.TemporaryDirectory() as directory:
        request = Path(directory) / "request.json"
        result = Path(directory) / "result.json"
        request.write_text(
            json.dumps({"audio": str(audio.resolve()), "text": transcript, "language": "English"}),
            encoding="utf-8",
        )
        subprocess.run(
            command + [str(request), str(result)],
            check=True,
            timeout=600,
            capture_output=True,
            text=True,
            shell=False,
            env={
                **os.environ,
                "CAPTION_ALIGN_MODEL_PATH": settings.caption_align_model_path,
                "CAPTION_ALIGN_DEVICE": settings.caption_align_device,
            },
        )  # nosec B603
        return json.loads(result.read_text(encoding="utf-8"))["words"]


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
            or end <= start
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
    cues, batch = [], []

    def flush():
        if batch:
            cues.append(
                {
                    "start": round(offset + batch[0]["start"], 3),
                    "end": round(offset + batch[-1]["end"], 3),
                    "text": " ".join(word["text"] for word in batch),
                }
            )
            batch.clear()

    for word in readable:
        if batch and (
            len(" ".join(item["text"] for item in batch)) + len(word["text"]) > 78
            or word["end"] - batch[0]["start"] > 6
            or word["start"] - batch[-1]["end"] > 0.4
        ):
            flush()
        batch.append(word)
        if word["text"].endswith((".", "!", "?", ";")):
            flush()
    flush()
    return cues


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
        cues, offset = [], 0.0
        for slide, clip_duration in zip(slides, durations, strict=True):
            audio = resolve_public_asset_path(slide["audio_path"], settings)
            duration = audio_duration(str(audio))
            if duration > clip_duration + 0.05:
                raise CaptionsUnavailable("Narration exceeds rendered clip")
            transcript, _ = display_words(slide["script"])
            cues.extend(
                group_cues(slide["script"], align_slide(audio, transcript), duration, offset)
            )
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
