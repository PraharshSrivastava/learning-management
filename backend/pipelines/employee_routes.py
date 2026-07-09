from core.database import get_all_courses, save_all_courses
import os
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from core.config import PUBLISHED_COURSES_FILE, EMPLOYEE_PROGRESS_FILE
from core.io_utils import atomic_write_json

router = APIRouter()
active_websockets = []

from core.database import get_all_progress, save_progress

def get_employee_progress():
    return get_all_progress()

def save_employee_progress(progress):
    for course_id, prog_data in progress.items():
        save_progress(course_id, prog_data)

def get_enriched_employee_courses():
    courses = get_all_courses('published')
        
    progress = get_employee_progress()
    now = datetime.now()
    progress_updated = False
    
    employee_courses = []
    for course in courses:
        course_id = course.get("course_id")
        if not course_id:
            continue
            
        if course_id not in progress:
            # Fallback if assignment missed
            progress[course_id] = {
                "status": "pending",
                "assigned_at": now.isoformat(),
                "deadline": (now + timedelta(days=7)).isoformat(),
                "modules": {}
            }
            progress_updated = True
            
        course_progress = progress[course_id]
        if "modules" not in course_progress:
            course_progress["modules"] = {}
            progress_updated = True
        if course_progress["status"] in ["pending", "started"]:
            deadline_dt = datetime.fromisoformat(course_progress["deadline"])
            if now > deadline_dt:
                course_progress["status"] = "overdue"
                progress_updated = True
                
        course["employee_status"] = course_progress["status"]
        course["assigned_at"] = course_progress["assigned_at"]
        course["deadline"] = course_progress["deadline"]
        course["employee_progress"] = course_progress.get("modules", {})
        employee_courses.append(course)
        
    if progress_updated:
        save_employee_progress(progress)
        
    return employee_courses

async def broadcast_employee_courses():
    if not active_websockets:
        return
    data = get_enriched_employee_courses()
    for ws in active_websockets:
        try:
            await ws.send_json(data)
        except Exception:
            pass

def assign_published_courses_to_employees(published_courses):
    progress = get_employee_progress()
    now = datetime.now()
    updated = False
    
    for course in published_courses:
        c_id = course.get("course_id")
        if c_id and c_id not in progress:
            progress[c_id] = {
                "status": "pending",
                "assigned_at": now.isoformat(),
                "deadline": (now + timedelta(days=7)).isoformat(),
                "modules": {}
            }
            updated = True
            
    if updated:
        save_employee_progress(progress)
    
    # Broadcast change to active websockets
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast_employee_courses())
        else:
            loop.run_until_complete(broadcast_employee_courses())
    except Exception:
        pass

@router.websocket("/api/employee/courses/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        await websocket.send_json(get_enriched_employee_courses())
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

@router.put("/api/employee/courses/{course_id}/status")
async def update_course_status(course_id: str, payload: dict):
    new_status = payload.get("status")
    if new_status not in ["pending", "started", "completed", "overdue"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    progress = get_employee_progress()
    if course_id not in progress:
        raise HTTPException(status_code=404, detail="Course not assigned to employee")
        
    progress[course_id]["status"] = new_status
    save_employee_progress(progress)
    
    await broadcast_employee_courses()
    return {"message": "Status updated", "status": new_status}

@router.put("/api/employee/courses/{course_id}/modules/{module_number}")
async def update_module_progress(course_id: str, module_number: str, payload: dict):
    progress = get_employee_progress()
    if course_id not in progress:
        raise HTTPException(status_code=404, detail="Course not assigned")
        
    course_progress = progress[course_id]
    if "modules" not in course_progress:
        course_progress["modules"] = {}
        
    mod_prog = course_progress["modules"].get(module_number, {})
    
    if "video_watched" in payload:
        mod_prog["video_watched"] = payload["video_watched"]
    if "quiz_passed" in payload:
        mod_prog["quiz_passed"] = payload["quiz_passed"]
    if "quiz_score" in payload:
        mod_prog["quiz_score"] = payload["quiz_score"]
    if "selected_answers" in payload:
        # payload["selected_answers"] will be a dict with string keys like {"0": "A", "1": "C"}
        # because JSON object keys must be strings.
        mod_prog["selected_answers"] = payload["selected_answers"]
        
    course_progress["modules"][module_number] = mod_prog
    
    # Auto-update course status
    published_courses = get_all_courses('published')
    if True:
        for pub_course in published_courses:
            if pub_course.get("course_id") == course_id:
                total_modules = len(pub_course.get("modules", []))
                completed_count = sum(
                    1 for p in course_progress["modules"].values() 
                    if p.get("video_watched") and p.get("quiz_passed")
                )
                
                if total_modules > 0 and completed_count == total_modules:
                    course_progress["status"] = "completed"
                elif course_progress["status"] == "pending":
                    course_progress["status"] = "started"
                break
                
    save_employee_progress(progress)
    
    await broadcast_employee_courses()
    return {"message": "Module progress updated"}
