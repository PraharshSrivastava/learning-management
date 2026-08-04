"""Logging setup used at application startup."""

from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def generation_logger(module_name: str) -> logging.Logger:
    """Keep worker-level generation diagnostics out of the normal terminal stream."""
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.WARNING)
    return logger
