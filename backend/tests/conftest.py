import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session", autouse=True)
def isolated_database(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "lms_test.db"
    os.environ["LMS_DB_PATH"] = str(db_path)
    os.environ["COURSE_THUMBNAILS_ENABLED"] = "false"
    yield db_path


@pytest.fixture
def app(isolated_database):
    import core.database as database
    import pipelines.employee_routes as employee_routes
    from main import app as fastapi_app

    database.init_db()
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM employee_course_progress")
        cursor.execute("DELETE FROM employee_progress")
        cursor.execute("DELETE FROM course_assignment_rules")
        cursor.execute("DELETE FROM courses")
        conn.commit()

    employee_routes._demo_sessions.clear()
    employee_routes._active_websockets.clear()

    return fastapi_app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def database(app):
    import core.database as database_module

    return database_module


@pytest.fixture
def employee_routes(app):
    import pipelines.employee_routes as employee_routes_module

    return employee_routes_module


@pytest.fixture
def active_employees(database):
    employees = database.list_employees()
    assert len(employees) >= 2
    return employees[:2]


@pytest.fixture
def inactive_employee(database):
    employees = database.list_employees(include_inactive=True)
    inactive = [employee for employee in employees if employee["status"] == "inactive"]
    assert inactive
    return inactive[0]


@pytest.fixture
def published_course():
    return {
        "id": "published-course-1",
        "course_id": "published-course-1",
        "title": "Published Course",
        "course_description": "Visible to employees",
        "modules": [
            {
                "module_number": 1,
                "title": "Module 1",
                "video_url": "/assets/videos/module-1.mp4",
                "quiz": [
                    {
                        "question": "Question 1",
                        "options": ["A", "B", "C", "D"],
                        "correct": "A",
                    }
                ],
                "pass_mark": 0.67,
            },
            {
                "module_number": 2,
                "title": "Module 2",
                "video_url": "/assets/videos/module-2.mp4",
                "quiz": [
                    {
                        "question": "Question 2",
                        "options": ["A", "B", "C", "D"],
                        "correct": "B",
                    }
                ],
                "pass_mark": 0.67,
            },
        ],
        "images": [],
    }


@pytest.fixture
def draft_course():
    return {
        "id": "draft-course-1",
        "course_id": "draft-course-1",
        "title": "Draft Course",
        "course_description": "Not visible to employees",
        "modules": [],
        "images": [],
    }


@pytest.fixture
def seed_courses(database, published_course, draft_course):
    database.save_all_courses([published_course], "published")
    database.save_all_courses([draft_course], "draft")
    return {"published": published_course, "draft": draft_course}


@pytest.fixture
def assigned_seed_courses(database, seed_courses):
    database.save_assignment_rule(
        seed_courses["published"]["course_id"],
        {"include_all": True, "deadline_days": 7},
        publish=True,
    )
    return seed_courses


def login_employee(client, employee_id):
    response = client.post("/api/auth/demo-login", json={"employee_id": employee_id})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["token"], body["employee"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
