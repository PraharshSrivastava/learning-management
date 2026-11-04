"""Delete stays available after a blueprint edit; only a claimed generation job blocks it."""

import pytest

from app.repositories.courses import _lifecycle_fields, generation_job_active


def _row(generation_status, worker_id=None, *, status="draft", has_history=False):
    return {
        "course_id": "c1",
        "status": status,
        "rule_published_at": None,
        "rule_active": None,
        "has_history": has_history,
        "generation_status": generation_status,
        "generation_worker_id": worker_id,
    }


@pytest.mark.parametrize(
    ("status", "worker", "active"),
    [
        ("pending", None, False),  # reset by a blueprint edit: generate again, no job
        ("pending", "worker-1", True),  # job queued
        ("running", "worker-1", True),
        ("running", None, False),  # left over without a worker
        ("completed", None, False),
        ("failed", None, False),
        (None, None, False),
    ],
)
def test_only_a_claimed_job_counts_as_generating(status, worker, active):
    assert generation_job_active(status, worker) is active


def test_draft_edited_after_its_blueprint_can_still_be_deleted():
    fields = _lifecycle_fields(_row("pending"))
    assert fields["can_delete"] is True
    assert fields["generation_active"] is False


def test_course_with_a_running_job_cannot_be_deleted():
    fields = _lifecycle_fields(_row("running", "worker-1"))
    assert fields["can_delete"] is False
    assert fields["generation_active"] is True


def test_history_and_published_courses_still_cannot_be_deleted():
    assert _lifecycle_fields(_row(None, has_history=True))["can_delete"] is False
    assert _lifecycle_fields(_row(None, status="published"))["can_delete"] is False
