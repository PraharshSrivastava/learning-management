import requests
from typing import List
from pydantic import BaseModel

from pipelines.config import get_llm_client, safe_chat_completion
from pipelines.prompts import SLIDE_EXTRACTION_PROMPT


# -------------------------------------------------------
# Pydantic Schemas for LLM Response
# -------------------------------------------------------
class BulletPointSchema(BaseModel):
    text: str  # 5–10 words, ideally 7


class SlideSchema(BaseModel):
    slide_title: str          # 3–6 words, topic-focused
    bullets: List[BulletPointSchema]
    image_ids: List[str] = [] # List of image_id strings (e.g. ["img_123"]) that appear in this slide's context


class SlideListSchema(BaseModel):
    slides: List[SlideSchema]


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


def _validate_and_clean_slides(slides: List[dict]) -> List[dict]:
    """
    Post-process the parsed slide list:
    - Strip bullet text that is empty
    - Clamp bullets that are far too long
    - Remove slides with no content
    - Re-number slide_number sequentially
    """
    cleaned_slides = []
    for s_idx, slide in enumerate(slides):
        bullets = slide.get("bullets", [])
        cleaned_bullets = [
            {"text": _clamp_bullet_words(b["text"].strip())}
            for b in bullets
            if b.get("text", "").strip()
        ]
        if not cleaned_bullets:
            continue  # skip empty slides
        cleaned_slides.append({
            "slide_number": len(cleaned_slides) + 1,
            "slide_title": slide.get("slide_title", "").strip(),
            "bullets": cleaned_bullets,
            "image_ids": slide.get("image_ids", []),
        })

    return cleaned_slides


# -------------------------------------------------------
# Core LLM Call — one module at a time
# -------------------------------------------------------
def extract_slides_for_module(
    module_text: str,
    module_title: str,
    module_number: int,
    total_modules: int,
    prior_slide_titles: List[str],
    module_images: List[dict] = None,
) -> List[dict]:
    """
    Call the LLM to produce a Slides → Bullets list
    for a single module's text content.

    prior_slide_titles: flat list of slide titles already generated
    for previous modules. Used as a style anchor.
    """
    print(f"  Extracting slides for Module {module_number}/{total_modules}: '{module_title}'")

    if not module_text.strip():
        print(f"    [WARNING] Module '{module_title}' has no text content — skipping.")
        return []

    if module_images is None:
        module_images = []

    json_schema = SlideListSchema.model_json_schema()

    # Build the style anchor block
    if prior_slide_titles:
        prior_block = (
            "Previously generated slide titles from earlier modules in this same course:\n"
            + "\n".join(f"  - {t}" for t in prior_slide_titles)
            + "\n\n"
            "You MUST match this exact style, abstraction level, and outcome-focused language "
            "in every slide title you produce. The course must feel authored by one person.\n\n"
        )
    else:
        prior_block = ""

    user_message = (
        f"{prior_block}"
        f"Generate slides for the module below.\n\n"
        f"Module Title: \"{module_title}\"\n"
        f"Module Number: {module_number} of {total_modules}\n\n"
        f"MODULE CONTENT:\n"
        f"{module_text}\n\n"
        f"Every fact in the content must appear as a bullet. Do not skip anything.\n"
    )

    try:
        client, model_name = get_llm_client()
        response = safe_chat_completion(
            client=client,
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": SLIDE_EXTRACTION_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "SlideListSchema",
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
        
        parsed = SlideListSchema.model_validate_json(raw_content)

        slides_raw = [slide.model_dump() for slide in parsed.slides]
        slides = _validate_and_clean_slides(slides_raw)

        # Map image_ids to actual image metadata dicts for each slide
        for slide in slides:
            slide["images"] = []
            image_ids = slide.pop("image_ids", [])
            for img_id in image_ids:
                # Find matching image metadata in module_images
                img_meta = next((img for img in module_images if img.get("image_id") == img_id), None)
                if img_meta and not any(x["image_id"] == img_id for x in slide["images"]):
                    slide["images"].append(img_meta)
                    print(f"    [MAPPED] Inline mapped image '{img_id}' to slide '{slide.get('slide_title')}'")

        # Ensure all module images are assigned somewhere to prevent loss
        mapped_image_ids = set()
        for slide in slides:
            for img in slide.get("images", []):
                mapped_image_ids.add(img["image_id"])
                
        unmapped_images = [img for img in module_images if img["image_id"] not in mapped_image_ids]
        if unmapped_images and slides:
            first_slide = slides[0]
            if "images" not in first_slide:
                first_slide["images"] = []
            for img in unmapped_images:
                first_slide["images"].append(img)
                print(f"    [FALLBACK] Inline fallback mapped unassigned image '{img['image_id']}' to slide '{first_slide.get('slide_title')}'")

        print(
            f"    -> {len(slides)} slides, "
            f"{sum(len(b['bullets']) for b in slides)} bullets"
        )
        return slides

    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"LLM request timed out for module '{module_title}' after 600 seconds."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"LLM request failed for module '{module_title}': {str(e)}")
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse slide response for module '{module_title}': {str(e)}"
        )


# Backward compatibility wrapper
def extract_lessons_for_module(
    module_text: str,
    module_title: str,
    module_number: int,
    total_modules: int,
    prior_lesson_titles: List[str],
    module_images: List[dict] = None,
) -> List[dict]:
    # Adapts the new slide output format into the legacy lessons structure
    slides = extract_slides_for_module(
        module_text=module_text,
        module_title=module_title,
        module_number=module_number,
        total_modules=total_modules,
        prior_slide_titles=prior_lesson_titles,
        module_images=module_images
    )
    return [{
        "lesson_number": 1,
        "lesson_title": module_title,
        "slides": slides
    }]
