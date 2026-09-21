from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import langfuse_tracing
from app.generation.parallel import run_parallel_stage_items


class FakeContext:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeGeneration:
    def __init__(self, values: dict):
        self.values = values
        self.ended = False

    def update(self, **kwargs):
        self.values.update(kwargs)
        return self

    def end(self):
        self.ended = True


class FakeTrace:
    def __init__(self):
        self.generations: list[dict] = []
        self.scores: list[dict] = []
        self.updates: list[dict] = []

    def start_observation(self, **kwargs):
        self.generations.append(kwargs)
        return FakeGeneration(kwargs)

    def start_as_current_observation(self, **kwargs):
        return FakeContext(self)

    def score_trace(self, **kwargs):
        self.scores.append(kwargs)

    def update(self, **kwargs):
        self.updates.append(kwargs)


class FakeClient:
    def __init__(self):
        self.trace_instance = FakeTrace()
        self.trace_calls: list[dict] = []
        self.flush_count = 0

    def start_as_current_observation(self, **kwargs):
        self.trace_calls.append(kwargs)
        return FakeContext(self.trace_instance)

    def flush(self):
        self.flush_count += 1


@pytest.fixture(autouse=True)
def reset_tracing(monkeypatch):
    langfuse_tracing._reset_for_tests()
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_enabled", False)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_host", None)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_public_key", None)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_secret_key", None)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_capture_content", False)
    yield
    langfuse_tracing._reset_for_tests()


def _enable(monkeypatch, fake_client: FakeClient) -> None:
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_enabled", True)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_host", "http://langfuse:3000")
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_public_key", "public")
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_secret_key", "secret")
    monkeypatch.setattr(langfuse_tracing, "_client", fake_client)
    monkeypatch.setattr(langfuse_tracing, "_client_checked", True)


def test_missing_configuration_is_a_noop():
    with langfuse_tracing.trace_scope("lms.test") as trace:
        assert trace is None
        assert langfuse_tracing.record_generation(name="llm", model="model") is None


def test_enabled_with_incomplete_configuration_warns_once(monkeypatch, caplog):
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_enabled", True)

    assert langfuse_tracing.get_langfuse() is None
    assert langfuse_tracing.get_langfuse() is None

    messages = [
        record.message
        for record in caplog.records
        if "langfuse_configuration_incomplete" in record.message
    ]
    assert len(messages) == 1
    assert "LANGFUSE_HOST" in messages[0]
    assert "LANGFUSE_PUBLIC_KEY" in messages[0]
    assert "LANGFUSE_SECRET_KEY" in messages[0]


def test_trace_scope_records_success_and_flushes(monkeypatch):
    client = FakeClient()
    _enable(monkeypatch, client)

    with langfuse_tracing.trace_scope(
        "lms.course_generation",
        session_id="job-1",
        user_id="trainer-1",
        metadata={"course_id": "course-1"},
    ) as trace:
        assert trace is client.trace_instance
        langfuse_tracing.record_generation(
            name="quiz",
            model="model-1",
            input_value=[{"role": "user", "content": "private"}],
            output_value="private output",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        )

    assert client.trace_instance.generations[0]["input"] is None
    assert client.trace_instance.generations[0]["output"] is None
    assert client.trace_instance.generations[0]["usage_details"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert client.trace_instance.scores == [
        {"name": "generation_success", "value": 1, "comment": None}
    ]
    assert client.trace_instance.updates == [{"output": {"status": "completed"}}]
    assert client.flush_count == 1


def test_trace_scope_preserves_business_exception(monkeypatch):
    client = FakeClient()
    _enable(monkeypatch, client)

    with pytest.raises(ValueError, match="pipeline failed"):
        with langfuse_tracing.trace_scope("lms.course_generation"):
            raise ValueError("pipeline failed")

    assert client.trace_instance.scores[0]["value"] == 0
    assert client.trace_instance.updates[0]["output"]["status"] == "failed"
    assert client.flush_count == 1


def test_content_capture_is_bounded(monkeypatch):
    client = FakeClient()
    _enable(monkeypatch, client)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_capture_content", True)
    monkeypatch.setattr(langfuse_tracing.settings, "langfuse_capture_max_chars", 100)

    with langfuse_tracing.trace_scope("lms.test"):
        langfuse_tracing.record_generation(
            name="llm",
            model="model",
            input_value=SimpleNamespace(value="x" * 200),
            output_value="y" * 200,
        )

    generation = client.trace_instance.generations[0]
    assert generation["input"].endswith("...[truncated]")
    assert generation["output"].endswith("...[truncated]")


def test_parallel_generation_items_inherit_trace_context(monkeypatch):
    client = FakeClient()
    _enable(monkeypatch, client)

    def record_item(item: int) -> int:
        langfuse_tracing.record_generation(name=f"item-{item}", model="model")
        return item

    with langfuse_tracing.trace_scope("lms.parallel"):
        results = run_parallel_stage_items(
            course_id="course-1",
            stage="quiz",
            items=[1, 2, 3],
            worker_count=3,
            operation=record_item,
            item_label=lambda item: {"module": item},
        )

    assert sorted(results) == [1, 2, 3]
    assert {item["name"] for item in client.trace_instance.generations} == {
        "item-1",
        "item-2",
        "item-3",
    }
