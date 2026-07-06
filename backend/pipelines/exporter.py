from core.database import get_all_courses, save_all_courses
import os
import json
import uuid
from pipelines.config import DRAFT_COURSES_FILE, PUBLISHED_COURSES_FILE
from core.io_utils import atomic_write_json

def sync_clean_database():
    """
    Reads courses_draft.json, generates UUIDs for quiz questions if missing,
    saves the updated draft back to disk, maps to the standardized production format,
    and writes the results to courses.json.
    """
    try:
        draft_courses = get_all_courses('draft')
    except Exception as e:
        print(f"[EXPORTER][ERROR] Failed to load draft database: {e}")
        return

    clean_courses = []
    draft_modified = False

    for course in draft_courses:
        course_id = course.get("id", str(uuid.uuid4()))
        if "id" not in course:
            course["id"] = course_id
            draft_modified = True

        modules = course.get("modules", [])
        if not modules:
            continue
            
        is_fully_made = True
        for m in modules:
            if not m.get("video_path"):
                is_fully_made = False
                break
            quiz = m.get("quiz")
            if not quiz or not isinstance(quiz, dict) or not quiz.get("questions"):
                is_fully_made = False
                break
                
        if not is_fully_made:
            continue

        clean_modules = []
        for m in course.get("modules", []):
            clean_quiz = []
            draft_quiz = m.get("quiz", {})
            draft_questions = draft_quiz.get("questions", []) if isinstance(draft_quiz, dict) else []

            for q in draft_questions:
                # Retrieve or generate a persistent UUID for each question
                q_id = q.get("question_id")
                if not q_id:
                    q_id = str(uuid.uuid4())
                    q["question_id"] = q_id
                    draft_modified = True

                # Options in draft: [{"key": "A", "text": "Opt A"}, ...]
                # Options in clean: ["Opt A", "Opt B", "Opt C", "Opt D"]
                draft_opts = q.get("options", [])
                # Ensure options are sorted by key (A, B, C, D)
                sorted_opts = sorted(draft_opts, key=lambda o: str(o.get("key", "")).strip().upper())
                clean_opts = [o.get("text", "") for o in sorted_opts]

                clean_quiz.append({
                    "question_id": q_id,
                    "question": q.get("question_text", ""),
                    "options": clean_opts,
                    "correct": q.get("correct_option", "A"),
                    "explanation": q.get("explanation", "")
                })

            clean_modules.append({
                "module_number": m.get("module_number", 1),
                "title": m.get("title", ""),
                "video_url": m.get("video_path", "") or "",
                "quiz": clean_quiz,
                "pass_mark": 0.67
            })

        clean_courses.append({
            "course_id": course_id,
            "title": course.get("course_name", ""),
            "course_description": course.get("course_description", ""),
            "created_at": course.get("created_at", 0),
            "modules": clean_modules
        })

    # If we generated any new UUIDs for course ids or question ids, save them back to draft file
    if draft_modified:
        try:
            save_all_courses(draft_courses, "draft")
            print("[EXPORTER] Saved generated IDs back to courses_draft.json")
        except Exception as e:
            print(f"[EXPORTER][WARNING] Failed to write updated draft database: {e}")

    # Write the clean production-ready database to courses.json
    try:
        save_all_courses(clean_courses, "published")
        print(f"[EXPORTER] Successfully synchronized clean database to {PUBLISHED_COURSES_FILE}")
        
        # Automatically assign to employees and broadcast
        try:
            from pipelines.employee_routes import assign_published_courses_to_employees
            assign_published_courses_to_employees(clean_courses)
        except Exception as e:
            print(f"[EXPORTER][ERROR] Failed to assign courses to employees: {e}")
            
    except Exception as e:
        print(f"[EXPORTER][ERROR] Failed to write clean database: {e}")

if __name__ == "__main__":
    sync_clean_database()
