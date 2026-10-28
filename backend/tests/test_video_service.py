from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

import pytest

from app.core.settings import Settings, settings
from app.generation import runtime, video_service
from app.generation.video_service import (
    ModuleVideoJob,
    VideoServiceBusy,
    VideoServiceClient,
    VideoServiceError,
    VideoServiceRequestRejected,
    build_module_request,
)

SECRET = "s" * 40
SOURCE = "Listen carefully to the customer and confirm the request before acting. " * 2
VIDEO_BYTES = b"fake mp4 bytes"
SRT = "1\n00:00:00,000 --> 00:00:01,500\nHello there\n\n2\n00:00:01,500 --> 00:00:03,000\nSecond line\n"


def reference_signature(method, path, query, timestamp, nonce, body):
    """Mirror of `sign()` in Video Generator's website/backend/middleware/service_auth.py."""
    canonical = "\n".join(
        [method.upper(), path, query, timestamp, nonce, hashlib.sha256(body).hexdigest()]
    ).encode()
    return hmac.new(SECRET.encode(), canonical, hashlib.sha256).hexdigest()


def course_fixture(**overrides) -> dict:
    course = {
        "course_id": "course_abc-123",
        "course_name": "Customer Support Training",
        "course_objective": "Handle requests clearly.",
        "target_audience": "Support employees",
        "language": "English",
        "modules": [
            {
                "module_id": "course_abc-123:module:1",
                "module_number": 1,
                "title": "Understanding Customer Needs",
                "source_text": SOURCE,
            }
        ],
    }
    course.update(overrides)
    return course


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b"", headers=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self._content = content
        self.headers = headers or {}
        self.reason = "reason"
        self.encoding = "utf-8"
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def iter_content(self, chunk_size):
        yield self._content

    def close(self):
        pass


class RecordingSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_signed_request_matches_service_reference_and_sends_signed_bytes():
    session = RecordingSession([FakeResponse(202, {"id": "anim_1", "status": "queued"})])
    client = VideoServiceClient("http://127.0.0.1:8090", SECRET, session=session)

    client.submit({"b": 1, "a": "x"})

    method, url, kwargs = session.calls[0]
    headers = kwargs["headers"]
    assert method == "POST"
    assert url == "http://127.0.0.1:8090/api/v1/animation-requests"
    assert kwargs["data"] == b'{"b":1,"a":"x"}'
    assert headers["Content-Type"] == "application/json"
    assert len(headers["X-VG-Nonce"]) >= 16
    assert headers["X-VG-Signature"] == reference_signature(
        "POST",
        "/api/v1/animation-requests",
        "",
        headers["X-VG-Timestamp"],
        headers["X-VG-Nonce"],
        kwargs["data"],
    )


def test_get_requests_sign_empty_body():
    session = RecordingSession([FakeResponse(200, {"id": "anim_1", "status": "processing"})])
    client = VideoServiceClient("http://vg", SECRET, session=session)

    client.status("anim_1")

    _method, url, kwargs = session.calls[0]
    headers = kwargs["headers"]
    assert url == "http://vg/api/v1/animation-requests/anim_1"
    assert kwargs["data"] is None
    assert "Content-Type" not in headers
    assert headers["X-VG-Signature"] == reference_signature(
        "GET", "/api/v1/animation-requests/anim_1", "", headers["X-VG-Timestamp"],
        headers["X-VG-Nonce"], b"",
    )


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (FakeResponse(429, {"detail": "busy"}, headers={"Retry-After": "7"}), VideoServiceBusy),
        (FakeResponse(409, {"detail": "request_id reused"}), VideoServiceRequestRejected),
        (FakeResponse(410, {"detail": "deleted"}), VideoServiceRequestRejected),
        (FakeResponse(422, {"detail": [{"loc": ["body"], "msg": "bad"}]}), VideoServiceError),
    ],
)
def test_submit_maps_http_errors(response, error_type):
    client = VideoServiceClient("http://vg", SECRET, session=RecordingSession([response]))

    with pytest.raises(error_type) as raised:
        client.submit({"request_id": "x"})

    if error_type is VideoServiceBusy:
        assert raised.value.retry_after == 7
    if response.status_code == 422:
        assert not raised.value.retryable


def test_build_module_request_strips_images_and_sanitizes_identifiers():
    course = course_fixture(document_builder={"revision": 3})
    module = dict(course["modules"][0])
    module["source_text"] = SOURCE + "\n\n[IMAGE: img_1]\nA caption"

    payload = build_module_request(course, module, "lms-1")

    assert payload["request_id"] == "lms-1"
    assert payload["course_id"] == "course_abc-123"
    assert payload["blueprint_revision"] == 3
    assert payload["language"] == "English"
    assert payload["module"]["module_id"] == "module-1"
    assert "[IMAGE" not in payload["module"]["source_text"]
    assert payload["module"]["source_text"].endswith("A caption")


@pytest.mark.parametrize(
    ("course_changes", "module_changes", "message"),
    [
        ({"language": "Hindi"}, {}, "English only"),
        ({}, {"source_text": "Too short [IMAGE: x]"}, "too short"),
        ({}, {"source_text": "x" * 100_001}, "exceeds"),
    ],
)
def test_build_module_request_rejects_input_the_service_refuses(
    course_changes, module_changes, message
):
    course = course_fixture(**course_changes)
    module = {**course["modules"][0], **module_changes}

    with pytest.raises(ValueError, match=message):
        build_module_request(course, module, "lms-1")


class FakeClient:
    """Scripted Video Generator: statuses are served in order after submission."""

    def __init__(self, statuses, *, submit_errors=(), video=VIDEO_BYTES, sha=None):
        self.statuses = list(statuses)
        self.submit_errors = list(submit_errors)
        self.video = video
        self.sha = sha
        self.submitted = []
        self.retried = []
        self.deleted = []
        self.status_calls = 0

    def _status(self, status, **extra):
        document = {"id": "anim_1", "status": status, "stage": "rendering", "progress": 50}
        if status == "succeeded":
            document["output"] = {
                "size_bytes": len(VIDEO_BYTES),
                "sha256": self.sha or hashlib.sha256(VIDEO_BYTES).hexdigest(),
                "duration_seconds": 3.0,
                "captions_url": "/captions",
            }
        document.update(extra)
        return document

    def submit(self, payload):
        if self.submit_errors:
            raise self.submit_errors.pop(0)
        self.submitted.append(payload)
        return self._status("queued")

    def status(self, run_id):
        self.status_calls += 1
        entry = self.statuses.pop(0)
        return self._status(**entry) if isinstance(entry, dict) else self._status(entry)

    def retry(self, run_id):
        self.retried.append(run_id)
        return self._status("queued")

    def delete(self, run_id):
        self.deleted.append(run_id)

    def download_video(self, run_id, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.video)

    def download_captions(self, run_id):
        return SRT


@pytest.fixture
def service_env(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "video_dir", tmp_path / "videos")
    monkeypatch.setattr(settings, "video_service_poll_interval_seconds", 5)
    monkeypatch.setattr(settings, "video_service_module_timeout_seconds", 3600)
    monkeypatch.setattr(settings, "video_service_max_remote_retries", 2)
    hls_calls = []
    monkeypatch.setattr(
        "app.generation.video.generate_hls_playlist", lambda path: hls_calls.append(path)
    )
    return {"hls": hls_calls, "dir": tmp_path / "videos"}


def run_job(client, module=None, *, sleeps=None):
    course = course_fixture()
    module = module or course["modules"][0]
    records = []
    job = ModuleVideoJob(
        client,
        course,
        module,
        save_record=records.append,
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
    )
    return job, job.run(), records


def test_module_job_submits_polls_downloads_and_cleans_up(service_env):
    client = FakeClient(["processing", "succeeded"])
    sleeps = []

    _job, video_path, records = run_job(client, sleeps=sleeps)

    video = service_env["dir"] / "course_course_abc-123" / "module_1.mp4"
    assert video_path == "assets/videos/course_course_abc-123/module_1.mp4"
    assert video.read_bytes() == VIDEO_BYTES
    assert service_env["hls"] == [video]
    assert client.deleted == ["anim_1"]
    assert sleeps == [5, 5]
    assert len(client.submitted) == 1
    assert client.submitted[0]["request_id"] == records[0]["request_id"]
    assert records[0]["status"] == "submitting"
    assert records[-1]["status"] == "stored"

    # Subtitles are burned in by the service; the SRT is kept only as a transcript.
    assert video.with_suffix(".srt").read_text(encoding="utf-8") == SRT
    assert not video.with_suffix(".vtt").exists()
    assert not video.with_suffix(".captions.json").exists()


def test_module_job_removes_local_soft_captions_to_avoid_duplicates(service_env):
    video = service_env["dir"] / "course_course_abc-123" / "module_1.mp4"
    video.parent.mkdir(parents=True)
    for suffix in (".vtt", ".captions.json", ".source.json"):
        video.with_suffix(suffix).write_text("stale", encoding="utf-8")

    run_job(FakeClient(["succeeded"]))

    for suffix in (".vtt", ".captions.json", ".source.json"):
        assert not video.with_suffix(suffix).exists()


def test_module_job_waits_when_service_is_busy(service_env):
    client = FakeClient(
        ["succeeded"], submit_errors=[VideoServiceBusy("busy", retry_after=60)]
    )
    sleeps = []

    run_job(client, sleeps=sleeps)

    assert sleeps[0] == 60
    assert len(client.submitted) == 1


def test_module_job_uses_new_request_id_after_rejection(service_env):
    client = FakeClient(
        ["succeeded"], submit_errors=[VideoServiceRequestRejected("gone", status_code=410)]
    )

    _job, _path, records = run_job(client)

    request_ids = {record.get("request_id") for record in records if record.get("request_id")}
    assert len(request_ids) == 2
    assert client.submitted[0]["request_id"] == records[-1]["request_id"]


def test_module_job_retries_retryable_failure_remotely(service_env):
    client = FakeClient(
        [{"status": "failed", "error": {"message": "tts down", "retryable": True}}, "succeeded"]
    )

    _job, _path, records = run_job(client)

    assert client.retried == ["anim_1"]
    assert records[-1]["status"] == "stored"


def test_module_job_fails_and_forgets_request_on_permanent_failure(service_env):
    client = FakeClient([{"status": "failed", "error": {"message": "bad", "retryable": False}}])
    course = course_fixture()
    records = []
    job = ModuleVideoJob(
        client, course, course["modules"][0], save_record=records.append, sleep=lambda _s: None
    )

    with pytest.raises(VideoServiceError, match="Module 1 video bad"):
        job.run()

    assert "request_id" not in records[-1]
    assert records[-1]["status"] == "failed"
    assert client.deleted == ["anim_1"]


def test_module_job_reports_needs_attention(service_env):
    client = FakeClient(["needs_attention"])
    course = course_fixture()
    job = ModuleVideoJob(
        client, course, course["modules"][0], save_record=lambda _r: None, sleep=lambda _s: None
    )

    with pytest.raises(VideoServiceError, match="manual step"):
        job.run()


def test_module_job_rejects_checksum_mismatch(service_env):
    client = FakeClient(["succeeded"], sha="0" * 64)
    course = course_fixture()
    job = ModuleVideoJob(
        client, course, course["modules"][0], save_record=lambda _r: None, sleep=lambda _s: None
    )

    with pytest.raises(VideoServiceError, match="checksum"):
        job.run()

    assert not (service_env["dir"] / "course_course_abc-123" / "module_1.mp4").exists()


def test_module_job_resumes_existing_run_without_resubmitting(service_env):
    client = FakeClient(["processing", "succeeded"])
    course = course_fixture()
    module = {
        **course["modules"][0],
        "video_service": {"request_id": "lms-old", "run_id": "anim_1", "status": "processing"},
    }

    run_job(client, module)

    assert client.submitted == []
    assert client.status_calls == 2


def test_module_job_times_out(service_env, monkeypatch):
    monkeypatch.setattr(settings, "video_service_module_timeout_seconds", 8)
    client = FakeClient(["processing"] * 5)
    course = course_fixture()
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    job = ModuleVideoJob(
        client,
        course,
        course["modules"][0],
        save_record=lambda _r: None,
        sleep=sleep,
        clock=lambda: now[0],
    )

    with pytest.raises(VideoServiceError, match="did not finish"):
        job.run()


def test_external_mode_readiness_ignores_slide_script_and_audio_outputs(monkeypatch):
    monkeypatch.setattr(settings, "video_generation_mode", "external")
    monkeypatch.setattr(runtime, "_thumbnail_output_complete", lambda course: True)
    monkeypatch.setattr(runtime, "_asset_is_nonempty", lambda path: bool(path))
    course = {
        "course_id": "c1",
        "modules": [
            {"num_questions": 0, "notes": "Notes", "video_path": "assets/videos/x.mp4"}
        ],
    }

    assert runtime.missing_generation_outputs(course) == []
    assert runtime.is_course_generation_complete(course)

    course["modules"][0].pop("video_path")
    assert runtime.missing_generation_outputs(course) == ["video"]

    monkeypatch.setattr(settings, "video_generation_mode", "local")
    course["modules"][0]["video_path"] = "assets/videos/x.mp4"
    assert {"slides", "html", "scripts", "tts"} <= set(runtime.missing_generation_outputs(course))


def test_external_mode_requires_service_url_and_long_secret():
    with pytest.raises(ValueError, match="VIDEO_SERVICE_BASE_URL"):
        Settings(video_generation_mode="external", video_service_hmac_secret=SECRET)
    with pytest.raises(ValueError, match="at least 32"):
        Settings(
            video_generation_mode="external",
            video_service_base_url="http://127.0.0.1:8090",
            video_service_hmac_secret="short",
        )
    with pytest.raises(ValueError, match="origin"):
        Settings(video_service_base_url="http://vg/api/v1")

    configured = Settings(
        video_generation_mode="external",
        video_service_base_url="http://127.0.0.1:8090/",
        video_service_hmac_secret=SECRET,
    )
    assert configured.video_service_base_url == "http://127.0.0.1:8090"


def test_generate_videos_via_service_skips_stored_videos_and_saves_per_module(
    monkeypatch, service_env
):
    course = course_fixture()
    course["modules"].append(
        {
            "module_id": "course_abc-123:module:2",
            "module_number": 2,
            "title": "Done already",
            "source_text": SOURCE,
            "video_path": "assets/videos/course_course_abc-123/module_2.mp4",
        }
    )
    existing = service_env["dir"] / "course_course_abc-123" / "module_2.mp4"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")
    monkeypatch.setattr(
        "app.core.storage.resolve_public_asset_path",
        lambda path, _settings: service_env["dir"] / Path(path).relative_to("assets/videos"),
    )
    monkeypatch.setattr(
        video_service,
        "resolve_public_asset_path",
        lambda path, _settings: service_env["dir"] / Path(path).relative_to("assets/videos"),
    )
    monkeypatch.setattr(runtime, "load_course_for_generation", lambda _course_id: course)
    saved = []
    monkeypatch.setattr(
        runtime,
        "save_generated_course",
        lambda course_id, snapshot, module_fields=(), **_: saved.append(
            (module_fields, snapshot["modules"])
        ),
    )
    client = FakeClient(["succeeded"])

    video_service.generate_videos_via_service("course_abc-123", client=client)

    assert [payload["module"]["module_number"] for payload in client.submitted] == [1]
    assert all(len(modules) == 1 for _fields, modules in saved)
    assert all(modules[0]["module_number"] == 1 for _fields, modules in saved)
    assert saved[-1][0] == ("video_path",)
    assert saved[-1][1][0]["video_path"] == "assets/videos/course_course_abc-123/module_1.mp4"


class FakeJobs:
    def __init__(self):
        self.calls = []

    def submit_process(self, course_id, **kwargs):
        self.calls.append((course_id, kwargs))
        return {"id": "job-1"}


def generation_service(course):
    from app.services.generation import GenerationService

    class Courses:
        def get_draft(self, _course_id):
            return course

        def get_draft_for_trainer(self, _course_id, _trainer_id):
            return course

    jobs = FakeJobs()
    return GenerationService(jobs, settings, courses=Courses()), jobs


def test_module_video_job_runs_in_background_worker():
    service, jobs = generation_service(course_fixture())

    service.start_module_video_job("course_abc-123", 1, "trainer-1")

    assert jobs.calls == [
        (
            "course_abc-123",
            {
                "backend_dir": settings.backend_dir,
                "restart_from_blueprint": False,
                "module_video": 1,
            },
        )
    ]
    with pytest.raises(ValueError, match="out of range"):
        service.start_module_video_job("course_abc-123", 2, "trainer-1")


def test_continue_job_resumes_failed_checkpoint_but_not_blueprint():
    course = course_fixture(generation={"status": "failed", "failed_checkpoint": "video"})
    service, jobs = generation_service(course)

    service.start_continue_job("course_abc-123", "trainer-1")

    assert jobs.calls[0][1]["restart_from_blueprint"] is False
    assert "module_video" not in jobs.calls[0][1]

    course["generation"]["failed_checkpoint"] = "blueprint"
    with pytest.raises(ValueError, match="continue-generation"):
        service.start_continue_job("course_abc-123", "trainer-1")


def test_job_manager_passes_module_video_to_worker(monkeypatch, tmp_path):
    from app.services import jobs as jobs_module

    commands = []

    class Process:
        returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(
        jobs_module.subprocess,
        "Popen",
        lambda command, **_kwargs: commands.append(command) or Process(),
    )
    manager = jobs_module.GenerationJobManager()
    try:
        manager.submit_process(
            "course-1", backend_dir=tmp_path, restart_from_blueprint=False, module_video=3
        )
        manager._executor_for_submit().submit(lambda: None).result(timeout=5)
        for _ in range(50):
            if commands:
                break
            time.sleep(0.05)
    finally:
        manager.shutdown()

    assert commands and commands[0][-2:] == ["--module-video", "3"]
    assert "--restart-from-blueprint" not in commands[0]


@pytest.mark.parametrize("mode", ["local", "external"])
def test_module_video_regeneration_follows_video_mode(monkeypatch, mode):
    monkeypatch.setattr(settings, "video_generation_mode", mode)
    calls = []
    monkeypatch.setattr(
        "app.generation.video_service.generate_video_for_module_via_service",
        lambda course_id, number, force: calls.append(("external", number, force)) or "ext",
    )
    monkeypatch.setattr(
        "app.generation.video.generate_video_for_module",
        lambda course_id, number: calls.append(("local", number)) or "loc",
    )

    runtime.run_module_video_generation("course-1", 2)

    assert calls == ([("external", 2, True)] if mode == "external" else [("local", 2)])


def test_module_response_exposes_video_service_progress():
    from app.schemas.course import ModuleResponse

    module = ModuleResponse.model_validate(
        {"title": "M", "video_service": {"status": "processing", "stage": "audio", "progress": 68}}
    )

    assert module.video_service.progress == 68
    assert module.video_service.stage == "audio"
