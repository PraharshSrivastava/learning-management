"""Plan, generate, store, and identify course thumbnails."""

import base64
import hashlib
import json
import os
import random
import re
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from PIL import Image, ImageDraw

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
# The signature also gates publishing (course_access.course_is_publishable), so
# bumping this marks every existing course's thumbnail stale. Change it only
# when old thumbnails must be regenerated, not for prompt wording tweaks.
THUMBNAIL_PROMPT_VERSION = "single-subject-v2"
# The planner picks the subject only; the shared style keeps course cards
# visually consistent across courses.
THUMBNAIL_STYLE = (
    "Polished modern 3D illustration for a corporate e-learning course card, "
    "soft studio lighting, smooth rounded shapes, cohesive professional colour palette, "
    "softly coloured gradient background, one clear focal point, high detail."
)
# The planner sometimes ignores its no-writing rule. Qwen Image then draws the
# words (often garbled), so subjects naming text or text-bearing objects are
# rejected and planned again.
_TEXT_BEARING_SUBJECT = re.compile(
    r"(?:^|\s)['\"‘“]"
    r"|\b(?:label(?:l?ed|s)?|written|words?|text|letters?|numbers?|signs?|signposts?"
    r"|newspapers?|books?|documents?|certificates?|papers?|screens?|monitors?"
    r"|display(?:s|ing|ed)?|interfaces?|dashboards?|charts?|graphs?|tickers?|boards?"
    r"|banknotes?|currency|phones?|tablets?|laptops?|flags?|logos?|brands?)\b",
    re.IGNORECASE,
)
THUMBNAIL_PLANNER_ATTEMPTS = 3
THUMBNAIL_QWEN_IMAGE_STEPS = 40
THUMBNAILS_ENABLED = settings.thumbnails_enabled

_PLACEHOLDER_PALETTES = (
    ("#173F5F", "#20639B", "#3CAEA3", "#F6D55C"),
    ("#2D1E5F", "#5B3CC4", "#8B5CF6", "#F0ABFC"),
    ("#12372A", "#436850", "#ADBC9F", "#FBFADA"),
    ("#4A1942", "#893168", "#C4547D", "#F4B8C5"),
    ("#102A43", "#336B87", "#90AFC5", "#F2F6F8"),
)


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
    # Qwen Image renders legible text eagerly, so the ban is spelled out in full.
    return (
        f"{subject}. {THUMBNAIL_STYLE} "
        "The image contains no text, letters, numbers, words, labels, logos or watermarks."
    )


def _planned_thumbnail_prompt(
    title: str, description: str, course_id: str, *, attempts: int = 3
) -> str:
    rejected_subjects: list[str] = []

    def plan_once() -> str:
        request = {
            "course_name": title,
            "course_description": description,
            "style": "polished modern corporate e-learning thumbnail",
            "size": "1024x1024",
        }
        if rejected_subjects:
            # Without this feedback the planner keeps returning the same idea.
            request["rejected_subjects"] = rejected_subjects
        base_url, model = get_llm_endpoint("thumbnail")
        response = safe_chat_completion(
            base_url,
            model,
            [
                {"role": "system", "content": COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2 if not rejected_subjects else 0.7,
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
        if _TEXT_BEARING_SUBJECT.search(subject):
            rejected_subjects.append(subject)
            raise ValueError(f"LLM thumbnail subject names text-bearing objects: {subject}")
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

    payload = {
        "model": THUMBNAIL_MODEL,
        "prompt": prompt,
        "size": "1024x1024",
    }
    # LiteLLM rejects the OpenAI-only `n` and `response_format` for Qwen Image
    # and Flux (HTTP 400); both already answer with base64 JSON by default.
    family = THUMBNAIL_MODEL.casefold()
    if "qwen-image" in family:
        # Some Qwen Image servers have no default and fail with HTTP 500 without
        # it; 40 matches the Video Generator's ANIMATION_IMAGE_STEPS default.
        payload["num_inference_steps"] = THUMBNAIL_QWEN_IMAGE_STEPS
    elif "flux" not in family:
        payload["n"] = 1
        payload["response_format"] = "b64_json"
    return payload


def _thumbnail_request_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if THUMBNAIL_API_KEY:
        headers["Authorization"] = f"Bearer {THUMBNAIL_API_KEY}"
    return headers


def _compressed_thumbnail(image_bytes: bytes) -> bytes:
    """Re-encode model output as WebP; Qwen Image returns ~4 MB uncompressed PNGs."""
    from io import BytesIO

    with Image.open(BytesIO(image_bytes)) as image:
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="WEBP", quality=85, method=6)
    return buffer.getvalue()


def _placeholder_image_bytes() -> bytes:
    """Create a random, text-free placeholder that is safe for course cards."""
    from io import BytesIO

    rng = random.SystemRandom()
    palette = rng.choice(_PLACEHOLDER_PALETTES)
    size = 1024
    image = Image.new("RGB", (size, size), palette[0])
    draw = ImageDraw.Draw(image, "RGBA")

    # Layer oversized translucent shapes so every fallback is visually distinct.
    for index in range(14):
        diameter = rng.randint(180, 680)
        x = rng.randint(-diameter // 2, size - diameter // 2)
        y = rng.randint(-diameter // 2, size - diameter // 2)
        color = palette[1 + (index % (len(palette) - 1))]
        draw.ellipse(
            (x, y, x + diameter, y + diameter),
            fill=color + rng.choice(("55", "70", "88", "A0")),
        )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def generate_course_thumbnail(
    course: dict, course_id: str, *, attempts: int = 3
) -> Optional[str]:
    """
    Generate and persist a course-card thumbnail.

    Returns a relative static asset path, e.g.
    assets/images/course_thumbnails/course-id-abc123.webp (model output) or
    .png (local placeholder).
    """
    title = course.get("course_name") or "Course"
    if not THUMBNAILS_ENABLED:
        logger.info("thumbnail_generation_skipped course_id=%s reason=disabled", course_id)
        return None

    start = time.perf_counter()
    description = course.get("course_description") or ""
    prompt_hash = course_thumbnail_signature(course)
    stem = f"{_safe_filename(course_id)}-{prompt_hash}"

    for extension in ("webp", "png"):
        filename = f"{stem}.{extension}"
        if os.path.exists(os.path.join(THUMBNAIL_DIR, filename)):
            elapsed = time.perf_counter() - start
            logger.info(
                f"[THUMBNAIL] Reused existing thumbnail for course {course_id} in {elapsed:.1f}s: {filename}"
            )
            return public_asset_url("images", "course_thumbnails", filename)

    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    try:
        logger.info("thumbnail_prompt_planning_started course_id=%s", course_id)
        prompt_start = time.perf_counter()
        # The image request deliberately gets one attempt; only the cheap planning
        # call is retried. Any failure is replaced locally below.
        prompt = _planned_thumbnail_prompt(
            str(title), str(description), course_id, attempts=THUMBNAIL_PLANNER_ATTEMPTS
        )
        logger.info(
            f"[THUMBNAIL] Prompt planned for course {course_id} in {time.perf_counter() - prompt_start:.1f}s"
        )
        logger.info(
            f"[THUMBNAIL] Requesting image for course {course_id} "
            f"(endpoint={THUMBNAIL_ENDPOINT}, timeout={THUMBNAIL_CONNECT_TIMEOUT:.0f}s/{THUMBNAIL_READ_TIMEOUT:.0f}s)..."
        )
        image_start = time.perf_counter()
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
        image_bytes = _compressed_thumbnail(image_bytes)
        filename = f"{stem}.webp"
        logger.info(
            f"[THUMBNAIL] Image response received for course {course_id} in {time.perf_counter() - image_start:.1f}s"
        )
    except Exception as exc:
        logger.warning(
            "thumbnail_generation_fallback course_id=%s reason=%s",
            course_id,
            str(exc)[:500],
        )
        image_bytes = _placeholder_image_bytes()
        filename = f"{stem}.png"

    output_path = os.path.join(THUMBNAIL_DIR, filename)
    with open(output_path, "wb") as image_file:
        image_file.write(image_bytes)

    elapsed = time.perf_counter() - start
    logger.info(
        f"[THUMBNAIL] Saved thumbnail for course {course_id} in {elapsed:.1f}s: {output_path}"
    )
    return public_asset_url("images", "course_thumbnails", filename)


logger = generation_logger(__name__)
