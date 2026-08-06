"""Plan, generate, store, and identify course thumbnails."""

import base64
import hashlib
import json
import os
import re
import time
from typing import Optional
from urllib.parse import urljoin

import requests

from app.core.logging import generation_logger
from app.core.providers import get_llm_endpoint, safe_chat_completion
from app.core.settings import settings
from app.core.storage import public_asset_url
from app.generation.prompts import COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT
from app.generation.runtime import retry

THUMBNAIL_ENDPOINT = settings.thumbnail_endpoint
THUMBNAIL_MODEL = settings.thumbnail_model
THUMBNAIL_API_KEY = settings.thumbnail_api_key
THUMBNAIL_CONNECT_TIMEOUT = settings.thumbnail_connect_timeout
THUMBNAIL_READ_TIMEOUT = settings.thumbnail_read_timeout
THUMBNAIL_DIR = os.path.join(str(settings.image_dir), "course_thumbnails")
THUMBNAIL_PROMPT_VERSION = "single-subject-v2"
THUMBNAILS_ENABLED = settings.thumbnails_enabled


def _safe_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return slug[:80] or "course"


def course_thumbnail_signature(course: dict) -> str:
    title = str(course.get("course_name") or "Course").strip()
    description = str(course.get("course_description") or "").strip()
    source = json.dumps(
        {
            "version": THUMBNAIL_PROMPT_VERSION,
            "title": title,
            "description": description,
        },
        sort_keys=True,
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def _extract_subject_from_llm(content: str) -> Optional[str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    subject = data.get("subject") if isinstance(data, dict) else None
    if not isinstance(subject, str):
        return None
    subject = re.sub(r"\s+", " ", subject).strip(" .")
    # A bounded scene keeps the image instruction simple even if the planner drifts.
    if not subject or len(subject) > 160 or not 3 <= len(subject.split()) <= 25:
        return None
    return subject


def _thumbnail_prompt_from_subject(subject: str) -> str:
    return f"{subject}. No text or logos."


def _planned_thumbnail_prompt(
    title: str, description: str, course_id: str, *, attempts: int = 3
) -> str:
    def plan_once() -> str:
        base_url, model = get_llm_endpoint("thumbnail")
        response = safe_chat_completion(
            base_url,
            model,
            [
                {"role": "system", "content": COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "course_name": title,
                            "course_description": description,
                            "style": "polished modern corporate e-learning thumbnail",
                            "size": "1024x1024",
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            default_max_tokens=500,
            course_id=course_id,
            stage="thumbnail_prompt",
            attempts=1,
        )
        if not response.choices:
            raise ValueError("LLM did not return a thumbnail prompt")
        subject = _extract_subject_from_llm(response.choices[0].message.content)
        if not subject:
            raise ValueError("LLM thumbnail subject response was not valid JSON")
        return _thumbnail_prompt_from_subject(subject)

    return retry(plan_once, course_id=course_id, stage="thumbnail_prompt", attempts=attempts)


def _decode_image_payload(payload: dict, endpoint: str = THUMBNAIL_ENDPOINT) -> Optional[bytes]:
    predictions = payload.get("predictions")
    if isinstance(predictions, list) and predictions:
        first_prediction = predictions[0]
        if isinstance(first_prediction, dict):
            image_b64 = first_prediction.get("image_b64")
            if isinstance(image_b64, str) and image_b64:
                return base64.b64decode(image_b64)

    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None

    first_image = data[0]
    if not isinstance(first_image, dict):
        return None

    b64_value = first_image.get("b64_json")
    if isinstance(b64_value, str) and b64_value:
        return base64.b64decode(b64_value)

    image_url = first_image.get("url")
    if isinstance(image_url, str) and image_url:
        if image_url.startswith("data:image/") and "," in image_url:
            return base64.b64decode(image_url.split(",", 1)[1])
        absolute_image_url = urljoin(endpoint, image_url)
        response = requests.get(absolute_image_url, timeout=120)
        response.raise_for_status()
        return response.content

    return None


def _thumbnail_request_payload(prompt: str) -> dict:
    if "/v1/images/generations" not in THUMBNAIL_ENDPOINT:
        return {"prompt": prompt}

    return {
        "model": THUMBNAIL_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }


def _thumbnail_request_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if THUMBNAIL_API_KEY:
        headers["Authorization"] = f"Bearer {THUMBNAIL_API_KEY}"
    return headers


def generate_course_thumbnail(
    course: dict, course_id: str, *, attempts: int = 3
) -> Optional[str]:
    """
    Generate and persist a course-card thumbnail.

    Returns a relative static asset path, e.g.
    assets/images/course_thumbnails/course-id-abc123.png.
    """
    title = course.get("course_name") or "Course"
    if not THUMBNAILS_ENABLED:
        logger.info("thumbnail_generation_skipped course_id=%s reason=disabled", course_id)
        return None

    start = time.perf_counter()
    description = course.get("course_description") or ""
    prompt_hash = course_thumbnail_signature(course)
    filename = f"{_safe_filename(course_id)}-{prompt_hash}.png"
    output_path = os.path.join(THUMBNAIL_DIR, filename)

    if os.path.exists(output_path):
        elapsed = time.perf_counter() - start
        logger.info(
            f"[THUMBNAIL] Reused existing thumbnail for course {course_id} in {elapsed:.1f}s: {filename}"
        )
        return public_asset_url("images", "course_thumbnails", filename)

    logger.info("thumbnail_prompt_planning_started course_id=%s", course_id)
    prompt_start = time.perf_counter()
    prompt = _planned_thumbnail_prompt(str(title), str(description), course_id, attempts=attempts)
    logger.info(
        f"[THUMBNAIL] Prompt planned for course {course_id} in {time.perf_counter() - prompt_start:.1f}s"
    )

    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    logger.info(
        f"[THUMBNAIL] Requesting image for course {course_id} "
        f"(endpoint={THUMBNAIL_ENDPOINT}, timeout={THUMBNAIL_CONNECT_TIMEOUT:.0f}s/{THUMBNAIL_READ_TIMEOUT:.0f}s)..."
    )
    image_start = time.perf_counter()

    def request_image_once() -> bytes:
        response = requests.post(
            THUMBNAIL_ENDPOINT,
            headers=_thumbnail_request_headers(),
            json=_thumbnail_request_payload(prompt),
            timeout=(THUMBNAIL_CONNECT_TIMEOUT, THUMBNAIL_READ_TIMEOUT),
        )
        response.raise_for_status()
        image_bytes = _decode_image_payload(response.json(), THUMBNAIL_ENDPOINT)
        if not image_bytes:
            raise ValueError("Image generation response did not include image data")
        return image_bytes

    image_bytes = retry(
        request_image_once, course_id=course_id, stage="thumbnail_image", attempts=attempts
    )
    logger.info(
        f"[THUMBNAIL] Image response received for course {course_id} in {time.perf_counter() - image_start:.1f}s"
    )

    with open(output_path, "wb") as image_file:
        image_file.write(image_bytes)

    elapsed = time.perf_counter() - start
    logger.info(
        f"[THUMBNAIL] Saved thumbnail for course {course_id} in {elapsed:.1f}s: {output_path}"
    )
    return public_asset_url("images", "course_thumbnails", filename)


logger = generation_logger(__name__)
