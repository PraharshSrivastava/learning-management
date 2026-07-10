import os
import sys
import shutil
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add the main backend directory to sys.path so we can reuse the pipeline modules
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.config import UPLOAD_DIR
from pipelines.exporter import sync_clean_database

# Import the modular sandbox steps
from pipeline_step1_blueprint import run_step1_extract_blueprint

from pipeline_step5_slide_planner import run_step5_slide_planner
from pipeline_step6_art_director import run_step6_art_director
from webslides_generator import generate_html_slides_for_module
app = FastAPI(title="Slide Experiment Sandbox")

# Ensure UPLOAD_DIR exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

class GenerateCourseRequest(BaseModel):
    filename: str

def _sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
    return filename or "unnamed.pdf"

from local_db import get_all_courses

@app.get("/api/mock-courses")
def get_mock_courses():
    try:
        courses = get_all_courses()
        return [{"id": c.get("id"), "name": c.get("course_name")} for c in courses]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load mock courses: {str(e)}")

@app.post("/api/upload")
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

@app.post("/api/courses/generate")
def generate_course(request: GenerateCourseRequest):
    try:
        outline = run_step1_extract_blueprint(request.filename)
        return outline
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate blueprint: {str(e)}")

@app.post("/api/courses/{course_id}/generate-slides")
def generate_slides(course_id: str):
    try:
        updated_course = run_step5_slide_planner(course_id)
        return updated_course
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate slides: {str(e)}")

@app.post("/api/courses/{course_id}/art-director")
def run_art_director(course_id: str):
    try:
        updated_course = run_step6_art_director(course_id)
        
        # After art direction, generate the HTML slides for preview
        modules = updated_course.get("modules", [])
        html_urls = []
        for i, mod in enumerate(modules):
            html_path = generate_html_slides_for_module(course_id, i, mod)
            if html_path:
                # Provide a URL route that serves this specific file
                html_urls.append(f"/api/slides/{course_id}/module_{i+1}.html")
        
        return {"course": updated_course, "html_urls": html_urls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run art director: {str(e)}")

@app.get("/api/slides/{course_id}/{filename}")
def get_slide_html(course_id: str, filename: str):
    import os
    from fastapi.responses import FileResponse
    from pipelines.config import BASE_DIR
    
    file_path = os.path.join(BASE_DIR, "assets", "slides", course_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Slide HTML not found")
    return FileResponse(file_path)

@app.get("/api/slides.css")
def get_slides_css():
    import os
    from fastapi.responses import FileResponse
    # Serve the local slides.css instead of the backend one
    file_path = os.path.join(os.path.dirname(__file__), "static", "slides.css")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="slides.css not found")
    return FileResponse(file_path)

@app.get("/api/images/{course_id}/{filename}")
def get_slide_image(course_id: str, filename: str):
    import os
    from fastapi.responses import FileResponse
    from pipelines.config import BASE_DIR
    file_path = os.path.join(BASE_DIR, "assets", "images", course_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)

# Mount the static dashboard
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
