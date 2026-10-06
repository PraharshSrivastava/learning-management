"""Employee Performance endpoints authenticate their own audience and scope."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import analytics
from app.core.exceptions import install_exception_handlers
from app.schemas.reporting_scope import EmployeePerformanceScope, TrainerPerformanceScope
from app.services import auth, report_access


@pytest.fixture
def employee_reports(monkeypatch):
    employee = {"employee_id": "e-1", "directory_uuid": "uuid-1", "status": "active", "directory_status": "active"}
    state = {"roles": {"hod", "observer"}, "scope": None}
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(auth, "_hub_session", lambda *_: None)
    monkeypatch.setattr(auth, "_local_employee_sessions", {"employee": "e-1"})
    monkeypatch.setattr(auth, "_local_trainer_sessions", {"trainer": "t-1"})
    monkeypatch.setattr(auth._employees, "get", lambda *_: employee)
    monkeypatch.setattr(auth._trainers, "get", lambda *_: {"trainer_id": "t-1", "status": "active"})
    monkeypatch.setattr(report_access, "report_roles", lambda *_: state["roles"])
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(analytics.router)
    return TestClient(app), state


class ScopeRead(Exception):
    pass


@pytest.mark.parametrize("path,method", [
    ("overview", "overview"), ("courses", "course_list"), ("courses/c-1", "course_detail"),
    ("assignments", "assignment_list"), ("assignments/a-1", "assignment_detail"),
    ("employees", "employee_list"), ("employees/e-2", "employee_detail"),
    ("export", "assignment_list"), ("employees/export", "employee_list"),
])
def test_all_employee_report_paths_use_employee_scope(employee_reports, monkeypatch, path, method):
    client, _ = employee_reports

    def read(scope, *args, **kwargs):
        assert scope == EmployeePerformanceScope("e-1", "directory:uuid-1", "combined")
        raise ScopeRead()

    monkeypatch.setattr(analytics.reports, method, read)
    with pytest.raises(ScopeRead):
        client.get("/api/employee/performance/" + path, headers={"Authorization": "Bearer employee"})
    assert client.get("/api/employee/performance/" + path, headers={"Authorization": "Bearer trainer"}).status_code == 401


@pytest.mark.parametrize("view", ["all_courses", "my_courses", "invalid"])
def test_employee_cannot_widen_to_trainer_views(employee_reports, view):
    client, _ = employee_reports
    assert client.get("/api/employee/performance/overview?view=" + view, headers={"Authorization": "Bearer employee"}).status_code == 403


def test_revocation_and_unmapped_employee_cannot_report(employee_reports):
    client, state = employee_reports
    state["roles"] = set()
    for view in ("combined", "my_departments", "observed"):
        assert client.get("/api/employee/performance/overview?view=" + view, headers={"Authorization": "Bearer employee"}).status_code == 403


def test_normal_trainer_optional_own_view_preserves_default(employee_reports, monkeypatch):
    client, _ = employee_reports

    def read(scope, **kwargs):
        assert scope == TrainerPerformanceScope("t-1", False)
        raise ScopeRead()

    monkeypatch.setattr(analytics.reports, "overview", read)
    with pytest.raises(ScopeRead):
        client.get("/api/trainer/performance/overview?view=my_courses", headers={"Authorization": "Bearer trainer"})
