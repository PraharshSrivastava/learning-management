from core.database import get_all_courses, save_all_courses
import os
import re
import shutil
import json
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.config import UPLOAD_DIR, DRAFT_COURSES_FILE
from core.io_utils import atomic_write_json
from pipelines.run_pipeline import generate_course_outline
from pipelines.pipeline_runtime import (
    PipelineStageError,
    complete_generation,
    generation_state,
    log_event,
    mark_stage,
    now_iso,
    retry,
)

router = APIRouter()


def _mark_interrupted_generations_failed() -> None:
    """A process restart cannot safely leave a synchronous pipeline marked running."""
    try:
        courses = get_all_courses("draft")
        changed = False
        for course in courses:
            state = generation_state(course)
            if state.get("status") != "running":
                continue
            checkpoint = state.get("current_checkpoint") or "pipeline"
            mark_stage(
                course,
                checkpoint,
                "failed",
                error="Generation interrupted because the backend process restarted. Continue from this checkpoint.",
            )
            log_event(course.get("id", "unknown"), checkpoint, "interrupted_by_restart")
            changed = True
        if changed:
            save_all_courses(courses, "draft")
    except Exception as exc:
        print(f"[PIPELINE][RECOVERY][WARNING] Could not mark interrupted generations failed: {exc}")


_mark_interrupted_generations_failed()

def _sanitize_filename(filename: str) -> str:
    """
    Strips any path components and replaces any character outside
    a safe allowlist, to prevent path traversal or unexpected file
    writes from a crafted upload filename.
    """
    filename = os.path.basename(filename)
    filename = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
    return filename or "unnamed.pdf"


def _invalidate_generated_course_content(course: dict) -> None:
    """Blueprint edits make every downstream generated artefact stale."""
    for module in course.get("modules", []):
        module.pop("quiz", None)
        module.pop("quiz_generation_error", None)
        module.pop("planned_slides", None)
        module.pop("slides", None)
        module.pop("notes", None)
        module.pop("video_path", None)

    course.pop("thumbnail", None)
    course.pop("thumbnail_url", None)
    course.pop("thumbnail_prompt_hash", None)
    generation = course.setdefault("generation", {})
    blueprint_stage = generation.get("stages", {}).get("blueprint")
    generation.clear()
    generation["status"] = "pending"
    generation["stages"] = {"blueprint": blueprint_stage} if blueprint_stage else {}
    generation["updated_at"] = now_iso()

class GenerateCourseRequest(BaseModel):
    filename: str

class ManualQuizRequest(BaseModel):
    questions: list[dict]

@router.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    safe_filename = _sanitize_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    return {"filename": safe_filename, "message": "File uploaded successfully"}

@router.get("/api/files")
def list_files():
    try:
        files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f)) and f.lower().endswith('.pdf')]
        file_details = []
        for f in files:
            path = os.path.join(UPLOAD_DIR, f)
            stat = os.stat(path)
            file_details.append({
                "filename": f,
                "size": stat.st_size,
                "created": stat.st_mtime
            })
        file_details.sort(key=lambda x: x["created"], reverse=True)
        return file_details
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.get("/api/files/{filename}")
def get_file(filename: str):
    safe_name = _sanitize_filename(filename)
    file_path = os.path.realpath(os.path.join(UPLOAD_DIR, safe_name))
    if not file_path.startswith(os.path.realpath(UPLOAD_DIR)) or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"inline; filename={safe_name}"}
    )

@router.post("/api/courses/generate")
def generate_course(request: GenerateCourseRequest):
    try:
        outline = generate_course_outline(request.filename)
        return outline
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate course: {str(e)}")


@router.get("/api/courses")
def list_courses(response: Response):
    try:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        courses = get_all_courses('draft')
        return courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve courses: {str(e)}")

@router.put("/api/courses/{course_id}")
def update_course(course_id: str, updated_fields: dict):
    try:
        courses = get_all_courses('draft')
            
        course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
        if course_idx is None:
            raise HTTPException(status_code=404, detail="Course not found")
            
        original_course = courses[course_idx]
        
        blueprint_changed = False
        for field in ["course_name", "course_description", "course_objective", "course_difficulty", "language", "target_audience", "course_type"]:
            if field in updated_fields:
                blueprint_changed = blueprint_changed or original_course.get(field) != updated_fields[field]
                original_course[field] = updated_fields[field]
                
        if "modules" in updated_fields:
            blueprint_changed = True
            updated_modules_data = updated_fields["modules"]
            new_modules = []
            
            original_modules = original_course.get("modules", [])

            def _sl_key(val):
                return str(val).strip() if val is not None and val != "" else None

            original_by_start_line = {
                _sl_key(m.get("start_line")): m
                for m in original_modules
                if isinstance(m, dict) and _sl_key(m.get("start_line"))
            }
            original_by_title = {
                m.get("title", "").strip(): m
                for m in original_modules
                if isinstance(m, dict) and m.get("title")
            }

            for idx, item in enumerate(updated_modules_data):
                if isinstance(item, str):
                    incoming_title = item
                    incoming_text = ""
                    incoming_start_line = None
                    incoming_num_questions = 3
                else:
                    incoming_title = item.get("title", "")
                    incoming_text = item.get("text", "")
                    incoming_start_line = item.get("start_line", None)
                    incoming_num_questions = item.get("num_questions", 3)

                matched = None
                sl_key = _sl_key(incoming_start_line)
                if sl_key and sl_key in original_by_start_line:
                    matched = original_by_start_line[sl_key]
                elif incoming_title and incoming_title.strip() in original_by_title:
                    matched = original_by_title[incoming_title.strip()]

                if matched:
                    existing = dict(matched)
                    existing["module_number"] = idx + 1
                    existing["title"] = incoming_title
                    existing["text"] = incoming_text
                    existing["start_line"] = incoming_start_line
                    existing["num_questions"] = incoming_num_questions
                    existing.pop("end_line", None)
                    if "lessons" not in existing:
                        existing["lessons"] = []
                    new_modules.append(existing)
                else:
                    new_modules.append({
                        "module_number": idx + 1,
                        "title": incoming_title,
                        "text": incoming_text,
                        "start_line": incoming_start_line,
                        "num_questions": incoming_num_questions,
                        "lessons": []
                    })
            original_course["modules"] = new_modules

        if blueprint_changed:
            _invalidate_generated_course_content(original_course)
                
        courses[course_idx] = original_course

        save_all_courses(courses, "draft")
        return original_course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update course: {str(e)}")

@router.post("/api/courses/{course_id}/generate-quiz")
def generate_quiz(course_id: str):
    try:
        from pipelines.quiz_generator import generate_quiz_for_course
        updated_course = generate_quiz_for_course(course_id)
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate quiz: {str(e)}")

@router.put("/api/courses/{course_id}/modules/{module_number}/quiz")
def update_module_quiz(course_id: str, module_number: int, payload: ManualQuizRequest):
    try:
        from pipelines.quiz_generator import ModuleQuiz

        parsed = ModuleQuiz.model_validate({"questions": payload.questions})
        for index, question in enumerate(parsed.questions, start=1):
            option_keys = {option.key.strip().upper() for option in question.options}
            if option_keys != {"A", "B", "C", "D"}:
                raise ValueError(f"Question {index} must include options A, B, C, and D.")
            correct = question.correct_option.strip().upper()
            if correct not in option_keys:
                raise ValueError(f"Question {index} has an invalid correct option.")
        courses = get_all_courses('draft')
        course_idx = next((i for i, c in enumerate(courses) if c.get("id") == course_id), None)
        if course_idx is None:
            raise HTTPException(status_code=404, detail="Course not found")

        course = courses[course_idx]
        modules = course.get("modules", [])
        module = next(
            (m for m in modules if int(m.get("module_number", 0)) == module_number),
            None,
        )
        if module is None:
            raise HTTPException(status_code=404, detail="Module not found")

        module["quiz"] = parsed.model_dump()
        module["num_questions"] = len(parsed.questions)
        module.pop("quiz_generation_error", None)
        courses[course_idx] = course
        save_all_courses(courses, "draft")
        return course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save module quiz: {str(e)}")

@router.post("/api/courses/{course_id}/generate-slides")
def generate_slides(course_id: str):
    try:
        from pipelines.slide_planner import generate_slides_for_course
        from pipelines.slides_generator import compile_slides_for_course
        updated_course = generate_slides_for_course(course_id)
        compile_slides_for_course(course_id)
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate slideshow: {str(e)}")

@router.post("/api/courses/{course_id}/generate-scripts")
def generate_scripts(course_id: str):
    try:
        from pipelines.run_pipeline import generate_scripts_for_course
        from pipelines.slides_generator import compile_slides_for_course
        updated_course = generate_scripts_for_course(course_id)
        compile_slides_for_course(course_id)
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate narration scripts: {str(e)}")

@router.post("/api/courses/{course_id}/modules/{module_number}/generate-video")
def generate_video(course_id: str, module_number: int):
    try:
        from pipelines.video_generator import generate_video_for_module
        
        generate_video_for_module(course_id, module_number)
        
        courses = get_all_courses('draft')
        course = next((c for c in courses if c.get("id") == course_id), None)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found after video generation")
        return course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate course video: {str(e)}")

@router.post("/api/courses/{course_id}/generate-full-course")
def generate_full_course(course_id: str):
    return _run_full_course_generation(course_id, restart_from_blueprint=True)


def _run_full_course_generation(course_id: str, restart_from_blueprint: bool):
    try:
        from pipelines.run_pipeline import generate_scripts_for_course, generate_notes_for_course, generate_tts_for_course
        from pipelines.quiz_generator import generate_quiz_for_course
        from pipelines.slide_planner import generate_slides_for_course
        from pipelines.slides_generator import compile_slides_for_course
        from pipelines.video_generator import generate_video_for_module
        from pipelines.thumbnail_generator import (
            course_thumbnail_signature,
            generate_course_thumbnail,
        )
        from pipelines.exporter import is_course_generation_complete, sync_clean_database

        pipeline_start = time.perf_counter()

        def load_course():
            all_courses = get_all_courses("draft")
            index = next((i for i, item in enumerate(all_courses) if item.get("id") == course_id), None)
            if index is None:
                raise ValueError(f"Course ID '{course_id}' not found in courses database.")
            return all_courses, index, all_courses[index]

        def save_course(course):
            all_courses, index, _ = load_course()
            all_courses[index] = course
            save_all_courses(all_courses, "draft")

        if restart_from_blueprint:
            _, _, fresh_course = load_course()
            _invalidate_generated_course_content(fresh_course)
            save_course(fresh_course)
            log_event(course_id, "pipeline", "restart_from_saved_blueprint")

        def run_stage(stage, func, attempts=1):
            _, _, snapshot = load_course()
            state = generation_state(snapshot)
            if state.get("stages", {}).get(stage, {}).get("status") == "completed":
                log_event(course_id, stage, "skipped_completed_checkpoint")
                return None
            started = time.perf_counter()
            mark_stage(snapshot, stage, "running")
            save_course(snapshot)
            log_event(course_id, stage, "start")
            try:
                result = (
                    retry(func, course_id=course_id, stage=stage, attempts=attempts)
                    if attempts > 1
                    else func()
                )
            except Exception as exc:
                _, _, failed_course = load_course()
                failure = exc if isinstance(exc, PipelineStageError) else PipelineStageError(stage, str(exc))
                mark_stage(
                    failed_course, stage, "failed", error=str(failure), module_number=failure.module_number,
                    slide_number=failure.slide_number, elapsed_seconds=time.perf_counter() - started,
                )
                save_course(failed_course)
                log_event(course_id, stage, "failed", elapsed=f"{time.perf_counter() - started:.1f}s", reason=str(failure))
                raise failure
            _, _, complete_course = load_course()
            mark_stage(complete_course, stage, "completed", elapsed_seconds=time.perf_counter() - started)
            save_course(complete_course)
            log_event(course_id, stage, "completed", elapsed=f"{time.perf_counter() - started:.1f}s")
            return result

        run_stage("quiz", lambda: generate_quiz_for_course(course_id))
        run_stage("slides", lambda: generate_slides_for_course(course_id))
        run_stage("html", lambda: compile_slides_for_course(course_id), attempts=3)
        run_stage("scripts", lambda: generate_scripts_for_course(course_id))
        run_stage("notes", lambda: generate_notes_for_course(course_id))
        run_stage("tts", lambda: generate_tts_for_course(course_id))

        def generate_all_videos():
            _, _, snapshot = load_course()
            for module in snapshot.get("modules", []):
                module_number = int(module.get("module_number", 0))
                if not module_number:
                    raise ValueError("Module has no valid module number")
                existing_video = str(module.get("video_path") or "")
                existing_video_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), existing_video)
                if existing_video and os.path.isfile(existing_video_path) and os.path.getsize(existing_video_path) > 0:
                    log_event(course_id, "video", "skipped_valid_video", module=module_number)
                    continue
                generate_video_for_module(course_id, module_number)

        run_stage("video", generate_all_videos, attempts=3)

        def create_thumbnail():
            all_courses, index, snapshot = load_course()
            thumbnail_path = generate_course_thumbnail(snapshot, course_id)
            if not thumbnail_path:
                raise ValueError("Thumbnail generation returned no file")
            snapshot["thumbnail"] = thumbnail_path
            snapshot["thumbnail_url"] = thumbnail_path
            snapshot["thumbnail_prompt_hash"] = course_thumbnail_signature(snapshot)
            all_courses[index] = snapshot
            save_all_courses(all_courses, "draft")

        run_stage("thumbnail", create_thumbnail)
        def validate_and_publish():
            _, _, snapshot = load_course()
            if not is_course_generation_complete(snapshot):
                raise PipelineStageError(
                    "publish",
                    "Course validation failed: required quiz, slides, scripts, notes, audio, video, or thumbnail output is missing.",
                )
            sync_clean_database()

        run_stage("publish", validate_and_publish, attempts=3)

        _, _, course = load_course()
        complete_generation(course, time.perf_counter() - pipeline_start)
        save_course(course)
        log_event(course_id, "pipeline", "completed", total_elapsed=f"{time.perf_counter() - pipeline_start:.1f}s")
        return course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate full course: {str(e)}")


@router.post("/api/courses/{course_id}/continue-generation")
def continue_generation(course_id: str):
    """Resume a stopped full-course generation from its saved failed checkpoint."""
    course = next((item for item in get_all_courses("draft") if item.get("id") == course_id), None)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    state = generation_state(course)
    checkpoint = state.get("failed_checkpoint") or state.get("current_checkpoint")
    if checkpoint == "blueprint":
        source_file = course.get("source_file")
        if not source_file:
            raise HTTPException(status_code=400, detail="Blueprint checkpoint has no source PDF")
        # Blueprint extraction has no downstream artefacts yet; the original endpoint creates a fresh outline.
        return generate_course_outline(source_file, course_id=course_id)
    if not checkpoint:
        raise HTTPException(status_code=400, detail="This course has no generation checkpoint to continue")
    return _run_full_course_generation(course_id, restart_from_blueprint=False)
