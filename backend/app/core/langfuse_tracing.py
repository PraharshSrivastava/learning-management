"""Fail-open Langfuse tracing for LMS generation work.

The Langfuse dependency is imported lazily.  Missing credentials, a missing
package, or an unavailable Langfuse server must never interrupt LMS business
logic.  Trace context is process-local and copied explicitly into generation
thread pools by their callers.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any, Iterator

from app.core.settings import settings

logger = logging.getLogger(__name__)

_client: Any | None = None
_client_checked = False
_client_lock = Lock()
_current_trace: ContextVar[Any | None] = ContextVar("langfuse_trace", default=None)


def _missing_configuration() -> list[str]:
    required = {
        "LANGFUSE_HOST": settings.langfuse_host,
        "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
        "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
    }
    return [name for name, value in required.items() if not value]


def get_langfuse() -> Any | None:
    """Return the shared client, or ``None`` when tracing is unavailable."""
    global _client, _client_checked
    if not settings.langfuse_enabled:
        return None
    if _client_checked:
        return _client

    with _client_lock:
        if _client_checked:
            return _client
        missing = _missing_configuration()
        if missing:
            logger.warning(
                "langfuse_configuration_incomplete missing=%s",
                ",".join(missing),
            )
            _client_checked = True
            return None
        try:
            from langfuse import Langfuse

            _client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_host,
                environment=settings.langfuse_environment,
                release=settings.langfuse_release,
                timeout=settings.langfuse_timeout_seconds,
            )
            logger.info(
                "langfuse_client_initialized host=%s environment=%s",
                settings.langfuse_host,
                settings.langfuse_environment,
            )
        except Exception as exc:  # Telemetry is deliberately fail-open.
            _client = None
            logger.warning("langfuse_client_unavailable error=%s", _safe_error(exc))
        finally:
            _client_checked = True
    return _client


def current_trace() -> Any | None:
    return _current_trace.get()


@contextmanager
def trace_scope(
    name: str,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any | None]:
    """Set the active trace and report the operation outcome without masking it."""
    client = get_langfuse()
    if client is None:
        yield None
        return

    propagation = None
    observation_context = None
    trace = None
    trace_metadata = {
        "application": "lms",
        "environment": settings.langfuse_environment,
        **(metadata or {}),
    }
    try:
        from langfuse import propagate_attributes

        propagation = propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=["lms", settings.langfuse_environment, *(tags or [])],
            trace_name=name,
            environment=settings.langfuse_environment,
        )
        propagation.__enter__()
        observation_context = client.start_as_current_observation(
            name=name,
            as_type="span",
            metadata=trace_metadata,
            version=settings.langfuse_release,
        )
        trace = observation_context.__enter__()
    except Exception as exc:
        logger.warning("langfuse_trace_create_failed error=%s", _safe_error(exc))
        _exit_context(observation_context)
        _exit_context(propagation)
        yield None
        return

    token = _current_trace.set(trace)
    try:
        yield trace
    except Exception as exc:
        output = {"status": "failed", "error_type": type(exc).__name__}
        if settings.langfuse_capture_content:
            output["error"] = _content_value(str(exc))
        _update_trace(trace, output=output)
        score_trace("generation_success", 0, trace=trace)
        raise
    else:
        _update_trace(trace, output={"status": "completed"})
        score_trace("generation_success", 1, trace=trace)
    finally:
        _current_trace.reset(token)
        _exit_context(observation_context)
        _exit_context(propagation)
        flush()


@contextmanager
def timed_span(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
    trace: Any | None = None,
) -> Iterator[Any | None]:
    parent = trace if trace is not None else current_trace()
    context = None
    span = None
    if parent is not None:
        try:
            context = parent.start_as_current_observation(
                name=name,
                as_type="span",
                metadata=metadata or {},
            )
            span = context.__enter__()
        except Exception as exc:
            logger.warning("langfuse_span_create_failed name=%s error=%s", name, _safe_error(exc))
    token = _current_trace.set(span or parent)
    try:
        yield span
    finally:
        _current_trace.reset(token)
        if context is not None:
            _exit_context(context, operation=f"span_end name={name}")


def record_generation(
    *,
    name: str,
    model: str,
    input_value: Any = None,
    output_value: Any = None,
    metadata: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    level: str = "DEFAULT",
    trace: Any | None = None,
) -> Any | None:
    generation = start_generation(
        name=name,
        model=model,
        input_value=input_value,
        metadata=metadata,
        level=level,
        trace=trace,
    )
    end_generation(
        generation,
        output_value=output_value,
        metadata=metadata,
        usage=usage,
        level=level,
        name=name,
    )
    return generation


def start_generation(
    *,
    name: str,
    model: str,
    input_value: Any = None,
    metadata: dict[str, Any] | None = None,
    level: str = "DEFAULT",
    trace: Any | None = None,
) -> Any | None:
    """Start a generation before the provider request so latency is accurate."""
    parent = trace if trace is not None else current_trace()
    if parent is None:
        return None
    try:
        return parent.start_observation(
            name=name,
            as_type="generation",
            model=model,
            input=_content_value(input_value),
            metadata=metadata or {},
            level=level,
        )
    except Exception as exc:
        logger.warning("langfuse_generation_create_failed name=%s error=%s", name, _safe_error(exc))
        return None


def end_generation(
    generation: Any | None,
    *,
    output_value: Any = None,
    metadata: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    level: str = "DEFAULT",
    status_message: str | None = None,
    name: str = "generation",
) -> None:
    """Update and end a generation without affecting the business operation."""
    if generation is None:
        return
    try:
        generation.update(
            output=_content_value(output_value),
            metadata=metadata or {},
            usage_details=usage,
            level=level,
            status_message=status_message,
        )
    except Exception as exc:
        logger.warning("langfuse_generation_update_failed name=%s error=%s", name, _safe_error(exc))
    try:
        generation.end()
    except Exception as exc:
        logger.warning("langfuse_generation_end_failed name=%s error=%s", name, _safe_error(exc))


def score_trace(
    name: str,
    value: float | int,
    *,
    comment: str | None = None,
    trace: Any | None = None,
) -> None:
    parent = trace if trace is not None else current_trace()
    if parent is None:
        return
    try:
        parent.score_trace(name=name, value=value, comment=comment)
    except Exception as exc:
        logger.warning("langfuse_score_failed name=%s error=%s", name, _safe_error(exc))


def flush() -> None:
    client = get_langfuse()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("langfuse_flush_failed error=%s", _safe_error(exc))


def _content_value(value: Any) -> Any:
    if not settings.langfuse_capture_content or value is None:
        return None
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        serialized = str(value)
    limit = settings.langfuse_capture_max_chars
    return serialized if len(serialized) <= limit else serialized[:limit] + "...[truncated]"


def _update_trace(trace: Any | None, *, output: dict[str, Any]) -> None:
    if trace is None:
        return
    try:
        trace.update(output=output)
    except Exception as exc:
        logger.warning("langfuse_trace_update_failed error=%s", _safe_error(exc))


def _exit_context(
    context: Any | None,
    *,
    operation: str = "context_exit",
) -> None:
    if context is None:
        return
    try:
        context.__exit__(None, None, None)
    except Exception as exc:
        logger.warning("langfuse_%s_failed error=%s", operation, _safe_error(exc))


def _safe_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    return f"{type(exc).__name__}: {text[:300]}"


def _reset_for_tests() -> None:
    """Reset lazy singleton state for isolated settings/client tests."""
    global _client, _client_checked
    _client = None
    _client_checked = False
    _current_trace.set(None)
