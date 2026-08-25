"""Date parsing helpers shared by filters and directory sync."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_date_like(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize_date_like(value: Any) -> str | None:
    parsed = parse_date_like(value)
    return parsed.isoformat() if parsed else None
