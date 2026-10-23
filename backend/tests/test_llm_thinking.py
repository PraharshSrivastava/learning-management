"""Verify the thinking switch is scoped to each client's outgoing requests."""

import pytest

from app.core.providers import LLMClient


@pytest.mark.parametrize("thinking", [None, False, True])
def test_thinking_request_option(monkeypatch, thinking):
    payloads = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]}

    def post(url, *, headers, json, timeout):
        payloads.append(json)
        return Response()

    monkeypatch.setattr("app.core.providers.requests.post", post)
    options = dict(
        base_url="http://proxy.example/v1", model="qwen", api_key=None,
        context_window=100000, max_input_tokens=87000, max_output_tokens=12000,
    )
    lms = LLMClient(**options, enable_thinking=thinking)
    other_project = LLMClient(**options)
    for client in (lms, other_project):
        assert client._post([{"role": "user", "content": "Reply OK"}], None, 0, 32).choices[0].message.content == "OK"
    if thinking is None:
        assert "chat_template_kwargs" not in payloads[0]
    else:
        assert payloads[0]["chat_template_kwargs"] == {"enable_thinking": thinking}
    assert "chat_template_kwargs" not in payloads[1]
