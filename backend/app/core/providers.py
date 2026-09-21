"""Typed clients and settings aliases for external generation providers."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from app.core.exceptions import ProviderError
from app.core.langfuse_tracing import end_generation, start_generation
from app.core.logging import generation_logger
from app.core.settings import settings
from app.generation.runtime import retry
from app.schemas.generation.providers import ChatCompletionRequest

logger = generation_logger(__name__)

BASE_DIR = str(settings.backend_dir)
UPLOAD_DIR = str(settings.upload_dir)
IMAGE_DIR = str(settings.image_dir)
AUDIO_DIR = str(settings.audio_dir)
SLIDE_DIR = str(settings.slide_dir)
VIDEO_DIR = str(settings.video_dir)
STATIC_DIR = str(settings.static_dir)
TEMPLATE_DIR = str(settings.template_dir)

LITELLM_BASE_URL = settings.llm_base_url
LITELLM_API_KEY = settings.llm_api_key
CHAT_MODEL_NAME = settings.llm_model_name
CHAT_MODEL_CONTEXT_WINDOW = settings.llm_context_window
TOKEN_SAFETY_MARGIN = 1000

TTS_ENDPOINT = settings.tts_endpoint
TTS_VOICE = settings.tts_voice
TTS_TEMPERATURE = settings.tts_temperature
TTS_SPEED = settings.tts_speed
SLIDE_TRANSITION_PAUSE_SECONDS = settings.slide_transition_pause_seconds


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ChatCompletionMessage:
    content: str


@dataclass(frozen=True)
class ChatCompletionChoice:
    message: ChatCompletionMessage
    finish_reason: str


@dataclass(frozen=True)
class ChatCompletionUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def as_langfuse_usage(self) -> dict[str, int] | None:
        usage = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }
        present = {key: value for key, value in usage.items() if value is not None}
        return present or None


@dataclass(frozen=True)
class ChatCompletionResponse:
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage | None = None


class LLMClient:
    """HTTP transport plus context-aware retry policy for chat completions."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        context_window: int,
        max_input_tokens: int,
        max_output_tokens: int,
        timeout_seconds: float = 600,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.context_window = context_window
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict | None = None,
        temperature: float = 0.2,
        default_max_tokens: int = 4096,
        course_id: str = "unknown",
        stage: str = "llm",
        module_number: int | None = None,
        attempts: int = 3,
    ) -> ChatCompletionResponse:
        total_chars = sum(len(str(message.get("content", ""))) for message in messages)
        estimated_input = int(total_chars / 3.0) + 500
        if estimated_input > self.max_input_tokens:
            raise ProviderError(
                f"Estimated input size is {estimated_input} tokens; the configured maximum is "
                f"{self.max_input_tokens}. The request was not truncated."
            )
        available_tokens = self.context_window - estimated_input - TOKEN_SAFETY_MARGIN
        max_tokens = min(
            default_max_tokens,
            self.max_output_tokens,
            max(256, available_tokens),
        )
        logger.debug(
            "llm_request course_id=%s stage=%s module=%s estimated_input=%s "
            "max_tokens=%s attempts=%s",
            course_id,
            stage,
            module_number,
            estimated_input,
            max_tokens,
            attempts,
        )

        def request_once() -> ChatCompletionResponse:
            nonlocal max_tokens
            started = time.perf_counter()
            initial_metadata: dict[str, Any] = {
                "course_id": course_id,
                "stage": stage,
            }
            if module_number is not None:
                initial_metadata["module_number"] = module_number
            generation = start_generation(
                name=stage,
                model=self.model,
                input_value=messages,
                metadata=initial_metadata,
            )
            try:
                result = self._post(messages, response_format, temperature, max_tokens)
            except ProviderError as exc:
                self._finish_attempt(
                    generation=generation,
                    response=None,
                    course_id=course_id,
                    stage=stage,
                    module_number=module_number,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    error=exc,
                )
                detail = str(exc).lower()
                if not any(
                    marker in detail for marker in ("max_tokens", "context length", "token")
                ):
                    raise
                match = re.search(
                    r"(?:request has|prompt contains at least) (\d+) input tokens",
                    detail,
                )
                max_tokens = (
                    min(
                        self.max_output_tokens,
                        max(256, self.context_window - int(match.group(1)) - TOKEN_SAFETY_MARGIN),
                    )
                    if match
                    else 512
                )
                logger.warning(
                    "llm_context_retry course_id=%s stage=%s reduced_output_tokens=%s",
                    course_id,
                    stage,
                    max_tokens,
                )
                raise
            except Exception as exc:
                self._finish_attempt(
                    generation=generation,
                    response=None,
                    course_id=course_id,
                    stage=stage,
                    module_number=module_number,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    error=exc,
                )
                raise
            self._finish_attempt(
                generation=generation,
                response=result,
                course_id=course_id,
                stage=stage,
                module_number=module_number,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return result

        return retry(
            request_once,
            course_id=course_id,
            stage=stage,
            attempts=attempts,
            module_number=module_number,
        )

    def _post(
        self,
        messages: list[dict[str, Any]],
        response_format: dict | None,
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletionResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        normalized_messages = [
            {**message, "content": str(message.get("content", ""))} for message in messages
        ]
        payload = ChatCompletionRequest(
            model=self.model,
            messages=normalized_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        ).model_dump(exclude_none=True)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 400:
                raise ProviderError(response.text)
            response.raise_for_status()
            body = response.json()
        except ProviderError:
            raise
        except requests.RequestException as exc:
            raise ProviderError(f"LLM request failed: {exc}") from exc
        except ValueError as exc:
            raise ProviderError("LLM returned invalid JSON") from exc

        choices = []
        for choice in body.get("choices", []):
            message = choice.get("message", {})
            content = message.get("content")
            finish_reason = str(choice.get("finish_reason", "stop"))
            if content is None:
                raise ProviderError(
                    "LLM response message.content was null"
                    + (f" with finish_reason={finish_reason}" if finish_reason else "")
                )
            choices.append(
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content=str(content)),
                    finish_reason=finish_reason,
                )
            )
        if not choices:
            raise ProviderError("LLM response contained no choices")
        usage_data = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        usage = ChatCompletionUsage(
            prompt_tokens=_optional_int(usage_data.get("prompt_tokens")),
            completion_tokens=_optional_int(usage_data.get("completion_tokens")),
            total_tokens=_optional_int(usage_data.get("total_tokens")),
        )
        return ChatCompletionResponse(
            choices=choices,
            usage=usage if usage.as_langfuse_usage() else None,
        )

    def _finish_attempt(
        self,
        *,
        generation: Any | None,
        response: ChatCompletionResponse | None,
        course_id: str,
        stage: str,
        module_number: int | None,
        duration_ms: float,
        error: Exception | None = None,
    ) -> None:
        output = None
        finish_reason = None
        if response and response.choices:
            output = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
        metadata: dict[str, Any] = {
            "course_id": course_id,
            "stage": stage,
            "duration_ms": round(duration_ms, 1),
            "status": "failed" if error else "completed",
        }
        if module_number is not None:
            metadata["module_number"] = module_number
        if finish_reason:
            metadata["finish_reason"] = finish_reason
        if error:
            metadata["error_type"] = type(error).__name__
            if settings.langfuse_capture_content:
                metadata["error"] = str(error)[:300]
        end_generation(
            generation,
            output_value=output,
            metadata=metadata,
            usage=response.usage.as_langfuse_usage() if response and response.usage else None,
            level="ERROR" if error else "DEFAULT",
            status_message=type(error).__name__ if error else None,
            name=stage,
        )


_default_llm_client = LLMClient(
    base_url=LITELLM_BASE_URL,
    model=CHAT_MODEL_NAME,
    api_key=LITELLM_API_KEY,
    context_window=CHAT_MODEL_CONTEXT_WINDOW,
    max_input_tokens=settings.llm_max_input_tokens,
    max_output_tokens=settings.llm_max_output_tokens,
)


def get_llm_endpoint(purpose: str | None = None) -> tuple[str, str]:
    del purpose
    return LITELLM_BASE_URL, CHAT_MODEL_NAME


def safe_chat_completion(
    base_url,
    model,
    messages,
    response_format=None,
    temperature=0.2,
    default_max_tokens=4096,
    course_id="unknown",
    stage="llm",
    module_number=None,
    attempts=3,
):
    client = _default_llm_client
    if base_url.rstrip("/") != client.base_url or model != client.model:
        client = LLMClient(
            base_url=base_url,
            model=model,
            api_key=settings.llm_api_key,
            context_window=settings.llm_context_window,
            max_input_tokens=settings.llm_max_input_tokens,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    return client.complete(
        messages,
        response_format=response_format,
        temperature=temperature,
        default_max_tokens=default_max_tokens,
        course_id=course_id,
        stage=stage,
        module_number=module_number,
        attempts=attempts,
    )


VOICE_TRANSCRIPTS = {
    "ref_tejas": "hello my name is Tejas and I am interning at Phillip Capital in the AI labs department.",
    "ref_srk": "I was born in a refugee colony in the capital city of India, New Delhi, and my father was a freedom fighter.",
    "ref_nitin": "mutual funds in an actual are professionally managed investments, wearing a money is pooled and invested across different markets by experts. No daily tracking, no stocks speaking, no asset allocation stress.",
    "ref_shreya": "We all work hard to earn and save while trying to do the right thing with money. Yet it never seems to grow the way we expect.",
}
