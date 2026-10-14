"""Opt-in Docker HTTP tests using the actual frontend nginx templates."""

import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

NGINX_IMAGE = (
    "nginxinc/nginx-unprivileged@sha256:"
    "6a23acdfca2b9cfbcec61419e3f1426bcbedb91362f2f19306a8567423bb4612"
)
pytestmark = pytest.mark.skipif(
    os.environ.get("LMS_TEST_DOCKER") != "1", reason="Set LMS_TEST_DOCKER=1 for real nginx tests"
)


def docker_command(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


GOOD_SESSION = "valid-session-marker"

def expected_cookie(role, prefix):
    from app.security.hub_launch import HubLaunchVerifier

    return f"{HubLaunchVerifier().cookie_name(role, prefix + '/')}={GOOD_SESSION}"

class BackendEchoHandler(BaseHTTPRequestHandler):
    def authorize_video(self):
        """Stand-in for PrivateCourseStaticFiles: same contract, no database."""
        headers = {key.lower(): value for key, value in self.headers.items()}
        role = headers.get("x-lms-app", "")
        prefix = headers.get("x-forwarded-prefix", "")
        cookies = [part.strip() for part in headers.get("cookie", "").split(";")]
        ticket = "media_ticket=good-ticket-marker" in self.path
        if role not in {"trainer", "employee"} or not (ticket or expected_cookie(role, prefix) in cookies):
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        name = self.path.split("?", 1)[0].removeprefix("/assets/videos/")
        self.send_response(200)
        if headers.get("x-lms-accel-videos") == "1":
            self.send_header("X-Accel-Redirect", "/_lms_private_videos/" + name)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/assets/videos/"):
            return self.authorize_video()
        body = json.dumps({"path": self.path, "headers": dict(self.headers)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def backend_echo():
    server = ThreadingHTTPServer(("0.0.0.0", 0), BackendEchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port
    server.shutdown()
    thread.join()


@pytest.mark.parametrize("directory,mount,role", [
    ("frontend", "/lms/trainer", "trainer"),
    ("employee_frontend", "/lms", "employee"),
])
@pytest.mark.parametrize("trusted", [False, True])
def test_nginx_serves_both_mounts_and_overwrites_forwarding(tmp_path, backend_echo, directory, mount, role, trusted):
    repo = Path(__file__).resolve().parents[2]
    template = (repo / directory / "nginx.conf").read_text().replace(
        "backend:8000", f"backend:{backend_echo}")
    config = tmp_path / "default.conf.template"
    config.write_text(template)
    static = tmp_path / "web"
    static.mkdir()
    (static / "index.html").write_text('<html><base href="/"><body>entry</body></html>')
    (static / "flutter_bootstrap.js").write_text("bootstrap")
    (static / "assets").mkdir()
    (static / "assets" / ".env").write_text("API_BASE_URL=\n")
    (static / "canvaskit").mkdir()
    (static / "canvaskit" / "canvaskit.wasm").write_bytes(b"wasm")
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "clip.mp4").write_bytes(b"0123456789")
    network = f"lms-mount-{uuid.uuid4().hex[:10]}"
    container = f"{network}-web"
    docker_command("network", "create", network)
    try:
        gateway = json.loads(docker_command("network", "inspect", network))[0]["IPAM"]["Config"][0]["Gateway"]
        docker_command("run", "-d", "--name", container, "--network", network,
                       "--add-host", f"backend:{gateway}", "-p", "127.0.0.1::8080",
                       "-e", f"TRUSTED_EDGE_PROXY_IP={gateway if trusted else ''}",
                       "-v", f"{config}:/etc/nginx/templates/default.conf.template:ro",
                       "-v", f"{static}:/usr/share/nginx/html:ro",
                       "-v", f"{videos}:/srv/lms/videos:ro", NGINX_IMAGE)
        port = docker_command("port", container, "8080").rsplit(":", 1)[1]
        origin = f"http://127.0.0.1:{port}"

        def fetch(path, headers=None):
            try:
                return urlopen(Request(origin + path, headers=headers or {}), timeout=5)
            except HTTPError as response:
                return response

        for _ in range(50):
            try:
                with fetch("/") as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail(docker_command("logs", container))

        for prefix in ["", mount]:
            for path in ["/", "/index.html", "/dashboard"]:
                with fetch(prefix + path) as response:
                    assert response.status == 200
                    assert f'<base href="{prefix}/">' in response.read().decode()
                    assert "no-store" in response.headers["Cache-Control"]
            for path, content in [("/flutter_bootstrap.js", b"bootstrap"),
                                  ("/assets/.env", b"API_BASE_URL=\n"),
                                  ("/canvaskit/canvaskit.wasm", b"wasm")]:
                with fetch(prefix + path) as response:
                    assert response.status == 200
                    assert response.read() == content
            with fetch(prefix + "/canvaskit/missing.wasm?hub_launch_token=private-missing-marker") as response:
                assert response.status == 404
            with fetch(prefix + "/api/hub/launch/" + role + "?hub_launch_token=private-launch-marker", {
                "X-Forwarded-Prefix": "/evil", "X-LMS-App": "evil",
                "X-Forwarded-Proto": "https", "Host": "public.example.test:9443",
            }) as response:
                echoed = json.load(response)
                assert echoed["path"].startswith(f"/api/hub/launch/{role}?")
                headers = {key.lower(): value for key, value in echoed["headers"].items()}
                assert headers.get("x-forwarded-prefix", "") == prefix
                assert headers["x-lms-app"] == role
                assert headers["host"] == "public.example.test:9443"
                assert headers["x-forwarded-proto"] == ("https" if trusted else "http")
            with fetch(prefix + "/api/me/courses/ws?token=private-ws-marker", {
                "Upgrade": "websocket", "Connection": "upgrade",
            }) as response:
                echoed = json.load(response)
                assert echoed["path"] == "/api/me/courses/ws?token=private-ws-marker"
                headers = {key.lower(): value for key, value in echoed["headers"].items()}
                assert headers["upgrade"] == "websocket"
                assert headers["connection"] == "upgrade"
            with fetch(prefix + "/assets/slides/course/module_1.html") as response:
                assert json.load(response)["path"] == "/assets/slides/course/module_1.html"
            video = prefix + "/assets/videos/clip.mp4"
            good = {"Cookie": expected_cookie(role, prefix)}
            with fetch(video, {**good, "Range": "bytes=2-5"}) as response:
                assert response.status == 206
                assert response.read() == b"2345"
                assert response.headers["Content-Range"] == "bytes 2-5/10"
                assert "no-store" in response.headers["Cache-Control"]
            with fetch(video, good) as response:
                assert response.status == 200 and response.read() == b"0123456789"
            with fetch(video + "?media_ticket=good-ticket-marker", {"Range": "bytes=0-1"}) as response:
                assert response.status == 206 and response.read() == b"01"
            # No session, a bad session, or the other mount's session never gets bytes.
            other = "" if prefix else mount
            for headers in [{}, {"Cookie": "x=y"}, {"Cookie": expected_cookie(role, other)},
                            {"Cookie": f"{expected_cookie(role, prefix).split('=')[0]}=forged"}]:
                with fetch(video, {**headers, "Range": "bytes=2-5"}) as response:
                    assert response.status in {401, 403}
                    assert b"2345" not in response.read()
            with fetch(prefix + "/assets/videos/clip.mp4?media_ticket=bad-ticket-marker") as response:
                assert response.status in {401, 403}
            # Spoofed headers cannot choose the role or the mount.
            with fetch(video, {"X-LMS-App": "trainer" if role == "employee" else "employee",
                               "X-Forwarded-Prefix": "/evil", "Cookie": expected_cookie(role, prefix)}) as response:
                assert response.status == 200 and response.read() == b"0123456789"
        # The internal location is not reachable from outside, even with a valid session.
        with fetch("/_lms_private_videos/clip.mp4", {"Cookie": expected_cookie(role, "")}) as response:
            assert response.status == 404
        with fetch(mount + "?keep=query") as response:
            assert response.url == origin + mount + "/?keep=query"
        logs = docker_command("logs", container)
        assert "private-launch-marker" not in logs
        assert "private-ws-marker" not in logs
        assert "private-missing-marker" not in logs
        assert "good-ticket-marker" not in logs
        assert "bad-ticket-marker" not in logs
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=False, capture_output=True)
        subprocess.run(["docker", "network", "rm", network], check=False, capture_output=True)
