"""Slide screenshots: the backend client and the slide renderer service."""

import base64
from types import SimpleNamespace

import pytest

from app.generation import video
from slide_renderer import server


@pytest.fixture
def deck_storage(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    (templates / "layouts").mkdir(parents=True)
    (templates / "slides.css").write_text("body { color: red; }")
    (templates / "layouts" / "grid.css").write_text(".grid {}")
    brand = tmp_path / "static" / "brand"
    brand.mkdir(parents=True)
    (brand / "logo.png").write_bytes(b"logo")
    images = tmp_path / "images" / "course-1"
    images.mkdir(parents=True)
    (images / "shot one.png").write_bytes(b"shot")
    (tmp_path / "secret.txt").write_text("not a slide asset")
    slides = tmp_path / "slides" / "course-1"
    slides.mkdir(parents=True)
    deck = slides / "module_1.html"
    deck.write_text(
        '<link rel="stylesheet" href="../../slides.css">'
        '<link rel="stylesheet" href="../../layouts/grid.css">'
        '<link href="https://fonts.googleapis.com/css2?family=Barlow" rel="stylesheet">'
        '<img src="../../brand/logo.png"><img src="../../brand/logo.png">'
        '<img src="../../images/course-1/shot%20one.png">'
        '<img src="../../images/course-1/missing.png">'
        '<img src="../../images/../../secret.txt">'
        '<img src="../../images/%2e%2e/secret.txt">'
    )
    monkeypatch.setattr(video.settings, "template_dir", templates)
    monkeypatch.setattr(video.settings, "static_dir", tmp_path / "static")
    monkeypatch.setattr(video.settings, "image_dir", tmp_path / "images")
    monkeypatch.setattr(video.settings, "slide_dir", tmp_path / "slides")
    return deck


def test_deck_files_hold_the_local_files_the_deck_links_to(deck_storage):
    document, files = video.slide_deck_files(deck_storage)

    assert document == "/assets/slides/course-1/module_1.html"
    assert files == {
        document: deck_storage.read_bytes(),
        "/assets/slides.css": b"body { color: red; }",
        "/assets/layouts/grid.css": b".grid {}",
        "/assets/brand/logo.png": b"logo",
        "/assets/images/course-1/shot%20one.png": b"shot",
    }


def test_capture_writes_one_frame_per_slide(deck_storage, tmp_path, monkeypatch):
    monkeypatch.setattr(video.settings, "slide_renderer_url", "http://renderer:8080")
    calls = []

    def post(url, *, json, timeout):
        calls.append((url, json))
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"frames": [base64.b64encode(b"png-0").decode(), base64.b64encode(b"png-1").decode()]},
        )

    monkeypatch.setattr(video.requests, "post", post)
    frames = video.capture_slide_frames(str(deck_storage), slide_count=2, output_dir=str(tmp_path))

    assert [open(frame, "rb").read() for frame in frames] == [b"png-0", b"png-1"]
    url, payload = calls[0]
    assert url == "http://renderer:8080/render"
    assert payload["document"] == "/assets/slides/course-1/module_1.html"
    assert payload["slide_count"] == 2
    assert base64.b64decode(payload["files"]["/assets/brand/logo.png"]) == b"logo"


def test_capture_reports_the_renderer_error(deck_storage, tmp_path, monkeypatch):
    monkeypatch.setattr(video.settings, "slide_renderer_url", "http://renderer:8080")
    monkeypatch.setattr(
        video.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=422,
            text="",
            json=lambda: {"error": "Slide images could not be loaded: missing.png"},
        ),
    )
    with pytest.raises(RuntimeError, match="HTTP 422: Slide images could not be loaded"):
        video.capture_slide_frames(str(deck_storage), slide_count=1, output_dir=str(tmp_path))


def test_capture_needs_the_renderer_address(deck_storage, tmp_path, monkeypatch):
    monkeypatch.setattr(video.settings, "slide_renderer_url", None)
    with pytest.raises(RuntimeError, match="SLIDE_RENDERER_URL"):
        video.capture_slide_frames(str(deck_storage), slide_count=1, output_dir=str(tmp_path))


def _request(**overrides):
    payload = {
        "document": "/assets/slides/c/module_1.html",
        "files": {"/assets/slides/c/module_1.html": base64.b64encode(b"<html>").decode()},
        "slide_count": 2,
    }
    payload.update(overrides)
    return payload


def test_renderer_accepts_a_valid_request():
    document, files, count = server.parse_render_request(_request())
    assert (document, files, count) == ("/assets/slides/c/module_1.html", {document: b"<html>"}, 2)


@pytest.mark.parametrize(
    "overrides",
    [
        {"document": "module_1.html"},
        {"files": {}},
        {"slide_count": 0},
        {"slide_count": True},
        {"files": {"/assets/slides/c/module_1.html": "not base64!"}},
    ],
)
def test_renderer_rejects_a_malformed_request(overrides):
    with pytest.raises(server.RenderRequestError):
        server.parse_render_request(_request(**overrides))


class FakeRoute:
    def __init__(self, url):
        self.request = SimpleNamespace(url=url)
        self.result = None

    def fulfill(self, **kwargs):
        self.result = ("fulfill", kwargs)

    def continue_(self):
        self.result = ("continue", None)

    def abort(self):
        self.result = ("abort", None)


def test_renderer_serves_deck_files_allows_fonts_and_blocks_other_requests():
    files = {"/assets/slides.css": b"css"}
    routes = {
        url: FakeRoute(url)
        for url in (
            server.DOCUMENT_ORIGIN + "/assets/slides.css",
            server.DOCUMENT_ORIGIN + "/assets/brand/missing.svg",
            "https://fonts.gstatic.com/s/barlow.woff2",
            "http://169.254.169.254/latest/meta-data",
        )
    }
    for route in routes.values():
        server.route_request(route, files)

    css, missing, font, other = routes.values()
    assert css.result == ("fulfill", {"status": 200, "body": b"css", "content_type": "text/css"})
    assert missing.result == ("fulfill", {"status": 404, "body": b""})
    assert font.result == ("continue", None)
    assert other.result == ("abort", None)
