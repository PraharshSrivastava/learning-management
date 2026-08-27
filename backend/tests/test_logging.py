from __future__ import annotations

import logging

from app.core.logging import _NoisyRequestFilter, generation_logger


def _record(name: str, message: str, args: tuple[object, ...]) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=None,
    )


def test_generation_logger_inherits_configured_level() -> None:
    logger = generation_logger("app.generation.slides")

    assert logger.level == logging.NOTSET


def test_noisy_request_filter_hides_generation_job_polling() -> None:
    record = _record(
        "app.http",
        "request_completed request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f",
        ("request_1", "GET", "/api/generation-jobs/job_1", 200, 4.2),
    )

    assert not _NoisyRequestFilter().filter(record)


def test_noisy_request_filter_hides_uvicorn_access_logs() -> None:
    record = _record(
        "uvicorn.access",
        '%s - "%s %s HTTP/%s" %s',
        ("127.0.0.1:54521", "POST", "/api/courses/course_1/generation-jobs", "1.1", 202),
    )

    assert not _NoisyRequestFilter().filter(record)


def test_noisy_request_filter_keeps_generation_course_actions() -> None:
    record = _record(
        "app.http",
        "request_completed request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f",
        ("request_1", "POST", "/api/courses/course_1/generate-full-course", 202, 4.2),
    )

    assert _NoisyRequestFilter().filter(record)


def test_noisy_request_filter_hides_options_requests() -> None:
    record = _record(
        "app.http",
        "request_completed request_id=%s method=%s path=%s status=%s elapsed_ms=%.1f",
        ("request_1", "OPTIONS", "/api/courses/course_1", 200, 0.2),
    )

    assert not _NoisyRequestFilter().filter(record)
