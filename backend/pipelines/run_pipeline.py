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
from core.io_utils import atomic_write_json

def generate_course_outline(filename):
    print(f"Running pipeline step 2: Extracting blueprint for file {filename}...")
    pdf_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        
    try:
        courses = get_all_courses('draft')
    except Exception:
        courses = []
            
    course_id = f"course_{int(time.time())}_{len(courses)}"
    outline = run_blueprint_extraction(pdf_path, course_id=course_id)
    
    # Ensure the course name is unique
    base_name = outline.get("course_name", "Untitled Course")
    course_name = base_name
    counter = 1
    while any(c.get("course_name") == course_name for c in courses):
        course_name = f"{base_name} ({counter})"
        counter += 1
    
    outline["course_name"] = course_name
    outline["source_file"] = filename
    outline["id"] = course_id
    outline["created_at"] = time.time()
    
    courses.append(outline)
        
    save_all_courses(courses, "draft")
        
    print(f"Successfully generated and stored course outline for {filename}!")
    return outline



def generate_scripts_for_course(course_id: str) -> dict:
    """
    Sequentially generate narration scripts and speech audio for all modules in a course
    and save them to courses.json.
    """
    print(f"Generating narration scripts for course {course_id}...")

    courses = get_all_courses('draft')

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found in courses database.")

    course = courses[course_idx]
    modules = course.get("modules", [])

    if not modules:
        raise ValueError("This course has no modules. Generate the outline first.")

    previous_script = ""
    for i, module in enumerate(modules):
        module_text = module.get("text", "")
        module_number = i + 1
        try:
            updated_module = generate_scripts_for_module(
                module_text=module_text,
                module=module,
                previous_script=previous_script
            )
            modules[i] = updated_module

            # Synthesize speech per slide in module
            for s_idx, slide in enumerate(updated_module.get("slides", [])):
                script_text = slide.get("script", "").strip()
                if script_text:
                    audio_dir_rel = f"assets/audio/course_{course_id}/module_{module_number}"
                    audio_path_rel = f"{audio_dir_rel}/slide_{s_idx + 1}.wav"
                    audio_path_abs = os.path.join(BASE_DIR, audio_path_rel)
                    
                    # print(f"  [TTS] Skipping speech synthesis for testing...")
                    success = synthesize_speech_for_slide(script_text, audio_path_abs)
                    if success:
                        slide["audio_path"] = audio_path_rel
                    else:
                        slide["audio_path"] = ""
                else:
                    slide["audio_path"] = ""

            # Accumulate scripts of the current module for the next module's context
            current_scripts = []
            for slide in updated_module.get("slides", []):
                slide_script = slide.get("script", "")
                if slide_script:
                    current_scripts.append(slide_script)
            if current_scripts:
                previous_script = " ".join(current_scripts)
        except Exception as e:
            print(f"  [WARNING] Script generation/synthesis failed for module '{module.get('title', '')}': {e}")

    course["modules"] = modules
    
    # Reload courses to prevent overwrite races
    fresh_courses = get_all_courses('draft')
    fresh_idx = next((i for i, c in enumerate(fresh_courses) if c.get("id") == course_id), None)
    if fresh_idx is not None:
        fresh_courses[fresh_idx] = course
    else:
        fresh_courses.append(course)

    save_all_courses(fresh_courses, "draft")

    print(f"Script and TTS generation complete for course '{course.get('course_name')}'!")
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

