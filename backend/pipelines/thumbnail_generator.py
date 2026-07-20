import base64
import hashlib
import json
import os
import re
from typing import Optional
from urllib.parse import urljoin

import requests

from core.config import IMAGE_DIR
from pipelines.config import get_llm_endpoint, safe_chat_completion
from pipelines.prompts import COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT

THUMBNAIL_ENDPOINT = os.environ.get(
    "COURSE_THUMBNAIL_ENDPOINT",
    "http://35.238.33.238:8002/generate",
)
THUMBNAIL_MODEL = os.environ.get("COURSE_THUMBNAIL_MODEL", "baidu/ERNIE-Image")
THUMBNAIL_CONNECT_TIMEOUT = float(os.environ.get("COURSE_THUMBNAIL_CONNECT_TIMEOUT", "60"))
THUMBNAIL_READ_TIMEOUT = float(os.environ.get("COURSE_THUMBNAIL_READ_TIMEOUT", "180"))
THUMBNAIL_DIR = os.path.join(IMAGE_DIR, "course_thumbnails")
THUMBNAIL_PROMPT_VERSION = "llm-planned-v1"
THUMBNAILS_ENABLED = os.environ.get("COURSE_THUMBNAILS_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}


def _safe_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return slug[:80] or "course"


def course_thumbnail_signature(course: dict) -> str:
    title = str(course.get("course_name") or course.get("title") or "Course").strip()
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


def _extract_prompt_from_llm(content: str) -> Optional[str]:
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
    prompt = data.get("prompt") if isinstance(data, dict) else None
    if not isinstance(prompt, str):
        return None
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt or None


def _planned_thumbnail_prompt(title: str, description: str) -> str:
    base_url, model = get_llm_endpoint()
    response = safe_chat_completion(
        base_url,
        model,
        [
            {
                "role": "system",
                "content": COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "course_name": title,
                        "course_description": description,
                        "style": "polished modern corporate e-learning thumbnail",
                        "size": "512x512",
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        default_max_tokens=500,
    )
    if not response.choices:
        raise ValueError("LLM did not return a thumbnail prompt")
    planned = _extract_prompt_from_llm(response.choices[0].message.content)
    if not planned:
        raise ValueError("LLM thumbnail prompt response was not valid JSON")
    return planned


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
        "size": "512x512",
        "num_inference_steps": 20,
        "use_pe": False,
    }


def generate_course_thumbnail(course: dict, course_id: str) -> Optional[str]:
    """
    Generate and persist a course-card thumbnail.

    Returns a relative static asset path, e.g.
    assets/images/course_thumbnails/course-id-abc123.png.
    """
    title = course.get("course_name") or course.get("title") or "Course"
    if not THUMBNAILS_ENABLED:
        return None

    description = course.get("course_description") or ""
    prompt = _planned_thumbnail_prompt(str(title), str(description))
    prompt_hash = course_thumbnail_signature(course)
    filename = f"{_safe_filename(course_id)}-{prompt_hash}.png"
    output_path = os.path.join(THUMBNAIL_DIR, filename)

    if os.path.exists(output_path):
        return f"assets/images/course_thumbnails/{filename}"

    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    response = requests.post(
        THUMBNAIL_ENDPOINT,
        headers={"Content-Type": "application/json"},
        json=_thumbnail_request_payload(prompt),
        timeout=(THUMBNAIL_CONNECT_TIMEOUT, THUMBNAIL_READ_TIMEOUT),
    )
    response.raise_for_status()

    image_bytes = _decode_image_payload(response.json(), THUMBNAIL_ENDPOINT)
    if not image_bytes:
        raise ValueError("Image generation response did not include image data")

    with open(output_path, "wb") as image_file:
        image_file.write(image_bytes)

    return f"assets/images/course_thumbnails/{filename}"
