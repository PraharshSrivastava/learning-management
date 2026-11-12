"""Optional PostHog product analytics. Off, and never imported, without an API key."""

from __future__ import annotations

import logging
from typing import Any

from app.core.request_context import posthog_session_id
from app.core.settings import settings

logger = logging.getLogger("app.analytics")

_client: Any = None


def start_analytics() -> None:
    """Create the PostHog client when an API key is configured."""
    global _client
    if _client is not None or not settings.posthog_api_key:
        return
    try:
        from posthog import Posthog

        _client = Posthog(
            settings.posthog_api_key,
            host=settings.posthog_host,
            enable_exception_autocapture=False,
        )
    except Exception:
        logger.warning("analytics_start_failed", exc_info=True)


def capture_event(
    distinct_id: str | None,
    event: str,
    properties: dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
) -> None:
    """Send one event. Properties hold ids, counts, flags and durations, never personal data.

    ``session_id`` defaults to the browser session of the current request.
    """
    client = _client
    if client is None or not distinct_id:
        return
    try:
        event_properties = dict(properties or {})
        session_id = session_id or posthog_session_id.get()
        if session_id:
            event_properties["$session_id"] = session_id
        client.capture(event, distinct_id=distinct_id, properties=event_properties)
    except Exception:
        logger.warning("analytics_capture_failed event=%s", event, exc_info=True)


def stop_analytics() -> None:
    """Flush queued events and stop the PostHog background thread."""
    global _client
    client, _client = _client, None
    if client is None:
        return
    try:
        client.flush()
        client.shutdown()
    except Exception:
        logger.warning("analytics_stop_failed", exc_info=True)
