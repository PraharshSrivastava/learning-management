import csv
import io
from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.api import analytics
from app.core.settings import settings
from app.main import app
from app.repositories import performance_reporting as repository
from app.schemas.performance_reporting import (
    AssignmentListReport,
    EmployeeDetailReport,
    EmployeeListReport,
    PerformanceOverview,
)
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
    monkeypatch.setattr(analytics, "_trainer_scope", lambda *_: "trainer-1")
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


def test_options_query_does_not_load_every_employee(monkeypatch):
    queries = []

    class Connection:
        def execute(self, query, params):
            queries.append((query, params))
            return self

        def fetchall(self):
            return []

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(repository, "get_connection", connection)
    options = repository.list_scope_options("trainer-1")
    assert options == {"courses": [], "departments": [], "mailing_lists": []}
    assert len(queries) == 3
    assert all(params == ("trainer-1",) for _, params in queries)
    assert "SELECT DISTINCT e.department" in queries[1][0]
    assert "e.name" not in queries[1][0]


def test_export_streams_bounded_pages_for_large_report(monkeypatch):
    monkeypatch.setattr(settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(analytics, "_trainer_scope", lambda *_: "trainer-1")
    calls = []

    def assignment_list(trainer_id, **kwargs):
        assert trainer_id == "trainer-1"
        calls.append((kwargs.get("page", 1), kwargs["page_size"]))
        start = (kwargs.get("page", 1) - 1) * kwargs["page_size"]
        return {
            "rows": [
                {"employee_id": str(index), "employee_name": "=unsafe" if index == 0 else "A"}
                for index in range(start, min(start + kwargs["page_size"], 205))
            ],
            "total": 205,
            "generated_at": "2026-09-24T12:00:00",
        }

    monkeypatch.setattr(analytics.reports, "assignment_list", assignment_list)
    response = TestClient(app).get("/api/trainer/performance/export")
    assert response.status_code == 200
    assert response.headers["X-Report-Assignment-Count"] == "205"
    records = list(csv.reader(io.StringIO(response.text)))
    assert len(records) == 206
    assert records[1][1] == "'=unsafe"
    assert calls == [(1, 100), (2, 100), (3, 100)]


def test_employee_totals_use_all_courses_before_pagination(monkeypatch):
    now = datetime.now()
    completed = _row("course-a", now, status="completed")
    started = _row("course-b", now)
    pending = _row("course-c", now, deadline_days=-1)
    for row in (completed, started, pending):
        row.update(employee_id="employee-1", employee_name="Kavya Nair")
    completed.update(average_score=90, scored_modules=2)
    started.update(average_score=70, scored_modules=1, started_at=now.isoformat())
    pending.update(completed_modules=0, average_score=None, scored_modules=0)

    def no_full_report_read(*args, **kwargs):
        raise AssertionError("Employee pagination must not load all assignments into Python")

    monkeypatch.setattr(
        repository,
        "list_assignment_summaries",
        no_full_report_read,
    )
    expected = performance_reporting._employee_summary(
        [performance_reporting._decorate(row, now) for row in (completed, started, pending)], now
    )
    calls = []

    def employee_page(trainer_id, **kwargs):
        calls.append((trainer_id, kwargs))
        return {"employees": 2, "assigned": 4, "completed": 2, "overdue": 1}, [expected]

    monkeypatch.setattr(repository, "employee_page", employee_page)
    result = performance_reporting.employee_list("trainer-1", page_size=1)
    EmployeeListReport.model_validate(result)
    employee = result["rows"][0]
    assert result["total"] == 2
    assert result["summary"] == {"employees": 2, "assigned": 4, "completed": 2, "overdue": 1}
    assert employee["assigned"] == 3 and employee["completed"] == 1
    assert employee["in_progress"] == 1 and employee["not_started"] == 1
    assert employee["completion_rate"] == 33.3
    assert employee["average_score"] == 83.3
    assert employee["overdue"] == 1 and employee["needs_attention"]
    performance_reporting.employee_list(
        "trainer-1",
        search="NEHA",
        attention="overdue",
        sort="completion",
        descending=True,
        page=3,
        page_size=1,
        department="Risk",
    )
    assert calls[-1][0] == "trainer-1"
    assert {key: value for key, value in calls[-1][1].items() if key != "now"} == {
        "search": "NEHA",
        "attention": "overdue",
        "sort": "completion",
        "descending": True,
        "page": 3,
        "page_size": 1,
        "department": "Risk",
    }


def test_employee_detail_keeps_trainer_and_filter_scope(monkeypatch):
    now = datetime.now()
    calls = []

    def rows(trainer_id, **scope):
        calls.append((trainer_id, scope))
        return [_row("one", now)] if trainer_id == "owner" else []

    monkeypatch.setattr(repository, "list_assignment_summaries", rows)
    result = performance_reporting.employee_detail("owner", "employee-one", department="Risk")
    EmployeeDetailReport.model_validate(result)
    assert result["employee"]["assigned"] == 1
    assert len(result["assignments"]) == 1
    assert calls[0] == ("owner", {"employee_id": "employee-one", "department": "Risk"})
    assert performance_reporting.employee_detail("other-trainer", "employee-one") is None


def test_employee_api_contracts_and_validation(monkeypatch):
    monkeypatch.setattr(settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(analytics, "_trainer_scope", lambda *_: "owner")
    monkeypatch.setattr(repository, "list_assignment_summaries", lambda *a, **k: [])
    monkeypatch.setattr(
        repository,
        "employee_page",
        lambda *a, **k: ({"employees": 0, "assigned": 0, "completed": 0, "overdue": 0}, []),
    )
    client = TestClient(app)
    response = client.get("/api/trainer/performance/employees")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert client.get("/api/trainer/performance/employees/missing").status_code == 404
    assert client.get("/api/trainer/performance/employees?page=0").status_code == 422
    assert client.get("/api/trainer/performance/employees?sort=unsafe").status_code == 422


def test_employee_query_aggregates_and_paginates_in_sql(monkeypatch):
    calls = []

    class Connection:
        def execute(self, query, params):
            calls.append((query, params))
            return self

        def fetchall(self):
            return [
                {
                    "summary_employees": 30,
                    "summary_assigned": 120,
                    "summary_completed": 50,
                    "summary_overdue": 10,
                    "employee_id": None,
                }
            ]

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(repository, "get_connection", connection)
    summary, rows = repository.employee_page(
        "trainer-1",
        search="Alice",
        attention="needs_attention",
        sort="completion",
        descending=True,
        page=3,
        page_size=10,
        now=datetime.now(),
        department="Risk",
    )
    query, params = calls[0]
    assert summary == {"employees": 30, "assigned": 120, "completed": 50, "overdue": 10}
    assert rows == []  # Empty pages still carry full filtered totals.
    assert "GROUP BY employee_id" in query
    assert "FROM employees WHERE" in query and "needs_attention" in query
    assert "FROM filtered" in query
    assert "c.trainer_id = ?" in query and "e.department = ?" in query
    assert "ORDER BY completion_rate DESC, employee_id DESC" in query
    assert "LIMIT ? OFFSET ?" in query
    assert params[-4:] == ["Alice", "Alice", 10, 20]
    assert "SUM(score_percent * scored_modules)" in query


def test_employee_export_retains_filters_and_streams_all_pages(monkeypatch):
    monkeypatch.setattr(settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(analytics, "_trainer_scope", lambda *_: "owner")
    calls = []

    def employee_list(trainer_id, **kwargs):
        calls.append((trainer_id, kwargs))
        start = (kwargs.get("page", 1) - 1) * kwargs["page_size"]
        return {
            "rows": [
                {
                    "employee_id": str(index),
                    "employee_name": "=unsafe" if index == 0 else "Alice",
                    "assigned": 4,
                    "completed": 2,
                    "completion_rate": 50,
                }
                for index in range(start, min(start + kwargs["page_size"], 205))
            ],
            "total": 205,
            "generated_at": "2026-09-29T12:00:00",
        }

    monkeypatch.setattr(analytics.reports, "employee_list", employee_list)
    response = TestClient(app).get(
        "/api/trainer/performance/employees/export",
        params={
            "search": "Alice",
            "attention": "needs_attention",
            "department": "Risk",
            "course_id": "course-1",
            "mailing_list": "Cohort A",
            "joined_less_than_days_ago": 30,
            "sort": "overdue",
            "descending": "true",
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Report-Employee-Count"] == "205"
    assert "performance-employees.csv" in response.headers["Content-Disposition"]
    records = list(csv.DictReader(io.StringIO(response.text)))
    assert len(records) == 205
    assert records[0]["employee_name"] == "'=unsafe"
    assert [kwargs["page"] for _, kwargs in calls] == [1, 2, 3]
    for trainer_id, kwargs in calls:
        assert trainer_id == "owner"
        assert kwargs["page_size"] == 100
        assert kwargs["search"] == "Alice" and kwargs["attention"] == "needs_attention"
        assert kwargs["department"] == "Risk" and kwargs["course_id"] == "course-1"
        assert kwargs["mailing_list"] == "Cohort A"
        assert kwargs["joined_less_than_days_ago"] == 30
        assert kwargs["sort"] == "overdue" and kwargs["descending"] is True


def test_employee_export_empty_result_has_header_and_validates_params(monkeypatch):
    monkeypatch.setattr(settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(analytics, "_trainer_scope", lambda *_: "owner")
    monkeypatch.setattr(
        analytics.reports,
        "employee_list",
        lambda *a, **k: {
            "rows": [],
            "total": 0,
            "generated_at": "2026-09-29T12:00:00",
        },
    )
    client = TestClient(app)
    result = client.get("/api/trainer/performance/employees/export?search=no-match")
    assert result.status_code == 200
    assert result.headers["X-Report-Employee-Count"] == "0"
    assert len(list(csv.reader(io.StringIO(result.text)))) == 1
    assert (
        client.get("/api/trainer/performance/employees/export?attention=invalid").status_code == 422
    )
    assert client.get("/api/trainer/performance/employees/export?sort=deadline").status_code == 422


def test_employee_export_rejects_unauthenticated_production_request(monkeypatch):
    monkeypatch.setattr(settings, "hub_launch_dev_mode", False)
    response = TestClient(app).get("/api/trainer/performance/employees/export")
    assert response.status_code == 403
