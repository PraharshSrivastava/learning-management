"""Produce module videos through the external Video Generator service.

The service contract lives in the Video Generator repository at
`docs/lms-integration-guide.md`: submit a module to `/api/v1/animation-requests`,
poll its status, download the MP4 and SRT, then delete the remote copy.
Every request is HMAC-SHA256 signed with a shared secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from app.core.exceptions import ProviderError
from app.core.logging import generation_logger
from app.core.settings import settings
from app.core.storage import public_asset_url, resolve_public_asset_path

logger = generation_logger(__name__)

API_PATH = "/api/v1/animation-requests"
TERMINAL_STATUSES = {"succeeded", "failed", "needs_attention"}
MIN_SOURCE_CHARS = 50
MAX_SOURCE_CHARS = 100_000
MAX_COURSE_NAME_CHARS = 200
MAX_TITLE_CHARS = 200
MAX_OBJECTIVE_CHARS = 2000
MAX_AUDIENCE_CHARS = 500
DEFAULT_BUSY_DELAY_SECONDS = 60
DOWNLOAD_ATTEMPTS = 2
MAX_REQUEST_REJECTIONS = 3
_IDENTIFIER_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_IMAGE_MARKER_PATTERN = re.compile(r"\[IMAGE:[^\]]*\]", re.IGNORECASE)
_ENGLISH_LANGUAGES = {"", "en", "english"}


class VideoServiceError(ProviderError):
    """A Video Generator call failed; `retryable` says whether waiting may help."""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.http_status = status_code
        self.retryable = retryable


class VideoServiceBusy(VideoServiceError):
    """The service already holds its maximum number of active runs (HTTP 429)."""

    def __init__(self, message: str, *, retry_after: float):
        super().__init__(message, status_code=429, retryable=True)
        self.retry_after = retry_after


class VideoServiceRequestRejected(VideoServiceError):
    """The request_id cannot be reused (409 body mismatch or 410 deleted run)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_detail(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, (list, dict)):
        detail = json.dumps(detail)[:500]
    return str(detail or response.reason or f"HTTP {response.status_code}")


class VideoServiceClient:
    """Thin HMAC-signed client for the Video Generator LMS API."""

    def __init__(
        self,
        base_url: str,
        secret: str,
        *,
        timeout_seconds: float = 60,
        session: requests.Session | None = None,
    ):
        if not base_url or not secret:
            raise VideoServiceError("Video service base URL and secret are required")
        self.base_url = base_url.rstrip("/")
        self._secret = secret.encode()
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    @classmethod
    def from_settings(cls) -> "VideoServiceClient":
        return cls(
            settings.video_service_base_url or "",
            settings.video_service_hmac_secret or "",
            timeout_seconds=settings.video_service_request_timeout_seconds,
        )

    def signed_headers(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        *,
        query: str = "",
        timestamp: str | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        timestamp = timestamp or str(int(time.time()))
        nonce = nonce or secrets.token_urlsafe(24)
        canonical = "\n".join(
            [method.upper(), path, query, timestamp, nonce, hashlib.sha256(body).hexdigest()]
        )
        signature = hmac.new(self._secret, canonical.encode(), hashlib.sha256).hexdigest()
        return {
            "X-VG-Timestamp": timestamp,
            "X-VG-Nonce": nonce,
            "X-VG-Signature": signature,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        stream: bool = False,
    ) -> requests.Response:
        # Sign the exact bytes sent; re-serialising would break the body hash.
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = self.signed_headers(method, path, body)
        if payload is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = self.session.request(
                method,
                self.base_url + path,
                data=body or None,
                headers=headers,
                timeout=self.timeout_seconds,
                stream=stream,
            )
        except requests.RequestException as error:
            raise VideoServiceError(
                f"Video service is unreachable: {error}", retryable=True
            ) from error
        if response.status_code == 429:
            try:
                retry_after = float(response.headers.get("Retry-After") or DEFAULT_BUSY_DELAY_SECONDS)
            except ValueError:
                retry_after = DEFAULT_BUSY_DELAY_SECONDS
            raise VideoServiceBusy(_error_detail(response), retry_after=max(1.0, retry_after))
        if response.status_code >= 400:
            message = f"Video service {method} {path} failed ({response.status_code}): {_error_detail(response)}"
            if response.status_code == 410 or (
                response.status_code == 409 and method == "POST" and path == API_PATH
            ):
                raise VideoServiceRequestRejected(message, status_code=response.status_code)
            raise VideoServiceError(
                message,
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )
        return response

    def _json(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError as error:
            raise VideoServiceError("Video service returned invalid JSON", retryable=True) from error
        if not isinstance(data, dict) or not data.get("id"):
            raise VideoServiceError("Video service response has no run id", retryable=True)
        return data

    def submit(self, payload: dict) -> dict:
        return self._json(self._request("POST", API_PATH, payload=payload))

    def status(self, run_id: str) -> dict:
        return self._json(self._request("GET", f"{API_PATH}/{run_id}"))

    def retry(self, run_id: str) -> dict:
        return self._json(self._request("POST", f"{API_PATH}/{run_id}/retry"))

    def delete(self, run_id: str) -> None:
        self._request("DELETE", f"{API_PATH}/{run_id}")

    def download_video(self, run_id: str, destination: Path) -> None:
        response = self._request("GET", f"{API_PATH}/{run_id}/video", stream=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        stream.write(chunk)
        except requests.RequestException as error:
            destination.unlink(missing_ok=True)
            raise VideoServiceError(f"Video download interrupted: {error}", retryable=True) from error
        finally:
            response.close()

    def download_captions(self, run_id: str) -> str:
        response = self._request("GET", f"{API_PATH}/{run_id}/captions")
        response.encoding = response.encoding or "utf-8"
        return response.text


def _identifier(value: str, fallback: str) -> str:
    cleaned = _IDENTIFIER_PATTERN.sub("-", str(value or "")).strip("-")[:100]
    return cleaned or fallback


def _clip(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def blueprint_revision(course: dict) -> int:
    builder = course.get("document_builder")
    try:
        revision = int(builder.get("revision")) if isinstance(builder, dict) else 1
    except (TypeError, ValueError):
        revision = 1
    return max(1, revision)


def module_source_text(module: dict) -> str:
    # The service accepts text only; image placeholders would be narrated literally.
    text = _IMAGE_MARKER_PATTERN.sub("", str(module.get("source_text") or ""))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_module_request(course: dict, module: dict, request_id: str) -> dict:
    """Build the animation request body, rejecting input the service would refuse."""
    module_number = int(module.get("module_number") or 0)
    if module_number < 1:
        raise ValueError("Module has no valid module number")
    language = str(course.get("language") or "").strip()
    if language.lower() not in _ENGLISH_LANGUAGES:
        raise ValueError(
            f"Video service supports English only; course language is '{language}'."
        )
    source_text = module_source_text(module)
    if len(source_text) < MIN_SOURCE_CHARS:
        raise ValueError(
            f"Module {module_number} source text is too short for video generation "
            f"({len(source_text)} of at least {MIN_SOURCE_CHARS} characters)."
        )
    if len(source_text) > MAX_SOURCE_CHARS:
        raise ValueError(
            f"Module {module_number} source text exceeds {MAX_SOURCE_CHARS} characters; "
            "split it into smaller modules."
        )
    course_id = str(course.get("course_id") or "")
    payload: dict[str, Any] = {
        "request_id": request_id,
        "course_id": _identifier(course_id, "course"),
        "blueprint_revision": blueprint_revision(course),
        "course_name": _clip(course.get("course_name"), MAX_COURSE_NAME_CHARS) or "Course",
        "language": "English",
        "module": {
            "module_id": f"module-{module_number}",
            "module_number": module_number,
            "title": _clip(module.get("title"), MAX_TITLE_CHARS) or f"Module {module_number}",
            "source_text": source_text,
        },
    }
    objective = _clip(course.get("course_objective"), MAX_OBJECTIVE_CHARS)
    if objective:
        payload["course_objective"] = objective
    audience = _clip(course.get("target_audience"), MAX_AUDIENCE_CHARS)
    if audience:
        payload["target_audience"] = audience
    return payload


def new_request_id() -> str:
    return f"lms-{secrets.token_hex(12)}"


def _module_video_file(course_id: str, module_number: int) -> Path:
    return settings.video_dir / f"course_{course_id}" / f"module_{module_number}.mp4"


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _remove_stale_captions(video: Path) -> None:
    # Soft-caption sidecars from local rendering would duplicate the burned-in subtitles.
    for suffix in (".vtt", ".captions.json", ".source.json", ".srt"):
        video.with_suffix(suffix).unlink(missing_ok=True)


class ModuleVideoJob:
    """Drive one module from submission to a stored, playable MP4."""

    def __init__(
        self,
        client: VideoServiceClient,
        course: dict,
        module: dict,
        *,
        save_record: Callable[[dict], None],
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.client = client
        self.course = course
        self.module = module
        self.course_id = str(course["course_id"])
        self.module_number = int(module.get("module_number") or 0)
        self.record: dict = dict(module.get("video_service") or {})
        self._save_record = save_record
        self._sleep = sleep
        self._clock = clock
        self._deadline = clock() + settings.video_service_module_timeout_seconds

    def _persist(self, **updates: Any) -> None:
        self.record.update(updates)
        self.record["updated_at"] = _now_iso()
        self._save_record(dict(self.record))

    def _remember_status(self, status: dict) -> None:
        error = status.get("error") if isinstance(status.get("error"), dict) else None
        self._persist(
            run_id=status.get("id") or self.record.get("run_id"),
            status=status.get("status"),
            stage=status.get("stage"),
            progress=status.get("progress"),
            error=(error or {}).get("message"),
        )

    def _wait(self, seconds: float) -> None:
        if self._clock() + seconds > self._deadline:
            raise VideoServiceError(
                f"Module {self.module_number} video did not finish within "
                f"{settings.video_service_module_timeout_seconds:.0f} seconds "
                f"(run {self.record.get('run_id') or 'not started'})."
            )
        self._sleep(seconds)

    def _submit(self) -> dict:
        rejections = 0
        while True:
            if not self.record.get("request_id"):
                # Persist the id before sending so a crash replays instead of duplicating.
                self._persist(request_id=new_request_id(), run_id=None, status="submitting")
            payload = build_module_request(self.course, self.module, self.record["request_id"])
            try:
                status = self.client.submit(payload)
            except VideoServiceBusy as busy:
                logger.info(
                    "video_service_busy course_id=%s module=%s retry_after=%s",
                    self.course_id,
                    self.module_number,
                    busy.retry_after,
                )
                self._wait(busy.retry_after)
                continue
            except VideoServiceRequestRejected as rejected:
                rejections += 1
                if rejections > MAX_REQUEST_REJECTIONS:
                    raise
                logger.info(
                    "video_service_request_rejected course_id=%s module=%s reason=%s",
                    self.course_id,
                    self.module_number,
                    rejected,
                )
                self.record.pop("request_id", None)
                continue
            self._persist(remote_retries=0)
            self._remember_status(status)
            return status

    def _current_status(self) -> dict:
        run_id = self.record.get("run_id")
        # A cleared request_id means the previous run is abandoned; submit fresh work.
        if (
            run_id
            and self.record.get("request_id")
            and self.record.get("status") not in {None, "submitting"}
        ):
            try:
                status = self.client.status(run_id)
            except VideoServiceError as error:
                if error.http_status != 404:
                    raise
                # The run was purged remotely; start a fresh submission.
                self.record.pop("request_id", None)
                return self._submit()
            self._remember_status(status)
            return status
        return self._submit()

    def _poll_until_terminal(self, status: dict) -> dict:
        while status.get("status") not in TERMINAL_STATUSES:
            self._wait(settings.video_service_poll_interval_seconds)
            try:
                status = self.client.status(self.record["run_id"])
            except VideoServiceBusy as busy:
                self._wait(busy.retry_after)
                continue
            except VideoServiceError as error:
                if not error.retryable:
                    raise
                logger.warning(
                    "video_service_poll_failed course_id=%s module=%s reason=%s",
                    self.course_id,
                    self.module_number,
                    error,
                )
                continue
            self._remember_status(status)
        return status

    def _download(self, status: dict) -> Path:
        output = status.get("output") or {}
        destination = _module_video_file(self.course_id, self.module_number)
        staged = destination.with_suffix(".download.mp4")
        last_error: Exception | None = None
        for _attempt in range(DOWNLOAD_ATTEMPTS):
            try:
                self.client.download_video(self.record["run_id"], staged)
                expected_size = output.get("size_bytes")
                expected_hash = str(output.get("sha256") or "").lower()
                if expected_size is not None and staged.stat().st_size != int(expected_size):
                    raise VideoServiceError("Downloaded video size does not match", retryable=True)
                if expected_hash and _file_sha256(staged) != expected_hash:
                    raise VideoServiceError("Downloaded video checksum does not match", retryable=True)
                if staged.stat().st_size <= 0:
                    raise VideoServiceError("Downloaded video is empty", retryable=True)
                _remove_stale_captions(destination)
                staged.replace(destination)
                return destination
            except VideoServiceError as error:
                last_error = error
                staged.unlink(missing_ok=True)
                if not error.retryable:
                    break
        raise VideoServiceError(
            f"Module {self.module_number} video download failed: {last_error}"
        )

    def _store_transcript(self, video: Path, status: dict) -> None:
        """Keep the service SRT as a transcript; its subtitles are already burned in."""
        output = status.get("output") or {}
        if not output.get("captions_url"):
            return
        try:
            from app.generation.captions import atomic_text

            atomic_text(video.with_suffix(".srt"), self.client.download_captions(self.record["run_id"]))
        except Exception as error:
            # The video already shows subtitles, so a missing transcript is not fatal.
            logger.warning("video_service_transcript_unavailable video=%s reason=%s", video, error)

    def _delete_remote(self) -> None:
        try:
            self.client.delete(self.record["run_id"])
        except VideoServiceError as error:
            # The service's retention policy purges runs we fail to delete.
            logger.warning(
                "video_service_delete_failed run_id=%s reason=%s", self.record["run_id"], error
            )

    def run(self) -> str:
        from app.generation.captions import module_lock
        from app.generation.video import generate_hls_playlist

        status = self._current_status()
        while True:
            status = self._poll_until_terminal(status)
            state = status.get("status")
            if state == "succeeded":
                break
            error = status.get("error") if isinstance(status.get("error"), dict) else {}
            retries = int(self.record.get("remote_retries") or 0)
            if (
                state == "failed"
                and error.get("retryable")
                and retries < settings.video_service_max_remote_retries
            ):
                self._persist(remote_retries=retries + 1)
                status = self.client.retry(self.record["run_id"])
                self._remember_status(status)
                continue
            if state == "needs_attention":
                message = "stopped at a manual step; contact the Video Generator team"
            else:
                message = error.get("message") or "generation failed"
            # Forget the request so the next pipeline attempt submits fresh work.
            self.record.pop("request_id", None)
            self._persist(status=state)
            if state == "failed":
                self._delete_remote()
            raise VideoServiceError(
                f"Module {self.module_number} video {message} (run {self.record.get('run_id')})."
            )

        destination = _module_video_file(self.course_id, self.module_number)
        with module_lock(destination):
            video = self._download(status)
            generate_hls_playlist(video)
            self._store_transcript(video, status)
        self._delete_remote()
        self._persist(status="stored", downloaded_at=_now_iso())
        logger.info(
            "video_service_module_stored course_id=%s module=%s run_id=%s",
            self.course_id,
            self.module_number,
            self.record.get("run_id"),
        )
        return public_asset_url("videos", f"course_{self.course_id}", destination.name)


def _module_has_video(module: dict) -> bool:
    path = str(module.get("video_path") or "")
    if not path:
        return False
    absolute = resolve_public_asset_path(path, settings)
    return absolute.is_file() and absolute.stat().st_size > 0


def _module_saver(course_id: str, module: dict, field: str) -> Callable[[Any], None]:
    """Persist one module field without touching sibling modules written in parallel."""
    from app.generation.runtime import save_generated_course

    def save(value: Any) -> None:
        snapshot = {
            "module_id": module.get("module_id"),
            "module_number": module.get("module_number"),
            field: value,
        }
        save_generated_course(
            course_id,
            {"course_id": course_id, "modules": [snapshot]},
            module_fields=(field,),
        )

    return save


def generate_video_for_module_via_service(
    course_id: str,
    module_number: int,
    *,
    client: VideoServiceClient | None = None,
    force: bool = False,
) -> str:
    from app.generation.runtime import load_course_for_generation

    course = load_course_for_generation(course_id)
    modules = course.get("modules") or []
    if module_number < 1 or module_number > len(modules):
        raise ValueError(f"Module number {module_number} out of range.")
    module = modules[module_number - 1]
    if force:
        module.pop("video_service", None)
        _module_saver(course_id, module, "video_service")({})
    job = ModuleVideoJob(
        client or VideoServiceClient.from_settings(),
        course,
        module,
        save_record=_module_saver(course_id, module, "video_service"),
    )
    video_path = job.run()
    _module_saver(course_id, module, "video_path")(video_path)
    return video_path


def generate_videos_via_service(
    course_id: str,
    *,
    client: VideoServiceClient | None = None,
) -> dict:
    """Generate every module video that is not already stored, bounded by service limits."""
    from app.generation.parallel import run_parallel_stage_items
    from app.generation.runtime import load_course_for_generation, log_event

    course = load_course_for_generation(course_id)
    client = client or VideoServiceClient.from_settings()
    pending: list[dict] = []
    for module in course.get("modules") or []:
        if not int(module.get("module_number") or 0):
            raise ValueError("Module has no valid module number")
        if _module_has_video(module):
            log_event(course_id, "video", "skipped_valid_video", module=module.get("module_number"))
            continue
        # Validate every module before submitting any, so bad input fails fast.
        build_module_request(course, module, "validation-only")
        pending.append(module)

    def produce(module: dict) -> tuple[int, str]:
        module_number = int(module["module_number"])
        log_event(course_id, "video", "module_started", module=module_number)
        job = ModuleVideoJob(
            client,
            course,
            module,
            save_record=_module_saver(course_id, module, "video_service"),
        )
        video_path = job.run()
        _module_saver(course_id, module, "video_path")(video_path)
        log_event(course_id, "video", "module_completed", module=module_number)
        return module_number, video_path

    run_parallel_stage_items(
        course_id=course_id,
        stage="video",
        items=pending,
        worker_count=settings.video_service_max_concurrency,
        item_label=lambda module: {"module": int(module["module_number"])},
        operation=produce,
    )
    return load_course_for_generation(course_id)
