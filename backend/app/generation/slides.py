"""Plan, lay out, validate, and persist course slides."""

import copy
import json
import re
import time
from typing import Any, Dict

from pydantic import ValidationError

from app.core.exceptions import ProviderError
from app.core.logging import generation_logger
from app.core.providers import get_llm_endpoint, safe_chat_completion
from app.generation.parallel import default_llm_workers, run_parallel_stage_items
from app.generation.prompts import (
    ART_DIRECTOR_PROMPT,
    IMAGE_SLIDE_MAPPING_PROMPT,
    MODULE_SLIDE_PLANNER_PROMPT,
    SLIDE_TITLES_PROMPT,
)
from app.generation.runtime import (
    ensure_module_cover_slide,
    load_course_for_generation,
    log_event,
    save_generated_course,
)
from app.schemas.course import ModuleResponse
from app.schemas.generation.slides import (
    ArtDirectorResponse,
    ImageMappingResult,
    ModuleSlidesSchema,
    SlideTitlesSchema,
)

logger = generation_logger(__name__)


def _slide_image_orientation(image: dict[str, Any]) -> str:
    stored = str(image.get("orientation") or "").lower()
    if stored in {"landscape", "portrait", "square"}:
        return stored
    try:
        width = float(image.get("width") or 0)
        height = float(image.get("height") or 0)
        if width > 0 and height > 0:
            ratio = width / height
            return "landscape" if ratio >= 1.2 else "portrait" if ratio <= 0.83 else "square"
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return "portrait"


def _image_slide_group_key(image: dict[str, Any]) -> str:
    return "landscape" if _slide_image_orientation(image) == "landscape" else "vertical"


def _chunk_images(images: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [images[index : index + size] for index in range(0, len(images), size)]


def _group_images_for_image_slides(images: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group mapped images for clean image-only slides while preserving local order."""
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    current_key = ""
    current_images: list[dict[str, Any]] = []

    def flush() -> None:
        if not current_images:
            return
        group_size = 1 if current_key == "landscape" else 3
        for chunk in _chunk_images(current_images, group_size):
            groups.append((current_key, chunk))

    for image in images:
        key = _image_slide_group_key(image)
        if current_images and key != current_key:
            flush()
            current_images = []
        current_key = key
        current_images.append(image)
    flush()
    return groups


def _figure_number_sort_key(image: dict[str, Any]) -> tuple[int, tuple[int, ...], str]:
    caption = str(image.get("raw_caption") or image.get("caption") or "")
    match = re.search(
        r"\b(?:figure|fig|image|img|chart)\s*(\d+(?:[.\-]\d+)*)",
        caption,
        re.IGNORECASE,
    )
    if not match:
        return (1, (), caption.lower())
    parts = tuple(int(part) for part in re.findall(r"\d+", match.group(1)))
    return (0, parts, caption.lower())


def _sort_slide_images_by_mapping(slide: dict[str, Any]) -> None:
    slide["images"] = sorted(
        slide.get("images") or [],
        key=lambda image: (
            int(image.get("mapped_bullet_index") or 10_000),
            *_figure_number_sort_key(image),
        ),
    )


def _append_image_to_slide(
    slide: dict[str, Any], image: dict[str, Any], mapped_bullet_index: int | None = None
) -> None:
    slide.setdefault("images", [])
    image_id = image.get("image_id")
    if image_id and any(existing.get("image_id") == image_id for existing in slide["images"]):
        return
    mapped_image = dict(image)
    if mapped_bullet_index is not None:
        mapped_image["mapped_bullet_index"] = mapped_bullet_index
    slide["images"].append(mapped_image)


def _expand_mapped_image_slides(module: dict) -> dict:
    expanded_slides: list[dict[str, Any]] = []
    for source_index, slide in enumerate(module.get("slides", []), start=1):
        slide_images = list(slide.get("images") or [])
        mapped_image_ids = [
            image.get("image_id")
            for image in slide_images
            if image.get("image_id")
        ]

        content_slide = dict(slide)
        if mapped_image_ids:
            content_slide["mapped_image_ids"] = mapped_image_ids
        content_slide["image_ids"] = []
        content_slide["images"] = []
        expanded_slides.append(content_slide)

        for group_number, (group_key, image_group) in enumerate(
            _group_images_for_image_slides(slide_images),
            start=1,
        ):
            group_ids = [
                image.get("image_id")
                for image in image_group
                if image.get("image_id")
            ]
            title = content_slide.get("slide_title") or content_slide.get("title", "")
            expanded_slides.append(
                {
                    "title": "",
                    "slide_title": "",
                    "layout_type": "image",
                    "is_image_slide": True,
                    "source_slide_index": source_index,
                    "source_slide_title": title,
                    "image_layout": group_key,
                    "image_ids": group_ids,
                    "images": image_group,
                    "content": [],
                    "bullets": [],
                    "bullets_data": [],
                }
            )

            logger.info(
                "image_slide_inserted module=%s source_slide=%s group=%s image_count=%s layout=%s",
                module.get("module_number"),
                source_index,
                group_number,
                len(group_ids),
                group_key,
            )

    module["slides"] = expanded_slides
    return module


def plan_slides_for_module(
    module: dict,
    base_url: str,
    model_name: str,
    *,
    course_id: str = "unknown",
) -> dict:
    """
    Step 5 logic: Groups bullets into slides, maps images, and generates titles.
    """
    text_input = module.get("source_text", "")
    if not text_input:
        module["planned_slides"] = []
        return module

    json_schema = ModuleSlidesSchema.model_json_schema()

    prompt = MODULE_SLIDE_PLANNER_PROMPT.format(text_input=text_input)
    try:
        logger.info("slide_planning_llm_started module=%s", module.get("module_number"))
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a logical presentation designer."},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ModuleSlidesSchema",
                    "schema": json_schema,
                    "strict": True,
                },
            },
            temperature=0.2,
            default_max_tokens=4096,
            course_id=course_id,
            stage="slide_planning",
            module_number=module.get("module_number"),
        )

        raw_content = response.choices[0].message.content
        parsed = ModuleSlidesSchema.model_validate_json(raw_content)

        # --- SECOND LLM CALL: SYNTHESIZE TITLES ---
        if parsed.slides:
            logger.info(
                f"    -> Calling LLM to synthesize titles for {len(parsed.slides)} slides..."
            )
            titles_prompt = SLIDE_TITLES_PROMPT.format(source_text=text_input)

            for i, slide in enumerate(parsed.slides):
                titles_prompt += f"Slide {i + 1}:\n"
                for b in slide.content:
                    titles_prompt += f"- {b}\n"
                titles_prompt += "\n"

            titles_response = safe_chat_completion(
                base_url=base_url,
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an expert copywriter."},
                    {"role": "user", "content": titles_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "SlideTitlesSchema",
                        "schema": SlideTitlesSchema.model_json_schema(),
                        "strict": True,
                    },
                },
                temperature=0.2,
                default_max_tokens=2048,
                course_id=course_id,
                stage="slide_titles",
                module_number=module.get("module_number"),
            )

            titles_raw = titles_response.choices[0].message.content
            titles_parsed = SlideTitlesSchema.model_validate_json(titles_raw)

            for i, slide in enumerate(parsed.slides):
                if i < len(titles_parsed.titles):
                    slide.title = titles_parsed.titles[i].title

        planned_slides = parsed.model_dump()["slides"]
        module["chain_of_thought"] = parsed.chain_of_thought

        # --- 3rd LLM Call: Map Images ---
        images = module.get("images", [])
        if images and planned_slides:
            for slide in planned_slides:
                slide["images"] = []

            logger.info(
                f"\n    -> Calling LLM (Image Mapper) for Module {module.get('module_number')}..."
            )
            slides_str = ""
            bullet_to_slide = {}
            bullet_counter = 1

            for s_idx, slide in enumerate(planned_slides):
                slides_str += f"Slide {s_idx + 1}: {slide.get('title')}\n"
                bullets = slide.get("content", [])
                for b in bullets:
                    slides_str += f"  - Bullet {bullet_counter}: {b}\n"
                    bullet_to_slide[bullet_counter] = s_idx
                    bullet_counter += 1
                if not bullets:
                    slides_str += "  - (No bullets)\n"
                slides_str += "\n"

            images_str = ""
            for img in images:
                images_str += f"Image ID: {img.get('image_id')}\n"
                images_str += f"Caption: {img.get('caption')}\n\n"

            mapping_prompt = f"SLIDES:\n{slides_str}\n\nIMAGES:\n{images_str}"

            mapping_response = safe_chat_completion(
                base_url=base_url,
                model=model_name,
                messages=[
                    {"role": "system", "content": str(IMAGE_SLIDE_MAPPING_PROMPT)},
                    {"role": "user", "content": mapping_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ImageMappingResult",
                        "schema": ImageMappingResult.model_json_schema(),
                        "strict": True,
                    },
                },
                temperature=0.1,
                default_max_tokens=1024,
                course_id=course_id,
                stage="slide_image_mapping",
                module_number=module.get("module_number"),
            )

            mapping_raw = mapping_response.choices[0].message.content
            mapping_parsed = ImageMappingResult.model_validate_json(mapping_raw)

            mapped_ids = set()
            for mapping in mapping_parsed.mappings:
                img_meta = next(
                    (img for img in images if img.get("image_id") == mapping.image_id),
                    None,
                )
                if not img_meta:
                    continue

                s_idx = bullet_to_slide.get(mapping.bullet_index, 0)
                if 0 <= s_idx < len(planned_slides):
                    _append_image_to_slide(
                        planned_slides[s_idx],
                        img_meta,
                        mapped_bullet_index=mapping.bullet_index,
                    )
                    mapped_ids.add(mapping.image_id)

            for img in images:
                if img.get("image_id") not in mapped_ids:
                    _append_image_to_slide(planned_slides[0], img)
                    logger.info(
                        f"      [FALLBACK] Mapped unassigned image {img.get('image_id')} to Slide 1"
                    )

            for slide in planned_slides:
                _sort_slide_images_by_mapping(slide)

        module["planned_slides"] = planned_slides

    except (
        ProviderError,
        ValidationError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
    ) as e:
        logger.warning(
            "slide_planning_failed module=%s error=%s",
            module.get("module_number"),
            e,
        )
        module["planned_slides"] = []
        module["chain_of_thought"] = str(e)

    ModuleResponse.model_validate(module)
    return module

def assign_layouts_to_module(
    module: dict,
    base_url: str,
    model_name: str,
    *,
    course_id: str = "unknown",
) -> dict:
    """
    Step 6 logic: Assigns layouts to the planned slides.
    """
    planned_slides = module.get("planned_slides", [])
    if not planned_slides:
        module["slides"] = []
        return module

    logger.info(
        f"\n    -> Calling Art Director LLM for Module {module.get('module_number', '1')}..."
    )

    slides_text = ""
    for idx, slide in enumerate(planned_slides):
        slides_text += f"Slide {idx + 1}:\n"
        slides_text += f"Title: {slide.get('title')}\n"
        slides_text += "Bullets:\n"
        for b in slide.get("content", []):
            slides_text += f" - {b}\n"
        slides_text += "\n"

    source_text = module.get("source_text", "").strip()
    prompt = ART_DIRECTOR_PROMPT.format(slides_text=slides_text, source_text=source_text)
    try:
        json_schema = ArtDirectorResponse.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": "You are a creative and analytical presentation art director.",
            },
            {"role": "user", "content": prompt},
        ]
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ArtDirectorResponse",
                    "schema": json_schema,
                    "strict": True,
                },
            },
            temperature=0.2,
            default_max_tokens=3072,
            course_id=course_id,
            stage="slide_art_direction",
            module_number=module.get("module_number"),
        )

        raw_payload = json.loads(response.choices[0].message.content)
        parsed = ArtDirectorResponse.model_validate(raw_payload)

        for i, enhanced_slide in enumerate(parsed.slides):
            if i < len(planned_slides):
                planned_slides[i]["layout_type"] = enhanced_slide.layout_type

                planned_slides[i]["slide_title"] = planned_slides[i].get("title", "")
                if "images" in planned_slides[i]:
                    planned_slides[i]["image_ids"] = [
                        img.get("image_id")
                        for img in planned_slides[i]["images"]
                        if img.get("image_id")
                    ]

                if enhanced_slide.steps_data:
                    planned_slides[i]["steps_data"] = enhanced_slide.steps_data.model_dump()
                if enhanced_slide.comparison_data:
                    planned_slides[i]["comparison_data"] = (
                        enhanced_slide.comparison_data.model_dump()
                    )
                if enhanced_slide.grid_data:
                    planned_slides[i]["grid_data"] = enhanced_slide.grid_data.model_dump()
                if enhanced_slide.bullets:
                    planned_slides[i]["bullets_data"] = enhanced_slide.bullets
                    planned_slides[i]["content"] = enhanced_slide.bullets
                    planned_slides[i]["bullets"] = enhanced_slide.bullets
        module["slides"] = planned_slides

    except (
        ProviderError,
        ValidationError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
    ) as e:
        logger.warning(
            "art_direction_failed module=%s error=%s",
            module.get("module_number"),
            e,
        )
        module["slides"] = planned_slides

    ModuleResponse.model_validate(module)
    return module

def _module_slides_are_valid(mod_copy: dict) -> bool:
    for slide in mod_copy.get("planned_slides", []):
        content = slide.get("content", [])
        layout = slide.get("layout_type", "")

        if not slide.get("slide_title"):
            logger.info(
                "slide_validation_failed module=%s reason=missing_slide_title",
                mod_copy.get("module_number"),
            )
            return False
        if len(content) == 0:
            logger.info(
                "slide_validation_failed module=%s reason=empty_slide",
                mod_copy.get("module_number"),
            )
            return False
        if layout == "steps" and not slide.get("steps_data"):
            logger.info(
                "slide_validation_failed module=%s reason=missing_steps_data",
                mod_copy.get("module_number"),
            )
            return False
        if layout == "comparison" and not slide.get("comparison_data"):
            logger.info(
                "slide_validation_failed module=%s reason=missing_comparison_data",
                mod_copy.get("module_number"),
            )
            return False
        if layout == "grid" and not slide.get("grid_data"):
            logger.info(
                "slide_validation_failed module=%s reason=missing_grid_data",
                mod_copy.get("module_number"),
            )
            return False
        if layout == "grid" and len(slide.get("grid_data", {}).get("columns", [])) < 2:
            logger.info(
                "slide_validation_failed module=%s reason=one_card_grid",
                mod_copy.get("module_number"),
            )
            return False
    return True


def _apply_slide_fallbacks(best_module_state: dict) -> dict:
    logger.info(
        "slide_module_fallback_started module=%s",
        best_module_state.get("module_number"),
    )
    fixed_slides = []
    for slide in best_module_state.get("planned_slides", []):
        content = slide.get("content", [])
        layout = slide.get("layout_type", "")

        if not slide.get("slide_title"):
            slide["slide_title"] = slide.get("title", "Fallback Title")
            logger.info("slide_title_forced title=%s", slide["slide_title"])

        if len(content) == 0:
            logger.info("empty_slide_dropped title=%s", slide.get("title"))
            continue
        if layout == "steps" and not slide.get("steps_data"):
            slide["layout_type"] = "bullets"
            logger.info(
                "slide_layout_forced title=%s reason=missing_steps_data layout=bullets",
                slide.get("title"),
            )
        elif layout == "comparison" and not slide.get("comparison_data"):
            slide["layout_type"] = "bullets"
            logger.info(
                "slide_layout_forced title=%s reason=missing_comparison_data layout=bullets",
                slide.get("title"),
            )
        elif layout == "grid" and not slide.get("grid_data"):
            slide["layout_type"] = "bullets"
            logger.info(
                "slide_layout_forced title=%s reason=missing_grid_data layout=bullets",
                slide.get("title"),
            )
        fixed_slides.append(slide)

    best_module_state["planned_slides"] = fixed_slides
    return best_module_state


def _generate_slides_for_module(
    *,
    course: dict,
    module: dict,
    index: int,
    base_url: str,
    model_name: str,
) -> tuple[int, dict]:
    max_retries = 3
    best_module_state = copy.deepcopy(module)
    is_valid = False
    module_number = best_module_state.get("module_number", index + 1)
    started = time.perf_counter()
    log_event(course["course_id"], "slides", "module_started", module=module_number)

    for attempt in range(max_retries):
        mod_copy = copy.deepcopy(module)
        logger.info(
            "slide_module_processing_started module=%s attempt=%s/%s",
            mod_copy.get("module_number"),
            attempt + 1,
            max_retries,
        )
        mod_copy = plan_slides_for_module(
            mod_copy,
            base_url,
            model_name,
            course_id=course["course_id"],
        )
        mod_copy = assign_layouts_to_module(
            mod_copy,
            base_url,
            model_name,
            course_id=course["course_id"],
        )

        is_valid = _module_slides_are_valid(mod_copy)
        best_module_state = mod_copy
        if is_valid:
            logger.info("slide_planning_validation_completed module=%s", module_number)
            break
        if attempt < max_retries - 1:
            logger.info("slide_module_retry module=%s", module_number)

    if not is_valid:
        best_module_state = _apply_slide_fallbacks(best_module_state)

    ensure_module_cover_slide(course, best_module_state, index + 1, len(course.get("modules", [])))
    best_module_state = _expand_mapped_image_slides(best_module_state)
    log_event(
        course["course_id"],
        "slides",
        "module_completed",
        module=module_number,
        elapsed=f"{time.perf_counter() - started:.1f}s",
    )
    return index, best_module_state


def generate_slides_for_course(course_id: str) -> Dict[str, Any]:
    """
    Main entrypoint: loads the persisted course and segments modules into slide decks via the
    multi-step LLM approach, saves database, and returns course dict.
    """
    logger.info("course_slide_planning_started course_id=%s", course_id)

    course = load_course_for_generation(course_id)
    modules = course.get("modules", [])

    base_url, model_name = get_llm_endpoint("slides")
    results = run_parallel_stage_items(
        course_id=course_id,
        stage="slides",
        items=list(enumerate(modules)),
        worker_count=default_llm_workers(len(modules)),
        item_label=lambda item: {"module": item[1].get("module_number", item[0] + 1)},
        operation=lambda item: _generate_slides_for_module(
            course=course,
            module=item[1],
            index=item[0],
            base_url=base_url,
            model_name=model_name,
        ),
    )
    for index, module in results:
        modules[index] = module

    course["modules"] = modules

    save_generated_course(
        course_id,
        course,
        module_fields=("planned_slides", "slides"),
    )

    logger.info(
        "course_slide_planning_completed course_id=%s course_name=%s",
        course_id,
        course.get("course_name"),
    )
    return course
