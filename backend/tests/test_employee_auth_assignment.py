import sqlite3

from conftest import auth_headers, login_employee


def _progress_row_count(database):
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM employee_course_progress")
        return cursor.fetchone()["count"]


def test_employees_endpoint_lists_only_active_employees(client):
    response = client.get("/api/employees")

    assert response.status_code == 200
    employees = response.json()
    assert employees
    assert all(employee["status"] == "active" for employee in employees)


def test_demo_login_returns_token_for_active_employee(client, active_employees):
    token, employee = login_employee(client, active_employees[0]["id"])

    assert token
    assert employee["id"] == active_employees[0]["id"]


def test_demo_login_rejects_inactive_employee(client, inactive_employee):
    response = client.post(
        "/api/auth/demo-login",
        json={"employee_id": inactive_employee["id"]},
    )

    assert response.status_code == 404


def test_me_requires_valid_bearer_token(client, active_employees):
    missing = client.get("/api/me")
    invalid = client.get("/api/me", headers={"Authorization": "Bearer bad-token"})

    token, employee = login_employee(client, active_employees[0]["id"])
    valid = client.get("/api/me", headers=auth_headers(token))

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["id"] == employee["id"]


def test_my_courses_assigns_all_published_courses_and_excludes_drafts(
    client,
    database,
    active_employees,
    seed_courses,
):
    database.save_assignment_rule(
        seed_courses["published"]["course_id"],
        {"include_all": True, "deadline_days": 7},
        publish=True,
    )
    token, employee = login_employee(client, active_employees[0]["id"])

    response = client.get("/api/me/courses", headers=auth_headers(token))

    assert response.status_code == 200
    courses = response.json()
    assert [course["course_id"] for course in courses] == [
        seed_courses["published"]["course_id"]
    ]
    assert courses[0]["employee_status"] == "pending"
    assert courses[0]["assigned_at"]
    assert courses[0]["deadline"]
    assert courses[0]["employee_progress"] == {}
    assert courses[0]["employee_attempts"] == {}
    assert database.get_employee_course_progress(
        employee["id"], seed_courses["published"]["course_id"]
    )


def test_published_course_without_published_assignment_rule_is_not_assigned(
    client,
    database,
    active_employees,
    seed_courses,
):
    token, employee = login_employee(client, active_employees[0]["id"])

    response = client.get("/api/me/courses", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json() == []
    assert database.get_employee_course_progress(
        employee["id"], seed_courses["published"]["course_id"]
    ) is None


def test_assignment_is_idempotent(
    client,
    database,
    employee_routes,
    active_employees,
    seed_courses,
):
    employee_id = active_employees[0]["id"]
    database.save_assignment_rule(
        seed_courses["published"]["course_id"],
        {"include_all": True, "deadline_days": 7},
        publish=True,
    )

    assert employee_routes.ensure_assignments_for_employee(employee_id) is True
    first_count = _progress_row_count(database)
    assert employee_routes.ensure_assignments_for_employee(employee_id) is False
    second_count = _progress_row_count(database)

    assert first_count == 1
    assert second_count == first_count


def test_publish_assignment_hook_assigns_new_course_to_active_employees(
    client,
    database,
    employee_routes,
    active_employees,
):
    first_course = {
        "id": "published-course-1",
        "course_id": "published-course-1",
        "title": "Published Course 1",
        "modules": [],
    }
    second_course = {
        "id": "published-course-2",
        "course_id": "published-course-2",
        "title": "Published Course 2",
        "modules": [],
    }
    database.save_all_courses([first_course], "published")
    database.save_assignment_rule(
        "published-course-1",
        {"include_all": True, "deadline_days": 7},
        publish=True,
    )
    employee_routes.assign_published_courses_to_employees()
    database.save_all_courses([first_course, second_course], "published")
    database.save_assignment_rule(
        "published-course-2",
        {"include_all": True, "deadline_days": 7},
        publish=True,
    )

    employee_routes.assign_published_courses_to_employees()

    for employee in active_employees:
        progress = database.get_employee_progress(employee["id"])
        assert "published-course-1" in progress
        assert "published-course-2" in progress
