"""Capture HTML slides, encode narration clips, and persist module videos."""

from __future__ import annotations

import base64
import re
import shutil
import subprocess  # nosec B404
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import imageio_ffmpeg
import requests

from app.core.logging import generation_logger
from app.core.settings import settings
from app.core.storage import public_asset_url, resolve_public_asset_path

logger = generation_logger(__name__)
SLIDE_TRANSITION_PAUSE_SECONDS = settings.slide_transition_pause_seconds
# Resolves a deck's relative links to /assets/ paths; any origin works.
_DECK_LINK_ORIGIN = "http://deck.invalid"


def _generate_captions_if_available(
    video_path: Path, slides: list[dict], *, already_locked: bool = False
) -> None:
    from app.generation.captions import generate_module_captions

    try:
        result = generate_module_captions(video_path, slides, already_locked=already_locked)
        logger.info("captions_%s video=%s", result, video_path)
    except Exception as error:
        # A caption provider failure must not take a playable lesson offline.
        logger.warning("captions_unavailable video=%s reason=%s", video_path, error)


class _SlideLinkCollector(HTMLParser):
    """Collect the src and href values of a compiled slide deck."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.links.extend(value for name, value in attrs if name in {"src", "href"} and value)


def _public_asset_file(asset_path: str) -> Path | None:
    """Map a /assets/ URL path to its file, as the API's /assets/ mounts do."""
    relative = asset_path.removeprefix("/assets/")
    if relative == "slides.css":
        return settings.template_dir / "slides.css"
    mount, _, name = relative.partition("/")
    directory = {
        "brand": settings.static_dir / "brand",
        "images": settings.image_dir,
        "layouts": settings.template_dir / "layouts",
    }.get(mount)
    if directory is None or not name:
        return None
    path = (directory / unquote(name)).resolve()
    return path if path.is_relative_to(directory.resolve()) else None


def slide_deck_files(html_file: Path) -> tuple[str, dict[str, bytes]]:
    """Return the deck's /assets/ path and every local file it links to, by URL path."""
    relative = html_file.resolve().relative_to(settings.slide_dir.resolve()).as_posix()
    document = f"/assets/slides/{relative}"
    html = html_file.read_bytes()
    collector = _SlideLinkCollector()
    collector.feed(html.decode("utf-8"))
    files = {document: html}
    for link in collector.links:
        parts = urlsplit(urljoin(_DECK_LINK_ORIGIN + document, link))
        if f"{parts.scheme}://{parts.netloc}" != _DECK_LINK_ORIGIN or parts.path in files:
            continue
        path = _public_asset_file(parts.path)
        # A missing file is left out; the renderer then reports any image it could not load.
        if path is not None and path.is_file():
            files[parts.path] = path.read_bytes()
    return document, files


def capture_slide_frames(
    html_file: str,
    *,
    slide_count: int,
    output_dir: str,
) -> list[str]:
    """Screenshot every slide of a compiled deck with the slide renderer service."""
    if not settings.slide_renderer_url:
        raise RuntimeError("SLIDE_RENDERER_URL is not set; standard video generation needs it.")
    document, files = slide_deck_files(Path(html_file))
    response = requests.post(
        f"{settings.slide_renderer_url}/render",
        json={
            "document": document,
            "files": {path: base64.b64encode(body).decode() for path, body in files.items()},
            "slide_count": slide_count,
        },
        timeout=settings.slide_renderer_timeout_seconds,
    )
    if response.status_code != 200:
        try:
            detail = response.json().get("error") or response.text
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Slide renderer failed with HTTP {response.status_code}: {detail}")
    frames = response.json().get("frames")
    if not isinstance(frames, list) or len(frames) != slide_count:
        raise RuntimeError(f"Slide renderer returned no frame for some of the {slide_count} slides.")
    frame_paths: list[str] = []
    for index, frame in enumerate(frames):
        frame_path = Path(output_dir) / f"slide_{index}.png"
        frame_path.write_bytes(base64.b64decode(frame, validate=True))
        frame_paths.append(str(frame_path))
    return frame_paths


def audio_duration(audio_path: str) -> float:
    if not audio_path or not Path(audio_path).is_file():
        raise FileNotFoundError(f"Narration audio not found: {audio_path}")
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(  # nosec B603
        [executable, "-i", audio_path],
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not determine narration duration: {audio_path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def encode_slide_clip(
    frame_path: str,
    audio_path: str,
    output_path: str,
    *,
    transition_pause_seconds: float,
) -> None:
    duration = audio_duration(audio_path)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-loop",
        "1",
        "-i",
        frame_path,
        "-i",
        audio_path,
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        f"apad=pad_dur={transition_pause_seconds}",
        "-pix_fmt",
        "yuv420p",
        "-t",
        str(duration + transition_pause_seconds),
        output_path,
    ]
    result = subprocess.run(  # nosec B603
        command,
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed encoding {frame_path}: {result.stderr}")


def concatenate_clips(clips: list[str], output_path: str, *, working_dir: str) -> None:
    manifest = Path(working_dir) / "concat.txt"
    manifest.write_text(
        "".join(f"file '{clip.replace(chr(92), '/')}'\n" for clip in clips),
        encoding="utf-8",
    )
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        output_path,
    ]
    result = subprocess.run(  # nosec B603
        command,
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")


def generate_hls_playlist(mp4_path: Path) -> Path:
    hls_dir = mp4_path.with_name(f"{mp4_path.stem}_hls")
    temporary_dir = mp4_path.with_name(f".{mp4_path.stem}_hls.tmp")
    if temporary_dir.exists():
        shutil.rmtree(temporary_dir)
    temporary_dir.mkdir(parents=True)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        str(mp4_path),
        "-c",
        "copy",
        "-hls_time",
        "6",
        "-hls_playlist_type",
        "vod",
        "-hls_segment_type",
        "fmp4",
        "-hls_fmp4_init_filename",
        "init.mp4",
        "-hls_segment_filename",
        "segment_%04d.m4s",
        "master.m3u8",
    ]
    try:
        result = subprocess.run(  # nosec B603
            command,
            cwd=str(temporary_dir),
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"FFmpeg HLS packaging failed for {mp4_path}: {result.stderr}")
        if hls_dir.exists():
            shutil.rmtree(hls_dir)
        temporary_dir.replace(hls_dir)
        return hls_dir / "master.m3u8"
    finally:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)


VIDEO_DIR = settings.video_dir

VIDEO_STAGE_WORKERS = 2


def render_video_for_module(course: dict, course_id: str, module_number: int) -> str:
    from app.generation.captions import module_lock

    path = VIDEO_DIR / f"course_{course_id}" / f"module_{module_number}.mp4"
    with module_lock(path):
        return _render_video_for_module(course, course_id, module_number)


def _render_video_for_module(course: dict, course_id: str, module_number: int) -> str:
    from app.generation.captions import source_inputs

    modules = course.get("modules", [])
    if module_number < 1 or module_number > len(modules):
        raise ValueError(f"Module number {module_number} out of range.")
    slides = modules[module_number - 1].get("slides", [])
    if not slides:
        raise ValueError(
            f"Module {module_number} has no slides generated yet. Generate slides first."
        )

    html_file = settings.slide_dir / course_id / f"module_{module_number}.html"
    if not html_file.is_file():
        raise FileNotFoundError(f"HTML slides file not found at {html_file}")

    output_dir = VIDEO_DIR / f"course_{course_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"module_{module_number}.mp4"
    caption_inputs = source_inputs(slides)

    with tempfile.TemporaryDirectory() as temporary_dir:
        logger.info(
            "video_capture_start course_id=%s module=%s slides=%s",
            course_id,
            module_number,
            len(slides),
        )
        frames = capture_slide_frames(
            str(html_file),
            slide_count=len(slides),
            output_dir=temporary_dir,
        )
        clips: list[str] = []
        clip_durations: list[float] = []
        for index, (slide, frame) in enumerate(zip(slides, frames, strict=True)):
            audio_reference = str(slide.get("audio_path") or "")
            audio_path = str(resolve_public_asset_path(audio_reference, settings))
            if not audio_reference or not Path(audio_path).is_file():
                raise FileNotFoundError(
                    f"Narration audio is missing for module {module_number}, slide {index + 1}."
                )
            clip_path = str(Path(temporary_dir) / f"clip_{index}.mp4")
            encode_slide_clip(
                frame,
                audio_path,
                clip_path,
                transition_pause_seconds=SLIDE_TRANSITION_PAUSE_SECONDS,
            )
            clips.append(clip_path)
            clip_durations.append(audio_duration(clip_path))
        staged_video = Path(temporary_dir) / "module.mp4"
        concatenate_clips(clips, str(staged_video), working_dir=temporary_dir)
        # Copy into the destination filesystem before atomic publication.
        staged_output = output_path.with_suffix(".rendering.mp4")
        try:
            shutil.copyfile(staged_video, staged_output)
            staged_output.replace(output_path)
        finally:
            staged_output.unlink(missing_ok=True)
        generate_hls_playlist(output_path)

    from app.generation.captions import record_video_source

    try:
        record_video_source(output_path, slides, clip_durations, caption_inputs)
        _generate_captions_if_available(output_path, slides, already_locked=True)
    except Exception as error:
        logger.warning("captions_source_unavailable video=%s reason=%s", output_path, error)

    video_path = public_asset_url(
        "videos",
        f"course_{course_id}",
        f"module_{module_number}.mp4",
    )
    logger.info(
        "video_generated course_id=%s module=%s path=%s",
        course_id,
        module_number,
        output_path,
    )
    return video_path


def generate_video_for_module(course_id: str, module_number: int) -> str:
    from app.generation.html import compile_slides_for_course
    from app.generation.runtime import load_course_for_generation, save_generated_course
    from app.generation.slides import module_is_cover_only
    from app.generation.tts import generate_tts_for_course

    course = load_course_for_generation(course_id)
    modules = course.get("modules", [])
    if 1 <= module_number <= len(modules) and module_is_cover_only(modules[module_number - 1]):
        # A failed slide plan left only the cover; rendering it again would give the same
        # few-second video, so rebuild this module's slides and narration first.
        from app.generation.scripts import generate_scripts_for_single_module
        from app.generation.slides import generate_slides_for_single_module

        logger.info(
            "cover_only_module_rebuild_started course_id=%s module=%s", course_id, module_number
        )
        generate_slides_for_single_module(course_id, module_number)
        generate_scripts_for_single_module(course_id, module_number)
    # Remakes only audio whose spoken text changed (e.g. a pronunciation fix); valid audio is kept.
    generate_tts_for_course(course_id, {module_number})
    course = load_course_for_generation(course_id)
    compile_slides_for_course(course_id)
    video_path = render_video_for_module(course, course_id, module_number)
    fresh_course = load_course_for_generation(course_id)
    fresh_course["modules"][module_number - 1]["video_path"] = video_path
    save_generated_course(course_id, fresh_course, module_fields=("video_path",))
    return video_path


def generate_videos_for_course(course_id: str) -> dict:
    from app.generation.parallel import run_parallel_stage_items
    from app.generation.runtime import load_course_for_generation, log_event, save_generated_course

    course = load_course_for_generation(course_id)
    modules = course.get("modules", [])
    module_numbers: list[int] = []
    for module in modules:
        module_number = int(module.get("module_number", 0))
        if not module_number:
            raise ValueError("Module has no valid module number")
        path = str(module.get("video_path") or "")
        absolute_path = resolve_public_asset_path(path, settings)
        if path and absolute_path.is_file() and absolute_path.stat().st_size > 0:
            _generate_captions_if_available(absolute_path, module.get("slides", []))
            log_event(course_id, "video", "skipped_valid_video", module=module_number)
            continue
        module_numbers.append(module_number)

    def render_module(module_number: int) -> tuple[int, str]:
        started = time.perf_counter()
        log_event(course_id, "video", "module_started", module=module_number)
        video_path = render_video_for_module(course, course_id, module_number)
        log_event(
            course_id,
            "video",
            "module_completed",
            module=module_number,
            elapsed=f"{time.perf_counter() - started:.1f}s",
        )
        return module_number, video_path

    results = run_parallel_stage_items(
        course_id=course_id,
        stage="video",
        items=module_numbers,
        worker_count=VIDEO_STAGE_WORKERS,
        item_label=lambda module_number: {"module": module_number},
        operation=render_module,
    )
    for module_number, video_path in results:
        modules[module_number - 1]["video_path"] = video_path
    course["modules"] = modules
    save_generated_course(course_id, course, module_fields=("video_path",))
    return course
