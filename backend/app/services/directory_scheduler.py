"""Optional background scheduler for daily Hub directory sync."""

from __future__ import annotations

import asyncio
import logging

from app.core.settings import settings
from app.repositories.employees import next_sync_due_seconds
from app.services.directory_sync import sync_directory_changes

logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None


async def _run_loop() -> None:
    if settings.directory_sync_initial_delay_seconds:
        await asyncio.sleep(settings.directory_sync_initial_delay_seconds)
    interval_seconds = settings.directory_sync_interval_hours * 60 * 60
    while True:
        due_in = next_sync_due_seconds("employee_change_logs", interval_seconds)
        if due_in > 0:
            await asyncio.sleep(due_in)
        try:
            await asyncio.to_thread(sync_directory_changes)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduled_directory_sync_failed")
        await asyncio.sleep(interval_seconds)


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
