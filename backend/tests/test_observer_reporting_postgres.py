"""Effective grants, union/deduplication and revocation tested on real SQL."""

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.core.exceptions import AuthorizationError, ConflictError, DomainValidationError
from app.repositories import database, observers, performance_reporting, report_access, schema
from app.repositories.access_migrations import apply_access_migrations
from app.schemas.observers import ObserverSaveRequest
from app.schemas.reporting_scope import EmployeePerformanceScope, TrainerPerformanceScope
from app.services import performance_reporting as reports

pytestmark = pytest.mark.skipif(os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated demo opt-in")


@pytest.fixture
def report_db(monkeypatch):
    with database.get_connection() as raw:
        assert raw.execute("SELECT current_database() AS name").fetchone()["name"] == "lms_performance_demo"
        name = "report_access_test_" + uuid4().hex
        try:
            raw.execute(f'CREATE SCHEMA "{name}"')
            raw.execute(f'SET LOCAL search_path TO "{name}"')
            schema._create_tables(raw.cursor())
            apply_access_migrations(raw)

            class Transaction:
                def execute(self, *args, **kwargs):
                    return raw.execute(*args, **kwargs)

                def commit(self):
                    pass

            tx = Transaction()

            @contextmanager
            def connection():
                with raw._connection.transaction():
                    yield tx

            for module in (observers, report_access, performance_reporting):
                monkeypatch.setattr(module, "get_connection", connection)
            raw.execute("INSERT INTO trainers(trainer_id, name) VALUES ('t-1', 'Creator'), ('t-2', 'Another')")
            for employee_id, department in (("observer", "Legal"), ("hod", "HR"), ("a", "Finance"), ("b", "Ops"), ("c", "Finance")):
                raw.execute("INSERT INTO employees(employee_id,name,job_title,department,directory_uuid) VALUES (?, ?, 'Employee', ?, ?)",
                            (employee_id, employee_id, department, "uuid-" + employee_id))
            for course_id, trainer_id in (("course-1", "t-1"), ("course-2", "t-2")):
                raw.execute("INSERT INTO courses(course_id,trainer_id,course_name,status) VALUES (?, ?, 'Same title', 'published')", (course_id, trainer_id))
                raw.execute("INSERT INTO assignment_rules(course_id,published_at,include_filters_json) VALUES (?, '2026-10-06', ?::jsonb)", (course_id, '{"include_all":false,"groups":[{"employee_ids":["a","b","c"]}]}'))
                for employee_id in ("a", "b", "c"):
                    raw.execute("INSERT INTO course_assignments(assignment_id,course_id,employee_id,assigned_at,deadline) VALUES (?, ?, ?, '2026-10-06', '2026-12-01')",
                                (course_id + employee_id, course_id, employee_id))
            raw.execute("INSERT INTO lms_departments VALUES ('finance', 'dir-finance', 'Finance', 'directory', TRUE), ('ops', 'dir-ops', 'Ops', 'directory', TRUE)")
            raw.execute("INSERT INTO hod_department_access(hod_employee_id,identity_key,department_id,source,source_key) VALUES ('hod','directory:uuid-hod','finance','directory','verified-fixture')")
            token = database._active_transaction.set(tx)
            try:
                yield tx
            finally:
                database._active_transaction.reset(token)
        finally:
            raw.rollback()


def payload(revision=0, employees=None, departments=None, observer="observer"):
    return ObserverSaveRequest(revision=revision, observers=[{
        "observer_employee_id": observer, "employee_ids": employees or [], "department_ids": departments or [],
    }])


def scope(view="observed", employee="observer"):
    return EmployeePerformanceScope(employee, "directory:uuid-" + employee, view)


def ids(selected):
    return {row["assignment_id"] for row in performance_reporting.list_assignment_summaries(selected)}


def test_pending_apply_cross_department_and_course_specific_scope(report_db):
    result = observers.save_config("course-1", "t-1", payload(employees=["b"]))
    assert result["revision"] == 1 and ids(scope()) == set()
    assert result["observers"][0]["is_active"] is False
    assert report_db.execute("SELECT COUNT(*) AS n FROM course_assignments").fetchone()["n"] == 6
    assert report_db.execute("SELECT COUNT(*) AS n FROM email_notifications").fetchone()["n"] == 0
    result = observers.apply_config("course-1", "t-1", 1)
    assert result["revision"] == 2 and ids(scope()) == {"course-1b"}
    assert result["observers"][0]["is_active"] is True
    assert report_access.report_roles(dict(report_db.execute("SELECT * FROM employees WHERE employee_id='observer'").fetchone())) == {"observer"}
    assert performance_reporting.get_assignment_detail(scope(), "course-2b") is None
    assert performance_reporting.get_assignment_detail(scope(), "course-1b") is not None


def test_expansion_pending_restrictions_immediate_and_revoke(report_db):
    observers.save_config("course-1", "t-1", payload(employees=["a", "b"]))
    observers.apply_config("course-1", "t-1", 1)
    observers.save_config("course-1", "t-1", payload(2, employees=["b", "c"]))
    assert ids(scope()) == {"course-1b"}
    observers.apply_config("course-1", "t-1", 3)
    assert ids(scope()) == {"course-1b", "course-1c"}
    observers.save_config("course-1", "t-1", ObserverSaveRequest(revision=4, observers=[]))
    assert ids(scope()) == set()
    assert observers.get_config("course-1")["observers"] == []
    observers.apply_config("course-1", "t-1", 5)
    assert ids(scope()) == set()
    assert report_db.execute("SELECT COUNT(*) AS n FROM lms_report_access_audit").fetchone()["n"] == 6


def test_hod_department_wide_and_combined_deduplicate_assignment_and_employee(report_db):
    observers.save_config("course-1", "t-1", payload(employees=["a", "b"], departments=["finance"], observer="hod"))
    observers.apply_config("course-1", "t-1", 1)
    assert ids(scope("my_departments", "hod")) == {"course-1a", "course-1c", "course-2a", "course-2c"}
    assert ids(scope("observed", "hod")) == {"course-1a", "course-1b", "course-1c"}
    assert len(ids(scope("combined", "hod"))) == 5
    result = reports.employee_list(scope("combined", "hod"))
    assert result["total"] == 3
    assert len(ids(TrainerPerformanceScope("t-1", True))) == 6
    assert len(ids(TrainerPerformanceScope("t-1", False))) == 3
    options = performance_reporting.list_scope_options(scope("observed", "hod"))
    assert [r["course_id"] for r in options["courses"]] == ["course-1"]
    assert set(options["departments"]) == {"Finance", "Ops"}


def test_dynamic_department_membership_and_recycled_explicit_identity(report_db):
    observers.save_config("course-1", "t-1", payload(employees=["b"], departments=["finance"]))
    observers.apply_config("course-1", "t-1", 1)
    assert len(ids(scope())) == 3
    report_db.execute("UPDATE employees SET department='Ops' WHERE employee_id='a'")
    report_db.execute("UPDATE employees SET directory_uuid='replacement-b' WHERE employee_id='b'")
    assert ids(scope()) == {"course-1c"}
    report_db.execute("UPDATE employees SET directory_uuid='replacement-observer' WHERE employee_id='observer'")
    assert ids(scope()) == set()


def test_conflicts_noncreator_invalid_scope_and_audit_rollback(report_db):
    with pytest.raises(AuthorizationError):
        observers.save_config("course-1", "t-2", payload(employees=["b"]))
    with pytest.raises(ConflictError):
        observers.save_config("course-1", "t-1", payload(99, employees=["b"]))
    with pytest.raises(DomainValidationError):
        observers.save_config("course-1", "t-1", payload(departments=["missing"]))
    assert observers.get_config("course-1")["revision"] == 0
    report_db.execute("ALTER TABLE lms_report_access_audit ADD CONSTRAINT reject_test CHECK (actor <> 't-1')")
    with pytest.raises(Exception):
        observers.save_config("course-1", "t-1", payload(employees=["b"]))
    assert observers.get_config("course-1")["revision"] == 0
    assert report_db.execute("SELECT COUNT(*) AS n FROM course_observer_grants").fetchone()["n"] == 0


def test_disable_suspends_and_republish_requires_explicit_owner_apply(report_db):
    observers.save_config("course-1", "t-1", payload(employees=["b"]))
    observers.apply_config("course-1", "t-1", 1)
    observers.suspend_course("course-1")
    assert ids(scope()) == set()
    observers.apply_config("course-1", "t-1", 3)
    assert ids(scope()) == {"course-1b"}
    report_db.execute("UPDATE assignment_rules SET is_active=FALSE WHERE course_id='course-1'")
    assert ids(scope()) == set()
    with pytest.raises(DomainValidationError):
        observers.apply_config("course-1", "t-1", 4)


def test_hod_cannot_be_inferred_from_own_department_or_manager(report_db):
    assert ids(scope("my_departments", "observer")) == set()
    report_db.execute("UPDATE employees SET department='Finance' WHERE employee_id='observer'")
    assert ids(scope("my_departments", "observer")) == set()
    report_db.execute("UPDATE lms_departments SET source='directory-label' WHERE department_id='finance'")
    assert ids(scope("my_departments", "hod")) == set()


def test_verified_directory_adapter_partial_revoke_rename_and_full_reconciliation(report_db, monkeypatch):
    from app.repositories import directory_report_access

    monkeypatch.setattr(directory_report_access, "get_connection", observers.get_connection)
    directory_report_access.reconcile_verified_departments([
        {"external_key": "dir-finance", "name": "Finance", "hod_directory_uuids": ["uuid-hod"]}
    ], source_key="verified-fixture")
    assert len(ids(scope("my_departments", "hod"))) == 4
    directory_report_access.reconcile_verified_departments([
        {"external_key": "dir-finance", "name": "Finance renamed"}
    ], source_key="verified-fixture")
    assert ids(scope("my_departments", "hod")) == set()
    report_db.execute("UPDATE employees SET department='Finance renamed' WHERE department='Finance'")
    assert len(ids(scope("my_departments", "hod"))) == 4
    directory_report_access.reconcile_verified_departments([
        {"external_key": "dir-finance", "name": "Finance renamed", "hod_directory_uuids": []}
    ], source_key="verified-fixture")
    assert ids(scope("my_departments", "hod")) == set()
    directory_report_access.reconcile_verified_departments([], source_key="verified-fixture", full_snapshot=True)
    assert report_db.execute("SELECT COUNT(*) AS n FROM lms_departments WHERE source='directory' AND active").fetchone()["n"] == 0
