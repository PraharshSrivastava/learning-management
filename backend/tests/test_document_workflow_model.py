from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core.exceptions import ProviderError
from app.core.settings import Settings
from app.document_builder.workflow_model import (
    InvalidModelResponse,
    ModelContextLimit,
    WorkflowModel,
)
from app.generation.runtime import PipelineStageError
from app.schemas.document_workflow import DraftMetadata, SourceReference, WritingSettings


def completion(value, reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=reason,
                message=SimpleNamespace(content=value),
            )
        ]
    )


def outline(count=2):
    return json.dumps(
        {
            "modules": [
                {
                    "title": f"Topic {i}",
                    "objective": f"Apply topic {i}",
                    "sections": ["Explanation", "Practice"],
                }
                for i in range(count)
            ]
        }
    )


class Client:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append((list(messages), kwargs))
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


def run(client, task="outline", **kwargs):
    return WorkflowModel(Settings(), client=client).complete(
        task,
        metadata=DraftMetadata(courseName="Customer Service", targetAudience="New staff"),
        settings=WritingSettings(moduleCount=2),
        context={"topic": "Customer needs"},
        **kwargs,
    )


def test_outline_uses_metadata_and_settings_and_has_no_full_rewrite_prompt():
    client = Client(completion(outline()))
    result = run(client)
    assert result.attempts == 1
    payload = json.loads(client.calls[0][0][1]["content"])
    assert payload["metadata"]["targetAudience"] == "New staff"
    assert payload["settings"]["moduleCount"] == 2
    assert "chain_of_thought" not in json.dumps(payload)
    assert client.calls[0][1]["attempts"] == 1


@pytest.mark.parametrize(
    "bad",
    [
        completion(""),
        completion(None),
        completion(outline(), "length"),
        completion(outline(), "content_filter"),
        completion(outline(), "tool_calls"),
        completion("{broken"),
        completion(outline(3)),
        completion('{"modules": [], "modules": []}'),
        completion('{"modules": [], "reply": "hello"}'),
        SimpleNamespace(choices=[]),
    ],
)
def test_invalid_or_truncated_response_is_repaired_once(bad):
    client = Client(bad, completion(outline()))
    result = run(client)
    assert len(client.calls) == 2
    assert result.attempts == 2
    assert "same task and scope" in client.calls[1][0][-1]["content"]


def test_repeated_invalid_output_is_error_not_salvaged_document():
    client = Client(completion("Module 1: raw text"), completion("still not JSON"))
    with pytest.raises(InvalidModelResponse):
        run(client)
    assert len(client.calls) == 2


def test_transient_and_repair_retries_share_four_request_maximum():
    client = Client(
        ProviderError("503 unavailable"),
        completion("bad JSON"),
        ProviderError("connection timeout"),
        completion(outline()),
    )
    assert run(client).attempts == 4
    assert len(client.calls) == 4


def test_configuration_failure_is_not_retried():
    client = Client(ProviderError("401 invalid key"))
    with pytest.raises(ProviderError, match="unavailable"):
        run(client)
    assert len(client.calls) == 1


def test_existing_provider_wrapped_errors_are_safe_and_bounded():
    client = Client(
        PipelineStageError("document_outline", "503 unavailable"), completion(outline())
    )
    assert run(client).attempts == 2


def test_cancelled_request_never_calls_provider():
    client = Client()
    with pytest.raises(ProviderError, match="cancelled"):
        run(client, cancelled=lambda: True)
    assert not client.calls


def test_cancelled_response_is_not_returned():
    client = Client(completion(outline()))
    with pytest.raises(ProviderError, match="cancelled"):
        run(client, cancelled=lambda: bool(client.calls))


def test_context_overflow_is_not_silently_truncated():
    client = Client()
    engine = WorkflowModel(Settings(llm_context_window=4000), client=client)
    with pytest.raises(ModelContextLimit):
        engine.complete(
            "outline",
            metadata=DraftMetadata(),
            settings=WritingSettings(),
            context={"source": "long" * 10000},
        )
    assert not client.calls


@pytest.mark.parametrize(
    "mode,expected",
    [("prompt", None), ("json_object", "json_object"), ("json_schema", "json_schema")],
)
def test_structured_output_is_selected_by_verified_configuration(mode, expected):
    client = Client(completion(outline()))
    engine = WorkflowModel(Settings(document_builder_output_mode=mode), client=client)
    engine.complete(
        "outline", metadata=DraftMetadata(), settings=WritingSettings(moduleCount=2), context={}
    )
    fmt = client.calls[0][1]["response_format"]
    assert (fmt["type"] if fmt else None) == expected


def test_known_source_reference_is_allowed_but_invented_reference_is_rejected():
    answer = {
        "answer": "Listen first.",
        "insufficientEvidence": False,
        "sourceReferences": [{"sourceId": "source_1", "spanId": "page_4"}],
    }
    client = Client(completion(json.dumps(answer)))
    assert (
        run(
            client,
            task="answer",
            allowed_references=[SourceReference(sourceId="source_1", spanId="page_4")],
        ).content.answer
        == "Listen first."
    )
    client = Client(completion(json.dumps(answer)), completion(json.dumps(answer)))
    with pytest.raises(InvalidModelResponse):
        run(client, task="answer")


def test_module_requires_explanation_not_only_heading():
    invalid = json.dumps({"blocks": [{"type": "heading", "text": "Needs"}]})
    valid = json.dumps({"blocks": [{"type": "paragraph", "text": "Listen to the customer."}]})
    assert run(Client(completion(invalid), completion(valid)), task="module").attempts == 2


def test_shared_model_is_not_changed_by_builder_override():
    config = Settings(document_builder_model="builder-test", llm_model_name="shared-test")
    assert WorkflowModel(config, client=Client()).model == "builder-test"
    assert config.llm_model_name == "shared-test"
