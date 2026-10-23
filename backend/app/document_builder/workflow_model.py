"""Bounded model adapter with strict task and semantic output validation.

Not wired into the legacy builder. The new workflow will call this adapter only
after server-side ownership, revision, target and outline checks.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from app.core.exceptions import ProviderError
from app.core.providers import LLMClient
from app.core.settings import Settings
from app.document_builder.workflow_prompts import PROMPT_VERSION, SYSTEM, TASKS
from app.generation.runtime import PipelineStageError
from app.schemas.document_workflow import (
    AnswerResponse,
    DraftMetadata,
    EditResponse,
    ModuleResponse,
    OutlineResponse,
    RevisionResponse,
    SourceReference,
    StrictModel,
    WritingSettings,
)

Task = Literal["outline", "module", "edit", "answer", "revise", "insert"]
RESPONSES = {
    "outline": OutlineResponse,
    "module": ModuleResponse,
    "edit": EditResponse,
    "answer": AnswerResponse,
    "revise": RevisionResponse,
    "insert": EditResponse,
}


class InvalidModelResponse(ProviderError):
    code = "invalid_model_response"


class ModelContextLimit(ProviderError):
    code = "model_context_limit"


@dataclass(frozen=True)
class ModelResult:
    content: StrictModel
    model: str
    prompt_version: str
    attempts: int
    evidence_flag_normalized: bool = False


class WorkflowModel:
    def __init__(self, config: Settings, client=None, clock: Callable[[], float] = time.monotonic):
        self.config = config
        self.clock = clock
        self.model = config.document_builder_model or config.llm_model_name
        self.client = client or LLMClient(
            base_url=config.llm_base_url,
            model=self.model,
            api_key=config.llm_api_key,
            context_window=config.llm_context_window,
            max_input_tokens=config.llm_max_input_tokens,
            max_output_tokens=config.llm_max_output_tokens,
            timeout_seconds=config.document_builder_model_timeout_seconds,
        )
        if hasattr(self.client, "enable_thinking"):
            # Its own setting when set, otherwise the LMS-wide one (false for Qwen on main).
            own = config.document_builder_enable_thinking
            self.client.enable_thinking = own if own is not None else config.llm_enable_thinking

    def complete(
        self,
        task: Task,
        *,
        metadata: DraftMetadata,
        settings: WritingSettings,
        context: dict,
        allowed_references: list[SourceReference] | None = None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> ModelResult:
        if task not in RESPONSES:
            raise ValueError("Unsupported document task")
        response_type = RESPONSES[task]
        references = {(ref.sourceId, ref.spanId) for ref in allowed_references or []}
        payload = {
            "TASK": TASKS[task],
            "metadata": metadata.model_dump(),
            "settings": settings.model_dump(),
            "context": context,
            "OUTPUT_SCHEMA": response_type.model_json_schema(),
        }
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        output_budget = min(
            6000 if task in {"module", "revise"} else 3000, self.config.llm_max_output_tokens
        )
        mode = self.config.document_builder_output_mode
        response_format = None
        if mode == "json_object":
            response_format = {"type": "json_object"}
        elif mode == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"document_{task}",
                    "strict": True,
                    "schema": response_type.model_json_schema(),
                },
            }
        started = self.clock()
        attempts = 0
        last_code = "invalid_model_response"
        # One original logical completion + one repair, with two transport tries
        # each. All physical calls have attempts=1: no nested provider retries.
        for logical in range(2):
            response = None
            for transport in range(2):
                if cancelled():
                    raise ProviderError("Document operation cancelled")
                remaining = self.config.document_builder_operation_deadline_seconds - (
                    self.clock() - started
                )
                if remaining <= 0:
                    raise ProviderError("Document operation exceeded its deadline")
                self._check_budget(messages, output_budget)
                # This adapter owns its client per operation, never the shared client.
                if isinstance(self.client, LLMClient):
                    self.client.timeout_seconds = min(
                        remaining, self.config.document_builder_model_timeout_seconds
                    )
                try:
                    attempts += 1
                    response = self.client.complete(
                        messages,
                        response_format=response_format,
                        temperature=0.2,
                        default_max_tokens=output_budget,
                        stage=f"document_{task}",
                        attempts=1,
                    )
                    break
                except (ProviderError, PipelineStageError) as exc:
                    # Legacy provider errors currently have no typed HTTP status.
                    # Only recognizable transient failures may consume transport retries.
                    detail = str(exc).lower()
                    transient = any(
                        word in detail
                        for word in (
                            "timeout",
                            "timed out",
                            "connection",
                            "429",
                            "502",
                            "503",
                            "504",
                        )
                    )
                    if not transient or transport == 1:
                        raise ProviderError(
                            "Document model is unavailable; your draft is unchanged"
                        ) from exc
            if cancelled():
                raise ProviderError("Document operation cancelled")
            if self.clock() - started >= self.config.document_builder_operation_deadline_seconds:
                raise ProviderError("Document operation exceeded its deadline")
            try:
                raw = self._content(response)
                parsed = self._parse(raw, response_type)
                evidence_flag_normalized = self._validate(task, parsed, settings, references)
                if task == "revise" and len(parsed.replacements) != len(context["originalTexts"]):
                    raise ValueError("wrong_replacement_count")
                return ModelResult(
                    parsed, self.model, PROMPT_VERSION, attempts, evidence_flag_normalized
                )
            except (InvalidModelResponse, ValidationError, ValueError) as exc:
                last_code = self._category(exc)
                # Do not include untrusted malformed output or proprietary content
                # in repair prompts/logs. Ask for a complete new object from context.
                if logical == 0:
                    messages.append(
                        {
                            "role": "user",
                            "content": "The prior response failed output validation. Generate a complete new "
                            "response for the same task and scope. Match OUTPUT_SCHEMA exactly. "
                            "Validation category: " + self._category(exc),
                        }
                    )
        raise InvalidModelResponse(
            "The model did not return a complete valid result. Your draft is unchanged. "
            "Retry this task or narrow its scope."
        ) from ValueError(last_code)

    def _check_budget(self, messages: list[dict], output_budget: int):
        estimated = int(sum(len(message["content"]) for message in messages) / 3) + 500
        if estimated > self.config.llm_max_input_tokens or (
            estimated + output_budget + 1000 > self.config.llm_context_window
        ):
            raise ModelContextLimit("This task exceeds the model context budget; narrow its scope")

    @staticmethod
    def _content(response) -> str:
        if not getattr(response, "choices", None):
            raise InvalidModelResponse("missing_completion")
        choice = response.choices[0]
        if choice.finish_reason != "stop":
            raise InvalidModelResponse("incomplete_completion")
        text = choice.message.content
        if not isinstance(text, str) or not text.strip() or len(text) > 160000:
            raise InvalidModelResponse("empty_or_oversized_completion")
        return text.strip()

    @staticmethod
    def _parse(raw: str, response_type: type[StrictModel]) -> StrictModel:
        fence = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if fence:
            raw = fence.group(1)

        def unique_keys(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("duplicate_json_key")
                obj[key] = value
            return obj

        value = json.loads(raw, object_pairs_hook=unique_keys)
        return response_type.model_validate(value)

    @staticmethod
    def _validate(task: Task, result: StrictModel, settings: WritingSettings, references: set):
        if task == "outline" and len(result.modules) != settings.moduleCount:
            raise ValueError("wrong_module_count")
        for ref in getattr(result, "sourceReferences", []):
            if (ref.sourceId, ref.spanId) not in references:
                raise ValueError("unknown_source_reference")
        if task == "module" and not any(block.type == "paragraph" for block in result.blocks):
            raise ValueError("missing_module_explanation")
        if task == "answer" and not result.insufficientEvidence:
            # Conservative English-only presentation guard: a response declaring
            # missing evidence must never carry a confident/supported label.
            # This does not verify the answer's facts or rewrite its content.
            missing = re.search(
                r"\b(?:no\b[^.!?]{0,100}\b(?:specified|provided|available)|not\s+(?:specified|provided|available)|does\s+not\s+(?:specify|provide|state|contain|mention)|cannot\s+(?:determine|confirm)|insufficient\s+(?:evidence|information))\b",
                result.answer,
                re.I,
            )
            if missing:
                result.insufficientEvidence = True
                return True
        return False

    @staticmethod
    def _category(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "schema_mismatch: " + "; ".join(
                ".".join(str(part) for part in error["loc"]) + "=" + error["type"]
                for error in exc.errors(include_input=False)[:8]
            )
        if isinstance(exc, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(exc, InvalidModelResponse):
            return exc.message
        return (
            str(exc)
            if str(exc)
            in {
                "wrong_module_count",
                "unknown_source_reference",
                "missing_module_explanation",
                "duplicate_json_key",
            }
            else "semantic_validation"
        )
