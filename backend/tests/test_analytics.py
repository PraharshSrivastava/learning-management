from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.core import analytics
from app.core.request_context import posthog_session_id


class _FakeClient:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.stopped: list[str] = []

    def capture(self, event: str, **kwargs) -> None:
        self.events.append((event, kwargs))

    def flush(self) -> None:
        self.stopped.append("flush")

    def shutdown(self) -> None:
        self.stopped.append("shutdown")


class _FailingClient(_FakeClient):
    def capture(self, event: str, **kwargs) -> None:
        raise RuntimeError("network down")


@pytest.fixture(autouse=True)
def reset_analytics(monkeypatch):
    monkeypatch.setattr(analytics, "_client", None)
    token = posthog_session_id.set(None)
    yield
    posthog_session_id.reset(token)


def test_start_without_key_never_imports_posthog() -> None:
    code = (
        "import sys\n"
        "from app.core import analytics\n"
        "from app.core.settings import settings\n"
        "assert not settings.posthog_api_key\n"
        "analytics.start_analytics()\n"
        "analytics.capture_event('trainer-1', 'x')\n"
        "analytics.stop_analytics()\n"
        "assert 'posthog' not in sys.modules\n"
        "assert analytics._client is None\n"
    )
    backend_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_dir,
        env={"POSTHOG_API_KEY": "", "PYTHONPATH": str(backend_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_capture_is_noop_when_off() -> None:
    analytics.capture_event("trainer-1", "anything", {"a": 1})
    assert analytics._client is None


def test_capture_sends_event_with_session_id() -> None:
    client = _FakeClient()
    analytics._client = client
    posthog_session_id.set("session-1")

    analytics.capture_event("trainer-1", "course_completed", {"course_id": "c1"})

    assert client.events == [
        (
            "course_completed",
            {
                "distinct_id": "trainer-1",
                "properties": {"course_id": "c1", "$session_id": "session-1"},
            },
        )
    ]


def test_capture_skips_missing_distinct_id_and_omits_empty_session() -> None:
    client = _FakeClient()
    analytics._client = client

    analytics.capture_event(None, "skipped")
    analytics.capture_event("employee-1", "sent")

    assert client.events == [("sent", {"distinct_id": "employee-1", "properties": {}})]


def test_capture_never_raises_when_client_fails() -> None:
    analytics._client = _FailingClient()
    analytics.capture_event("trainer-1", "generation_job_failed", {"job_id": "j1"})


def test_stop_flushes_and_clears_client() -> None:
    client = _FakeClient()
    analytics._client = client

    analytics.stop_analytics()

    assert client.stopped == ["flush", "shutdown"]
    assert analytics._client is None


def test_capture_prefers_explicit_session_id() -> None:
    client = _FakeClient()
    analytics._client = client
    posthog_session_id.set("request-session")

    analytics.capture_event("trainer-1", "x", session_id="job-session")

    assert client.events[0][1]["properties"] == {"$session_id": "job-session"}


def test_process_job_outcome_keeps_the_submitting_session(monkeypatch, tmp_path) -> None:
    from app.services import jobs as jobs_module

    class _DoneProcess:
        returncode = 0

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(jobs_module.subprocess, "Popen", lambda *a, **k: _DoneProcess())
    client = _FakeClient()
    analytics._client = client
    manager = jobs_module.GenerationJobManager()
    posthog_session_id.set("browser-session")

    try:
        job = manager.submit_process(
            "course-1", backend_dir=tmp_path, restart_from_blueprint=True, trainer_id="trainer-1"
        )
    finally:
        manager.shutdown()
        # shutdown() stops the shared generation queue; later tests need it running.
        jobs_module.generation_queue.start()

    event, kwargs = client.events[0]
    assert event == "generation_job_completed"
    assert kwargs["distinct_id"] == "trainer-1"
    assert kwargs["properties"]["job_id"] == job.id
    assert kwargs["properties"]["$session_id"] == "browser-session"
