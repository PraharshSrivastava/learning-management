from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient

from conftest import auth_headers


def _employee_flow(app, employee_id, course_id):
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/demo-login",
            json={"employee_id": employee_id},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        courses_response = client.get("/api/me/courses", headers=auth_headers(token))
        assert courses_response.status_code == 200
        assert len(courses_response.json()) == 1

        update_response = client.put(
            f"/api/me/courses/{course_id}/modules/1",
            headers=auth_headers(token),
            json={"video_watched": True},
        )
        assert update_response.status_code == 200

        return employee_id


def test_many_employees_can_fetch_and_update_progress_concurrently(
    app,
    database,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    employees = database.list_employees()[:80]

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(_employee_flow, app, employee["id"], course_id)
            for employee in employees
        ]
        completed = [future.result() for future in as_completed(futures)]

    assert len(completed) == len(employees)
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM employee_course_progress
            WHERE course_id = ?
            """,
            (course_id,),
        )
        assert cursor.fetchone()["count"] == len(employees)

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM employee_course_progress
            WHERE course_id = ? AND modules_json LIKE '%video_watched%'
            """,
            (course_id,),
        )
        assert cursor.fetchone()["count"] == len(employees)
