"""HTTP regression tests for root and shared LMS launch mounts."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from security_test_values import TEST_HUB_SIGNING_VALUE
from test_hub_launch import _token, _verifier

from app.api import hub
from app.security.hub_launch import HubLaunchMiddleware


@pytest.fixture
def mount_client(monkeypatch):
    verifier = _verifier()
    monkeypatch.setattr(hub, "hub_launch_verifier", verifier)
    app = FastAPI()
    app.include_router(hub.router)
    app.add_middleware(HubLaunchMiddleware, verifier=verifier)

    @app.get("/api/protected")
    def protected_route():
        return {"ok": True}

    with TestClient(app, follow_redirects=False) as client:
        yield client, verifier


def launch_token(app="trainer"):
    return _token(TEST_HUB_SIGNING_VALUE, {
        "app_key": f"lms-{app}", "sub": 42, "email": "user@example.test",
        "exp": int(time.time()) + 60,
    })


@pytest.mark.parametrize("app,prefix", [
    ("trainer", ""), ("employee", ""),
    ("trainer", "/lms/trainer"), ("employee", "/lms"),
])
def test_launch_and_logout_keep_active_mount(mount_client, app, prefix):
    client, verifier = mount_client
    headers = {"X-Forwarded-Prefix": prefix, "X-LMS-App": app}
    response = client.get(f"/api/hub/launch/{app}",
                          params={"hub_launch_token": launch_token(app)}, headers=headers)
    assert response.status_code == 302
    assert response.headers["location"] == f"{prefix}/"
    assert f"Path={prefix}/" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Secure" not in response.headers["set-cookie"]
    session_cookie = response.cookies.get(verifier.cookie_name(app, f"{prefix}/"))
    assert session_cookie is not None
    assert (f"{verifier.cookie_name(app)}=" in response.headers["set-cookie"]) == (prefix == "")
    assert verifier.verify_session_token(session_cookie, app) is not None
    assert verifier.verify(session_cookie, app) is None
    response = client.post(f"/api/hub/logout/{app}", headers=headers)
    assert response.status_code == 204
    assert f"Path={prefix}/" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.parametrize("token", ["", "invalid", "a.b", "☃.bad"])
def test_invalid_launch_is_denied(mount_client, token):
    client, _ = mount_client
    response = client.get("/api/hub/launch/trainer", params={"hub_launch_token": token})
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_wrong_role_and_missing_session_are_denied(mount_client):
    client, _ = mount_client
    assert client.get("/api/hub/launch/trainer", params={
        "hub_launch_token": launch_token("employee")}).status_code == 403
    assert client.get("/api/protected", headers={"X-LMS-App": "trainer"}).status_code == 403
    assert client.get("/api/protected").status_code == 403


@pytest.mark.parametrize("prefix", ["//evil.test", "/other", "/lms/../ai", "/lms%2f", "/lms/trainer"])
def test_employee_rejects_unsafe_or_wrong_role_mount(mount_client, prefix):
    client, _ = mount_client
    response = client.get("/api/hub/launch/employee", params={
        "hub_launch_token": launch_token("employee")}, headers={"X-Forwarded-Prefix": prefix})
    assert response.status_code == 400
    assert "set-cookie" not in response.headers


def test_cookie_names_are_distinct_per_mount(mount_client):
    _, verifier = mount_client
    names = {
        verifier.cookie_name("trainer"), verifier.cookie_name("trainer", "/lms/trainer/"),
        verifier.cookie_name("employee"), verifier.cookie_name("employee", "/lms/"),
    }
    assert len(names) == 4
    assert verifier.cookie_name("trainer") == "lms_trainer_hub"
    assert verifier.cookie_name("employee") == "lms_employee_hub"

def _launch(client, app, prefix):
    """Return the cookie (name, value) a browser would store for this mount."""
    response = client.get(f"/api/hub/launch/{app}", params={"hub_launch_token": launch_token(app)},
                          headers={"X-Forwarded-Prefix": prefix})
    assert response.status_code == 302
    name, _, rest = response.headers["set-cookie"].partition("=")
    return name, rest.split(";", 1)[0]

def _get(client, app, prefix, *cookies, path="/api/protected"):
    # Explicit Cookie header: the test jar does not model browser path matching.
    header = "; ".join(f"{name}={value}" for name, value in cookies)
    return client.get(path, headers={"X-LMS-App": app, "X-Forwarded-Prefix": prefix, "Cookie": header})

@pytest.mark.parametrize("app,prefix", [("trainer", "/lms/trainer"), ("employee", "/lms")])
def test_root_session_is_not_accepted_at_prefix(mount_client, app, prefix):
    client, verifier = mount_client
    root = _launch(client, app, "")
    assert root[0] == verifier.cookie_name(app)
    # A browser sends a Path=/ cookie to prefixed requests too.
    assert _get(client, app, "", root).status_code == 200
    assert _get(client, app, prefix, root).status_code == 403
    session = _get(client, app, prefix, root, path=f"/api/hub/session/{app}")
    assert session.json()["authenticated"] is False

@pytest.mark.parametrize("app,prefix", [("trainer", "/lms/trainer"), ("employee", "/lms")])
def test_prefix_logout_leaves_prefix_unauthenticated_and_keeps_root(mount_client, app, prefix):
    client, verifier = mount_client
    root = _launch(client, app, "")
    mount = _launch(client, app, prefix)
    assert mount[0] == verifier.cookie_name(app, f"{prefix}/") != root[0]
    assert _get(client, app, prefix, root, mount).status_code == 200
    response = client.post(f"/api/hub/logout/{app}", headers={
        "X-LMS-App": app, "X-Forwarded-Prefix": prefix})
    cleared = response.headers["set-cookie"]
    assert cleared.startswith(mount[0] + "=")
    assert f"Path={prefix}/" in cleared and "Max-Age=0" in cleared
    # The browser drops the prefixed cookie but keeps the root cookie.
    assert _get(client, app, prefix, root).status_code == 403
    assert _get(client, app, "", root).status_code == 200

def test_trainer_and_employee_mount_cookies_do_not_collide(mount_client):
    client, _ = mount_client
    trainer = _launch(client, "trainer", "/lms/trainer")
    employee = _launch(client, "employee", "/lms")
    assert trainer[0] != employee[0]
    # A Path=/lms/ cookie also reaches /lms/trainer/ requests.
    assert _get(client, "trainer", "/lms/trainer", employee).status_code == 403
    assert _get(client, "trainer", "/lms/trainer", employee, trainer).status_code == 200
    assert _get(client, "employee", "/lms", employee, trainer).status_code == 200
    assert _get(client, "employee", "/lms", trainer).status_code == 403

def test_invalid_mount_never_authenticates(mount_client):
    from starlette.requests import Request

    client, verifier = mount_client
    _, cookie = _launch(client, "trainer", "")
    request = Request({"type": "http", "headers": [
        (b"cookie", f"lms_trainer_hub={cookie}".encode()), (b"x-forwarded-prefix", b"/evil")]})
    assert verifier.session_from_request(request, "trainer") is None

def test_shared_tls_and_direct_http_cookie_policies_can_coexist(mount_client):
    client, verifier = mount_client
    verifier.config.hub_shared_cookie_secure = True
    for prefix in ["", "/lms/trainer"]:
        headers = {"X-Forwarded-Prefix": prefix, "X-Forwarded-Proto": "https"}
        response = client.get("/api/hub/launch/trainer", params={
            "hub_launch_token": launch_token()}, headers=headers)
        assert ("Secure" in response.headers["set-cookie"]) == bool(prefix)
        response = client.post("/api/hub/logout/trainer", headers=headers)
        assert ("Secure" in response.headers["set-cookie"]) == bool(prefix)


def test_root_path_takes_priority_over_proxy_header(mount_client):
    from starlette.requests import Request

    from app.security.public_mount import lms_public_mount

    request = Request({"type": "http", "root_path": "/lms/trainer",
                       "headers": [(b"x-forwarded-prefix", b"/evil")]})
    assert lms_public_mount(request, "trainer") == "/lms/trainer/"


def test_secure_cookie_is_explicit_deployment_setting(mount_client):
    client, verifier = mount_client
    verifier.config.hub_cookie_secure = True
    response = client.get("/api/hub/launch/trainer", params={"hub_launch_token": launch_token()})
    assert "Secure" in response.headers["set-cookie"]
    response = client.post("/api/hub/logout/trainer")
    assert "Secure" in response.headers["set-cookie"]
