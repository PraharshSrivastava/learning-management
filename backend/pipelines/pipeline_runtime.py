"""Shared runtime primitives for resumable course generation."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable, TypeVar


T = TypeVar("T")


PIPELINE_STAGES = (
    "blueprint",
    "quiz",
    "slides",
    "html",
    "scripts",
    "notes",
    "tts",
    "video",
    "thumbnail",
    "publish",
)


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str, module_number: int | None = None, slide_number: int | None = None):
        super().__init__(message)
        self.stage = stage
        self.module_number = module_number
        self.slide_number = slide_number


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(course_id: str, stage: str, event: str, **details: Any) -> None:
    suffix = " ".join(f"{key}={value}" for key, value in details.items() if value is not None)
    print(f"{now_iso()} [PIPELINE][{course_id}][{stage.upper()}] {event}{' ' + suffix if suffix else ''}")


def retry(operation: Callable[[], T], *, course_id: str, stage: str, attempts: int, module_number: int | None = None,
          slide_number: int | None = None) -> T:
    """Run one external operation with clear, bounded retry logging."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        log_event(course_id, stage, "attempt_start", attempt=f"{attempt}/{attempts}", module=module_number, slide=slide_number)
        try:
            result = operation()
            log_event(
                course_id, stage, "attempt_success", attempt=f"{attempt}/{attempts}", module=module_number,
                slide=slide_number, elapsed=f"{time.perf_counter() - started:.1f}s",
            )
            return result
        except Exception as exc:
            last_error = exc
            log_event(
                course_id, stage, "attempt_failed", attempt=f"{attempt}/{attempts}", module=module_number,
                slide=slide_number, elapsed=f"{time.perf_counter() - started:.1f}s", reason=str(exc)[:500],
            )
    raise PipelineStageError(stage, str(last_error or "Unknown generation error"), module_number, slide_number)


def generation_state(course: dict) -> dict:
    state = course.setdefault("generation", {})
    state.setdefault("status", "pending")
    state.setdefault("stages", {})
    state.setdefault("started_at", now_iso())
    return state


def mark_stage(course: dict, stage: str, status: str, *, error: str = "", module_number: int | None = None,
               slide_number: int | None = None, elapsed_seconds: float | None = None) -> None:
    state = generation_state(course)
    entry = state["stages"].setdefault(stage, {})
    entry.update({"status": status, "updated_at": now_iso()})
    if status == "running":
        entry["started_at"] = now_iso()
        entry.pop("error", None)
    if status in {"completed", "failed"}:
        entry["completed_at"] = now_iso()
    if elapsed_seconds is not None:
        entry["duration_seconds"] = round(elapsed_seconds, 2)
    if module_number is not None:
        entry["module_number"] = module_number
    if slide_number is not None:
        entry["slide_number"] = slide_number
    if error:
        entry["error"] = error

    if status == "failed":
        state.update({
            "status": "failed", "failed_checkpoint": stage, "error": error,
            "module_number": module_number, "slide_number": slide_number,
            "failed_at": now_iso(),
        })
    elif status == "running":
        state.update({"status": "running", "current_checkpoint": stage})


def complete_generation(course: dict, elapsed_seconds: float) -> None:
    state = generation_state(course)
    previous_total = float(state.get("total_duration_seconds") or 0)
    state.update({
        "status": "completed", "completed_at": now_iso(),
        "last_run_duration_seconds": round(elapsed_seconds, 2),
        "total_duration_seconds": round(previous_total + elapsed_seconds, 2),
    })
    for key in ("failed_checkpoint", "error", "module_number", "slide_number"):
        state.pop(key, None)
