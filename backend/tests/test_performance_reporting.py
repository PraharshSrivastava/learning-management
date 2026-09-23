from contextlib import contextmanager
from datetime import datetime, timedelta

from app.repositories import performance_reporting as repository
from app.schemas.performance_reporting import AssignmentListReport, PerformanceOverview
from app.services import performance_reporting


def _row(identifier, now, *, status="pending", deadline_days=1, learner_days=None, failed=0):
    return {
        "assignment_id": identifier,
        "employee_id": f"employee-{identifier}",
        "employee_name": f"Learner {identifier}",
        "employee_status": "active",
        "department": "Risk",
        "mailing_lists": ["All staff"],
        "course_id": "course-1",
        "course_name": "AML Essentials",
        "status": status,
        "assigned_at": (now - timedelta(days=20)).isoformat(),
        "deadline": (now + timedelta(days=deadline_days)).isoformat(),
        "started_at": None,
        "completed_at": (now - timedelta(days=1)).isoformat() if status == "completed" else None,
        "last_learner_activity_at": (now - timedelta(days=learner_days)).isoformat()
        if learner_days is not None
        else None,
        "total_modules": 4,
        "completed_modules": 4 if status == "completed" else 1,
        "total_attempts": 1,
        "average_score": 0.8,
        "scored_modules": 1,
        "failed_attempts": failed,
    }


def test_due_soon_excludes_completed_and_overdue(monkeypatch):
    now = datetime.now()
    rows = [
        _row("pending", now),
        _row("completed", now, status="completed"),
        _row("overdue", now, deadline_days=-1),
    ]
    monkeypatch.setattr(
        performance_reporting.reports, "list_assignment_summaries", lambda *args, **kwargs: rows
    )
    result = performance_reporting.overview("trainer-1")
    PerformanceOverview.model_validate(result)
    assert result["summary"]["average_score"] == 80
    assert result["summary"]["due_soon"] == 1
    assert result["summary"]["overdue"] == 1
    filtered = performance_reporting.assignment_list("trainer-1", status="due_soon")
    AssignmentListReport.model_validate(filtered)
    assert [row["assignment_id"] for row in filtered["rows"]] == ["pending"]


def test_inactivity_uses_learner_activity_and_pagination(monkeypatch):
    now = datetime.now()
    rows = [
        _row("old", now, learner_days=16, failed=2),
        _row("recent", now, learner_days=2),
    ]
    monkeypatch.setattr(
        performance_reporting.reports, "list_assignment_summaries", lambda *args, **kwargs: rows
    )
    inactive = performance_reporting.assignment_list("trainer-1", status="inactive", page_size=1)
    assert inactive["total"] == 1
    assert inactive["rows"][0]["assignment_id"] == "old"
    failures = performance_reporting.assignment_list("trainer-1", status="repeated_failures")
    assert [row["assignment_id"] for row in failures["rows"]] == ["old"]
    assert performance_reporting.assignment_list("trainer-1", page=2, page_size=1)["total"] == 2


def test_assignment_query_enforces_trainer_scope(monkeypatch):
    calls = []

    class Connection:
        def execute(self, query, params):
            calls.append((query, params))
            return self

        def fetchall(self):
            return []

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(repository, "get_connection", connection)
    assert (
        repository.list_assignment_summaries("trainer-1", course_id="course-1", mailing_list="Risk")
        == []
    )
    query, params = calls[0]
    assert "c.trainer_id = ?" in query
    assert "ca.course_id = ?" in query
    assert "eg.group_cn = ?" in query
    assert params == ["trainer-1", "course-1", "Risk"]
