from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.api import analytics
from app.core.settings import settings
from app.main import app
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
    monkeypatch.setattr(
        performance_reporting.reports,
        "assignment_page",
        lambda *args, **kwargs: (1, [rows[0]]),
    )
    filtered = performance_reporting.assignment_list("trainer-1", status="due_soon")
    AssignmentListReport.model_validate(filtered)
    assert [row["assignment_id"] for row in filtered["rows"]] == ["pending"]


def test_inactivity_uses_learner_activity_and_pagination(monkeypatch):
    now = datetime.now()
    old = _row("old", now, learner_days=16, failed=2)
    recent = _row("recent", now, learner_days=2)
    assert performance_reporting._decorate(old, now)["inactive"]
    assert performance_reporting._decorate(old, now)["repeated_failures"]
    assert not performance_reporting._decorate(recent, now)["inactive"]
    calls = []

    def page(*args, **kwargs):
        calls.append(kwargs)
        return 2, [recent]

    monkeypatch.setattr(performance_reporting.reports, "assignment_page", page)
    result = performance_reporting.assignment_list("trainer-1", page=2, page_size=1)
    assert result["total"] == 2
    assert len(result["rows"]) == 1
    assert calls[0]["page"] == 2 and calls[0]["page_size"] == 1


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


def test_assignment_page_limits_and_filters_in_sql(monkeypatch):
    calls = []

    class Connection:
        def execute(self, query, params):
            calls.append((query, params))
            return self

        def fetchall(self):
            return [{"report_total": 0, "assignment_id": None}]

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(repository, "get_connection", connection)
    total, rows = repository.assignment_page(
        "trainer-1",
        status="overdue",
        search="Alice",
        sort="progress",
        descending=True,
        page=3,
        page_size=25,
        now=datetime.now(),
        department="Risk",
    )
    query, params = calls[0]
    assert total == 0 and rows == []
    assert "SELECT COUNT(*) FROM filtered" in query
    assert "report_status = ?" in query
    assert "ORDER BY completion_percent DESC, assignment_id DESC" in query
    assert "LIMIT ? OFFSET ?" in query
    assert "c.trainer_id = ?" in query and "e.department = ?" in query
    assert params[-5:] == ["Alice", "Alice", "Alice", 25, 50]


def test_overview_accepts_trend_days_from_browser_query(monkeypatch):
    monkeypatch.setattr(settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(analytics, "_trainer_id", lambda *_: "trainer-1")
    monkeypatch.setattr(
        performance_reporting.reports,
        "list_assignment_summaries",
        lambda *args, **kwargs: [],
    )
    client = TestClient(app)
    for days in (30, 90):
        response = client.get("/api/trainer/performance/overview", params={"trend_days": str(days)})
        assert response.status_code == 200
        assert len(response.json()["completion_trend"]) == days
    assert client.get("/api/trainer/performance/overview?trend_days=31").status_code == 422
