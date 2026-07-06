import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from core.config import DB_PATH

def get_connection():
    # check_same_thread=False allows FastAPI async defs to use the connection if needed,
    # though it's better to open/close short-lived connections anyway.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                data TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employee_progress (
                course_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        ''')
        conn.commit()

# Initialize immediately on import
init_db()


# ==========================================
# Course Operations
# ==========================================

def get_all_courses(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT data FROM courses WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT data FROM courses")
        rows = cursor.fetchall()
        return [json.loads(row['data']) for row in rows]

def get_course(course_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM courses WHERE id = ?", (course_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None

def save_course(course: Dict[str, Any], status: str):
    """Save or update a course"""
    if "id" not in course:
        course["id"] = str(uuid.uuid4())
    course_id = course["id"]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO courses (id, status, data) VALUES (?, ?, ?)",
            (course_id, status, json.dumps(course, ensure_ascii=False))
        )
        conn.commit()

def save_all_courses(courses: List[Dict[str, Any]], status: str):
    """Save an entire list of courses"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Delete existing courses of this status to mimic replacing the entire file
        cursor.execute("DELETE FROM courses WHERE status = ?", (status,))
        for course in courses:
            if "id" not in course:
                course["id"] = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO courses (id, status, data) VALUES (?, ?, ?)",
                (course["id"], status, json.dumps(course, ensure_ascii=False))
            )
        conn.commit()

def update_course_status(course_id: str, new_status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE courses SET status = ? WHERE id = ?", (new_status, course_id))
        conn.commit()

def delete_course(course_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        cursor.execute("DELETE FROM employee_progress WHERE course_id = ?", (course_id,))
        conn.commit()


# ==========================================
# Employee Progress Operations
# ==========================================

def get_all_progress() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT course_id, data FROM employee_progress")
        rows = cursor.fetchall()
        return {row['course_id']: json.loads(row['data']) for row in rows}

def get_progress(course_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM employee_progress WHERE course_id = ?", (course_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None

def save_progress(course_id: str, progress_data: Dict[str, Any]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO employee_progress (course_id, data) VALUES (?, ?)",
            (course_id, json.dumps(progress_data, ensure_ascii=False))
        )
        conn.commit()
