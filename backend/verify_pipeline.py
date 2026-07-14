from core.database import get_all_courses, save_all_courses
import sys
import io
import os
import json
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure backend directory is in the python path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipelines.run_pipeline import (
    generate_course_outline,
    generate_scripts_for_course
)
from pipelines.quiz_generator import generate_quiz_for_course
from pipelines.video_generator import generate_video_for_module
from pipelines.config import DRAFT_COURSES_FILE

def get_latest_course_id():
    try:
        courses = get_all_courses('draft')
        if courses:
            return courses[-1].get("id")
    except Exception as e:
        print(f"Error reading courses.json: {e}")
    return None

def print_course_outline_summary(outline):
    print("\n==================================================")
    print("STAGE 1 SUMMARY: Course Outline (Blueprint)")
    print("==================================================")
    print(f"Course Name:        {outline.get('course_name')}")
    print(f"Course ID:          {outline.get('id')}")
    print(f"Description:        {outline.get('course_description')}")
    print(f"Objective:          {outline.get('course_objective')}")
    print(f"Difficulty:         {outline.get('course_difficulty')}")
    print(f"Target Audience:    {outline.get('target_audience')}")
    print(f"Source File:        {outline.get('source_file')}")
    
    modules = outline.get("modules", [])
    print(f"\nModules Extracted ({len(modules)}):")
    for m in modules:
        images = m.get("images", [])
        print(f"  * Module {m.get('module_number')}: '{m.get('title')}'")
        print(f"    - Lines: {m.get('start_line')} to {m.get('end_line')}")
        print(f"    - Extracted Images: {len(images)}")
        for img in images:
            print(f"      - [Image ID: {img.get('image_id')}] Caption: {img.get('caption')}")
            print(f"        Path: {img.get('file_path')}")
    print("==================================================\n")




def print_quiz_summary(course):
    print("\n==================================================")
    print("STAGE 4 SUMMARY: MCQ Quiz Generation")
    print("==================================================")
    print(f"Course Name: {course.get('course_name')}")
    print(f"Course ID:   {course.get('id')}")
    print(f"Difficulty:  {course.get('course_difficulty', 'Easy')}")
    
    modules = course.get("modules", [])
    for m in modules:
        quiz = m.get("quiz", {})
        questions = quiz.get("questions", []) if quiz else []
        print(f"\n* Module {m.get('module_number')}: '{m.get('title')}'")
        print(f"  - Quiz Questions Count (Set limit): {m.get('num_questions', 0)}")
        print(f"  - Questions Generated ({len(questions)}):")
        for q_idx, q in enumerate(questions):
            options_str = ", ".join([f"{opt.get('key')}: {opt.get('text')}" for opt in q.get("options", [])])
            print(f"    - Q{q_idx + 1}: {q.get('question_text')}")
            print(f"      Options:  {options_str}")
            print(f"      Correct:  {q.get('correct_option')}")
            print(f"      Explain:  {q.get('explanation')}")
    print("==================================================\n")

def run_step_1_blueprint(filename):
    print(f"\n--- STAGE 1: Generating Course Outline (Blueprint) for {filename} ---")
    outline = generate_course_outline(filename)
    print_course_outline_summary(outline)
    return outline.get("id")



def run_step_4_quiz(course_id):
    print(f"\n--- STAGE 4: Generating Quizzes for Course ID {course_id} ---")
    
    # Load the course to check and update num_questions if needed for testing
    courses = get_all_courses('draft')
        
    course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
    if course_idx is None:
        raise ValueError(f"Course ID '{course_id}' not found in courses.json.")
        
    course = courses[course_idx]
    
    # Enable test questions count if all modules have 0 questions set
    has_any_num_questions = False
    for m in course.get("modules", []):
        try:
            if int(m.get("num_questions", 0)) > 0:
                has_any_num_questions = True
                break
        except (ValueError, TypeError):
            pass
            
    if not has_any_num_questions:
        print("[INFO] No module has 'num_questions' set. Setting default 'num_questions' = 3 for testing/verification purposes.")
        for m in course.get("modules", []):
            m["num_questions"] = 3
        courses[course_idx] = course
        with open(DRAFT_COURSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(courses, f, indent=2, ensure_ascii=False)
            
    course = generate_quiz_for_course(course_id)
    print_quiz_summary(course)
    return course

def print_slides_summary(course, html_files):
    print("\n==================================================")
    print("STAGE 5 SUMMARY: HTML/CSS Slide Deck Generation")
    print("==================================================")
    print(f"Course Name: {course.get('course_name')}")
    print(f"Course ID:   {course.get('id')}")
    print(f"Generated Slide HTML files ({len(html_files)}):")
    for f_path in html_files:
        print(f"  * {f_path}")
    
    modules = course.get("modules", [])
    for m in modules:
        slides = m.get("slides", [])
        print(f"\n* Module {m.get('module_number')}: '{m.get('title')}'")
        print(f"  - Slides Planned: {len(slides)}")
        for s_idx, slide in enumerate(slides):
            print(f"    - Slide {s_idx + 1}: '{slide.get('slide_title')}' (Layout: {slide.get('layout_type')}, Images: {len(slide.get('image_ids', []))})")
    print("==================================================\n")

def run_step_5_slides(course_id):
    print(f"\n--- STAGE 5: Generating Slide Decks for Course ID {course_id} ---")
    from pipelines.slide_planner import generate_slides_for_course
    from pipelines.slides_generator import compile_slides_for_course
    
    course = generate_slides_for_course(course_id)
    html_files = compile_slides_for_course(course_id)
    print_slides_summary(course, html_files)
    return course

def run_step_6_scripts(course_id):
    print(f"\n--- STAGE 6: Generating Narration Scripts & Audio for Course ID {course_id} ---")
    from pipelines.slides_generator import compile_slides_for_course
    
    course = generate_scripts_for_course(course_id)
    compile_slides_for_course(course_id) # Re-compile to embed audio
    print(f"STAGE 6 SUMMARY: Scripts & TTS Audio synthesized for course {course_id}")
    return course

def run_step_7_video(course_id):
    print(f"\n--- STAGE 7: Compiling Final MP4 Videos for Course ID {course_id} ---")
    courses = get_all_courses('draft')
    course = next((c for c in courses if c.get("id") == course_id), None)
    if course:
        for m in course.get("modules", []):
            mod_num = m.get("module_number")
            print(f"  -> Rendering Video for Module {mod_num}...")
            generate_video_for_module(course_id, mod_num)
        print(f"STAGE 7 SUMMARY: Video generation complete for course {course_id}")
    return course

def main():
    parser = argparse.ArgumentParser(
        description="LMS Pipeline Verification & Interactive Step Runner Utility",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run the complete pipeline end-to-end (Stages 1 -> 2 -> 3 -> 4 -> 5) sequentially."
    )
    group.add_argument(
        "--step", "-s",
        type=str,
        choices=["1", "2", "4", "5", "blueprint", "lessons", "quiz", "slides"],
        help="Run an individual stage of the pipeline:\n"
             "  1, blueprint : Stage 1 (Blueprint Outline Slicing)\n"
             "  4, quiz      : Stage 4 (MCQ Quiz Generation)\n"
             "  5, slides    : Stage 5 (HTML Slide Deck Generation)"
    )
    
    parser.add_argument(
        "--file", "-f",
        type=str,
        default="AI_test_img.pdf",
        help="The PDF file to use for Stage 1. Default: 'AI_test_img.pdf'. Must reside in 'uploads/' directory."
    )
    parser.add_argument(
        "--course_id", "-c",
        type=str,
        help="The Course ID to use for Stages 2, 3, 4, or 5. If omitted, the latest course from 'courses.json' will be used."
    )
    
    args = parser.parse_args()
    
    if args.all:
        print("==================================================")
        print("RUNNING THE FULL LMS PIPELINE END-TO-END")
        print("==================================================")
        course_id = run_step_1_blueprint(args.file)
        run_step_4_quiz(course_id)
        run_step_5_slides(course_id)
        run_step_6_scripts(course_id)
        run_step_7_video(course_id)
        print("==================================================")
        print("FULL PIPELINE END-TO-END RUN COMPLETED SUCCESSFULLY!")
        print("==================================================")
    else:
        step = args.step.lower()
        if step in ["1", "blueprint"]:
            run_step_1_blueprint(args.file)
        else:
            course_id = args.course_id
            if not course_id:
                course_id = get_latest_course_id()
                if not course_id:
                    print("[ERROR] No course_id was provided and no existing courses were found in 'courses.json'.")
                    print("Please run Stage 1 first to create a course, or specify a valid '--course_id'.")
                    sys.exit(1)
                print(f"[INFO] Using latest course from courses.json: '{course_id}'")
            
            if step in ["4", "quiz"]:
                run_step_4_quiz(course_id)
            elif step in ["5", "slides"]:
                run_step_5_slides(course_id)

if __name__ == "__main__":
    main()

