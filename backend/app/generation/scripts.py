"""Generate and persist slide narration scripts."""

import json
from typing import List

from app.core.logging import generation_logger
from app.core.providers import (
    get_llm_endpoint,
    safe_chat_completion,
)
from app.generation.prompts import SCRIPT_GENERATION_PROMPT
from app.generation.runtime import (
    ensure_module_cover_slide,
    load_course_for_generation,
    retry,
    save_generated_course,
)
from app.schemas.generation.narration import SlideScriptSchema, batch_script_schema

logger = generation_logger(__name__)

def _build_script_prompt(
    module_text: str,
    module: dict,
    previous_script: str = None,
    course_context: dict = None,
    slide_number_offset: int = 0,
    batch_number: int = 1,
    total_batches: int = 1,
) -> str:
    """Build a narration prompt for one ordered batch of a module's slides."""
    lines = []

    if previous_script:
        lines.extend(
            [
                "=== PRIOR NARRATION (FOR CONTINUITY) ===",
                previous_script,
                "==============================================================",
                "",
            ]
        )

    if course_context:
        lines.extend(
            [
                "=== COURSE AND MODULE CONTEXT ===",
                f"Course Name: {course_context.get('course_name', '')}",
                f"Module Number: {course_context.get('module_number', '')} of {course_context.get('total_modules', '')}",
                f"Current Module Title: {course_context.get('module_title', module.get('title', ''))}",
                f"Is First Module: {course_context.get('is_first_module', False)}",
                f"Is Final Module: {course_context.get('is_last_module', False)}",
                "Use this context to write the module cover narration and the final slide wrap-up.",
                "=================================",
                "",
            ]
        )

    lines.extend(
        [
            f"=== MODULE TITLE: {module.get('title', '')} ===",
            "",
            "=== SUPPORTING SOURCE TEXT ===",
            "Use this to enrich the slide narration. Do not narrate it directly or follow it ahead of the slide order.",
            module_text,
            "==============================",
            "",
            "=== SLIDE-BY-SLIDE PRESENTATION PLAN ===",
            "Follow this slide order exactly. Each script must sound like the presenter is discussing the slide while it is visible.",
        ]
    )

    if total_batches > 1:
        first_slide = slide_number_offset + 1
        last_slide = slide_number_offset + len(module.get("slides", []))
        lines.extend(
            [
                "",
                "=== BATCH INSTRUCTIONS ===",
                f"This is batch {batch_number} of {total_batches} for this module.",
                f"Generate only slides {first_slide} through {last_slide}.",
                f"Return exactly {len(module.get('slides', []))} scripts: one per listed slide, in that order.",
                "Never return scripts for any other slide in this module.",
                "Do not add a module wrap-up unless this is the final batch.",
                "==========================",
            ]
        )

    for index, slide in enumerate(module.get("slides", []), start=slide_number_offset + 1):
        layout = str(slide.get("layout_type", "bullets")).lower().split(".")[-1]
        if slide.get("is_cover_slide") or layout == "cover":
            lines.extend(
                [
                    f"    [SLIDE {index}] MODULE COVER",
                    f"      Course: {slide.get('course_name') or (course_context or {}).get('course_name', '')}",
                    f"      Module Title: {slide.get('slide_title') or slide.get('title') or module.get('title', '')}",
                    "      Purpose: Introduce this module before content begins. Do not teach detailed content on this cover slide.",
                ]
            )
        else:
            lines.extend(
                [
                    f"    [SLIDE {index}] CONTENT SLIDE",
                    json.dumps(slide, indent=6, ensure_ascii=True),
                ]
            )

    lines.append("")
    if total_batches > 1:
        lines.append(
            f"Output JSON with exactly {len(module.get('slides', []))} items in `slides`, matching only this batch."
        )
    else:
        lines.append(
            "Please output the ModuleScriptSchema JSON containing the spoken script for each slide in order."
        )
    return "\n".join(lines)

def generate_scripts_for_module(
    module_text: str,
    module: dict,
    previous_script: str = None,
    course_context: dict = None,
) -> dict:
    """Generate narration in batches of up to five slides, preserving continuity."""
    slides = module.get("slides", [])
    if not slides:
        raise ValueError(
            f"No slides found for module '{module.get('title')}'; narration script generation cannot continue."
        )

    logger.info(
        "script_generation_started module_title=%s slide_count=%s",
        module.get("title"),
        len(slides),
    )
    batch_size = 5
    slide_batches = [
        slides[index : index + batch_size] for index in range(0, len(slides), batch_size)
    ]
    generated_scripts: List[SlideScriptSchema] = []
    previous_batch_narration = previous_script

    for batch_index, batch_slides in enumerate(slide_batches):
        batch_number = batch_index + 1
        batch_module = dict(module)
        batch_module["slides"] = batch_slides
        batch_schema = batch_script_schema(len(batch_slides))
        batch_context = dict(course_context or {})
        if len(slide_batches) > 1:
            batch_context["is_first_module"] = (
                bool(batch_context.get("is_first_module")) and batch_index == 0
            )
            batch_context["is_last_module"] = (
                bool(batch_context.get("is_last_module")) and batch_index == len(slide_batches) - 1
            )

        logger.info(
            "script_batch_started batch=%s/%s slide_count=%s",
            batch_number,
            len(slide_batches),
            len(batch_slides),
        )

        def generate_once():
            base_url, model_name = get_llm_endpoint("scripts")
            response = safe_chat_completion(
                base_url=base_url,
                model=model_name,
                messages=[
                    {"role": "system", "content": str(SCRIPT_GENERATION_PROMPT)},
                    {
                        "role": "user",
                        "content": _build_script_prompt(
                            module_text,
                            batch_module,
                            previous_batch_narration,
                            batch_context,
                            slide_number_offset=batch_index * batch_size,
                            batch_number=batch_number,
                            total_batches=len(slide_batches),
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ModuleScriptSchema",
                        "schema": batch_schema.model_json_schema(),
                    },
                },
                temperature=0.2,
                # Five slide scripts fit comfortably beside this model's
                # source-text prompt within its 8,128-token context window.
                default_max_tokens=3072,
                course_id=str((course_context or {}).get("course_id") or "unknown"),
                stage="scripts",
                module_number=(course_context or {}).get("module_number"),
                attempts=1,
            )
            parsed = batch_schema.model_validate_json(response.choices[0].message.content)
            if len(parsed.slides) != len(batch_slides):
                raise ValueError(
                    f"Expected {len(batch_slides)} slide scripts in batch {batch_number}, "
                    f"received {len(parsed.slides)}"
                )
            if any(not item.script.strip() for item in parsed.slides):
                raise ValueError(f"LLM returned an empty slide script in batch {batch_number}")
            return parsed

        parsed = retry(
            generate_once,
            course_id=str((course_context or {}).get("course_id") or "unknown"),
            stage="scripts",
            attempts=3,
            module_number=(course_context or {}).get("module_number"),
        )

        generated_scripts.extend(parsed.slides)
        previous_batch_narration = "\n\n".join(
            f"[SLIDE {batch_index * batch_size + offset + 1}] {item.script.strip()}"
            for offset, item in enumerate(parsed.slides)
        )

    if len(generated_scripts) != len(slides):
        raise ValueError(f"Expected {len(slides)} slide scripts, received {len(generated_scripts)}")

    logger.info("script_generation_llm_completed slide_count=%s", len(generated_scripts))
    for index, slide in enumerate(slides):
        slide["script"] = generated_scripts[index].script.strip()
    return module

def generate_scripts_for_course(course_id: str) -> dict:
    """
    Sequentially generate narration scripts and speech audio for all modules in a course
    and persist them through the course repository.
    """
    logger.info("course_scripts_generation_started course_id=%s", course_id)

    course = load_course_for_generation(course_id)
    modules = course.get("modules", [])

    if not modules:
        raise ValueError("This course has no modules. Generate the outline first.")

    previous_script = ""
    for i, module in enumerate(modules):
        module_text = module.get("source_text", "")
        module_number = i + 1
        ensure_module_cover_slide(course, module, module_number, len(modules))
        course_context = {
            "course_name": course.get("course_name", ""),
            "module_number": module_number,
            "total_modules": len(modules),
            "module_title": module.get("title", ""),
            "is_first_module": module_number == 1,
            "is_last_module": module_number == len(modules),
            "previous_module_title": modules[i - 1].get("title", "") if i > 0 else "",
            "next_module_title": modules[i + 1].get("title", "") if i + 1 < len(modules) else "",
        }
        course_context["course_id"] = course_id
        updated_module = generate_scripts_for_module(
            module_text=module_text,
            module=module,
            previous_script=previous_script,
            course_context=course_context,
        )
        modules[i] = updated_module

        current_scripts = [
            slide.get("script", "")
            for slide in updated_module.get("slides", [])
            if slide.get("script")
        ]
        previous_script = " ".join(current_scripts)

    course["modules"] = modules

    save_generated_course(course_id, course, module_fields=("slides",))

    logger.info(
        "course_scripts_generation_completed course_id=%s course_name=%s",
        course_id,
        course.get("course_name"),
    )
    return course
