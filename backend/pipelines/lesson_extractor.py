import requests
from typing import List
from pydantic import BaseModel

from pipelines.config import get_llm_endpoint, safe_chat_completion
from pipelines.prompts import LESSON_EXTRACTION_PROMPT


# -------------------------------------------------------
# Pydantic Schemas for LLM Response
# -------------------------------------------------------
class BulletPointSchema(BaseModel):
    text: str  # 5–10 words, ideally 7


class LessonSchema(BaseModel):
    lesson_title: str          # 3–6 words, topic-focused
    bullets: List[BulletPointSchema]
    image_ids: List[str] = [] # List of image_id strings (e.g. ["img_123"]) that appear in this lesson's context


class LessonListSchema(BaseModel):
    lessons: List[LessonSchema]


# -------------------------------------------------------
# Validation helpers
# -------------------------------------------------------
def _clamp_bullet_words(text: str) -> str:
    """
    Soft-fix bullet points that are clearly too long (> 25 words).
    Truncate at word 20 — the style refiner will handle tightening later.
    """
    words = text.split()
    if len(words) > 25:
        return ' '.join(words[:20])
    return text


def _validate_and_clean_lessons(raw_lessons: List[dict]) -> List[dict]:
    """
    Post-process the parsed lesson list:
    - Strip bullet text that is empty
    - Clamp bullets that are far too long
    - Remove lessons with no content
    - Number lessons sequentially
    """
    cleaned_lessons = []
    for l_idx, lesson in enumerate(raw_lessons):
        bullets = lesson.get("bullets", [])
        cleaned_bullets = [
            {"text": _clamp_bullet_words(b["text"].strip())}
            for b in bullets
            if b.get("text", "").strip()
        ]
        if not cleaned_bullets:
            continue  # skip empty lessons
        cleaned_lessons.append({
            "lesson_number": len(cleaned_lessons) + 1,
            "lesson_title": lesson.get("lesson_title", "").strip(),
            "bullets": cleaned_bullets,
            "image_ids": lesson.get("image_ids", []),
        })

    return cleaned_lessons


# -------------------------------------------------------
# Core LLM Call — one module at a time
# -------------------------------------------------------
def extract_lessons_for_module(
    module_text: str,
    module_title: str,
    module_number: int,
    total_modules: int,
    prior_lesson_titles: List[str],
    module_images: List[dict] = None,
) -> List[dict]:
    """
    Call the LLM to produce a Lessons → Bullets list
    for a single module's text content.

    prior_lesson_titles: flat list of lesson titles already generated
    for previous modules. Used as a style anchor.
    """
    print(f"  Extracting lessons for Module {module_number}/{total_modules}: '{module_title}'")

    if not module_text.strip():
        print(f"    [WARNING] Module '{module_title}' has no text content — skipping.")
        return []

    if module_images is None:
        module_images = []

    json_schema = LessonListSchema.model_json_schema()

    # Build the style anchor block
    if prior_lesson_titles:
        prior_block = (
            "Previously generated lesson titles from earlier modules in this same course:\n"
            + "\n".join(f"  - {t}" for t in prior_lesson_titles)
            + "\n\n"
            "You MUST match this exact style, abstraction level, and outcome-focused language "
            "in every lesson title you produce. The course must feel authored by one person.\n\n"
        )
    else:
        prior_block = ""

    user_message = (
        f"{prior_block}"
        f"Generate lessons for the module below.\n\n"
        f"Module Title: \"{module_title}\"\n"
        f"Module Number: {module_number} of {total_modules}\n\n"
        f"MODULE CONTENT:\n"
        f"{module_text}\n\n"
        f"Every fact in the content must appear as a bullet. Do not skip anything.\n"
    )

    try:
        base_url, model_name = get_llm_endpoint()
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": LESSON_EXTRACTION_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "LessonListSchema",
                    "schema": json_schema,
                },
            },
            temperature=0.2,
            default_max_tokens=2048,
        )

        raw_content = response.choices[0].message.content
        
        finish_reason = response.choices[0].finish_reason or "unknown"
        if finish_reason == "length":
            print(f"    [WARNING] LLM output was TRUNCATED (hit max_tokens) for module '{module_title}'.")
        
        parsed = LessonListSchema.model_validate_json(raw_content)

        lessons_raw = [lesson.model_dump() for lesson in parsed.lessons]
        lessons = _validate_and_clean_lessons(lessons_raw)

        # Map image_ids to actual image metadata dicts for each lesson
        for lesson in lessons:
            lesson["images"] = []
            image_ids = lesson.pop("image_ids", [])
            for img_id in image_ids:
                # Find matching image metadata in module_images
                img_meta = next((img for img in module_images if img.get("image_id") == img_id), None)
                if img_meta and not any(x["image_id"] == img_id for x in lesson["images"]):
                    lesson["images"].append(img_meta)
                    print(f"    [MAPPED] Inline mapped image '{img_id}' to lesson '{lesson.get('lesson_title')}'")

        # Ensure all module images are assigned somewhere to prevent loss
        mapped_image_ids = set()
        for lesson in lessons:
            for img in lesson.get("images", []):
                mapped_image_ids.add(img["image_id"])
                
        unmapped_images = [img for img in module_images if img["image_id"] not in mapped_image_ids]
        if unmapped_images and lessons:
            first_lesson = lessons[0]
            if "images" not in first_lesson:
                first_lesson["images"] = []
            for img in unmapped_images:
                first_lesson["images"].append(img)
                print(f"    [FALLBACK] Inline fallback mapped unassigned image '{img['image_id']}' to lesson '{first_lesson.get('lesson_title')}'")

        print(
            f"    -> {len(lessons)} lessons, "
            f"{sum(len(b['bullets']) for b in lessons)} bullets"
        )
        return lessons

    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"LLM request timed out for module '{module_title}' after 600 seconds."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"LLM request failed for module '{module_title}': {str(e)}")
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse lesson response for module '{module_title}': {str(e)}"
        )
