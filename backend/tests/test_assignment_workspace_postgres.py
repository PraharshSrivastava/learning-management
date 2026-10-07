"""Assignment workspace invariants exercised against isolated real PostgreSQL."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import uuid4

import pytest

from app.repositories import database, observers, schema
from app.repositories.access_migrations import apply_access_migrations
from app.repositories.assignments import get_assignment_rule, save_assignment_rule
from app.repositories.progress import save_employee_course_progress
from app.schemas.assignment import AssignmentRuleRequest
from app.schemas.observers import ObserverSaveRequest
from app.services import assignments
from app.services.assignment_conflicts import EmployeeObserverConflict

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated PostgreSQL opt-in"
)


@pytest.fixture
def workspace_db(monkeypatch):
    pool = database._pool_instance()
    name = "assignment_workspace_test_" + uuid4().hex
    with database.get_connection() as db:
        assert (
            db.execute("SELECT current_database() AS name").fetchone()["name"]
            == "lms_performance_demo"
        )
        db.execute(f'CREATE SCHEMA "{name}"')
        db.execute(f'SET LOCAL search_path TO "{name}"')
        schema._create_tables(db.cursor())
        apply_access_migrations(db)
        db.commit()

    class ScopedPool:
        @contextmanager
        def connection(self):
            with pool.connection() as raw:
                raw.execute(f'SET LOCAL search_path TO "{name}"')
                yield raw

    monkeypatch.setattr(database, "_pool_instance", lambda: ScopedPool())
    with database.get_connection() as db:
        db.execute("INSERT INTO trainers(trainer_id,name) VALUES ('creator','Creator')")
        for employee_id, dept in (("a", "Risk"), ("b", "Risk"), ("observer", "Legal")):
            db.execute(
                "INSERT INTO employees(employee_id,name,job_title,department,directory_uuid) VALUES (?, ?, 'Associate', ?, ?)",
                (employee_id, employee_id, dept, "uuid-" + employee_id),
            )
        db.execute(
            "INSERT INTO courses(course_id,trainer_id,course_name,status) VALUES ('course','creator','Test course','ready')"
        )
        db.execute("INSERT INTO lms_departments VALUES ('risk','dir-risk','Risk','directory',TRUE)")
        db.commit()
    save_assignment_rule(
        "course", {"include_all": False, "include_groups": [{"employee_ids": ["a"]}]}
    )
    monkeypatch.setattr(assignments, "course_is_publishable", lambda _: True)
    try:
        yield
    finally:
        monkeypatch.setattr(database, "_pool_instance", lambda: pool)
        with database.get_connection() as db:
            db.execute(f'DROP SCHEMA "{name}" CASCADE')
            db.commit()


def selection(observer="observer", revision=0):
    return ObserverSaveRequest(
        revision=revision, observers=[{"observer_employee_id": observer, "employee_ids": ["a"]}]
    )


def test_observer_conflict_and_explicit_removal_repair(workspace_db):
    with pytest.raises(EmployeeObserverConflict):
        observers.save_config("course", "creator", selection("a"))
    assert observers.get_config("course")["revision"] == 0
    observers.save_config("course", "creator", selection())
    with pytest.raises(EmployeeObserverConflict):
        assignments.api_save_course_assignment(
            "course", AssignmentRuleRequest(include_all=True), "creator"
        )
    observers.save_config("course", "creator", ObserverSaveRequest(revision=1, observers=[]))
    assignments.api_save_course_assignment(
        "course", AssignmentRuleRequest(include_all=True), "creator"
    )


def test_existing_assignment_conflict_even_if_rule_excludes_employee(workspace_db):
    save_employee_course_progress(
        "observer",
        "course",
        {
            "status": "completed",
            "assigned_at": "2026-10-01",
            "deadline": "2026-12-01",
            "modules": {},
            "attempts": {},
        },
    )
    with pytest.raises(EmployeeObserverConflict):
        observers.save_config("course", "creator", selection())


def test_preview_full_pagination_is_read_only_and_counts_real_assignments(workspace_db):
    payload = AssignmentRuleRequest(include_all=True)
    page1 = assignments.assignment_employee_page("course", payload, page_size=2)
    page2 = assignments.assignment_employee_page("course", payload, page=2, page_size=2)
    assert page1["total"] == 3
    assert len({e["employee_id"] for e in page1["employees"] + page2["employees"]}) == 3
    assert assignments.assignment_total("course") == 0
    assert get_assignment_rule("course")["include_all"] is False
    save_employee_course_progress(
        "a",
        "course",
        {
            "status": "completed",
            "assigned_at": "2026-10-01",
            "deadline": "2026-12-01",
            "modules": {},
            "attempts": {},
        },
    )
    save_employee_course_progress(
        "b",
        "course",
        {
            "status": "revoked",
            "assigned_at": "2026-10-01",
            "deadline": "2026-12-01",
            "revoked_at": "2026-10-02",
            "modules": {},
            "attempts": {},
        },
    )
    result = assignments.assignment_employee_page("course", payload, view="assigned")
    assert result["total"] == result["total_assigned_count"] == 1
    assert result["employees"][0]["employee_id"] == "a"


def test_publish_failure_rolls_back_course_rule_assignments_and_notifications(
    workspace_db, monkeypatch
):
    original = assignments._progress.save

    def fail_second(employee_id, course_id, progress):
        if employee_id == "b":
            raise RuntimeError("Injected write failure")
        return original(employee_id, course_id, progress)

    monkeypatch.setattr(assignments._progress, "save", fail_second)
    before = get_assignment_rule("course")
    with pytest.raises(RuntimeError):
        assignments.api_publish_course_assignment(
            "course",
            AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["a", "b"]}]),
            "creator",
        )
    assert get_assignment_rule("course") == before
    assert assignments.assignment_total("course") == 0
    with database.get_connection() as db:
        assert (
            db.execute("SELECT status FROM courses WHERE course_id='course'").fetchone()["status"]
            == "ready"
        )
        assert db.execute("SELECT count(*) AS n FROM email_notifications").fetchone()["n"] == 0


def test_concurrent_employee_and_observer_saves_cannot_both_succeed(workspace_db):
    gate = Barrier(2)

    def save_rule():
        gate.wait()
        try:
            assignments.api_save_course_assignment(
                "course", AssignmentRuleRequest(include_all=True), "creator"
            )
            return "saved"
        except EmployeeObserverConflict:
            return "conflict"

    def save_observer():
        gate.wait()
        try:
            observers.save_config("course", "creator", selection())
            return "saved"
        except EmployeeObserverConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda f: f(), [save_rule, save_observer]))
    assert sorted(results) == ["conflict", "saved"]


def test_fixed_date_roundtrip_and_direct_assignment_guard(workspace_db):
    result = assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(
            include_all=False,
            include_groups=[{"employee_ids": ["a"]}],
            deadline_mode="fixed",
            deadline_date="2099-10-31",
        ),
        "creator",
    )
    assert str(result["rule"]["deadline_date"]) == "2099-10-31"
    assert result["assigned_count"] == result["total_assigned_count"] == 1
    with database.get_connection() as db:
        assert (
            db.execute("SELECT deadline FROM course_assignments WHERE employee_id='a'").fetchone()[
                "deadline"
            ]
            == "2099-10-31T18:29:59.999999"
        )
    observers.save_config("course", "creator", selection())
    with pytest.raises(EmployeeObserverConflict):
        save_employee_course_progress(
            "observer", "course", {"status": "pending", "modules": {}, "attempts": {}}
        )


def test_unsaved_observer_preview_checks_full_matching_set(workspace_db):
    from app.schemas.assignment import AssignmentPreviewRequest

    result = assignments.assignment_employee_page(
        "course",
        AssignmentPreviewRequest(include_all=True, observer_employee_ids=["observer"]),
        page_size=1,
    )
    assert result["conflicting_observer_ids"] == ["observer"]
    assert result["blocked_employee_count"] == 1
    assert assignments.assignment_total("course") == 0


def test_publish_race_with_observer_save_cannot_enrol_observer(workspace_db):
    gate = Barrier(2)

    def publish():
        gate.wait()
        try:
            assignments.api_publish_course_assignment(
                "course", AssignmentRuleRequest(include_all=True), "creator"
            )
            return "saved"
        except EmployeeObserverConflict:
            return "conflict"

    def save_observer():
        gate.wait()
        try:
            observers.save_config("course", "creator", selection())
            return "saved"
        except EmployeeObserverConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda f: f(), [publish, save_observer]))
    assert sorted(results) == ["conflict", "saved"]
    from app.services.assignment_conflicts import observer_ids

    assert not (observer_ids("course") and assignments.assignment_total("course") == 3)


def test_directory_change_blocks_automatic_enrolment_and_apply(workspace_db):
    assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(include_all=False, include_groups=[{"departments": ["Risk"]}]),
        "creator",
    )
    observers.save_config("course", "creator", selection())
    with database.get_connection() as db:
        db.execute("UPDATE employees SET department='Risk' WHERE employee_id='observer'")
        db.commit()
    assert assignments.reconcile_assignments_for_employee("observer")["assigned"] == 0
    assert assignments.assignment_total("course") == 2
    with pytest.raises(EmployeeObserverConflict):
        observers.apply_config("course", "creator", 1)


def test_saving_future_deadline_does_not_change_applied_deadline(workspace_db):
    assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(
            include_all=False,
            include_groups=[{"departments": ["Risk"]}],
            deadline_mode="fixed",
            deadline_date="2099-10-31",
        ),
        "creator",
    )
    assignments.api_save_course_assignment(
        "course",
        AssignmentRuleRequest(deadline_mode="fixed", deadline_date="2099-12-31"),
        "creator",
    )
    with database.get_connection() as db:
        db.execute("UPDATE employees SET department='Risk' WHERE employee_id='observer'")
        db.commit()
    assert assignments.reconcile_assignments_for_employee("observer")["assigned"] == 1
    with database.get_connection() as db:
        assert (
            db.execute(
                "SELECT deadline FROM course_assignments WHERE employee_id='observer'"
            ).fetchone()["deadline"]
            == "2099-10-31T18:29:59.999999"
        )


def test_stale_observer_identity_does_not_block_replacement_employee(workspace_db):
    observers.save_config("course", "creator", selection())
    with database.get_connection() as db:
        db.execute(
            "UPDATE employees SET directory_uuid='replacement-uuid' WHERE employee_id='observer'"
        )
        db.commit()
    from app.services.assignment_conflicts import observer_ids

    assert observer_ids("course") == set()


def test_completed_employee_is_preserved_and_not_reported_removed(workspace_db):
    assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["a", "b"]}]),
        "creator",
    )
    from app.repositories.progress import get_employee_course_progress

    progress = get_employee_course_progress("a", "course")
    progress["status"] = "completed"
    progress["completed_at"] = "2026-10-01T12:00:00"
    save_employee_course_progress("a", "course", progress)
    result = assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["b"]}]),
        "creator",
    )
    assert result["removed_count"] == 0
    assert result["total_assigned_count"] == 2
    assert get_employee_course_progress("a", "course")["status"] == "completed"


def test_relative_deadline_draft_does_not_change_automatic_enrolment(workspace_db):
    assignments.api_publish_course_assignment(
        "course",
        AssignmentRuleRequest(
            include_all=False, include_groups=[{"departments": ["Risk"]}], deadline_days=7
        ),
        "creator",
    )
    assignments.api_save_course_assignment(
        "course", AssignmentRuleRequest(deadline_days=30), "creator"
    )
    with database.get_connection() as db:
        db.execute("UPDATE employees SET department='Risk' WHERE employee_id='observer'")
        db.commit()
    assert assignments.reconcile_assignments_for_employee("observer")["assigned"] == 1
    from datetime import datetime, timedelta

    from app.repositories.progress import get_employee_course_progress

    progress = get_employee_course_progress("observer", "course")
    assert datetime.fromisoformat(progress["deadline"]) - datetime.fromisoformat(
        progress["assigned_at"]
    ) == timedelta(days=7)
