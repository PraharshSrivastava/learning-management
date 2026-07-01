import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from fastapi.staticfiles import StaticFiles
from pipelines.run_pipeline import generate_course_outline, generate_lessons_for_course
from pipelines.bullet_refiner import refine_bullets_for_course
from pipelines.config import COURSES_FILE
from pipelines.exporter import sync_clean_database

app = FastAPI(title="LMS Document Management System Backend")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets directory
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class GenerateCourseRequest(BaseModel):
    filename: str

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # Validate it's a PDF
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Save the file
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    return {"filename": file.filename, "message": "File uploaded successfully"}

@app.get("/api/files")
async def list_files():
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
        # Sort by creation time descending
        file_details.sort(key=lambda x: x["created"], reverse=True)
        return file_details
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@app.get("/api/files/{filename}")
async def get_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@app.post("/api/courses/generate")
async def generate_course(request: GenerateCourseRequest):
    try:
        outline = generate_course_outline(request.filename)
        sync_clean_database()
        return outline
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate course: {str(e)}")

@app.post("/api/courses/{course_id}/generate-lessons")
async def generate_lessons(course_id: str):
    try:
        updated_course = generate_lessons_for_course(course_id)
        sync_clean_database()
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate lessons: {str(e)}")

@app.post("/api/courses/{course_id}/refine-bullets")
async def refine_bullets(course_id: str):
    try:
        updated_course = refine_bullets_for_course(course_id)
        sync_clean_database()
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine bullets: {str(e)}")



@app.get("/api/courses")
async def list_courses():
    try:
        if not os.path.exists(COURSES_FILE):
            return []
        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            courses = json.load(f)
        return courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve courses: {str(e)}")

@app.put("/api/courses/{course_id}")
async def update_course(course_id: str, updated_fields: dict):
    try:
        if not os.path.exists(COURSES_FILE):
            raise HTTPException(status_code=404, detail="Courses database not found")
            
        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            courses = json.load(f)
            
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
            
            # Map original modules by start_line and title to preserve sub-fields (like slides)
            original_modules = original_course.get("modules", [])

            # start_line can now be an int (new) or str (legacy) — normalise to str key for lookup
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
                # Normalize item — support both plain strings (legacy) and full dicts
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

                # Look for a match in original modules to preserve lessons
                matched = None
                sl_key = _sl_key(incoming_start_line)
                if sl_key and sl_key in original_by_start_line:
                    matched = original_by_start_line[sl_key]
                elif incoming_title and incoming_title.strip() in original_by_title:
                    matched = original_by_title[incoming_title.strip()]

                if matched:
                    # Found match: preserve lessons and other existing keys, update editable ones
                    existing = dict(matched)
                    existing["module_number"] = idx + 1
                    existing["title"] = incoming_title
                    existing["text"] = incoming_text
                    existing["start_line"] = incoming_start_line
                    existing["num_questions"] = incoming_num_questions
                    existing.pop("end_line", None)
                    # Preserve generated lessons — blueprint edits must never wipe them
                    if "lessons" not in existing:
                        existing["lessons"] = []
                    new_modules.append(existing)
                else:
                    # Brand-new module added manually via the UI
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
        
        with open(COURSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(courses, f, indent=2, ensure_ascii=False)
            
        sync_clean_database()
        return original_course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update course: {str(e)}")

# -------------------------------------------------------
# Quiz Generation Endpoints
# -------------------------------------------------------

@app.post("/api/courses/{course_id}/generate-quiz")
async def generate_quiz(course_id: str):
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


# -------------------------------------------------------
# Slide Deck Generation Endpoints
# -------------------------------------------------------

@app.post("/api/courses/{course_id}/generate-slides")
async def generate_slides(course_id: str):
    try:
        from pipelines.slide_planner import generate_slides_for_course
        from pipelines.slides_generator import compile_slides_for_course
        # Plan layout types and map images/scripts
        updated_course = generate_slides_for_course(course_id)
        # Compile visual slide pages into static HTML slide decks
        compile_slides_for_course(course_id)
        sync_clean_database()
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate slideshow: {str(e)}")


@app.post("/api/courses/{course_id}/generate-scripts")
async def generate_scripts(course_id: str):
    try:
        from pipelines.run_pipeline import generate_scripts_for_course
        from pipelines.slides_generator import compile_slides_for_course
        updated_course = generate_scripts_for_course(course_id)
        # Re-compile slideshow files to ensure slide speaker notes are synchronized
        compile_slides_for_course(course_id)
        sync_clean_database()
        return updated_course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate narration scripts: {str(e)}")


@app.post("/api/courses/{course_id}/modules/{module_number}/generate-video")
async def generate_video(course_id: str, module_number: int):
    try:
        from pipelines.video_generator import generate_video_for_module
        from pipelines.config import COURSES_FILE
        
        generate_video_for_module(course_id, module_number)
        
        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            courses = json.load(f)
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


@app.post("/api/courses/{course_id}/generate-full-course")
async def generate_full_course(course_id: str):
    try:
        from pipelines.run_pipeline import generate_lessons_for_course, generate_scripts_for_course
        from pipelines.quiz_generator import generate_quiz_for_course
        from pipelines.slide_planner import generate_slides_for_course
        from pipelines.slides_generator import compile_slides_for_course
        from pipelines.video_generator import generate_video_for_module

        # Step 2: Lesson Generation & Bullet Refinement & Image Mapping
        generate_lessons_for_course(course_id)

        # Step 3: MCQ Quiz Generation
        generate_quiz_for_course(course_id)

        # Step 4: Slides Planning & Compilation
        generate_slides_for_course(course_id)
        compile_slides_for_course(course_id)

        # Step 5: Scripts Generation & Text-to-Speech Narration Synthesis
        generate_scripts_for_course(course_id)
        compile_slides_for_course(course_id) # Re-compile slides to sync narrations

        # Step 6: Slide-to-Video compilation (FFmpeg) per module
        if not os.path.exists(COURSES_FILE):
            raise FileNotFoundError("Courses database not found.")

        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            courses = json.load(f)

        course = next((c for c in courses if c.get("id") == course_id), None)
        if not course:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")

        modules = course.get("modules", [])
        for m in modules:
            mod_num = m.get("module_number")
            generate_video_for_module(course_id, mod_num)

        sync_clean_database()

        # Reload course to return the fully updated course
        with open(COURSES_FILE, 'r', encoding='utf-8') as f:
            courses = json.load(f)
        course = next((c for c in courses if c.get("id") == course_id), None)

        return course
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate full course: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


