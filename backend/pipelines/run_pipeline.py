from core.database import get_all_courses, save_all_courses
import os
import sys
import argparse
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from pipelines.blueprint_extractor import run_blueprint_extraction
from pipelines.config import UPLOAD_DIR, DRAFT_COURSES_FILE, BASE_DIR
from pipelines.script_generator import generate_scripts_for_module, synthesize_speech_for_slide
from pipelines.summary_generator import generate_summary_for_module
from core.io_utils import atomic_write_json
from pipelines.pipeline_runtime import complete_generation, log_event, mark_stage

def _ensure_module_cover_slide(course: dict, module: dict, module_number: int, total_modules: int) -> None:
    slides = module.setdefault("slides", [])
    cover_title = module.get("title", f"Module {module_number}")
    cover_slide = {
        "slide_title": cover_title,
        "title": cover_title,
        "layout_type": "cover",
        "is_cover_slide": True,
        "course_name": course.get("course_name", ""),
        "module_number": module_number,
        "total_modules": total_modules,
        "bullets": [],
        "bullets_data": [],
        "image_ids": [],
    }

    if slides and (slides[0].get("is_cover_slide") or str(slides[0].get("layout_type", "")).lower() == "cover"):
        existing_script = slides[0].get("script")
        existing_audio = slides[0].get("audio_path")
        slides[0].update(cover_slide)
        if existing_script:
            slides[0]["script"] = existing_script
        if existing_audio:
            slides[0]["audio_path"] = existing_audio
        return

    slides.insert(0, cover_slide)

def generate_course_outline(filename, course_id: str | None = None):
    print(f"Running pipeline step 2: Extracting blueprint for file {filename}...")
    pdf_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        
    blueprint_start = time.perf_counter()
    try:
        courses = get_all_courses('draft')
    except Exception:
        courses = []
            
    course_id = course_id or f"course_{int(time.time())}_{len(courses)}"
    existing_index = next((i for i, course in enumerate(courses) if course.get("id") == course_id), None)
    checkpoint_course = courses[existing_index] if existing_index is not None else {
        "id": course_id,
        "course_name": f"Blueprint generation: {filename}",
        "course_description": "",
        "course_objective": "",
        "course_difficulty": "",
        "language": "",
        "target_audience": "",
        "source_file": filename,
        "created_at": time.time(),
        "images": [],
        "modules": [],
    }
    mark_stage(checkpoint_course, "blueprint", "running")
    if existing_index is None:
        courses.append(checkpoint_course)
    else:
        courses[existing_index] = checkpoint_course
    save_all_courses(courses, "draft")
    log_event(course_id, "blueprint", "start", source_file=filename)

    try:
        outline = run_blueprint_extraction(pdf_path, course_id=course_id)
    except Exception as exc:
        fresh_courses = get_all_courses("draft")
        idx = next((i for i, item in enumerate(fresh_courses) if item.get("id") == course_id), None)
        if idx is not None:
            mark_stage(fresh_courses[idx], "blueprint", "failed", error=str(exc))
            save_all_courses(fresh_courses, "draft")
        log_event(course_id, "blueprint", "failed", reason=str(exc))
        raise
    
    # Ensure the course name is unique
    base_name = outline.get("course_name", "Untitled Course")
    course_name = base_name
    counter = 1
    while any(c.get("id") != course_id and c.get("course_name") == course_name for c in courses):
        course_name = f"{base_name} ({counter})"
        counter += 1
    
    outline["course_name"] = course_name
    outline["source_file"] = filename
    outline["id"] = course_id
    outline["created_at"] = time.time()
    mark_stage(outline, "blueprint", "completed")
    complete_generation(outline, time.perf_counter() - blueprint_start)
    
    courses = [course for course in courses if course.get("id") != course_id]
    courses.append(outline)
        
    save_all_courses(courses, "draft")
        
    print(f"Successfully generated and stored course outline for {filename}!")
    return outline



def _load_course_for_generation(course_id: str) -> tuple[list, int, dict]:
    courses = get_all_courses('draft')
    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found in courses database.")
    return courses, course_idx, courses[course_idx]


def _save_generated_course(course_id: str, course: dict) -> None:
    fresh_courses = get_all_courses('draft')
    fresh_idx = next((i for i, c in enumerate(fresh_courses) if c.get("id") == course_id), None)
    if fresh_idx is None:
        fresh_courses.append(course)
    else:
        fresh_courses[fresh_idx] = course
    save_all_courses(fresh_courses, 'draft')


def generate_scripts_for_course(course_id: str) -> dict:
    """
    Sequentially generate narration scripts and speech audio for all modules in a course
    and save them to courses.json.
    """
    print(f"Generating narration scripts for course {course_id}...")

    _, _, course = _load_course_for_generation(course_id)
    modules = course.get("modules", [])

    if not modules:
        raise ValueError("This course has no modules. Generate the outline first.")

    previous_script = ""
    for i, module in enumerate(modules):
        module_text = module.get("text", "")
        module_number = i + 1
        _ensure_module_cover_slide(course, module, module_number, len(modules))
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
            module_text=module_text, module=module, previous_script=previous_script, course_context=course_context,
        )
        modules[i] = updated_module

        current_scripts = [slide.get("script", "") for slide in updated_module.get("slides", []) if slide.get("script")]
        previous_script = " ".join(current_scripts)

    course["modules"] = modules
    
    _save_generated_course(course_id, course)

    print(f"Script and TTS generation complete for course '{course.get('course_name')}'!")
    return course


def generate_notes_for_course(course_id: str) -> dict:
    _, _, course = _load_course_for_generation(course_id)
    for module in course.get("modules", []):
        module["notes"] = generate_summary_for_module(module, course_id=course_id)
    _save_generated_course(course_id, course)
    return course


def generate_tts_for_course(course_id: str) -> dict:
    from pipelines.pipeline_runtime import retry
    from pipelines.video_generator import get_audio_duration

    _, _, course = _load_course_for_generation(course_id)
    for module in course.get("modules", []):
        module_number = int(module.get("module_number", 0))
        for s_idx, slide in enumerate(module.get("slides", []), start=1):
            script_text = str(slide.get("script") or "").strip()
            if not script_text:
                raise ValueError(f"Module {module_number} slide {s_idx} has no narration script")
            audio_rel = f"assets/audio/course_{course_id}/module_{module_number}/slide_{s_idx}.wav"
            audio_abs = os.path.join(BASE_DIR, audio_rel)
            if (
                str(slide.get("audio_path") or "") == audio_rel
                and os.path.isfile(audio_abs)
                and os.path.getsize(audio_abs) > 0
                and get_audio_duration(audio_abs) > 0
            ):
                log_event(course_id, "tts", "skipped_valid_audio", module=module_number, slide=s_idx)
                continue

            def synthesize_once():
                if not synthesize_speech_for_slide(script_text, audio_abs):
                    raise RuntimeError("TTS endpoint did not produce audio")
                if not os.path.exists(audio_abs) or os.path.getsize(audio_abs) == 0 or get_audio_duration(audio_abs) <= 0:
                    raise RuntimeError("Generated audio file failed validation")
                return True

            retry(synthesize_once, course_id=course_id, stage="tts", attempts=2, module_number=module_number, slide_number=s_idx)
            slide["audio_path"] = audio_rel
    _save_generated_course(course_id, course)
    return course


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LMS Pipeline Runner")
    parser.add_argument("--file", type=str, required=True, help="Filename of the PDF to extract")
    args = parser.parse_args()
    
    try:
        generate_course_outline(args.file)
    except Exception as e:
        print(f"Error executing pipeline: {e}")
        sys.exit(1)
