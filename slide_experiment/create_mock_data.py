import os
import sys
import json
import time

# Force stdout to utf-8 to prevent charmap print errors (e.g. PhillipX CRM \u2192 character)
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend imports work
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipelines.blueprint_extractor import run_blueprint_extraction
from pipelines.lesson_extractor import extract_lessons_for_module
from pipelines.bullet_refiner import refine_bullets_inplace
from pipelines.image_mapper import map_images_to_lessons
from pipelines.config import UPLOAD_DIR

def run_pipeline_to_step1(pdf_filename):
    pdf_path = os.path.join(UPLOAD_DIR, pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"Skipping {pdf_filename}, not found.")
        return None
        
    course_id = f"course_{int(time.time())}_{pdf_filename}"
    
    # Step 1: Blueprint
    print(f"\n--- Processing {pdf_filename} ---")
    try:
        course = run_blueprint_extraction(pdf_path, course_id=course_id)
    except Exception as e:
        print(f"Error in blueprint extraction for {pdf_filename}: {e}")
        return None
        
    course["course_name"] = course.get("course_name", "Untitled")
    course["source_file"] = pdf_filename
    course["id"] = course_id
    
    return course

def main():
    if not os.path.exists(UPLOAD_DIR):
        print(f"Upload dir {UPLOAD_DIR} not found.")
        return
        
    output_path = os.path.join(os.path.dirname(__file__), "mock_data.json")
    all_courses = []
    
    print(f"Running pipeline for ALL PDFs in {UPLOAD_DIR} (Blueprint only)...")
    
    for filename in os.listdir(UPLOAD_DIR):
        if filename.lower().endswith(".pdf"):
            course = run_pipeline_to_step1(filename)
            if course:
                all_courses.append(course)
            else:
                print(f"Failed to generate course for {filename}")
    
    if all_courses:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_courses, f, indent=2)
        print(f"\nSuccessfully generated fresh mock data for all PDFs in {output_path}")
    else:
        print("\nNo courses were generated.")

if __name__ == "__main__":
    main()
