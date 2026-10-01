from datetime import datetime, timedelta

import pytest
from starlette.requests import Request

from app.api import analytics as analytics_api
from app.core.exceptions import AuthenticationError
from app.services import analytics, auth


class _Employees:
    def assignment_options(self):
        return {"employees": self.list(), "departments": ["Risk"], "mailing_lists": []}

    def list(self, include_inactive=False):
        return [
            {
                "employee_id": "direct-report",
                "name": "Direct Report",
                "job_title": "Analyst",
                "department": "Risk",
                "join_date": "2025-01-01",
                "status": "active",
                "manager_employee_id": "hod-1",
                "mailing_lists": [],
            },
            {
                "employee_id": "other-employee",
                "name": "Other Employee",
                "job_title": "Analyst",
                "department": "Risk",
                "join_date": "2025-01-01",
                "status": "active",
                "manager_employee_id": "hod-2",
                "mailing_lists": [],
            },
        ]


class _Courses:
    def list(self, status):
        return [
            {
                "course_id": "course-1",
                "course_name": "AML Essentials",
                "trainer_id": "trainer-1",
                "status": "published",
                "modules": [],
            }
        ]


class _Progress:
    def list(self):
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        return [
            {
                "assignment_id": "a-1",
                "employee_id": "direct-report",
                "course_id": "course-1",
                "status": "pending",
                "deadline": deadline,
                "modules": {},
                "attempts": {},
            },
            {
                "assignment_id": "a-2",
                "employee_id": "other-employee",
                "course_id": "course-1",
                "status": "pending",
                "deadline": deadline,
                "modules": {},
                "attempts": {},
            },
        ]


class _Assignments:
    def get(self, course_id):
        return {"course_id": course_id, "published_at": "2026-01-01", "is_active": True}


def test_hod_performance_contains_only_direct_reports(monkeypatch):
    monkeypatch.setattr(analytics, "_employees", _Employees())
    monkeypatch.setattr(analytics, "_courses", _Courses())
    monkeypatch.setattr(analytics, "_progress", _Progress())
    monkeypatch.setattr(analytics, "_assignments", _Assignments())

    result = analytics.api_trainer_performance(manager_employee_id="hod-1")

    assert result["summary"]["assigned"] == 1
    assert [row["employee"]["employee_id"] for row in result["rows"]] == ["direct-report"]
    assert [employee["employee_id"] for employee in result["options"]["employees"]] == [
        "direct-report"
    ]


class _SharedCourses(_Courses):
    def list(self, status):
        assert status == "published"
        return super().list(status) + [
            {"course_id": "course-2", "course_name": "Risk Training",
             "trainer_id": "trainer-2", "status": "published", "modules": []}
        ]


class _SharedProgress(_Progress):
    def list(self):
        return super().list() + [
            {"assignment_id": "a-3", "employee_id": "other-employee",
             "course_id": "course-2", "status": "completed",
             "deadline": (datetime.now() + timedelta(days=1)).isoformat(),
             "modules": {}, "attempts": {}}
        ]


@pytest.fixture
def shared_reporting(monkeypatch):
    monkeypatch.setattr(analytics, "_employees", _Employees())
    monkeypatch.setattr(analytics, "_courses", _SharedCourses())
    monkeypatch.setattr(analytics, "_progress", _SharedProgress())
    monkeypatch.setattr(analytics, "_assignments", _Assignments())
    # Use the actual trainer authenticator, with isolated local sessions.
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(auth, "_hub_session", lambda request, app: None)
    monkeypatch.setattr(auth, "_local_trainer_sessions", {
        "first-token": "trainer-1", "second-token": "trainer-2",
        "inactive-token": "inactive-trainer",
    })
    monkeypatch.setattr(auth, "_local_employee_sessions", {"employee-token": "direct-report"})

    class Trainers:
        def get(self, trainer_id):
            return {"trainer_id": trainer_id,
                    "status": "inactive" if trainer_id == "inactive-trainer" else "active"}

    monkeypatch.setattr(auth, "_trainers", Trainers())
    return Request({"type": "http", "headers": []})


@pytest.mark.parametrize("token", ["first-token", "second-token"])
def test_every_authorized_trainer_sees_other_trainers_performance(shared_reporting, token):
    result = analytics_api.trainer_performance(shared_reporting, authorization=f"Bearer {token}")
    assert result["summary"]["assigned"] == 3
    assert result["summary"]["completed"] == 1
    assert {row["course"]["course_id"] for row in result["rows"]} == {"course-1", "course-2"}
    assert {course["course_id"] for course in result["options"]["courses"]} == {"course-1", "course-2"}


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Bearer employee-token", "Bearer inactive-token"])
def test_shared_reporting_still_requires_active_trainer(shared_reporting, authorization):
    with pytest.raises(AuthenticationError):
        analytics_api.trainer_performance(shared_reporting, authorization=authorization)


def test_shared_reporting_preserves_filters(shared_reporting):
    result = analytics_api.trainer_performance(
        shared_reporting, authorization="Bearer first-token", course_id="course-2",
        employee_id="other-employee", department="Risk", status="completed",
    )
    assert result["summary"]["assigned"] == 1
    assert result["rows"][0]["course"]["course_id"] == "course-2"
    assert result["rows"][0]["employee"]["employee_id"] == "other-employee"


def test_shared_reporting_does_not_expand_hod_scope(shared_reporting):
    result = analytics.api_trainer_performance(manager_employee_id="hod-1")
    assert result["summary"]["assigned"] == 1
    assert {row["employee"]["employee_id"] for row in result["rows"]} == {"direct-report"}


def test_production_hub_trainer_gets_shared_report(shared_reporting, monkeypatch):
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", False)
    monkeypatch.setattr(auth, "_hub_session", lambda request, app: {"sub": 22} if app == "trainer" else None)

    class Employees:
        def get_by_hub_user_id(self, hub_id):
            assert hub_id == 22
            return {"employee_id": "kiran", "status": "active"}

    class Trainers:
        def upsert_from_employee(self, employee):
            return {"trainer_id": employee["employee_id"], "status": "active"}

    monkeypatch.setattr(auth, "_employees", Employees())
    monkeypatch.setattr(auth, "_trainers", Trainers())
    result = analytics_api.trainer_performance(shared_reporting, authorization=None)
    assert result["summary"]["assigned"] == 3


def test_shared_report_still_excludes_revoked_and_disabled_assignments(shared_reporting, monkeypatch):
    class Progress(_SharedProgress):
        def list(self):
            return super().list() + [{**super().list()[0], "assignment_id": "revoked", "status": "revoked"}]

    class Assignments(_Assignments):
        def get(self, course_id):
            return {**super().get(course_id), "is_active": course_id != "course-2"}

    monkeypatch.setattr(analytics, "_progress", Progress())
    monkeypatch.setattr(analytics, "_assignments", Assignments())
    result = analytics_api.trainer_performance(shared_reporting, authorization="Bearer second-token")
    assert result["summary"]["assigned"] == 2
    assert {row["course"]["course_id"] for row in result["rows"]} == {"course-1"}


def test_shared_reporting_does_not_grant_course_edit_or_assignment_rights(monkeypatch):
    from app.core.exceptions import NotFoundError
    from app.schemas.course import CourseUpdateRequest
    from app.services import assignments
    from app.services.courses import CourseService

    class ForeignCourseRepository:
        def get_draft_for_trainer(self, course_id, trainer_id):
            assert (course_id, trainer_id) == ("course-1", "trainer-2")
            return None

        def list_for_trainer(self, trainer_id):
            assert trainer_id == "trainer-2"
            return []

    repository = ForeignCourseRepository()
    with pytest.raises(NotFoundError):
        CourseService(repository).update_course("course-1", CourseUpdateRequest(course_name="Changed"), "trainer-2")
    monkeypatch.setattr(assignments, "_courses", repository)
    with pytest.raises(NotFoundError):
        assignments.api_get_course_assignment("course-1", "trainer-2")


def test_due_soon_filter_uses_configured_window(monkeypatch):
    monkeypatch.setattr(analytics, "_employees", _Employees())
    monkeypatch.setattr(analytics, "_courses", _Courses())
    monkeypatch.setattr(analytics, "_progress", _Progress())
    monkeypatch.setattr(analytics, "_assignments", _Assignments())
    monkeypatch.setattr(analytics.settings, "email_due_soon_days", 2)

    result = analytics.api_trainer_performance(
        manager_employee_id="hod-1",
        status="due_soon",
    )

    assert result["summary"]["assigned"] == 1
