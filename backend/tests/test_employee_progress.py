from datetime import datetime, timedelta

from conftest import auth_headers, login_employee


def test_employee_a_progress_does_not_affect_employee_b(
    client,
    database,
    active_employees,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    token_a, employee_a = login_employee(client, active_employees[0]["id"])
    token_b, employee_b = login_employee(client, active_employees[1]["id"])

    response = client.put(
        f"/api/me/courses/{course_id}/status",
        headers=auth_headers(token_a),
        json={"status": "started"},
    )

    assert response.status_code == 200
    progress_a = database.get_employee_course_progress(employee_a["id"], course_id)
    progress_b = database.get_employee_course_progress(employee_b["id"], course_id)
    assert progress_a["status"] == "started"
    assert progress_a["started_at"]
    assert progress_b["status"] == "pending"
    assert progress_b["started_at"] is None


def test_module_progress_tracks_video_quiz_answers_and_attempts(
    client,
    database,
    active_employees,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    token, employee = login_employee(client, active_employees[0]["id"])

    video_response = client.put(
        f"/api/me/courses/{course_id}/modules/1",
        headers=auth_headers(token),
        json={"video_watched": True},
    )
    quiz_response = client.put(
        f"/api/me/courses/{course_id}/modules/1",
        headers=auth_headers(token),
        json={
            "quiz_passed": True,
            "quiz_score": 1.0,
            "selected_answers": {"0": "A"},
        },
    )

    assert video_response.status_code == 200
    assert quiz_response.status_code == 200
    progress = database.get_employee_course_progress(employee["id"], course_id)
    module = progress["modules"]["1"]
    attempt = progress["attempts"]["1"]
    assert progress["status"] == "started"
    assert progress["started_at"]
    assert progress["last_activity_at"]
    assert module["video_watched"] is True
    assert module["video_watched_at"]
    assert module["quiz_passed"] is True
    assert module["quiz_score"] == 1.0
    assert module["selected_answers"] == {"0": "A"}
    assert attempt["count"] == 1
    assert attempt["last_score"] == 1.0
    assert attempt["last_passed"] is True
    assert attempt["last_attempt_at"]


def test_quiz_attempt_count_increments_on_repeated_submissions(
    client,
    database,
    active_employees,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    token, employee = login_employee(client, active_employees[0]["id"])

    for score in [0.25, 0.5, 1.0]:
        response = client.put(
            f"/api/me/courses/{course_id}/modules/1",
            headers=auth_headers(token),
            json={"quiz_passed": score == 1.0, "quiz_score": score},
        )
        assert response.status_code == 200

    progress = database.get_employee_course_progress(employee["id"], course_id)
    attempt = progress["attempts"]["1"]
    assert attempt["count"] == 3
    assert attempt["last_score"] == 1.0
    assert attempt["last_passed"] is True


def test_course_completes_after_all_modules_have_video_and_passing_quiz(
    client,
    database,
    active_employees,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    token, employee = login_employee(client, active_employees[0]["id"])

    for module_number in [1, 2]:
        video_response = client.put(
            f"/api/me/courses/{course_id}/modules/{module_number}",
            headers=auth_headers(token),
            json={"video_watched": True},
        )
        quiz_response = client.put(
            f"/api/me/courses/{course_id}/modules/{module_number}",
            headers=auth_headers(token),
            json={"quiz_passed": True, "quiz_score": 1.0},
        )
        assert video_response.status_code == 200
        assert quiz_response.status_code == 200

    progress = database.get_employee_course_progress(employee["id"], course_id)
    assert progress["status"] == "completed"
    assert progress["completed_at"]


def test_overdue_is_applied_on_course_fetch_without_overwriting_completed(
    client,
    database,
    active_employees,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    token_pending, employee_pending = login_employee(client, active_employees[0]["id"])
    token_complete, employee_complete = login_employee(client, active_employees[1]["id"])
    expired_deadline = (datetime.now() - timedelta(days=1)).isoformat()

    pending_progress = database.get_employee_course_progress(employee_pending["id"], course_id)
    pending_progress["deadline"] = expired_deadline
    database.save_employee_course_progress(employee_pending["id"], course_id, pending_progress)

    completed_progress = database.get_employee_course_progress(employee_complete["id"], course_id)
    completed_progress["status"] = "completed"
    completed_progress["completed_at"] = datetime.now().isoformat()
    completed_progress["deadline"] = expired_deadline
    database.save_employee_course_progress(employee_complete["id"], course_id, completed_progress)

    pending_response = client.get("/api/me/courses", headers=auth_headers(token_pending))
    completed_response = client.get("/api/me/courses", headers=auth_headers(token_complete))

    assert pending_response.status_code == 200
    assert completed_response.status_code == 200
    assert pending_response.json()[0]["employee_status"] == "overdue"
    assert completed_response.json()[0]["employee_status"] == "completed"
