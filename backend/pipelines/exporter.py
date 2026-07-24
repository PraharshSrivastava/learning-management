import uuid
import time
import os

from core.config import BASE_DIR, DB_PATH
from core.database import get_all_courses, save_all_courses
from pipelines.thumbnail_generator import course_thumbnail_signature


def is_course_generation_complete(course: dict) -> bool:
    modules = course.get("modules", [])
    if not modules:
        return False

    thumbnail_path = course.get("thumbnail") or course.get("thumbnail_url")
    if not thumbnail_path:
        return False
    if course.get("thumbnail_prompt_hash") != course_thumbnail_signature(course):
        return False

    for module in modules:
        slides = module.get("slides", []) or []
        if not slides or not str(module.get("notes") or "").strip():
            return False
        for slide in slides:
            audio_path = str(slide.get("audio_path") or "").strip()
            if (
                not str(slide.get("script") or "").strip()
                or not audio_path
                or not os.path.isfile(os.path.join(BASE_DIR, audio_path))
                or os.path.getsize(os.path.join(BASE_DIR, audio_path)) == 0
            ):
                return False
        video_path = str(module.get("video_path") or "").strip()
        if not video_path or not os.path.isfile(os.path.join(BASE_DIR, video_path)) or os.path.getsize(os.path.join(BASE_DIR, video_path)) == 0:
            return False
        try:
            num_questions = int(module.get("num_questions", 0))
        except (TypeError, ValueError):
            num_questions = 0
        if num_questions <= 0:
            continue
        quiz = module.get("quiz")
        if not quiz or not isinstance(quiz, dict) or not quiz.get("questions"):
            return False

    return True


def sync_clean_database():
    """
    Convert already-complete draft courses into the employee-facing published shape.

    This function intentionally does not run generation work. The full pipeline is
    responsible for creating quizzes, videos, and thumbnails before this exporter runs.
    """
    start = time.perf_counter()
    print(f"[EXPORTER] Starting SQLite publish sync: db={DB_PATH}")

    try:
        draft_courses = get_all_courses('draft')
    except Exception as e:
        print(f"[EXPORTER][ERROR] Failed to load draft database: {e}")
        return

    clean_courses = []
    draft_modified = False

    skipped_courses = []

    for course in draft_courses:
        course_id = course.get("id", str(uuid.uuid4()))
        if "id" not in course:
            course["id"] = course_id
            draft_modified = True

        if not is_course_generation_complete(course):
            skipped_courses.append(course_id)
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
                "notes": m.get("notes", "") or "",
                "video_url": m.get("video_path", "") or "",
                "quiz": clean_quiz,
                "pass_mark": 0.67
            })

        first_slide = None
        for m_draft in course.get("modules", []):
            for l_draft in m_draft.get("lessons", []):
                for img in l_draft.get("images", []):
                    first_slide = img
                    break
                if first_slide: break
            if first_slide: break
        
        course_images = [first_slide] if first_slide else []
        thumbnail_path = course.get("thumbnail") or course.get("thumbnail_url")

        clean_courses.append({
            "course_id": course_id,
            "title": course.get("course_name", ""),
            "course_description": course.get("course_description", ""),
            "created_at": course.get("created_at", 0),
            "modules": clean_modules,
            "images": course_images,
            "thumbnail": thumbnail_path or "",
            "thumbnail_url": thumbnail_path or "",
            "thumbnail_prompt_hash": course.get("thumbnail_prompt_hash", "") if thumbnail_path else "",
        })

    print(
        f"[EXPORTER] Prepared {len(clean_courses)} published course(s) "
        f"from {len(draft_courses)} draft course(s); skipped incomplete={len(skipped_courses)}"
    )
    if skipped_courses:
        preview = ", ".join(skipped_courses[:5])
        suffix = "..." if len(skipped_courses) > 5 else ""
        print(f"[EXPORTER] Incomplete draft course ids skipped: {preview}{suffix}")

    # If we generated any new UUIDs for course ids or question ids, save them back to SQLite draft rows.
    if draft_modified:
        try:
            write_start = time.perf_counter()
            save_all_courses(draft_courses, "draft")
            print(
                f"[EXPORTER] Saved generated IDs back to SQLite draft rows "
                f"in {time.perf_counter() - write_start:.1f}s"
            )
        except Exception as e:
            print(f"[EXPORTER][WARNING] Failed to write updated draft database: {e}")

    # Write the clean production-ready courses to SQLite published rows.
    try:
        write_start = time.perf_counter()
        save_all_courses(clean_courses, "published")
        print(
            f"[EXPORTER] Synchronized SQLite published rows in "
            f"{time.perf_counter() - write_start:.1f}s: {DB_PATH}"
        )
        print(f"[EXPORTER] Publish sync finished in {time.perf_counter() - start:.1f}s")
        
    except Exception as e:
        print(f"[EXPORTER][ERROR] Failed to write clean database: {e}")

if __name__ == "__main__":
    sync_clean_database()
