from datetime import datetime

from app.repositories.assignments import employee_matches_assignment_rule
from app.services import assignments as assignment_service


def _employee(**overrides):
    employee = {
        "employee_id": "emp_0001",
        "status": "active",
        "department": "Risk",
        "mailing_lists": [
            "LMS-All",
            "Risk-Training",
        ],
        "job_title": "Associate",
        "join_date": "2026-08-01",
    }
    employee.update(overrides)
    return employee


def test_assignment_matches_employee_department_and_group_cn_mailing_list():
    rule = {
        "include_all": False,
        "include_groups": [
            {
                "departments": ["Risk"],
                "mailing_lists": ["Risk-Training"],
            }
        ],
        "exclude_groups": [],
    }

    assert employee_matches_assignment_rule(_employee(), rule, datetime(2026, 8, 18))


def test_assignment_does_not_match_without_required_group_cn_mailing_list():
    rule = {
        "include_all": False,
        "include_groups": [
            {
                "departments": ["Risk"],
                "mailing_lists": ["Compliance-Training"],
            }
        ],
        "exclude_groups": [],
    }

    assert not employee_matches_assignment_rule(_employee(), rule, datetime(2026, 8, 18))


def test_job_title_no_longer_drives_assignment_matching():
    rule = {
        "include_all": False,
        "include_groups": [{"job_titles": ["Associate"]}],
        "exclude_groups": [],
    }

    assert not employee_matches_assignment_rule(_employee(), rule, datetime(2026, 8, 18))


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 8, 20, 12, 0, 0)
        return value if tz is None else value.replace(tzinfo=tz)


class _FakeEmployees:
    def __init__(self, employees):
        self.employees = employees

    def get(self, employee_id):
        return self.employees.get(employee_id)


class _FakeCourses:
    def __init__(self, courses):
        self.courses = courses

    def list(self, status=None):
        return [
            course
            for course in self.courses
            if status is None or course.get("status") == status
        ]


class _FakeAssignments:
    def __init__(self, rules):
        self.rules = rules

    def get(self, course_id):
        return self.rules[course_id]

    def matches_employee(self, employee, rule, as_of=None):
        return employee_matches_assignment_rule(employee, rule, as_of)


class _FakeProgress:
    def __init__(self, rows):
        self.rows = rows

    def get_for_employee(self, employee_id):
        return self.rows.setdefault(employee_id, {})

    def save(self, employee_id, course_id, progress):
        self.rows.setdefault(employee_id, {})[course_id] = progress


def _published_rule():
    return {
        "include_all": False,
        "include_groups": [{"departments": ["Risk"], "mailing_lists": ["Risk-Training"]}],
        "exclude_groups": [],
        "deadline_days": 7,
        "published_at": "2026-08-18T09:00:00",
        "is_active": True,
    }


def test_reconcile_revokes_started_assignment_when_mailing_list_is_removed(monkeypatch):
    employee_id = "emp_0001"
    progress = {
        employee_id: {
            "course_1": {
                "status": "started",
                "assigned_at": "2026-08-18T12:00:00",
                "deadline": "2026-08-25T12:00:00",
                "started_at": "2026-08-19T12:00:00",
                "completed_at": None,
                "modules": {"1": {"video_watched": True}},
                "attempts": {"1": {"count": 1}},
                "last_activity_at": "2026-08-19T12:00:00",
                "revoked_at": None,
                "assigned_department": "Risk",
                "revoked_reason": None,
            }
        }
    }
    monkeypatch.setattr(assignment_service, "datetime", _FixedDatetime)
    monkeypatch.setattr(
        assignment_service,
        "_employees",
        _FakeEmployees({employee_id: _employee(mailing_lists=[])}),
    )
    monkeypatch.setattr(
        assignment_service,
        "_courses",
        _FakeCourses([{"course_id": "course_1", "status": "published"}]),
    )
    monkeypatch.setattr(assignment_service, "_assignments", _FakeAssignments({"course_1": _published_rule()}))
    monkeypatch.setattr(assignment_service, "_progress", _FakeProgress(progress))

    changes = assignment_service.reconcile_assignments_for_employee(employee_id)

    saved = progress[employee_id]["course_1"]
    assert changes == {"assigned": 0, "removed": 1, "reactivated": 0}
    assert saved["status"] == "revoked"
    assert saved["revoked_reason"] == "assignment_rule_no_longer_matches"
    assert saved["modules"] == {"1": {"video_watched": True}}
    assert saved["attempts"] == {"1": {"count": 1}}


def test_reconcile_reactivates_revoked_assignment_with_remaining_deadline(monkeypatch):
    employee_id = "emp_0001"
    progress = {
        employee_id: {
            "course_1": {
                "status": "revoked",
                "assigned_at": "2026-08-18T12:00:00",
                "deadline": "2026-08-22T12:00:00",
                "started_at": "2026-08-18T13:00:00",
                "completed_at": None,
                "modules": {"1": {"video_watched": True}},
                "attempts": {"1": {"count": 1}},
                "last_activity_at": "2026-08-19T12:00:00",
                "revoked_at": "2026-08-19T12:00:00",
                "assigned_department": "Risk",
                "revoked_reason": "assignment_rule_no_longer_matches",
            }
        }
    }
    monkeypatch.setattr(assignment_service, "datetime", _FixedDatetime)
    monkeypatch.setattr(assignment_service, "_employees", _FakeEmployees({employee_id: _employee()}))
    monkeypatch.setattr(
        assignment_service,
        "_courses",
        _FakeCourses([{"course_id": "course_1", "status": "published"}]),
    )
    monkeypatch.setattr(assignment_service, "_assignments", _FakeAssignments({"course_1": _published_rule()}))
    monkeypatch.setattr(assignment_service, "_progress", _FakeProgress(progress))

    changes = assignment_service.reconcile_assignments_for_employee(employee_id)

    saved = progress[employee_id]["course_1"]
    assert changes == {"assigned": 0, "removed": 0, "reactivated": 1}
    assert saved["status"] == "started"
    assert saved["deadline"] == "2026-08-23T12:00:00"
    assert saved["revoked_at"] is None
    assert saved["revoked_reason"] is None
    assert saved["modules"] == {"1": {"video_watched": True}}
