"""Capability discovery preserves Trainer access and separates app audiences."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lms_access import router
from app.core.exceptions import install_exception_handlers
from app.repositories import lms_access as grants
from app.services import auth, lms_access


@pytest.fixture
def access_client(monkeypatch):
    employee = {
        "employee_id": "e-1",
        "directory_uuid": "uuid-1",
        "hub_user_id": 42,
        "name": "Kiran",
        "status": "active",
        "directory_status": "active",
        "source": "hub",
    }
    trainer = {"trainer_id": "t-1", "directory_uuid": "uuid-1", "name": "Kiran", "status": "active"}
    state = {"roles": set(), "version": 0}
    monkeypatch.setattr(lms_access, "report_roles", lambda *_: set())
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(auth, "_hub_session", lambda *_: None)
    monkeypatch.setattr(auth, "_local_employee_sessions", {"employee-token": "e-1"})
    monkeypatch.setattr(auth, "_local_trainer_sessions", {"trainer-token": "t-1"})
    monkeypatch.setattr(auth._trainers, "get", lambda *_: trainer)
    monkeypatch.setattr(auth._employees, "get", lambda *_: employee)
    monkeypatch.setattr(lms_access._employees, "get_by_directory_uuid", lambda *_: employee)
    monkeypatch.setattr(grants, "access_snapshot", lambda *_: (state["roles"], state["version"]))
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    return TestClient(app), state, employee, trainer


def request(client, app, token):
    return client.get(
        "/api/lms/me", params={"app": app}, headers={"Authorization": "Bearer " + token}
    )


def test_existing_trainer_retains_authoring_and_all_course_reporting(access_client):
    client, _, _, _ = access_client
    result = request(client, "trainer", "trainer-token").json()
    assert result["roles"] == ["trainer"]
    assert result["performance_views"] == ["all_courses", "my_courses"]
    assert result["capabilities"]["can_author_courses"]
    assert result["capabilities"]["can_view_all_performance"]
    assert not result["capabilities"]["can_view_other_trainers_courses"]
    assert not result["capabilities"]["can_manage_other_trainers_courses"]
    assert result["employee_id"] == "e-1" and result["trainer_id"] == "t-1"


def test_employee_session_never_becomes_trainer_even_with_stored_admin(access_client):
    client, state, _, _ = access_client
    state["roles"] = {"admin_trainer"}
    result = request(client, "employee", "employee-token").json()
    assert result["roles"] == []
    assert result["trainer_id"] is None
    assert result["performance_views"] == []
    assert result["capabilities"]["can_learn"]
    assert not result["capabilities"]["can_author_courses"]
    assert not result["capabilities"]["can_view_all_performance"]


def test_admin_grant_and_revoke_refresh_existing_session(access_client):
    client, state, _, _ = access_client
    state.update(roles={"admin_trainer"}, version=1)
    result = request(client, "trainer", "trainer-token").json()
    assert result["roles"] == ["admin_trainer"]
    assert result["permissions_version"] == 1
    assert result["capabilities"]["can_view_other_trainers_courses"]
    assert not result["capabilities"]["can_manage_other_trainers_courses"]
    state.update(roles=set(), version=2)
    result = request(client, "trainer", "trainer-token").json()
    assert result["roles"] == ["trainer"]
    assert result["permissions_version"] == 2
    assert not result["capabilities"]["can_view_other_trainers_courses"]
    assert result["capabilities"]["can_view_all_performance"]


@pytest.mark.parametrize(
    "app,token",
    [
        ("trainer", "employee-token"),
        ("employee", "trainer-token"),
        ("trainer", "invalid"),
        ("employee", "invalid"),
    ],
)
def test_app_audiences_do_not_accept_each_others_tokens(access_client, app, token):
    client, _, _, _ = access_client
    assert request(client, app, token).status_code == 401


@pytest.mark.parametrize("field", ["status", "directory_status"])
def test_disabled_identity_loses_discovery(access_client, field):
    client, _, employee, _ = access_client
    employee[field] = "inactive"
    assert request(client, "trainer", "trainer-token").status_code == 401
    assert request(client, "employee", "employee-token").status_code == 401


def test_canonical_identity_conflict_is_denied(access_client):
    client, _, employee, _ = access_client
    employee["directory_uuid"] = "different-person"
    assert request(client, "trainer", "trainer-token").status_code == 401


def test_client_role_and_scope_cannot_promote_employee(access_client):
    client, _, _, _ = access_client
    result = client.get(
        "/api/lms/me?app=employee&role=admin_trainer&view=all_courses",
        headers={"Authorization": "Bearer employee-token"},
    ).json()
    assert result["roles"] == [] and not result["capabilities"]["can_view_all_performance"]
    assert client.get("/api/lms/me?app=unknown").status_code == 422
    assert client.get("/api/lms/me?app=employee").status_code == 401


def test_stable_identity_never_uses_name_or_email():
    assert (
        grants.identity_key({"directory_uuid": "u-1", "email": "same@example.test"})
        == "directory:u-1"
    )
    assert grants.identity_key({"hub_user_id": 42}) == "hub:42"
    from app.core.exceptions import DomainValidationError

    with pytest.raises(DomainValidationError):
        grants.identity_key({"name": "Kiran", "email": "same@example.test"})


def test_production_hub_trainer_discovery_preserves_verified_identity(access_client, monkeypatch):
    client, state, employee, trainer = access_client
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", False)
    monkeypatch.setattr(
        auth,
        "_hub_session",
        lambda request, app: {"sub": 42, "app": "trainer"} if app == "trainer" else None,
    )
    monkeypatch.setattr(
        auth._employees, "get_by_hub_user_id", lambda hub_id: employee if hub_id == 42 else None
    )
    monkeypatch.setattr(auth._trainers, "upsert_from_employee", lambda synced: trainer)
    state.update(roles={"admin_trainer"}, version=1)
    response = client.get("/api/lms/me?app=trainer")
    assert response.status_code == 200
    assert response.json()["employee_id"] == "e-1"
    assert response.json()["roles"] == ["admin_trainer"]
    assert client.get("/api/lms/me?app=employee").status_code == 401
