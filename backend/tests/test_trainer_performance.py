from datetime import datetime, timedelta


def _published_course(course_id="performance-course-1"):
    return {
        "id": f"published-row-{course_id}",
        "course_id": course_id,
        "title": "Performance Course",
        "course_description": "Visible to employees",
        "modules": [
            {
                "module_number": 1,
                "title": "Module 1",
                "video_url": "/assets/videos/module-1.mp4",
                "quiz": [{"question": "Q1", "options": ["A"], "correct": "A"}],
            },
            {
                "module_number": 2,
                "title": "Module 2",
                "video_url": "/assets/videos/module-2.mp4",
                "quiz": [{"question": "Q2", "options": ["A"], "correct": "A"}],
            },
        ],
        "images": [],
    }


def _first_employee(database, **criteria):
    for employee in database.list_employees():
        if all(employee[key] == value for key, value in criteria.items()):
            return employee
    raise AssertionError(f"No employee found for {criteria}")


def test_trainer_performance_summary_and_module_metrics(client, database):
    course_id = "performance-course-1"
    now = datetime.now()
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    operations_associate = _first_employee(database, department="Operations", role="Associate")
    database.save_all_courses([_published_course(course_id)], "published")
    database.save_employee_course_progress(
        sales_manager["id"],
        course_id,
        {
            "status": "completed",
            "assigned_at": (now - timedelta(days=8)).isoformat(),
            "deadline": (now + timedelta(days=2)).isoformat(),
            "started_at": (now - timedelta(days=7)).isoformat(),
            "completed_at": (now - timedelta(days=1)).isoformat(),
            "modules": {
                "1": {"video_watched": True, "quiz_passed": True, "quiz_score": 0.8},
                "2": {"video_watched": True, "quiz_passed": True, "quiz_score": 1.0},
            },
            "attempts": {
                "1": {"count": 2, "last_score": 0.8, "last_passed": True},
                "2": {"count": 1, "last_score": 1.0, "last_passed": True},
            },
            "last_activity_at": now.isoformat(),
        },
    )
    database.save_employee_course_progress(
        operations_associate["id"],
        course_id,
        {
            "status": "pending",
            "assigned_at": (now - timedelta(days=3)).isoformat(),
            "deadline": (now + timedelta(days=1)).isoformat(),
            "modules": {},
            "attempts": {},
            "last_activity_at": (now - timedelta(days=3)).isoformat(),
        },
    )

    response = client.get("/api/trainer/performance")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["assigned"] == 2
    assert body["summary"]["completed"] == 1
    assert body["summary"]["pending"] == 1
    assert body["summary"]["completion_rate"] == 50
    completed_row = next(row for row in body["rows"] if row["employee"]["id"] == sales_manager["id"])
    assert completed_row["completed_modules"] == 2
    assert completed_row["completion_percent"] == 100
    assert completed_row["total_attempts"] == 3
    assert completed_row["best_score"] == 1.0
    assert len(completed_row["modules"]) == 2


def test_trainer_performance_filters_match_assignment_dimensions(client, database):
    course_id = "performance-course-1"
    now = datetime.now()
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    operations_manager = _first_employee(database, department="Operations", role="Manager")
    database.save_all_courses([_published_course(course_id)], "published")
    for employee in [sales_manager, operations_manager]:
        database.save_employee_course_progress(
            employee["id"],
            course_id,
            {
                "status": "started",
                "assigned_at": now.isoformat(),
                "deadline": (now + timedelta(days=8)).isoformat(),
                "modules": {},
                "attempts": {},
                "last_activity_at": now.isoformat(),
            },
        )

    response = client.get(
        "/api/trainer/performance",
        params={"department": "Sales", "role": "Manager", "status": "started"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["assigned"] == 1
    assert body["rows"][0]["employee"]["id"] == sales_manager["id"]
    assert body["breakdowns"]["departments"][0]["label"] == "Sales"


def test_trainer_performance_filters_recent_joiners(client, database):
    course_id = "performance-course-1"
    now = datetime.now()
    recent_employee = next(
        employee
        for employee in database.list_employees()
        if (now.date() - datetime.fromisoformat(employee["join_date"]).date()).days < 30
    )
    older_employee = next(
        employee
        for employee in database.list_employees()
        if (now.date() - datetime.fromisoformat(employee["join_date"]).date()).days > 120
    )
    database.save_all_courses([_published_course(course_id)], "published")
    for employee in [recent_employee, older_employee]:
        database.save_employee_course_progress(
            employee["id"],
            course_id,
            {
                "status": "pending",
                "assigned_at": now.isoformat(),
                "deadline": (now + timedelta(days=8)).isoformat(),
                "modules": {},
                "attempts": {},
                "last_activity_at": now.isoformat(),
            },
        )

    response = client.get(
        "/api/trainer/performance",
        params={"joined_less_than_days_ago": 30},
    )

    assert response.status_code == 200
    employee_ids = {row["employee"]["id"] for row in response.json()["rows"]}
    assert recent_employee["id"] in employee_ids
    assert older_employee["id"] not in employee_ids
