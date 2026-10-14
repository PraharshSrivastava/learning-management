"""Direct private media delivery preserves range/HLS and denies report-only access."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api import media
from app.core.exceptions import AuthenticationError, NotFoundError, install_exception_handlers
from app.services import media_access


def request(ticket=None):
    return Request({"type": "http", "headers": [], "query_string": ("media_ticket=" + ticket).encode() if ticket else b""})


@pytest.fixture
def ticket_identity(monkeypatch):
    employee = {"employee_id": "e-1", "directory_uuid": "uuid-1", "status": "active", "directory_status": "active"}
    trainer = {"trainer_id": "t-1", "status": "active"}
    monkeypatch.setattr(media_access, "current_trainer_from_request", lambda *_: trainer)
    monkeypatch.setattr(media_access, "_employee_for_trainer", lambda *_: employee)
    monkeypatch.setattr(media_access._employees, "get", lambda *_: employee)
    monkeypatch.setattr(media_access, "get_trainer", lambda *_: trainer)
    return employee, trainer


def test_ticket_signature_current_identity_and_active_status(ticket_identity):
    employee, _ = ticket_identity
    token = media_access.issue_media_ticket(request(), None, "trainer")
    assert media_access.media_principal(request(token)).employee["employee_id"] == "e-1"
    with pytest.raises(AuthenticationError):
        media_access.media_principal(request(token[:-1] + ("a" if token[-1] != "a" else "b")))
    employee["directory_uuid"] = "replacement"
    with pytest.raises(AuthenticationError):
        media_access.media_principal(request(token))
    employee["directory_uuid"] = "uuid-1"
    employee["directory_status"] = "inactive"
    with pytest.raises(AuthenticationError):
        media_access.media_principal(request(token))


def test_expired_standalone_ticket_is_denied(ticket_identity, monkeypatch):
    token = media_access.issue_media_ticket(request(), None, "trainer")
    monkeypatch.setattr(media_access.time, "time", lambda: 99999999999)

    def no_cookie(*args):
        raise AuthenticationError("Session expired")

    monkeypatch.setattr(media_access, "current_trainer_from_request", no_cookie)
    with pytest.raises(AuthenticationError):
        media_access.media_principal(request(token))


def test_unauthenticated_direct_media_is_denied():
    with pytest.raises(AuthenticationError):
        media_access.media_principal(request())


def test_range_and_hls_playlist_children_preserve_private_delivery(tmp_path, monkeypatch):
    (tmp_path / "video.mp4").write_bytes(b"0123456789")
    (tmp_path / "master.m3u8").write_text('#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\nsegment.ts\n', encoding="utf-8")
    state = {"allowed": True}
    monkeypatch.setattr(media, "media_principal", lambda *_: SimpleNamespace())
    monkeypatch.setattr(media, "asset_courses", lambda *_: ["course-1"])

    def authorize(*args):
        if not state["allowed"]:
            raise NotFoundError("Media not found")

    monkeypatch.setattr(media, "authorize_course_media", authorize)
    app = FastAPI()
    install_exception_handlers(app)
    app.mount("/assets/videos", media.PrivateCourseStaticFiles(directory=tmp_path))
    client = TestClient(app)
    response = client.get("/assets/videos/video.mp4", headers={"Range": "bytes=2-5"})
    assert response.status_code == 206 and response.content == b"2345"
    assert response.headers["cache-control"] == "no-store"
    playlist = client.get("/assets/videos/master.m3u8?media_ticket=short-ticket")
    assert playlist.status_code == 200
    assert 'URI="init.mp4?media_ticket=short-ticket"' in playlist.text
    assert 'segment.ts?media_ticket=short-ticket' in playlist.text
    state["allowed"] = False
    assert client.get("/assets/videos/video.mp4").status_code == 404


def test_preview_authorizes_record_before_conversion(tmp_path, monkeypatch):
    from app.api import uploads

    events = []
    monkeypatch.setattr(uploads, "media_principal", lambda *_: SimpleNamespace())
    monkeypatch.setattr(uploads, "get_document_by_file_name", lambda *_: {"document_id": "d-1"})

    def denied(*args):
        events.append("authorization")
        raise NotFoundError("Document not found")

    monkeypatch.setattr(uploads, "authorize_document", denied)
    monkeypatch.setattr(uploads.service, "document_path", lambda *_: events.append("filesystem") or tmp_path / "private.docx")
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(uploads.router)
    client = TestClient(app)
    assert client.get("/api/files/private.docx/preview").status_code == 404
    assert events == ["authorization"]

def _accel_client(tmp_path, monkeypatch, allowed=True):
    (tmp_path / "a b.mp4").write_bytes(b"0123456789")
    (tmp_path / "master.m3u8").write_text("#EXTM3U\nsegment.ts\n", encoding="utf-8")
    monkeypatch.setattr(media, "media_principal", lambda *_: SimpleNamespace())
    monkeypatch.setattr(media, "asset_courses", lambda *_: ["course-1"])

    def authorize(*args):
        if not allowed:
            raise NotFoundError("Media not found")

    monkeypatch.setattr(media, "authorize_course_media", authorize)
    app = FastAPI()
    install_exception_handlers(app)
    app.mount("/assets/videos", media.PrivateCourseStaticFiles(
        directory=tmp_path, accel_location="/_lms_private_videos/"))
    return TestClient(app)

def test_authorized_video_is_handed_to_nginx_only_when_proxy_asks(tmp_path, monkeypatch):
    client = _accel_client(tmp_path, monkeypatch)
    direct = client.get("/assets/videos/a%20b.mp4", headers={"Range": "bytes=2-5"})
    assert direct.status_code == 206 and "x-accel-redirect" not in direct.headers
    response = client.get("/assets/videos/a%20b.mp4", headers={"X-LMS-Accel-Videos": "1"})
    assert response.status_code == 200 and response.content == b""
    assert response.headers["x-accel-redirect"] == "/_lms_private_videos/a%20b.mp4"
    assert response.headers["cache-control"] == "no-store"
    missing = client.get("/assets/videos/none.mp4", headers={"X-LMS-Accel-Videos": "1"})
    assert missing.status_code == 404 and "x-accel-redirect" not in missing.headers
    escape = client.get("/assets/videos/%2e%2e/x.mp4", headers={"X-LMS-Accel-Videos": "1"})
    assert "x-accel-redirect" not in escape.headers

def test_ticketed_playlists_are_still_rewritten_by_backend(tmp_path, monkeypatch):
    client = _accel_client(tmp_path, monkeypatch)
    response = client.get("/assets/videos/master.m3u8?media_ticket=t", headers={"X-LMS-Accel-Videos": "1"})
    assert "x-accel-redirect" not in response.headers
    assert "segment.ts?media_ticket=t" in response.text

def test_denied_video_never_gets_accel_redirect(tmp_path, monkeypatch):
    client = _accel_client(tmp_path, monkeypatch, allowed=False)
    response = client.get("/assets/videos/a%20b.mp4", headers={"X-LMS-Accel-Videos": "1"})
    assert response.status_code == 404 and "x-accel-redirect" not in response.headers
