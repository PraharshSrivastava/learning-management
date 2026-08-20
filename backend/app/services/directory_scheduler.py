"""Optional background scheduler for daily Hub directory sync."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.settings import settings
from app.services.directory_sync import sync_directory_changes

logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None


def _sync_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.directory_sync_timezone)
    except ZoneInfoNotFoundError:
        logger.warning(
            "invalid_directory_sync_timezone timezone=%s falling_back=Asia/Kolkata",
            settings.directory_sync_timezone,
        )
        return ZoneInfo("Asia/Kolkata")


def _sync_time() -> time:
    try:
        hour, minute = settings.directory_sync_time.split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except (AttributeError, TypeError, ValueError):
        logger.warning(
            "invalid_directory_sync_time time=%s falling_back=09:10",
            settings.directory_sync_time,
        )
        return time(hour=9, minute=10)


def next_directory_sync_run(now: datetime | None = None) -> datetime:
    timezone = _sync_timezone()
    current = (now or datetime.now(timezone)).astimezone(timezone)
    target = datetime.combine(current.date(), _sync_time(), tzinfo=timezone)
    if current >= target:
        target += timedelta(days=1)
    return target


async def _run_loop() -> None:
    if settings.directory_sync_initial_delay_seconds:
        await asyncio.sleep(settings.directory_sync_initial_delay_seconds)
    while True:
        due_in = (next_directory_sync_run() - datetime.now(_sync_timezone())).total_seconds()
        if due_in > 0:
            await asyncio.sleep(due_in)
        try:
            await asyncio.to_thread(sync_directory_changes)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduled_directory_sync_failed")
        await asyncio.sleep(60)


def start_directory_sync_scheduler() -> None:
    global _task
    if not settings.directory_sync_enabled or _task is not None:
        return
    _task = asyncio.create_task(_run_loop(), name="directory-sync-scheduler")


async def stop_directory_sync_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
