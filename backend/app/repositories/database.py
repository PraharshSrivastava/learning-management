"""Low-level SQLite connection factory."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.core.settings import settings


def database_path() -> Path:
    """Resolve the active path at call time so tests and CLIs can override it."""
    return Path(os.environ.get("LMS_DB_PATH", settings.db_path)).resolve()


def get_connection() -> sqlite3.Connection:
    """Return a short-lived connection configured for concurrent workers."""
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection
