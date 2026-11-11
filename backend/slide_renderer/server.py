"""Slide renderer: screenshot compiled slide decks in headless Chromium.

The LMS backend posts one compiled module deck and the local files it links to.
This service serves those files to Chromium from memory, shows each slide with
``window.goToSlide(n)`` and returns one PNG per slide. It keeps no state and
reads no LMS storage, so the API image needs no browser.

POST /render  {"document": "/assets/slides/<course>/module_1.html",
               "files": {"/assets/...": "<base64>"}, "slide_count": 3}
           -> {"frames": ["<base64 PNG>", ...]}
GET  /health  -> {"status": "ok"}
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import mimetypes
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

logger = logging.getLogger("slide_renderer")

# The deck is served from this origin so its relative links resolve as they do
# under the API's /assets/ mount. ".invalid" never resolves on a real network.
DOCUMENT_ORIGIN = "http://slides.invalid"
# The decks load the Barlow web font from Google Fonts, as the HTML preview does.
REMOTE_ORIGINS = ("https://fonts.googleapis.com", "https://fonts.gstatic.com")
VIEWPORT = {"width": 1280, "height": 720}
MAX_SLIDES = 200
MAX_REQUEST_BYTES = int(os.environ.get("SLIDE_RENDERER_MAX_REQUEST_BYTES", 256 * 1024 * 1024))
MAX_CONCURRENT_RENDERS = int(os.environ.get("SLIDE_RENDERER_MAX_CONCURRENCY", "2"))
IMAGE_LOAD_TIMEOUT_MS = 15000

_render_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RENDERS)


class RenderRequestError(ValueError):
    """The request is malformed; the caller must fix it."""


class SlideRenderError(RuntimeError):
    """The deck loaded but cannot be rendered as it is."""


def parse_render_request(payload: object) -> tuple[str, dict[str, bytes], int]:
    if not isinstance(payload, dict):
        raise RenderRequestError("Request body must be a JSON object")
    document = payload.get("document")
    files = payload.get("files")
    slide_count = payload.get("slide_count")
    if not isinstance(document, str) or not document.startswith("/"):
        raise RenderRequestError("document must be an absolute path such as /assets/slides/...")
    if not isinstance(files, dict) or document not in files:
        raise RenderRequestError("files must be an object that contains the document")
    if isinstance(slide_count, bool) or not isinstance(slide_count, int):
        raise RenderRequestError("slide_count must be an integer")
    if not 1 <= slide_count <= MAX_SLIDES:
        raise RenderRequestError(f"slide_count must be between 1 and {MAX_SLIDES}")
    decoded: dict[str, bytes] = {}
    for path, body in files.items():
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(body, str):
            raise RenderRequestError("files must map absolute paths to base64 strings")
        try:
            decoded[path] = base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError) as error:
            raise RenderRequestError(f"File {path} is not valid base64") from error
    return document, decoded, slide_count


def route_request(route, files: dict[str, bytes]) -> None:
    """Serve deck files from memory, allow web fonts, block everything else."""
    url = route.request.url
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin == DOCUMENT_ORIGIN:
        body = files.get(parts.path)
        if body is None:
            route.fulfill(status=404, body=b"")
            return
        content_type = mimetypes.guess_type(parts.path)[0] or "application/octet-stream"
        route.fulfill(status=200, body=body, content_type=content_type)
    elif origin in REMOTE_ORIGINS:
        route.continue_()
    else:
        route.abort()


def render_slides(document: str, files: dict[str, bytes], slide_count: int) -> list[bytes]:
    from playwright.sync_api import sync_playwright

    frames: list[bytes] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport=VIEWPORT)
            page.route("**/*", lambda route: route_request(route, files))
            page.goto(DOCUMENT_ORIGIN + document)
            page.wait_for_load_state("networkidle")
            page.wait_for_function(
                "Array.from(document.images).every(image => image.complete)",
                timeout=IMAGE_LOAD_TIMEOUT_MS,
            )
            broken_images = page.evaluate(
                "Array.from(document.images).filter(image => image.naturalWidth === 0)"
                ".map(image => image.getAttribute('src') || '(empty image source)')"
            )
            if broken_images:
                raise SlideRenderError(
                    "Slide images could not be loaded: " + ", ".join(broken_images)
                )
            page.evaluate("document.fonts.ready")
            page.add_style_tag(
                content=".slide { animation: none !important; transition: none !important; }"
            )
            for index in range(slide_count):
                page.evaluate(f"window.goToSlide({index})")
                frames.append(page.screenshot(type="png"))
        finally:
            browser.close()
    return frames


class SlideRendererHandler(BaseHTTPRequestHandler):
    server_version = "lms-slide-renderer"

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/render":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(HTTPStatus.LENGTH_REQUIRED, {"error": "Content-Length is required"})
            return
        if length > MAX_REQUEST_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"Request is larger than {MAX_REQUEST_BYTES} bytes"},
            )
            return
        try:
            document, files, slide_count = parse_render_request(json.loads(self.rfile.read(length)))
        except (RenderRequestError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        try:
            with _render_slots:
                frames = render_slides(document, files, slide_count)
        except SlideRenderError as error:
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
            return
        except Exception as error:
            logger.exception("slide_render_failed document=%s", document)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Slide rendering failed: {error}"}
            )
            return
        logger.info("slide_render_completed document=%s slides=%s", document, slide_count)
        self._send_json(
            HTTPStatus.OK, {"frames": [base64.b64encode(frame).decode() for frame in frames]}
        )

    def log_message(self, format: str, *args) -> None:
        logger.debug("%s %s", self.address_string(), format % args)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
    # Listens on every container interface; Compose does not publish the port.
    host = os.environ.get("SLIDE_RENDERER_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("SLIDE_RENDERER_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), SlideRendererHandler)
    logger.info("slide_renderer_listening host=%s port=%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
