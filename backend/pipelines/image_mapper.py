import json
import requests
from pydantic import BaseModel
from typing import List, Dict, Any
from pipelines.config import get_llm_client, safe_chat_completion
from pipelines.prompts import IMAGE_LESSON_MAPPING_PROMPT

class ImageMapping(BaseModel):
    image_id: str
    bullet_index: int  # 1-based index in the flat list of bullets for this module

class ImageMappingResult(BaseModel):
    mappings: List[ImageMapping]

def map_images_to_lessons(course: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dedicated pass to map images to lessons using a semantic LLM matching prompt at the bullet point level.
    """
    modules = course.get("modules", [])
    if not modules:
        return course

    print("  [IMAGE MAPPER] Running dedicated image-to-lesson mapping pass...")

    for m_idx, module in enumerate(modules):
        images = module.get("images", [])
        lessons_flat = module.get("lessons", [])
        if not images or not lessons_flat:
            continue

        print(f"    [IMAGE MAPPER] Mapping {len(images)} images to {len(lessons_flat)} lessons in Module '{module.get('title')}'")

        # Build lessons string with sequential bullet indexing
        lessons_str = ""
        bullet_to_lesson = {}  # 1-based bullet index -> 0-based lesson index
        bullet_to_text = {}    # 1-based bullet index -> bullet text
        bullet_counter = 1

        for idx, lesson in enumerate(lessons_flat):
            lessons_str += f"Lesson {idx + 1}: {lesson.get('lesson_title')}\n"
            bullets = lesson.get("bullets", [])
            for b in bullets:
                bullet_text = b.get("text", "")
                lessons_str += f"  - Bullet {bullet_counter}: {bullet_text}\n"
                bullet_to_lesson[bullet_counter] = idx
                bullet_to_text[bullet_counter] = bullet_text
                bullet_counter += 1
            if not bullets:
                lessons_str += "  - (No bullets in this lesson)\n"
            lessons_str += "\n"

        # Build images string for the prompt
        images_str = ""
        for img in images:
            images_str += f"Image ID: {img.get('image_id')}\n"
            images_str += f"Caption: {img.get('caption')}\n\n"

        # Call LLM for mapping
        try:
            client, model_name = get_llm_client()
            response = safe_chat_completion(
                client=client,
                model=model_name,
                messages=[
                    {"role": "system", "content": IMAGE_LESSON_MAPPING_PROMPT},
                    {"role": "user", "content": f"LESSONS:\n{lessons_str}\n\nIMAGES:\n{images_str}"}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ImageMappingResult",
                        "schema": ImageMappingResult.model_json_schema()
                    }
                },
                temperature=0.1,
                default_max_tokens=1024
            )
            
            raw_content = response.choices[0].message.content
            result = ImageMappingResult.model_validate_json(raw_content)

            # Clear any existing images to prevent duplication/stale mappings
            for lesson in lessons_flat:
                lesson["images"] = []

            mapped_ids = set()
            for mapping in result.mappings:
                bullet_idx = mapping.bullet_index
                lesson_idx = bullet_to_lesson.get(bullet_idx, 0)
                if 0 <= lesson_idx < len(lessons_flat):
                    img_meta = next((img for img in images if img.get("image_id") == mapping.image_id), None)
                    if img_meta:
                        if "images" not in lessons_flat[lesson_idx]:
                            lessons_flat[lesson_idx]["images"] = []
                        if not any(existing.get("image_id") == mapping.image_id for existing in lessons_flat[lesson_idx]["images"]):
                            img_copy = dict(img_meta)
                            img_copy["mapped_bullet_text"] = bullet_to_text.get(bullet_idx, "")
                            lessons_flat[lesson_idx]["images"].append(img_copy)
                        mapped_ids.add(mapping.image_id)
                        print(f"      Mapped {mapping.image_id} to Lesson {lesson_idx + 1} ('{lessons_flat[lesson_idx].get('lesson_title')}') via Bullet {bullet_idx}")

            # Fallback for unmapped images to prevent loss
            for img in images:
                if img.get("image_id") not in mapped_ids:
                    if "images" not in lessons_flat[0]:
                        lessons_flat[0]["images"] = []
                    if not any(existing.get("image_id") == img.get("image_id") for existing in lessons_flat[0]["images"]):
                        lessons_flat[0]["images"].append(img)
                    print(f"      [FALLBACK] Mapped unassigned image {img.get('image_id')} to Lesson 1")

        except Exception as e:
            print(f"      [WARNING] Image mapping failed for module '{module.get('title')}': {e}")
            # In case of error, fall back to assigning all module images to lesson 1 so we don't lose them
            for lesson in lessons_flat:
                lesson["images"] = []
            for img in images:
                if "images" not in lessons_flat[0]:
                    lessons_flat[0]["images"] = []
                if not any(existing.get("image_id") == img.get("image_id") for existing in lessons_flat[0]["images"]):
                    lessons_flat[0]["images"].append(img)

    return course
