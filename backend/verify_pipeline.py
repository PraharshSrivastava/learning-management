import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pipelines.run_pipeline import generate_course_outline, generate_lessons_for_course
from pipelines.slide_generator import generate_all_slides_for_course

def main():
    filename = "AI_test_img.pdf"
    print(f"--- STARTING VERIFICATION FOR {filename} ---")
    
    # 1. Generate Course Outline (Blueprint)
    outline = generate_course_outline(filename)
    course_id = outline["id"]
    print(f"\nCourse ID: {course_id}")
    
    # Check if images are extracted and assigned to modules
    print("\n--- STAGE 1: Blueprint Module Slicing ---")
    modules = outline.get("modules", [])
    for m in modules:
        images = m.get("images", [])
        print(f"Module '{m.get('title')}' (start_line={m.get('start_line')}) has {len(images)} images.")
        for img in images:
            print(f"  - Image ID: {img.get('image_id')}, Caption: \"{img.get('caption')}\", Path: {img.get('file_path')}")
            
    # 2. Generate Lessons & Bullet Refinement & Image-to-Slide Mapping
    print("\n--- STAGE 2: Lesson Extraction & Image Mapping ---")
    course = generate_lessons_for_course(course_id)
    
    # Check if images are assigned to slides
    for m_idx, m in enumerate(course.get("modules", [])):
        print(f"\nModule '{m.get('title')}':")
        for l_idx, lesson in enumerate(m.get("lessons", [])):
            print(f"  Lesson '{lesson.get('lesson_title')}':")
            # Images assigned at lesson level (original assignments before mapping)
            lesson_imgs = lesson.get("images", [])
            print(f"    - Original Lesson images ({len(lesson_imgs)}): {[img.get('image_id') for img in lesson_imgs]}")
            
            for s_idx, slide in enumerate(lesson.get("slides", [])):
                slide_imgs = slide.get("images", [])
                print(f"    - Slide {slide.get('slide_number')}: '{slide.get('slide_title')}' has {len(slide_imgs)} images.")
                for img in slide_imgs:
                    print(f"        * Image ID: {img.get('image_id')}, Path: {img.get('file_path')}")
                    
    # 3. Generate PowerPoint slides
    print("\n--- STAGE 3: PPTX Generation ---")
    manifest = generate_all_slides_for_course(course_id)
    print("\nGenerated Slides Manifest:")
    print(json.dumps(manifest, indent=2))
    
    print("\n--- VERIFICATION COMPLETED ---")

if __name__ == "__main__":
    main()
