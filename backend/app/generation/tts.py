"""Synthesize, validate, and persist slide narration audio."""

import copy
import os
import subprocess
import time

import imageio_ffmpeg
import requests

from app.core.logging import generation_logger
from app.core.providers import (
    TTS_ENDPOINT,
    TTS_SPEED,
    TTS_TEMPERATURE,
    TTS_VOICE,
)
from app.core.settings import settings
from app.core.storage import public_asset_url
from app.generation.parallel import run_parallel_stage_items
from app.generation.runtime import (
    load_course_for_generation,
    log_event,
    retry,
    save_generated_course,
)
from app.generation.tts_normalization import clean_text_for_tts

logger = generation_logger(__name__)

TTS_STAGE_WORKERS = 3

def _apply_tts_speed(output_path: str) -> bool:
    if abs(TTS_SPEED - 1.0) < 0.001:
        return True
    if TTS_SPEED <= 0:
        logger.warning("tts_invalid_speed speed=%s", TTS_SPEED)
        return True

    temp_path = f"{output_path}.speed.wav"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        output_path,
        "-filter:a",
        f"atempo={TTS_SPEED}",
        temp_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, errors="ignore")
    if result.returncode != 0:
        logger.warning("tts_speed_apply_failed speed=%s error=%s", TTS_SPEED, result.stderr)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
    os.replace(temp_path, output_path)
    logger.info("tts_speed_applied speed=%s output=%s", TTS_SPEED, output_path)
    return True

def synthesize_speech_for_slide(text: str, output_path: str, language: str = "English") -> bool:
    text = text.strip()
    if not text:
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cleaned_text = clean_text_for_tts(text)

    if not TTS_ENDPOINT:
        return False

    voice = TTS_VOICE
    tts_url = f"{TTS_ENDPOINT.rstrip('/')}/v1/audio/speech"
    payload = {
        "model": "qwen3-tts",
        "input": cleaned_text,
        "voice": voice,
        "response_format": "wav",
    }
    if language:
        payload["language"] = language
    if TTS_TEMPERATURE is not None:
        payload["temperature"] = TTS_TEMPERATURE
    headers = {"Content-Type": "application/json"}

    try:
        logger.info("tts_request_started voice=%s output=%s", voice, output_path)
        response = requests.post(tts_url, json=payload, headers=headers, timeout=600)
        if response.status_code != 200:
            logger.error(
                "tts_endpoint_error status_code=%s response=%s",
                response.status_code,
                response.text,
            )
            return False
        with open(output_path, "wb") as audio_file:
            audio_file.write(response.content)
        _apply_tts_speed(output_path)
        logger.info("tts_request_completed voice=%s output=%s", voice, output_path)
        return True
    except (requests.RequestException, OSError, subprocess.SubprocessError):
        logger.exception("tts_request_failed voice=%s output=%s", voice, output_path)
        return False

def generate_tts_for_course(course_id: str) -> dict:
    from app.generation.video import audio_duration

    course = load_course_for_generation(course_id)
    modules = copy.deepcopy(course.get("modules", []))
    slide_jobs = []
    for module_index, module in enumerate(modules):
        module_number = int(module.get("module_number", module_index + 1))
        for slide_index, slide in enumerate(module.get("slides", []), start=1):
            slide_jobs.append((module_index, module_number, slide_index, slide))

    def synthesize_slide(item: tuple[int, int, int, dict]) -> tuple[int, int, str]:
        module_index, module_number, slide_index, slide = item
        started = time.perf_counter()
        script_text = str(slide.get("script") or "").strip()
        if not script_text:
            raise ValueError(f"Module {module_number} slide {slide_index} has no narration script")
        audio_rel = public_asset_url(
            "audio",
            f"course_{course_id}",
            f"module_{module_number}",
            f"slide_{slide_index}.wav",
        )
        audio_abs = str(
            settings.audio_dir
            / f"course_{course_id}"
            / f"module_{module_number}"
            / f"slide_{slide_index}.wav"
        )
        if (
            str(slide.get("audio_path") or "") == audio_rel
            and os.path.isfile(audio_abs)
            and os.path.getsize(audio_abs) > 0
            and audio_duration(audio_abs) > 0
        ):
            log_event(course_id, "tts", "skipped_valid_audio", module=module_number, slide=slide_index)
            return module_index, slide_index - 1, audio_rel

        log_event(course_id, "tts", "slide_started", module=module_number, slide=slide_index)

        def synthesize_once():
            if not synthesize_speech_for_slide(script_text, audio_abs):
                raise RuntimeError("TTS endpoint did not produce audio")
            if (
                not os.path.exists(audio_abs)
                or os.path.getsize(audio_abs) == 0
                or audio_duration(audio_abs) <= 0
            ):
                raise RuntimeError("Generated audio file failed validation")
            return True

        retry(
            synthesize_once,
            course_id=course_id,
            stage="tts",
            attempts=2,
            module_number=module_number,
            slide_number=slide_index,
        )
        log_event(
            course_id,
            "tts",
            "slide_completed",
            module=module_number,
            slide=slide_index,
            elapsed=f"{time.perf_counter() - started:.1f}s",
        )
        return module_index, slide_index - 1, audio_rel

    results = run_parallel_stage_items(
        course_id=course_id,
        stage="tts",
        items=slide_jobs,
        worker_count=TTS_STAGE_WORKERS,
        item_label=lambda item: {"module": item[1], "slide": item[2]},
        operation=synthesize_slide,
    )
    for module_index, slide_index, audio_rel in results:
        modules[module_index]["slides"][slide_index]["audio_path"] = audio_rel
    course["modules"] = modules
    save_generated_course(course_id, course, module_fields=("slides",))
    return course
