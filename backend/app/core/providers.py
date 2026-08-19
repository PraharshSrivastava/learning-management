"""Typed clients and settings aliases for external generation providers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

from app.core.exceptions import ProviderError
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

TTS_ENDPOINT = settings.tts_endpoint
TTS_VOICE = settings.tts_voice
TTS_TEMPERATURE = settings.tts_temperature
TTS_SPEED = settings.tts_speed
SLIDE_TRANSITION_PAUSE_SECONDS = settings.slide_transition_pause_seconds


@dataclass(frozen=True)
class ChatCompletionMessage:
    content: str


@dataclass(frozen=True)
class ChatCompletionChoice:
    message: ChatCompletionMessage
    finish_reason: str


@dataclass(frozen=True)
class ChatCompletionResponse:
    choices: list[ChatCompletionChoice]


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
        enable_thinking: bool | None = None,
        timeout_seconds: float = 600,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.context_window = context_window
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.enable_thinking = enable_thinking
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
        estimated_input = int(total_chars / 6.0) + 100
        if estimated_input > self.max_input_tokens:
            raise ProviderError(
                f"Estimated input size is {estimated_input} tokens; the configured maximum is "
                f"{self.max_input_tokens}. The request was not truncated."
            )
        available_tokens = self.context_window - estimated_input - 150
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
            try:
                return self._post(messages, response_format, temperature, max_tokens)
            except ProviderError as exc:
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
                        max(256, self.context_window - int(match.group(1)) - 100),
                    )
                    if match
                    else 512
                )
                logger.warning(
                    "llm_context_retry course_id=%s stage=%s max_tokens=%s",
                    course_id,
                    stage,
                    max_tokens,
                )
                raise

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
        chat_template_kwargs = (
            {"enable_thinking": self.enable_thinking}
            if self.enable_thinking is not None
            else None
        )
        payload = ChatCompletionRequest(
            model=self.model,
            messages=normalized_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            chat_template_kwargs=chat_template_kwargs,
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
        return ChatCompletionResponse(choices=choices)


_default_llm_client = LLMClient(
    base_url=LITELLM_BASE_URL,
    model=CHAT_MODEL_NAME,
    api_key=LITELLM_API_KEY,
    context_window=CHAT_MODEL_CONTEXT_WINDOW,
    max_input_tokens=settings.llm_max_input_tokens,
    max_output_tokens=settings.llm_max_output_tokens,
    enable_thinking=settings.llm_enable_thinking,
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
            enable_thinking=settings.llm_enable_thinking,
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
