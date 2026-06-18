import os
import sys
import argparse
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from pipelines.blueprint_extractor import run_blueprint_extraction
from pipelines.lesson_extractor import extract_slides_for_module
from pipelines.bullet_refiner import refine_bullets_inplace
from pipelines.script_generator import generate_scripts_for_module
from pipelines.config import UPLOAD_DIR, COURSES_FILE

def generate_course_outline(filename):
    print(f"Running pipeline step 2: Extracting blueprint for file {filename}...")
    pdf_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        
    courses = []
    if os.path.exists(COURSES_FILE):
        try:
            with open(COURSES_FILE, 'r', encoding='utf-8') as f:
                courses = json.load(f)
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
        
    with open(COURSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully generated and stored course outline for {filename}!")
    return outline


def generate_lessons_for_course(course_id: str) -> dict:
    """
    Pipeline Step 3: For each module in the course, call the LLM once to produce
    Slides → Bullet Points directly. Runs sequentially so that each module call
    can be seeded with slide titles from all previously processed modules.
    """
    print(f"Running pipeline step 3: Generating slides for course {course_id}...")

    if not os.path.exists(COURSES_FILE):
        raise FileNotFoundError("Courses database not found.")

    with open(COURSES_FILE, 'r', encoding='utf-8') as f:
        courses = json.load(f)

    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course '{course_id}' not found in courses database.")

    course = courses[course_idx]
    modules = course.get("modules", [])

    if not modules:
        raise ValueError("This course has no modules. Generate the blueprint first.")

    total_modules = len(modules)
    prior_slide_titles: list[str] = []  # accumulated across modules for style anchoring

    for i, module in enumerate(modules):
        module_title = module.get("title", f"Module {i + 1}")
        module_text = module.get("text", "")
        module_number = i + 1

        try:
            slides = extract_slides_for_module(
                module_text=module_text,
                module_title=module_title,
                module_number=module_number,
                total_modules=total_modules,
                prior_slide_titles=prior_slide_titles,
                module_images=module.get("images", []),
            )
            module["slides"] = slides

            # Collect all slide titles from this module for the next module's anchor
            for slide in slides:
                title = slide.get("slide_title", "")
                if title:
                    prior_slide_titles.append(title)

        except Exception as e:
            print(f"  [ERROR] Failed to generate slides for module '{module_title}': {e}")
            # Leave existing slides intact (or empty list) rather than crashing the whole job
            if "slides" not in module:
                module["slides"] = []

    course["modules"] = modules

    # Step 4: Holistic bullet refinement — one LLM call for the entire course
    print("Running holistic bullet refinement pass...")
    try:
        course = refine_bullets_inplace(course)
    except Exception as e:
        print(f"  [WARNING] Bullet refinement failed ({e}). Saving with original bullets.")

    # Step 4.5: Map images to slides
    try:
        from pipelines.image_mapper import map_images_to_slides
        course = map_images_to_slides(course)
    except Exception as e:
        print(f"  [WARNING] Image mapping to slides failed: {e}")

    courses[course_idx] = course

    with open(COURSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)

    print(f"Slide generation complete for course '{course.get('course_name')}'.")
    return course


def generate_scripts_for_course(course_id: str) -> dict:
    """
    Sequentially generate narration scripts for all modules in a course
    and save them to courses.json.
    """
    print(f"Generating narration scripts for course {course_id}...")

    if not os.path.exists(COURSES_FILE):
        raise FileNotFoundError("Courses database not found.")

    with open(COURSES_FILE, 'r', encoding='utf-8') as f:
        courses = json.load(f)

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
        try:
            updated_module = generate_scripts_for_module(
                module_text=module_text,
                module=module,
                previous_script=previous_script
            )
            modules[i] = updated_module

            # Accumulate scripts of the current module for the next module's context
            current_scripts = []
            for slide in updated_module.get("slides", []):
                slide_script = slide.get("script", "")
                if slide_script:
                    current_scripts.append(slide_script)
            if current_scripts:
                previous_script = " ".join(current_scripts)
        except Exception as e:
            print(f"  [WARNING] Script generation failed for module '{module.get('title', '')}': {e}")

    course["modules"] = modules
    courses[course_idx] = course

    with open(COURSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)

    print(f"Script generation complete for course '{course.get('course_name')}'!")
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
