from core.database import get_all_courses, save_all_courses
import os
import re
import shutil
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.config import UPLOAD_DIR, DRAFT_COURSES_FILE
from core.io_utils import atomic_write_json
from pipelines.run_pipeline import generate_course_outline
from pipelines.exporter import sync_clean_database

router = APIRouter()

def _sanitize_filename(filename: str) -> str:
    """
    Strips any path components and replaces any character outside
    a safe allowlist, to prevent path traversal or unexpected file
    writes from a crafted upload filename.
    """
    filename = os.path.basename(filename)
    filename = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
    return filename or "unnamed.pdf"

class GenerateCourseRequest(BaseModel):
    filename: str

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
        sync_clean_database()
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
        
        for field in ["course_name", "course_description", "course_objective", "course_difficulty", "language", "target_audience", "course_type"]:
            if field in updated_fields:
                original_course[field] = updated_fields[field]
                
        if "modules" in updated_fields:
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
                
        courses[course_idx] = original_course
        
        save_all_courses(courses, "draft")
            
        sync_clean_database()
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
        sync_clean_database()
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate quiz: {str(e)}")

@router.post("/api/courses/{course_id}/generate-slides")
def generate_slides(course_id: str):
    try:
        from pipelines.slide_planner import generate_slides_for_course
        from pipelines.slides_generator import compile_slides_for_course
        updated_course = generate_slides_for_course(course_id)
        compile_slides_for_course(course_id)
        sync_clean_database()
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
        sync_clean_database()
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
        sync_clean_database()
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
    try:
        from pipelines.run_pipeline import generate_scripts_for_course
        from pipelines.quiz_generator import generate_quiz_for_course
        from pipelines.slide_planner import generate_slides_for_course
        from pipelines.slides_generator import compile_slides_for_course
        from pipelines.video_generator import generate_video_for_module

        generate_quiz_for_course(course_id)
        generate_slides_for_course(course_id)
        compile_slides_for_course(course_id)
        generate_scripts_for_course(course_id)
        compile_slides_for_course(course_id)

        courses = get_all_courses('draft')

        course = next((c for c in courses if c.get("id") == course_id), None)
        if not course:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")

        modules = course.get("modules", [])
        for m in modules:
            mod_num = m.get("module_number")
            generate_video_for_module(course_id, mod_num)

        sync_clean_database()

        courses = get_all_courses('draft')
        course = next((c for c in courses if c.get("id") == course_id), None)

        return course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate full course: {str(e)}")
