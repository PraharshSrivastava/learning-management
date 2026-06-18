import json
import requests
from pydantic import BaseModel
from typing import List, Dict, Any
from pipelines.config import get_llm_client, safe_chat_completion
from pipelines.prompts import IMAGE_SLIDE_MAPPING_PROMPT

class ImageMapping(BaseModel):
    image_id: str
    slide_index: int  # 1-based index in the flat list of slides for this module

class ImageMappingResult(BaseModel):
    mappings: List[ImageMapping]

def map_images_to_slides(course: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dedicated pass to map images to slides using a semantic LLM matching prompt.
    """
    modules = course.get("modules", [])
    if not modules:
        return course

    print("  [IMAGE MAPPER] Running dedicated image-to-slide mapping pass...")

    for m_idx, module in enumerate(modules):
        images = module.get("images", [])
        slides_flat = module.get("slides", [])
        if not images or not slides_flat:
            continue

        print(f"    [IMAGE MAPPER] Mapping {len(images)} images to {len(slides_flat)} slides in Module '{module.get('title')}'")

        # Build slides string for the prompt
        slides_str = ""
        for idx, slide in enumerate(slides_flat):
            slides_str += f"Slide {idx + 1}: {slide.get('slide_title')}\n"
            for b in slide.get("bullets", []):
                slides_str += f"  - {b.get('text')}\n"
            slides_str += "\n"

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
                    {"role": "system", "content": IMAGE_SLIDE_MAPPING_PROMPT},
                    {"role": "user", "content": f"SLIDES:\n{slides_str}\n\nIMAGES:\n{images_str}"}
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
            for slide in slides_flat:
                slide["images"] = []

            mapped_ids = set()
            for mapping in result.mappings:
                slide_idx = mapping.slide_index - 1
                if 0 <= slide_idx < len(slides_flat):
                    img_meta = next((img for img in images if img.get("image_id") == mapping.image_id), None)
                    if img_meta:
                        if "images" not in slides_flat[slide_idx]:
                            slides_flat[slide_idx]["images"] = []
                        slides_flat[slide_idx]["images"].append(img_meta)
                        mapped_ids.add(mapping.image_id)
                        print(f"      Mapped {mapping.image_id} to Slide {mapping.slide_index} ('{slides_flat[slide_idx].get('slide_title')}')")

            # Fallback for unmapped images to prevent loss
            for img in images:
                if img.get("image_id") not in mapped_ids:
                    if "images" not in slides_flat[0]:
                        slides_flat[0]["images"] = []
                    slides_flat[0]["images"].append(img)
                    print(f"      [FALLBACK] Mapped unassigned image {img.get('image_id')} to Slide 1")

        except Exception as e:
            print(f"      [WARNING] Image mapping failed for module '{module.get('title')}': {e}")
            # In case of error, fall back to assigning all module images to slide 1 so we don't lose them
            for slide in slides_flat:
                slide["images"] = []
            for img in images:
                if "images" not in slides_flat[0]:
                    slides_flat[0]["images"] = []
                slides_flat[0]["images"].append(img)

    return course
