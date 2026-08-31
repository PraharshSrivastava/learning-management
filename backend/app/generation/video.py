"""Capture HTML slides, encode narration clips, and persist module videos."""

from __future__ import annotations

import re
import shutil
import subprocess  # nosec B404
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg

from app.core.logging import generation_logger
from app.core.providers import SLIDE_TRANSITION_PAUSE_SECONDS
from app.core.settings import settings
from app.core.storage import public_asset_url, resolve_public_asset_path
from app.generation.html import compile_slides_for_course
from app.generation.parallel import run_parallel_stage_items
from app.generation.runtime import load_course_for_generation, log_event, save_generated_course

logger = generation_logger(__name__)


def _inject_local_slide_assets(page) -> None:
    """Load slide template assets when Playwright opens generated HTML via file://."""
    css_files = [
        settings.template_dir / "slides.css",
        settings.template_dir / "layouts" / "cover.css",
        settings.template_dir / "layouts" / "comparison.css",
        settings.template_dir / "layouts" / "bullets.css",
        settings.template_dir / "layouts" / "steps.css",
        settings.template_dir / "layouts" / "grid.css",
    ]
    for css_file in css_files:
        if css_file.is_file():
            page.add_style_tag(path=str(css_file))

    brand_base = (settings.static_dir / "brand").resolve().as_uri().rstrip("/") + "/"
    image_base = settings.image_dir.resolve().as_uri().rstrip("/") + "/"
    page.evaluate(
        """
        ({ brandBase, imageBase }) => {
          document.querySelectorAll('img[src]').forEach((image) => {
            const source = image.getAttribute('src') || '';
            if (source.startsWith('../../brand/')) {
              image.src = brandBase + source.slice('../../brand/'.length);
            }
            if (source.startsWith('../../images/')) {
              image.src = imageBase + source.slice('../../images/'.length);
            }
          });
        }
        """,
        {"brandBase": brand_base, "imageBase": image_base},
    )


def capture_slide_frames(
    html_file: str,
    *,
    slide_count: int,
    output_dir: str,
) -> list[str]:
    from playwright.sync_api import sync_playwright

    frame_paths: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(Path(html_file).resolve().as_uri())
            page.wait_for_load_state("networkidle")
            _inject_local_slide_assets(page)
            page.evaluate("document.fonts.ready")
            page.add_style_tag(
                content=".slide { animation: none !important; transition: none !important; }"
            )
            for index in range(slide_count):
                frame_path = str(Path(output_dir) / f"slide_{index}.png")
                page.evaluate(f"window.goToSlide({index})")
                page.screenshot(path=frame_path)
                frame_paths.append(frame_path)
        finally:
            browser.close()
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
            raise RuntimeError(
                f"FFmpeg HLS packaging failed for {mp4_path}: {result.stderr}"
            )
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
        concatenate_clips(clips, str(output_path), working_dir=temporary_dir)
        generate_hls_playlist(output_path)

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
    course = load_course_for_generation(course_id)
    compile_slides_for_course(course_id)
    video_path = render_video_for_module(course, course_id, module_number)
    fresh_course = load_course_for_generation(course_id)
    fresh_course["modules"][module_number - 1]["video_path"] = video_path
    save_generated_course(course_id, fresh_course, module_fields=("video_path",))
    return video_path


def generate_videos_for_course(course_id: str) -> dict:
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
