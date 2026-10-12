"""Lifecycle, retained learning, snapshots and stale writes on isolated PostgreSQL."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest
from test_assignment_workspace_postgres import workspace_db as workspace_db

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.repositories import database, observers, performance_reporting
from app.repositories.assignments import get_applied_assignment_rule, get_assignment_rule
from app.repositories.courses import (
    delete_course_for_trainer,
    get_course,
    list_course_summaries_for_trainer,
)
from app.repositories.progress import get_employee_course_progress, save_employee_course_progress
from app.schemas.assignment import AssignmentRuleRequest
from app.schemas.observers import ObserverSaveRequest
from app.schemas.reporting_scope import TrainerPerformanceScope
from app.services import assignments, learning
from app.services import performance_reporting as reports
from app.services.course_lifecycle import change_lifecycle

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated PostgreSQL opt-in"
)


def publish(ids=("a", "b"), revision=None):
    return assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(
            include_all=False,
            include_groups=[{"employee_ids": list(ids)}],
            expected_lifecycle_revision=revision,
        ),
        "creator",
    )


def completed():
    with database.get_connection() as db:
        db.execute(
            "INSERT INTO course_modules(module_id,course_id,module_number,title,num_questions) VALUES ('module-1','course',1,'Module',0)"
        )
        db.commit()
    progress = get_employee_course_progress("a", "course")
    progress.update(
        status="completed",
        completed_at="2026-10-01T12:00:00",
        modules={
            "1": {
                "video_watched": True,
                "quiz_passed": True,
                "quiz_score": 0.8,
                "selected_answers": {"0": "A"},
            }
        },
        attempts={"1": {"count": 2}},
    )
    save_employee_course_progress("a", "course", progress)
    return get_employee_course_progress("a", "course")


def test_disable_archive_restore_enable_preserves_completion(workspace_db):
    publish()
    original = completed()
    observers.save_config(
        "course",
        "creator",
        ObserverSaveRequest(
            revision=0, observers=[{"observer_employee_id": "observer", "employee_ids": ["a"]}]
        ),
    )
    observers.apply_config("course", "creator", 1)
    disabled = change_lifecycle("course", "creator", "disable", 1)
    assert disabled["lifecycle_state"] == "disabled"
    assert observers.get_config("course")["observers"][0]["is_active"] is False
    archived = change_lifecycle("course", "creator", "archive", disabled["lifecycle_revision"])
    assert archived["lifecycle_state"] == "archived"
    with pytest.raises(DomainValidationError):
        assignments.api_save_course_assignment("course", AssignmentRuleRequest(), "creator")
    with pytest.raises(DomainValidationError):
        publish()
    restored = change_lifecycle("course", "creator", "restore", archived["lifecycle_revision"])
    assert restored["lifecycle_state"] == "disabled"
    progress = get_employee_course_progress("a", "course")
    assert progress["revoked_at"] and progress["status"] == "completed"
    assert progress["completed_at"] == original["completed_at"]
    publish(revision=restored["lifecycle_revision"])
    progress = get_employee_course_progress("a", "course")
    assert progress["revoked_at"] is None
    assert progress["status"] == "completed"
    assert progress["deadline"] == original["deadline"]
    assert progress["modules"] == original["modules"]
    assert progress["attempts"] == original["attempts"]
    assert observers.get_config("course")["observers"][0]["is_active"] is False
    assert list_course_summaries_for_trainer("creator")[0]["lifecycle_state"] == "active"


def test_exclusion_preserves_completion_and_reports_access_separately(workspace_db):
    publish()
    original = completed()
    publish(ids=("b",))
    active = TrainerPerformanceScope("creator")
    history = TrainerPerformanceScope("creator", course_status="all")
    assert len(performance_reporting.list_assignment_summaries(active)) == 1
    rows = reports.assignment_list(
        history, status=None, search=None, sort="employee", descending=False, page=1, page_size=25
    )
    row = next(r for r in rows["rows"] if r["employee_id"] == "a")
    assert row["status"] == "completed" and row["access_available"] is False
    assert row["average_score"] == 80.0 and row["total_attempts"] == 2
    assert row["access_reason"] == "assignment_rule_no_longer_matches"
    detail = reports.assignment_detail(history, row["assignment_id"])
    assert detail["assignment"]["completed_at"] == original["completed_at"]
    assert get_employee_course_progress("a", "course")["deadline"] == original["deadline"]
    total, page = performance_reporting.employee_page(
        history,
        search=None,
        attention="all",
        sort="employee",
        descending=False,
        page=1,
        page_size=25,
        now=datetime.now(),
    )
    assert total["employees"] == 2
    assert all(not r["needs_attention"] for r in page)


def test_saved_selection_is_draft_until_explicit_publish(workspace_db):
    publish(ids=("a",))
    assignments.api_save_course_assignment(
        "course",
        AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["b"]}]),
        "creator",
    )
    assert get_assignment_rule("course")["include_groups"][0]["employee_ids"] == ["b"]
    assert get_applied_assignment_rule("course")["include_groups"][0]["employee_ids"] == ["a"]
    assert assignments.reconcile_assignments_for_employee("b")["assigned"] == 0
    assert assignments.reconcile_assignments_for_employee("a")["removed"] == 0
    publish(ids=("b",))
    assert get_employee_course_progress("a", "course")["revoked_at"]
    assert get_employee_course_progress("b", "course")["revoked_at"] is None


def test_stale_publish_and_duplicate_lifecycle_write_rejected(workspace_db):
    publish()
    barrier = Barrier(2)

    def disable():
        barrier.wait()
        try:
            change_lifecycle("course", "creator", "disable", 1)
            return "ok"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: disable(), range(2))) == ["conflict", "ok"]
    with pytest.raises(ConflictError):
        publish(revision=1)
    assert get_course("course")["lifecycle_state"] == "disabled"


def test_history_blocks_delete_and_unused_delete_is_audited(workspace_db):
    publish()
    with pytest.raises(ConflictError):
        delete_course_for_trainer("course", "creator")
    with database.get_connection() as db:
        db.execute(
            "INSERT INTO courses(course_id,trainer_id,course_name,status) VALUES ('unused','creator','Unused','draft')"
        )
        db.commit()
    with pytest.raises(ConflictError):
        delete_course_for_trainer("unused", "creator", 1)
    assert delete_course_for_trainer("unused", "creator", 0)["deleted"]
    with database.get_connection() as db:
        assert (
            db.execute(
                "SELECT action FROM course_lifecycle_audit WHERE course_id='unused'"
            ).fetchone()["action"]
            == "delete"
        )


def test_disabled_learner_and_media_access_are_denied(workspace_db):
    publish()
    change_lifecycle("course", "creator", "disable", 1)
    with database.get_connection() as db:
        employee = dict(db.execute("SELECT * FROM employees WHERE employee_id='a'").fetchone())
    with pytest.raises(NotFoundError):
        learning._assigned_progress_for_employee(employee, "course", datetime.now())


def test_legacy_revocation_migration_is_evidence_based_and_idempotent(workspace_db):
    from app.repositories.course_lifecycle_migrations import (
        VERSION,
        apply_course_lifecycle_migration,
    )

    publish()
    with database.get_connection() as db:
        db.execute("DELETE FROM lms_schema_migrations WHERE version=?", (VERSION,))
        db.execute(
            "UPDATE course_assignments SET status='revoked', revoked_at=NULL, completed_at='2026-10-01T12:00:00' WHERE employee_id='a'"
        )
        db.execute(
            "UPDATE course_assignments SET status='revoked', revoked_at=NULL, started_at='2026-10-01T11:00:00' WHERE employee_id='b'"
        )
        apply_course_lifecycle_migration(db.cursor())
        apply_course_lifecycle_migration(db.cursor())
        db.commit()
    assert get_employee_course_progress("a", "course")["status"] == "completed"
    assert get_employee_course_progress("b", "course")["status"] == "started"
    assert get_employee_course_progress("a", "course")["revoked_at"]
    assert get_employee_course_progress("b", "course")["revoked_at"]


def test_archived_course_cannot_be_reopened_by_stale_content_or_generation(workspace_db):
    from types import SimpleNamespace

    from app.core.settings import settings
    from app.repositories.courses import save_course
    from app.repositories.jobs import GenerationJobRepository
    from app.schemas.generation import GenerationJobResponse
    from app.services.generation import GenerationService

    publish()
    stale = get_course("course")
    change_lifecycle("course", "creator", "archive", 1)
    with pytest.raises(ConflictError):
        save_course(stale, "ready")
    job = GenerationJobResponse(
        id="late-worker", course_id="course", status="pending", created_at="2026-10-12"
    )
    service = GenerationService(jobs=SimpleNamespace(get=lambda _: job), config=settings)
    assert service.get_job("late-worker", "creator") == job
    with pytest.raises(ConflictError, match="Restore"):
        service.draft("course", "creator")
    with pytest.raises(ValueError, match="Restore"):
        GenerationJobRepository().create(job)
    assert get_course("course")["lifecycle_state"] == "archived"


def test_lifecycle_uses_one_pool_connection_and_preserves_lock_order(workspace_db):
    publish()
    pool = database._pool
    original_max_size = pool.max_size
    pool.resize(min_size=0, max_size=1)
    try:
        result = change_lifecycle("course", "creator", "archive", 1)
        assert result["lifecycle_state"] == "archived"
        result = change_lifecycle("course", "creator", "restore", result["lifecycle_revision"])
        assert result["lifecycle_state"] == "disabled"
    finally:
        pool.resize(min_size=0, max_size=original_max_size)
