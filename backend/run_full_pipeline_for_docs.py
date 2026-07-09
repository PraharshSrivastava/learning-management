from core.database import get_all_courses, save_all_courses
import os
import sys
import json
import traceback

# Ensure backend directory is in the python path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipelines.run_pipeline import (
    generate_course_outline,
    generate_lessons_for_course,
    generate_scripts_for_course
)
from pipelines.quiz_generator import generate_quiz_for_course
from pipelines.slide_planner import generate_slides_for_course
from pipelines.slides_generator import compile_slides_for_course
from pipelines.video_generator import generate_video_for_module
from pipelines.config import DRAFT_COURSES_FILE, get_llm_endpoint
from pipelines.exporter import sync_clean_database
from pipelines.image_generator import enrich_sparse_slides_with_flux

def run_pipeline_for_file(filename):
    print("\n" + "="*80)
    print(f"STARTING FULL END-TO-END PIPELINE FOR: {filename}")
    print("="*80)
    
    # Step 1: Outline / Blueprint Extraction
    try:
        url, model = get_llm_endpoint()
        print(f"[STEP 1][MODEL CHECK] Blueprint extraction will run using: {model} at {url}")
        outline = generate_course_outline(filename)
        course_id = outline.get("id")
        print(f"[SUCCESS] Step 1: Course blueprint generated. Course ID: {course_id}")
    except Exception as e:
        print(f"[ERROR] Step 1 failed: {e}")
        traceback.print_exc()
        return False
        
    # Step 1.5: Set num_questions = 3 for all modules so quiz generation executes
    try:
        courses = get_all_courses('draft')
        course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
        if course_idx is not None:
            course = courses[course_idx]
            for m in course.get("modules", []):
                m["num_questions"] = 3
            courses[course_idx] = course
            with open(DRAFT_COURSES_FILE, 'w', encoding='utf-8') as f:
                json.dump(courses, f, indent=2, ensure_ascii=False)
            print("[INFO] Set num_questions = 3 for all modules.")
        else:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")
    except Exception as e:
        print(f"[ERROR] Setting num_questions failed: {e}")
        traceback.print_exc()
        return False

    # Step 2: Lesson Generation & Bullet Refinement & Image Mapping
    try:
        url, model = get_llm_endpoint()
        print(f"[STEP 2][MODEL CHECK] Lesson extraction will run using: {model} at {url}")
        generate_lessons_for_course(course_id)
        print("[SUCCESS] Step 2: Lessons generated and image-mapped.")
    except Exception as e:
        print(f"[ERROR] Step 2 failed: {e}")
        traceback.print_exc()
        return False

    # Step 3: MCQ Quiz Generation
    try:
        url, model = get_llm_endpoint()
        print(f"[STEP 3][MODEL CHECK] Quiz generation will run using: {model} at {url}")
        generate_quiz_for_course(course_id)
        print("[SUCCESS] Step 3: Quizzes generated.")
    except Exception as e:
        print(f"[ERROR] Step 3 failed: {e}")
        traceback.print_exc()
        return False

    # Step 4: Slides Planning & Compilation
    try:
        url, model = get_llm_endpoint("slides")
        print(f"[STEP 4][MODEL CHECK] Slide planning will run using: {model} at {url}")
        generate_slides_for_course(course_id)
        enrich_sparse_slides_with_flux(course_id)
        compile_slides_for_course(course_id)
        print("[SUCCESS] Step 4: Slides planned, enriched, and compiled.")
    except Exception as e:
        print(f"[ERROR] Step 4 failed: {e}")
        traceback.print_exc()
        return False

    # Step 5: Scripts Generation & Text-to-Speech Narration Synthesis
    try:
        url, model = get_llm_endpoint("scripts")
        print(f"[STEP 5][MODEL CHECK] Script generation will run using: {model} at {url}")
        generate_scripts_for_course(course_id)
        compile_slides_for_course(course_id) # Re-compile slides to sync narrations
        print("[SUCCESS] Step 5: Narration script and TTS synthesized.")
    except Exception as e:
        print(f"[ERROR] Step 5 failed: {e}")
        traceback.print_exc()
        return False

    # Step 6: Slide-to-Video compilation (FFmpeg) per module
    try:
        courses = get_all_courses('draft')
        course = next((c for c in courses if c.get("id") == course_id), None)
        if course:
            modules = course.get("modules", [])
            print(f"[INFO] Compiling videos for {len(modules)} modules...")
            for m in modules:
                mod_num = m.get("module_number")
                print(f"  [Video] Compiling module {mod_num} video...")
                generate_video_for_module(course_id, mod_num)
            print("[SUCCESS] Step 6: All module videos generated.")
        else:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")
    except Exception as e:
        print(f"[ERROR] Step 6 failed: {e}")
        traceback.print_exc()
        return False

    # Sync clean database
    try:
        sync_clean_database()
        print("[SUCCESS] Step 7: Clean database synchronized to courses.json.")
    except Exception as e:
        print(f"[ERROR] Clean database synchronization failed: {e}")
        traceback.print_exc()
        return False

    print("="*80)
    print(f"COMPLETED PIPELINE SUCCESSFULLY FOR: {filename}")
    print("="*80 + "\n")
    return True

if __name__ == "__main__":
    docs = [
        "Test_Doc_2.pdf",
        "CRM_structured.pdf",
        "EKYC_semistructured.pdf",
        "Sales_semistructured.pdf"
    ]
    
    success_count = 0
    for doc in docs:
        if run_pipeline_for_file(doc):
            success_count += 1
            
    print(f"\nPipeline execution finished: {success_count}/{len(docs)} files processed successfully.")
