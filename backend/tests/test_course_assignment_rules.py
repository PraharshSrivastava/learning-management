from datetime import datetime, timedelta

from conftest import auth_headers, login_employee


def _course(course_id="assignment-course-1"):
    return {
        "id": course_id,
        "course_id": course_id,
        "title": "Assignment Rule Course",
        "course_description": "Course for assignment tests",
        "modules": [
            {
                "module_number": 1,
                "title": "Module 1",
                "video_url": "assets/videos/test/module_1.mp4",
                "quiz": [],
            }
        ],
        "images": [],
        "thumbnail": f"assets/images/course_thumbnails/{course_id}.png",
        "thumbnail_url": f"assets/images/course_thumbnails/{course_id}.png",
    }


def _ready_draft_course(course_id="assignment-course-1"):
    from pipelines.thumbnail_generator import course_thumbnail_signature

    course = {
        "id": course_id,
        "course_name": "Assignment Rule Course",
        "course_description": "Course for assignment tests",
        "course_objective": "Test assignment",
        "course_difficulty": "Beginner",
        "language": "English",
        "target_audience": "Employees",
        "modules": [
            {
                "module_number": 1,
                "title": "Module 1",
                "text": "Module content",
                "start_line": "1",
                "end_line": "10",
                "video_path": "assets/videos/test/module_1.mp4",
                "quiz": {
                    "questions": [
                        {
                            "question_text": "Question 1",
                            "options": [
                                {"key": "A", "text": "A"},
                                {"key": "B", "text": "B"},
                            ],
                            "correct_option": "A",
                        }
                    ]
                },
            }
        ],
    }
    thumbnail = f"assets/images/course_thumbnails/{course_id}.png"
    course["thumbnail"] = thumbnail
    course["thumbnail_url"] = thumbnail
    course["thumbnail_prompt_hash"] = course_thumbnail_signature(course)
    return course


def _unfinished_draft_course(course_id="unfinished-course-1"):
    course = _ready_draft_course(course_id)
    course["modules"][0].pop("video_path")
    return course


def _first_employee(database, **criteria):
    for employee in database.list_employees():
        if all(employee[key] == value for key, value in criteria.items()):
            return employee
    raise AssertionError(f"No employee found for {criteria}")


def test_department_and_role_rule_uses_and_logic_with_exclusions(
    client,
    database,
    employee_routes,
):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    sales_associate = _first_employee(database, department="Sales", role="Associate")
    operations_manager = _first_employee(database, department="Operations", role="Manager")
    database.save_all_courses([_course()], "published")

    rule = database.save_assignment_rule(
        "assignment-course-1",
        {
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "exclude_employee_ids": [sales_manager["id"]],
            "deadline_days": 11,
        },
        publish=True,
    )

    assert not database.employee_matches_assignment_rule(sales_manager, rule)
    assert not database.employee_matches_assignment_rule(sales_associate, rule)
    assert not database.employee_matches_assignment_rule(operations_manager, rule)

    employee_routes.assign_published_course_to_matching_employees("assignment-course-1")
    assert database.get_employee_course_progress(sales_manager["id"], "assignment-course-1") is None
    assert database.get_employee_course_progress(sales_associate["id"], "assignment-course-1") is None
    assert database.get_employee_course_progress(operations_manager["id"], "assignment-course-1") is None


def test_department_and_role_rule_assigns_matching_employee(database, employee_routes):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    database.save_all_courses([_course()], "published")
    database.save_assignment_rule(
        "assignment-course-1",
        {
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 11,
        },
        publish=True,
    )

    employee_routes.assign_published_course_to_matching_employees("assignment-course-1")

    progress = database.get_employee_course_progress(sales_manager["id"], "assignment-course-1")
    assert progress is not None
    assert progress["status"] == "pending"
    deadline = datetime.fromisoformat(progress["deadline"])
    assigned_at = datetime.fromisoformat(progress["assigned_at"])
    assert 10 <= (deadline - assigned_at).days <= 11


def test_all_employees_rule_respects_department_and_role_exclusions(
    database,
    employee_routes,
):
    sales_employee = _first_employee(database, department="Sales")
    manager = _first_employee(database, role="Manager")
    allowed_employee = next(
        employee
        for employee in database.list_employees()
        if employee["department"] != "Sales" and employee["role"] != "Manager"
    )
    database.save_all_courses([_course()], "published")
    database.save_assignment_rule(
        "assignment-course-1",
        {
            "include_all": True,
            "exclude_departments": ["Sales"],
            "exclude_roles": ["Manager"],
            "deadline_days": 5,
        },
        publish=True,
    )

    employee_routes.assign_published_course_to_matching_employees("assignment-course-1")

    assert database.get_employee_course_progress(sales_employee["id"], "assignment-course-1") is None
    assert database.get_employee_course_progress(manager["id"], "assignment-course-1") is None
    assert database.get_employee_course_progress(allowed_employee["id"], "assignment-course-1")


def test_joined_less_than_days_rule_and_future_catch_up(
    client,
    database,
):
    newer_employee = next(
        employee
        for employee in database.list_employees()
        if (datetime.now().date() - datetime.fromisoformat(employee["join_date"]).date()).days < 30
    )
    older_employee = next(
        employee
        for employee in database.list_employees()
        if (datetime.now().date() - datetime.fromisoformat(employee["join_date"]).date()).days > 120
    )
    database.save_all_courses([_course()], "published")
    database.save_assignment_rule(
        "assignment-course-1",
        {
            "include_all": False,
            "joined_less_than_days_ago": 30,
            "deadline_days": 3,
        },
        publish=True,
    )

    newer_token, newer = login_employee(client, newer_employee["id"])
    older_token, older = login_employee(client, older_employee["id"])
    newer_courses = client.get("/api/me/courses", headers=auth_headers(newer_token)).json()
    older_courses = client.get("/api/me/courses", headers=auth_headers(older_token)).json()

    assert newer["id"] == newer_employee["id"]
    assert older["id"] == older_employee["id"]
    assert [course["course_id"] for course in newer_courses] == ["assignment-course-1"]
    assert older_courses == []
    progress = database.get_employee_course_progress(newer["id"], "assignment-course-1")
    assert progress is not None
    deadline = datetime.fromisoformat(progress["deadline"])
    assigned_at = datetime.fromisoformat(progress["assigned_at"])
    assert 2 <= (deadline - assigned_at).days <= 3


def test_republish_removes_non_matching_employee_and_readd_starts_fresh(
    database,
    employee_routes,
):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    operations_manager = _first_employee(database, department="Operations", role="Manager")
    course_id = "assignment-course-1"
    database.save_all_courses([_course(course_id)], "published")
    database.save_assignment_rule(
        course_id,
        {
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 7,
        },
        publish=True,
    )
    employee_routes.assign_published_course_to_matching_employees(course_id)
    progress = database.get_employee_course_progress(sales_manager["id"], course_id)
    progress["modules"] = {"1": {"video_watched": True}}
    database.save_employee_course_progress(sales_manager["id"], course_id, progress)

    database.save_assignment_rule(
        course_id,
        {
            "include_all": False,
            "include_departments": ["Operations"],
            "include_roles": ["Manager"],
            "deadline_days": 7,
        },
        publish=True,
    )
    changes = employee_routes.assign_published_course_to_matching_employees(course_id)

    assert changes["removed"] >= 1
    assert database.get_employee_course_progress(sales_manager["id"], course_id) is None
    assert database.get_employee_course_progress(operations_manager["id"], course_id) is not None

    database.save_assignment_rule(
        course_id,
        {
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 7,
        },
        publish=True,
    )
    employee_routes.assign_published_course_to_matching_employees(course_id)
    fresh_progress = database.get_employee_course_progress(sales_manager["id"], course_id)

    assert fresh_progress is not None
    assert fresh_progress["modules"] == {}
    assert fresh_progress["attempts"] == {}
    assert fresh_progress["status"] == "pending"


def test_republish_deadline_change_preserves_matching_employee_progress(
    database,
    employee_routes,
):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    course_id = "assignment-course-1"
    database.save_all_courses([_course(course_id)], "published")
    database.save_assignment_rule(
        course_id,
        {
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 7,
        },
        publish=True,
    )
    employee_routes.assign_published_course_to_matching_employees(course_id)
    progress = database.get_employee_course_progress(sales_manager["id"], course_id)
    original_assigned_at = progress["assigned_at"]
    original_deadline = progress["deadline"]
    progress["status"] = "started"
    progress["started_at"] = datetime.now().isoformat()
    progress["modules"] = {"1": {"video_watched": True}}
    database.save_employee_course_progress(sales_manager["id"], course_id, progress)

    database.save_assignment_rule(
        course_id,
        {
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 14,
        },
        publish=True,
    )
    changes = employee_routes.assign_published_course_to_matching_employees(
        course_id,
        deadline_changed=True,
    )
    updated = database.get_employee_course_progress(sales_manager["id"], course_id)

    assert changes["deadline_updates"] >= 1
    assert updated["assigned_at"] == original_assigned_at
    assert updated["deadline"] != original_deadline
    assert updated["status"] == "started"
    assert updated["modules"] == {"1": {"video_watched": True}}
    assert datetime.fromisoformat(updated["deadline"]) > datetime.fromisoformat(original_deadline)


def test_saved_deadline_change_updates_existing_deadline_on_publish(
    client,
    database,
):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    course_id = "assignment-course-1"
    published_course = _course(course_id)
    published_course["id"] = "published-row-assignment-course-1"
    database.save_all_courses([published_course], "published")
    database.save_all_courses([_ready_draft_course(course_id)], "draft")

    first = client.post(
        f"/api/courses/{course_id}/publish-assignment",
        json={
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 7,
        },
    )
    assert first.status_code == 200
    original = database.get_employee_course_progress(sales_manager["id"], course_id)

    saved = client.put(
        f"/api/courses/{course_id}/assignment",
        json={
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 21,
        },
    )
    assert saved.status_code == 200

    second = client.post(
        f"/api/courses/{course_id}/publish-assignment",
        json={
            "include_all": False,
            "include_departments": ["Sales"],
            "include_roles": ["Manager"],
            "deadline_days": 21,
        },
    )
    assert second.status_code == 200
    assert second.json()["deadline_update_count"] >= 1
    updated = database.get_employee_course_progress(sales_manager["id"], course_id)

    assert updated["assigned_at"] == original["assigned_at"]
    assert updated["deadline"] != original["deadline"]
    assert datetime.fromisoformat(updated["deadline"]) > datetime.fromisoformat(original["deadline"])


def test_assignable_courses_only_lists_publishable_drafts(client, database):
    database.save_all_courses(
        [
            _ready_draft_course("ready-course-1"),
            _unfinished_draft_course("unfinished-course-1"),
        ],
        "draft",
    )

    response = client.get("/api/assignment/courses")

    assert response.status_code == 200
    assert [course["id"] for course in response.json()] == ["ready-course-1"]


def test_publish_assignment_rejects_unpublishable_course_without_progress(
    client,
    database,
):
    employee = _first_employee(database, department="Sales", role="Manager")
    database.save_all_courses([_unfinished_draft_course("unfinished-course-1")], "draft")

    response = client.post(
        "/api/courses/unfinished-course-1/publish-assignment",
        json={
            "include_all": True,
            "deadline_days": 7,
        },
    )

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()
    assert database.get_assignment_rule("unfinished-course-1")["published_at"] is None
    assert database.get_employee_course_progress(employee["id"], "unfinished-course-1") is None


def test_group_rule_assigns_managers_or_sales_directors(
    database,
    employee_routes,
):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    sales_director = _first_employee(database, department="Sales", role="Director")
    operations_manager = _first_employee(database, department="Operations", role="Manager")
    sales_associate = _first_employee(database, department="Sales", role="Associate")
    course_id = "assignment-course-1"
    database.save_all_courses([_course(course_id)], "published")
    database.save_assignment_rule(
        course_id,
        {
            "include_all": False,
            "include_groups": [
                {"roles": ["Manager"]},
                {"departments": ["Sales"], "roles": ["Director"]},
            ],
            "deadline_days": 7,
        },
        publish=True,
    )

    employee_routes.assign_published_course_to_matching_employees(course_id)

    assert database.get_employee_course_progress(sales_manager["id"], course_id) is not None
    assert database.get_employee_course_progress(sales_director["id"], course_id) is not None
    assert database.get_employee_course_progress(operations_manager["id"], course_id) is not None
    assert database.get_employee_course_progress(sales_associate["id"], course_id) is None


def test_group_rule_assigns_it_managers_or_sales_directors(database):
    it_manager = _first_employee(database, department="IT", role="Manager")
    sales_director = _first_employee(database, department="Sales", role="Director")
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    it_associate = _first_employee(database, department="IT", role="Associate")
    rule = database.save_assignment_rule(
        "assignment-course-1",
        {
            "include_all": False,
            "include_groups": [
                {"departments": ["IT"], "roles": ["Manager"]},
                {"departments": ["Sales"], "roles": ["Director"]},
            ],
            "deadline_days": 7,
        },
        publish=True,
    )

    assert database.employee_matches_assignment_rule(it_manager, rule)
    assert database.employee_matches_assignment_rule(sales_director, rule)
    assert not database.employee_matches_assignment_rule(sales_manager, rule)
    assert not database.employee_matches_assignment_rule(it_associate, rule)


def test_group_exclusions_subtract_from_included_groups(database):
    sales_manager = _first_employee(database, department="Sales", role="Manager")
    operations_manager = _first_employee(database, department="Operations", role="Manager")
    rule = database.save_assignment_rule(
        "assignment-course-1",
        {
            "include_all": False,
            "include_groups": [{"roles": ["Manager"]}],
            "exclude_groups": [{"departments": ["Sales"]}],
            "deadline_days": 7,
        },
        publish=True,
    )

    assert not database.employee_matches_assignment_rule(sales_manager, rule)
    assert database.employee_matches_assignment_rule(operations_manager, rule)
