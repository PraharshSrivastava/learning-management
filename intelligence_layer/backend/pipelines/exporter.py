import os
import json
import uuid
from pipelines.config import COURSES_FILE, CLEAN_COURSES_FILE

def sync_clean_database():
    """
    Reads courses_draft.json, generates UUIDs for quiz questions if missing,
    saves the updated draft back to disk, maps to the standardized production format,
    and writes the results to courses.json.
    """
    if not os.path.exists(COURSES_FILE):
        # If no draft database exists yet, write empty list to clean database
        with open(CLEAN_COURSES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        return

    try:
        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            draft_courses = json.load(f)
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
            "modules": clean_modules
        })

    # If we generated any new UUIDs for course ids or question ids, save them back to draft file
    if draft_modified:
        try:
            with open(COURSES_FILE, 'w', encoding='utf-8') as f:
                json.dump(draft_courses, f, indent=2, ensure_ascii=False)
            print("[EXPORTER] Saved generated IDs back to courses_draft.json")
        except Exception as e:
            print(f"[EXPORTER][WARNING] Failed to write updated draft database: {e}")

    # Write the clean production-ready database to courses.json
    try:
        with open(CLEAN_COURSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(clean_courses, f, indent=2, ensure_ascii=False)
        print(f"[EXPORTER] Successfully synchronized clean database to {CLEAN_COURSES_FILE}")
    except Exception as e:
        print(f"[EXPORTER][ERROR] Failed to write clean database: {e}")

if __name__ == "__main__":
    sync_clean_database()
