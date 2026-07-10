import json
import os

JSON_PATH = os.path.join(os.path.dirname(__file__), "mock_data.json")

def get_all_courses(status=None):
    if not os.path.exists(JSON_PATH):
        return []
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_all_courses(courses, status=None):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(courses, f, indent=2)
