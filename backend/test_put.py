import requests
import json
import time

def test_update():
    # 1. Create a dummy course first since we cleared the db
    print("Creating dummy course...")
    from core.io_utils import atomic_write_json
    from core.config import DRAFT_COURSES_FILE
    
    courses = [{
        "id": "test_course_1",
        "course_name": "Test Course",
        "modules": [
            {
                "module_number": 1,
                "title": "Module 1",
                "text": "Text 1",
                "start_line": 1,
                "num_questions": 3
            }
        ]
    }]
    atomic_write_json(DRAFT_COURSES_FILE, courses)
    
    # Wait a sec just in case
    time.sleep(1)
    
    # 2. Try to update it via the API
    print("Updating course via API...")
    url = "http://localhost:8000/api/courses/test_course_1"
    payload = {
        "course_name": "Updated Test Course",
        "modules": [
            {
                "title": "Updated Module 1",
                "text": "Updated Text 1",
                "start_line": "1",
                "end_line": "10",
                "num_questions": 5
            }
        ]
    }
    try:
        response = requests.put(url, json=payload)
        print("Status Code:", response.status_code)
        print("Response:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_update()
