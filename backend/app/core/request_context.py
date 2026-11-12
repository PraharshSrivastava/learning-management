"""HTTP request correlation and access logging."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request, Response

logger = logging.getLogger("app.http")

# PostHog session id the frontend sends, so server events join the browser session replay.
posthog_session_id: ContextVar[str | None] = ContextVar("posthog_session_id", default=None)


async def request_context_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    posthog_session_id.set(request.headers.get("X-POSTHOG-SESSION-ID") or None)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response
