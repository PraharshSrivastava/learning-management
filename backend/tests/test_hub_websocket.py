"""Employee WebSocket authentication uses the independently typed Hub session."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_hub_launch import _verifier

from app.security.hub_launch import HubSession
from app.services import learning, notifications


@pytest.fixture
def websocket_client(monkeypatch):
    verifier = _verifier()
    monkeypatch.setattr(notifications, "hub_launch_verifier", verifier, raising=False)
    monkeypatch.setattr(notifications._employees, "get_by_hub_user_id", lambda _: {
        "employee_id": "employee-42", "status": "active", "source": "hub",
    })
    monkeypatch.setattr(learning, "get_enriched_employee_courses", lambda _: [])
    notifications.clear_active_websockets()
    app = FastAPI()
    app.add_api_websocket_route("/api/me/courses/ws", notifications.websocket_endpoint)
    with TestClient(app) as client:
        yield client, verifier
    notifications.clear_active_websockets()


def session_token(verifier, app="employee"):
    return verifier.issue_session_token(HubSession(
        app=app, app_key=verifier.app_key(app), app_id=None,
        sub=42, email="user@example.test", exp=int(time.time()) + 60,
    ))


def test_employee_hub_cookie_opens_websocket_without_local_token(websocket_client):
    client, verifier = websocket_client
    headers = {"X-LMS-App": "employee", "Cookie":
               f"{verifier.cookie_name('employee')}={session_token(verifier)}"}
    with client.websocket_connect("/api/me/courses/ws?token=", headers=headers) as socket:
        assert socket.receive_json() == []


@pytest.mark.parametrize("app,cookie_app", [("trainer", "employee"), ("employee", "trainer"), ("", "employee")])
def test_websocket_rejects_wrong_role(websocket_client, app, cookie_app):
    client, verifier = websocket_client
    headers = {"X-LMS-App": app, "Cookie":
               f"{verifier.cookie_name('employee')}={session_token(verifier, cookie_app)}"}
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/me/courses/ws?token=", headers=headers):
            pass
    assert error.value.code == 1008


@pytest.mark.parametrize("prefix", ["", "/lms"])
def test_websocket_uses_cookie_of_its_own_mount(websocket_client, prefix):
    client, verifier = websocket_client
    token = session_token(verifier)
    own = verifier.cookie_name("employee", f"{prefix}/")
    other = verifier.cookie_name("employee", "/" if prefix else "/lms/")
    headers = {"X-LMS-App": "employee", "X-Forwarded-Prefix": prefix}
    with client.websocket_connect("/api/me/courses/ws?token=", headers={
            **headers, "Cookie": f"{own}={token}"}) as socket:
        assert socket.receive_json() == []
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/me/courses/ws?token=", headers={
                **headers, "Cookie": f"{other}={token}"}):
            pass
    assert error.value.code == 1008

def test_websocket_rejects_missing_session(websocket_client):
    client, _ = websocket_client
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/me/courses/ws?token=", headers={"X-LMS-App": "employee"}):
            pass
    assert error.value.code == 1008
