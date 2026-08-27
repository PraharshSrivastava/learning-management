"""Logging setup used at application startup."""

from __future__ import annotations

import logging


class _NoisyRequestFilter(logging.Filter):
    """Hide routine frontend polling/access logs from the terminal."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access":
            return False
        if _record_is_options_request(record):
            return False
        path = _path_from_log_record(record)
        method = _method_from_log_record(record)
        return not _is_noisy_polling_path(path, method)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    request_filter = _NoisyRequestFilter()
    for logger_name in ("app.http", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(existing, _NoisyRequestFilter) for existing in logger.filters):
            logger.addFilter(request_filter)


def generation_logger(module_name: str) -> logging.Logger:
    """Return a generation logger that follows the configured app log level."""
    return logging.getLogger(module_name)


def _is_noisy_polling_path(path: str, method: str) -> bool:
    if method and method.upper() != "GET":
        return False

    clean_path = path.split("?", 1)[0]
    if clean_path.startswith("/api/generation-jobs/"):
        return True

    parts = [part for part in clean_path.split("/") if part]
    return len(parts) == 3 and parts[:2] == ["api", "courses"]


def _record_is_options_request(record: logging.LogRecord) -> bool:
    args = record.args if isinstance(record.args, tuple) else ()
    if len(args) >= 2 and str(args[1]).upper() == "OPTIONS":
        return True
    return " method=OPTIONS " in record.getMessage()


def _path_from_log_record(record: logging.LogRecord) -> str:
    args = record.args if isinstance(record.args, tuple) else ()
    for arg in args:
        text = str(arg)
        if text.startswith("/"):
            return text

    message = record.getMessage()
    marker = " path="
    if marker in message:
        return message.split(marker, 1)[1].split(" ", 1)[0]
    return ""


def _method_from_log_record(record: logging.LogRecord) -> str:
    args = record.args if isinstance(record.args, tuple) else ()
    if len(args) >= 2:
        possible_method = str(args[1]).upper()
        if possible_method.isalpha():
            return possible_method

    message = record.getMessage()
    marker = " method="
    if marker in message:
        return message.split(marker, 1)[1].split(" ", 1)[0].upper()
    return ""
