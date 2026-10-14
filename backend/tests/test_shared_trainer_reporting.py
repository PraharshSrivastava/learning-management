"""All-course reporting stays independent from course authoring permission."""

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import analytics
from app.core.exceptions import install_exception_handlers
from app.repositories import performance_reporting as repository
from app.schemas.reporting_scope import TrainerPerformanceScope, owner_filter
from app.services import auth


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(auth, "_hub_session", lambda *_: None)
    monkeypatch.setattr(
        auth, "_local_trainer_sessions", {"active": "trainer-a", "inactive": "trainer-b"}
    )
    monkeypatch.setattr(
        auth._trainers,
        "get",
        lambda identity: {
            "trainer_id": identity,
            "status": "inactive" if identity == "trainer-b" else "active",
        },
    )
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(analytics.router)
    return TestClient(app)


ENDPOINTS = [
    ("overview", "overview"),
    ("courses", "course_list"),
    ("courses/foreign-course", "course_detail"),
    ("assignments", "assignment_list"),
    ("assignments/foreign-assignment", "assignment_detail"),
    ("employees", "employee_list"),
    ("employees/foreign-employee", "employee_detail"),
    ("export", "assignment_list"),
    ("employees/export", "employee_list"),
]


class ScopeObserved(Exception):
    pass


@pytest.mark.parametrize("path,operation", ENDPOINTS)
def test_improved_reports_use_authenticated_all_course_scope(client, monkeypatch, path, operation):
    def report(scope, *args, **kwargs):
        assert scope == TrainerPerformanceScope("trainer-a", all_courses=True)
        raise ScopeObserved()

    monkeypatch.setattr(analytics.reports, operation, report)
    with pytest.raises(ScopeObserved):
        client.get("/api/trainer/performance/" + path, headers={"Authorization": "Bearer active"})


@pytest.mark.parametrize("path,operation", ENDPOINTS + [("options", "unused")])
@pytest.mark.parametrize("token", [None, "invalid", "inactive"])
def test_improved_reports_deny_non_active_trainer(client, path, operation, token):
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    assert client.get("/api/trainer/performance/" + path, headers=headers).status_code == 401


def test_options_use_the_same_all_course_scope(client, monkeypatch):
    def options(scope):
        assert scope == TrainerPerformanceScope("trainer-a", all_courses=True)
        return {"courses": [], "departments": [], "mailing_lists": []}

    monkeypatch.setattr(repository, "list_scope_options", options)
    assert (
        client.get(
            "/api/trainer/performance/options", headers={"Authorization": "Bearer active"}
        ).status_code
        == 200
    )


def test_scope_requires_explicit_verified_identity():
    for identity in (None, "", " "):
        with pytest.raises(ValueError):
            TrainerPerformanceScope(identity, all_courses=True)
        with pytest.raises(ValueError):
            owner_filter(identity)
    assert owner_filter("trainer-a") == ("c.trainer_id = ? AND ", ("trainer-a",))


def test_all_course_scope_preserves_eligibility_and_bound_filters(monkeypatch):
    calls = []

    class Connection:
        def execute(self, query, params):
            calls.append((query, params))
            return self

        def fetchall(self):
            return []

        def fetchone(self):
            return None

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(repository, "get_connection", connection)
    scope = TrainerPerformanceScope("trainer-a", all_courses=True)
    repository.list_assignment_summaries(scope, course_id="foreign-course", department="Finance")
    repository.list_scope_options(scope)
    repository.get_assignment_detail(scope, "foreign-assignment")
    repository.course_module_summary(scope, "foreign-course", department="Finance")
    assert len(calls) == 6
    for query, params in calls:
        assert "c.trainer_id = ?" not in query
        assert "trainer-a" not in params
        assert "c.status = 'published'" in query
        assert "ar.is_active = TRUE" in query
        assert "ar.published_at IS NOT NULL" in query
    assert calls[0][1] == ["foreign-course", "Finance"]
    assert calls[4][1] == ("foreign-assignment",)
    assert calls[5][1] == ["foreign-course", "Finance"]


def test_same_title_courses_remain_separate_in_all_course_overview(monkeypatch):
    from datetime import datetime

    from test_performance_reporting import _row

    from app.schemas.performance_reporting import PerformanceOverview
    from app.services import performance_reporting as reports

    now = datetime.now()
    first = _row("first", now, status="completed")
    second = {**_row("second", now), "course_id": "another-creator-course"}
    monkeypatch.setattr(
        repository, "list_assignment_summaries", lambda *args, **kwargs: [first, second]
    )
    result = reports.overview(TrainerPerformanceScope("trainer-a", all_courses=True))
    PerformanceOverview.model_validate(result)
    courses = result["breakdowns"]["courses"]
    assert len(courses) == 2
    assert {c["course_id"] for c in courses} == {first["course_id"], second["course_id"]}
    assert sorted(c["assigned"] for c in courses) == [1, 1]


def test_streamed_export_rechecks_session_before_next_page(client, monkeypatch):
    import asyncio

    from starlette.requests import Request

    from app.core.exceptions import AuthenticationError

    calls = []

    def assignments(scope, **kwargs):
        calls.append(scope)
        return {"rows": [{"employee_name": "Ananya"}], "total": 101, "generated_at": "2026-10-06"}

    monkeypatch.setattr(analytics.reports, "assignment_list", assignments)
    response = analytics.performance_export(
        Request({"type": "http", "headers": [], "query_string": b""}),
        authorization="Bearer active",
        joined_less_than_days_ago=None,
        search=None,
    )

    async def consume():
        iterator = response.body_iterator
        await anext(iterator)
        auth._local_trainer_sessions.pop("active")
        with pytest.raises(AuthenticationError):
            await anext(iterator)

    asyncio.run(consume())
    assert len(calls) == 1
