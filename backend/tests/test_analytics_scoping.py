from datetime import datetime, timedelta

from app.services import analytics


class _Employees:
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
