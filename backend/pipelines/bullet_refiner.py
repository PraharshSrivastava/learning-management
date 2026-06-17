import json
import requests
from typing import List
from pydantic import BaseModel

from pipelines.config import get_llm_client, safe_chat_completion
from pipelines.prompts import BULLET_REFINEMENT_PROMPT


# -------------------------------------------------------
# Pydantic Response Schema
# Positional lists — order matches input exactly
# Slides can now have MORE bullets than input (splits allowed)
# -------------------------------------------------------

class RefinedBullet(BaseModel):
    text: str


class RefinedSlide(BaseModel):
    bullets: List[RefinedBullet]


class RefinedLesson(BaseModel):
    slides: List[RefinedSlide]


class RefinedModule(BaseModel):
    lessons: List[RefinedLesson]


class RefinedCourse(BaseModel):
    modules: List[RefinedModule]


# -------------------------------------------------------
# Prompt Builder — EDIT-ONLY MODE
# No raw text. Only the existing skeleton + bullets.
# -------------------------------------------------------

def _build_edit_prompt(course: dict) -> str:
    """
    Builds the user message containing the full course skeleton
    WITH existing bullets. The refiner will rephrase/split bullets
    for style consistency. No raw source text is included.
    """
    modules = course.get("modules", [])
    course_name = course.get("course_name", "Untitled Course")

    lines: List[str] = []
    lines.append(f"COURSE: {course_name}")
    lines.append("")
    lines.append("Below is the complete course with all bullets already assigned.")
    lines.append("Rewrite every bullet for style consistency. You may split long bullets.")
    lines.append("Do NOT change meaning, move bullets, or add new topics.")
    lines.append("")

    for mi, module in enumerate(modules):
        lines.append(f"[MODULE {mi}] {module.get('title', '')}")
        for li, lesson in enumerate(module.get("lessons", [])):
            lines.append(f"  [LESSON {li}] {lesson.get('lesson_title', '')}")
            for si, slide in enumerate(lesson.get("slides", [])):
                lines.append(f"    [SLIDE {si}] {slide.get('slide_title', '')}")
                for bi, bullet in enumerate(slide.get("bullets", [])):
                    bullet_text = bullet.get("text", "")
                    lines.append(f"      • {bullet_text}")
        lines.append("")

    lines.append("Return the RefinedCourse JSON with style-edited bullets for every slide.")

    return "\n".join(lines)


# -------------------------------------------------------
# Core function — takes a course dict, returns updated dict
# Called directly from generate_lessons_for_course()
# -------------------------------------------------------

def refine_bullets_inplace(course: dict) -> dict:
    """
    Edit-only holistic pass:
    - Receives the full course WITH existing bullets
    - Rephrases for consistent voice, length, and style
    - Can split long bullets into two
    - CANNOT change meaning, move bullets, or add new topics
    - Falls back gracefully if LLM fails
    """
    modules = course.get("modules", [])

    if not modules or not any(m.get("lessons") for m in modules):
        print("  [REFINE] No lessons found — skipping bullet refinement.")
        return course

    total_bullets = sum(
        len(slide.get("bullets", []))
        for m in modules
        for lesson in m.get("lessons", [])
        for slide in lesson.get("slides", [])
    )
    print(f"  [REFINE] Starting style edit pass: {len(modules)} modules, {total_bullets} input bullets.")

    json_schema = RefinedCourse.model_json_schema()
    user_message = _build_edit_prompt(course)
    print(f"  [REFINE] Prompt length: {len(user_message):,} chars")

    try:
        print("  [REFINE] Calling LLM for style editing...")
        client, model_name = get_llm_client()
        response = safe_chat_completion(
            client=client,
            model=model_name,
            messages=[
                {"role": "system", "content": BULLET_REFINEMENT_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "RefinedCourse",
                    "schema": json_schema,
                },
            },
            temperature=0.15,
            default_max_tokens=4096,
        )
        raw_content = response.choices[0].message.content

        refined = RefinedCourse.model_validate_json(raw_content)
        print(f"  [REFINE] LLM returned {len(refined.modules)} modules.")

    except Exception as e:
        print(f"  [REFINE][ERROR] LLM call or parse failed: {e}. Keeping original bullets.")
        return course

    # --- Positional merge ---
    bullets_written = 0
    for mi, module in enumerate(modules):
        if mi >= len(refined.modules):
            print(f"  [REFINE][WARNING] No refined data for module index {mi}. Keeping original.")
            continue

        ref_mod = refined.modules[mi]

        for li, lesson in enumerate(module.get("lessons", [])):
            if li >= len(ref_mod.lessons):
                print(f"  [REFINE][WARNING] No refined data for module {mi} lesson {li}. Keeping original.")
                continue

            ref_les = ref_mod.lessons[li]

            for si, slide in enumerate(lesson.get("slides", [])):
                if si >= len(ref_les.slides):
                    print(f"  [REFINE][WARNING] No refined data for mod {mi} les {li} slide {si}. Keeping original.")
                    continue

                ref_slide = ref_les.slides[si]
                clean_bullets = [
                    {"text": b.text.strip()}
                    for b in ref_slide.bullets
                    if b.text.strip()
                ]

                original_count = len(slide.get("bullets", []))

                if not clean_bullets:
                    print(f"  [REFINE][WARNING] Empty bullets for mod {mi} les {li} slide {si}. Keeping original.")
                    continue

                # Safety: if refiner returned way fewer bullets than original, keep original
                # (the refiner might have hallucinated and dropped content)
                if len(clean_bullets) < original_count * 0.5:
                    print(f"  [REFINE][WARNING] Refiner dropped too many bullets for mod {mi} les {li} slide {si} "
                          f"({original_count} → {len(clean_bullets)}). Keeping original.")
                    continue

                slide["bullets"] = clean_bullets
                bullets_written += len(clean_bullets)

    print(f"  [REFINE] Done. {bullets_written} bullets written (input had {total_bullets}).")
    return course


# -------------------------------------------------------
# Standalone entry point (for the API endpoint)
# -------------------------------------------------------

def refine_bullets_for_course(course_id: str) -> dict:
    from pipelines.config import COURSES_FILE

    with open(COURSES_FILE, "r", encoding="utf-8") as f:
        courses = json.load(f)

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found.")

    course = courses[course_idx]
    course = refine_bullets_inplace(course)

    courses[course_idx] = course
    with open(COURSES_FILE, "w", encoding="utf-8") as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)

    return course
