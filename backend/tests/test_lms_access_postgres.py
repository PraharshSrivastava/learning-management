"""Opt-in role migrations/grants tested inside a rolled-back isolated schema."""

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.core.exceptions import DomainValidationError
from app.repositories import database, lms_access
from app.repositories.access_migrations import VERSION, apply_access_migrations

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true",
    reason="Requires explicit isolated demo PostgreSQL selection",
)


@pytest.fixture
def access_db(monkeypatch):
    with database.get_connection() as raw:
        assert (
            raw.execute("SELECT current_database() AS name").fetchone()["name"]
            == "lms_performance_demo"
        ), "Access tests refuse databases other than the isolated demo."
        schema = "lms_access_test_" + uuid4().hex
        try:
            # Identifier contains only a fixed ASCII prefix and generated hexadecimal digits.
            raw.execute(f'CREATE SCHEMA "{schema}"')
            raw.execute(f'SET LOCAL search_path TO "{schema}"')
            raw.execute("""CREATE TABLE employees (employee_id TEXT PRIMARY KEY, directory_uuid TEXT,
                hub_user_id INTEGER, name TEXT, email TEXT, status TEXT, directory_status TEXT, source TEXT)""")
            raw.execute("""CREATE TABLE courses (course_id TEXT PRIMARY KEY, trainer_id TEXT,
                course_name TEXT, course_description TEXT, status TEXT, created_at TEXT, updated_at TEXT)""")
            raw.execute("CREATE TABLE assignment_rules(course_id TEXT PRIMARY KEY, is_active BOOLEAN, published_at TEXT)")
            raw.execute(
                "INSERT INTO employees VALUES ('employee-1', 'uuid-1', 42, 'Kiran', 'same@example.test', 'active', 'active', 'hub')"
            )
            raw.execute(
                "CREATE TABLE preserved_progress (assignment_id TEXT PRIMARY KEY, completed BOOLEAN)"
            )
            raw.execute("INSERT INTO preserved_progress VALUES ('assignment-1', TRUE)")

            class Transaction:
                def execute(self, *args, **kwargs):
                    return raw.execute(*args, **kwargs)

                def commit(self):
                    pass  # The outer test transaction always rolls back.

            transaction = Transaction()

            @contextmanager
            def connection():
                with raw._connection.transaction():
                    yield transaction

            monkeypatch.setattr(lms_access, "get_connection", connection)
            from app.repositories import report_access
            monkeypatch.setattr(report_access, "get_connection", connection)
            apply_access_migrations(transaction)
            yield transaction
        finally:
            raw.rollback()  # Removes schema, roles, audit and fixtures without touching demo data.


def employee(db):
    return dict(db.execute("SELECT * FROM employees WHERE employee_id = 'employee-1'").fetchone())


def change(active=True, **kwargs):
    return lms_access.set_admin_grant(
        "employee-1",
        active=active,
        expected_identity=kwargs.get("identity", "directory:uuid-1"),
        operator="test-operator",
        reason="isolated regression test",
    )


def test_migration_is_idempotent_and_preserves_existing_data(access_db):
    apply_access_migrations(access_db)
    assert (
        access_db.execute(
            "SELECT COUNT(*) AS count FROM lms_schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()["count"]
        == 1
    )
    assert access_db.execute("SELECT completed FROM preserved_progress").fetchone()["completed"]
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 0)


def test_grant_revoke_and_noop_have_atomic_versioned_audit(access_db):
    assert change() == {"changed": True, "permissions_version": 1}
    assert lms_access.access_snapshot(employee(access_db)) == ({"admin_trainer"}, 1)
    assert change() == {"changed": False, "permissions_version": 1}
    assert change(False) == {"changed": True, "permissions_version": 2}
    assert change(False) == {"changed": False, "permissions_version": 2}
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 2)
    rows = access_db.execute(
        "SELECT action, permissions_version, operator, reason FROM lms_access_audit ORDER BY permissions_version"
    ).fetchall()
    assert [r["action"] for r in rows] == ["grant", "revoke"]
    assert [r["permissions_version"] for r in rows] == [1, 2]
    assert all(r["operator"] == "test-operator" and r["reason"] for r in rows)


@pytest.mark.parametrize(
    "field,value", [("status", "inactive"), ("directory_status", "inactive"), ("source", "local")]
)
def test_grant_requires_active_synced_identity(access_db, field, value):
    access_db.execute(f"UPDATE employees SET {field} = ?", (value,))
    with pytest.raises(DomainValidationError):
        change()
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 0)


def test_expected_identity_mismatch_cannot_promote(access_db):
    with pytest.raises(DomainValidationError):
        change(identity="directory:someone-else")
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 0)


def test_identity_reuse_cannot_inherit_admin_even_with_same_email(access_db):
    change()
    access_db.execute("UPDATE employees SET directory_uuid = 'uuid-2'")
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 1)
    with pytest.raises(DomainValidationError):
        change()
    # Explicit new identity provisioning is required, and separately audited.
    assert change(identity="directory:uuid-2")["permissions_version"] == 2
    assert lms_access.access_snapshot(employee(access_db)) == ({"admin_trainer"}, 2)


def test_name_email_changes_keep_stable_grant_and_disabled_identity_can_revoke(access_db):
    change()
    access_db.execute("UPDATE employees SET name = 'Renamed', email = 'new@example.test'")
    assert lms_access.access_snapshot(employee(access_db)) == ({"admin_trainer"}, 1)
    access_db.execute("UPDATE employees SET status = 'inactive'")
    assert change(False)["permissions_version"] == 2
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 2)


def test_audit_failure_rolls_back_grant_and_version(access_db, monkeypatch):
    execute = access_db.execute

    def fail_audit(query, params=None):
        if "INSERT INTO lms_access_audit" in query:
            raise RuntimeError("simulated audit failure")
        return execute(query, params)

    monkeypatch.setattr(access_db, "execute", fail_audit)
    with pytest.raises(RuntimeError, match="audit failure"):
        change()
    assert lms_access.access_snapshot(employee(access_db)) == (set(), 0)
    assert (
        access_db.execute("SELECT COUNT(*) AS count FROM lms_access_audit").fetchone()["count"] == 0
    )


def test_persistent_grant_changes_capabilities_for_existing_trainer_session(access_db, monkeypatch):
    from starlette.requests import Request

    from app.services import auth
    from app.services import lms_access as service

    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(auth, "_hub_session", lambda *_: None)
    monkeypatch.setattr(auth, "_local_trainer_sessions", {"existing-token": "trainer-1"})
    monkeypatch.setattr(
        auth._trainers,
        "get",
        lambda *_: {"trainer_id": "trainer-1", "directory_uuid": "uuid-1", "status": "active"},
    )
    monkeypatch.setattr(service._employees, "get_by_directory_uuid", lambda *_: employee(access_db))
    request = Request({"type": "http", "headers": []})
    initial = service.current_lms_access(request, "Bearer existing-token", "trainer")
    assert initial.roles == ["trainer"] and initial.capabilities.can_view_all_performance
    change()
    granted = service.current_lms_access(request, "Bearer existing-token", "trainer")
    assert granted.roles == ["admin_trainer"] and granted.permissions_version == 1
    assert granted.capabilities.can_view_other_trainers_courses
    assert not granted.capabilities.can_manage_other_trainers_courses
    change(False)
    revoked = service.current_lms_access(request, "Bearer existing-token", "trainer")
    assert revoked.roles == ["trainer"] and revoked.permissions_version == 2
    assert revoked.capabilities.can_author_courses and revoked.capabilities.can_view_all_performance
    assert not revoked.capabilities.can_view_other_trainers_courses
