"""Small helpers for bounded parallel generation stages."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, TypeVar

from app.generation.runtime import PipelineStageError, log_event

T = TypeVar("T")
R = TypeVar("R")


def default_llm_workers(item_count: int) -> int:
    """Use broad LLM parallelism while keeping local tests and tiny jobs tidy."""
    if item_count <= 0:
        return 1
    configured = os.environ.get("GENERATION_LLM_STAGE_WORKERS")
    if configured:
        try:
            return max(1, min(item_count, int(configured)))
        except ValueError:
            pass
    return item_count


def run_parallel_stage_items(
    *,
    course_id: str,
    stage: str,
    items: Iterable[T],
    worker_count: int,
    operation: Callable[[T], R],
    item_label: Callable[[T], dict],
) -> list[R]:
    """Run independent stage items in parallel and preserve fail-fast context."""
    item_list = list(items)
    if not item_list:
        return []

    started = time.perf_counter()
    log_event(
        course_id,
        stage,
        "parallel_started",
        items=len(item_list),
        workers=max(1, min(worker_count, len(item_list))),
    )
    results: list[R] = []
    with ThreadPoolExecutor(
        max_workers=max(1, min(worker_count, len(item_list))),
        thread_name_prefix=f"{stage}-worker",
    ) as executor:
        futures = {executor.submit(operation, item): item for item in item_list}
        for future in as_completed(futures):
            item = futures[future]
            labels = item_label(item)
            try:
                results.append(future.result())
                log_event(course_id, stage, "parallel_item_completed", **labels)
            except PipelineStageError:
                raise
            except Exception as exc:
                raise PipelineStageError(
                    stage,
                    str(exc),
                    labels.get("module"),
                    labels.get("slide"),
                ) from exc

    log_event(
        course_id,
        stage,
        "parallel_completed",
        items=len(item_list),
        elapsed=f"{time.perf_counter() - started:.1f}s",
    )
    return results
