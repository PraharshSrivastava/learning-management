"""Additive, transactionally serialized migrations for LMS access metadata."""

from app.repositories.database import advisory_xact_lock

VERSION = "20261006_authoring_access_v1"

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS lms_access_versions (
        employee_id TEXT PRIMARY KEY REFERENCES employees(employee_id),
        permissions_version BIGINT NOT NULL DEFAULT 0 CHECK (permissions_version >= 0)
    )""",
    """CREATE TABLE IF NOT EXISTS lms_authoring_roles (
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        role TEXT NOT NULL CHECK (role IN ('trainer', 'admin_trainer')),
        identity_key TEXT NOT NULL,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        granted_by TEXT NOT NULL,
        granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        revoked_at TIMESTAMPTZ,
        PRIMARY KEY (employee_id, role)
    )""",
    """CREATE TABLE IF NOT EXISTS lms_access_audit (
        audit_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        identity_key TEXT NOT NULL,
        role TEXT NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('grant', 'revoke')),
        previous_active BOOLEAN NOT NULL,
        next_active BOOLEAN NOT NULL,
        operator TEXT NOT NULL,
        reason TEXT NOT NULL,
        permissions_version BIGINT NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_lms_access_audit_employee ON lms_access_audit(employee_id, occurred_at)",
)


def _apply_authoring_migration(connection) -> None:
    advisory_xact_lock(connection, "lms-access-schema-migrations")
    connection.execute("""CREATE TABLE IF NOT EXISTS lms_schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    if connection.execute(
        "SELECT version FROM lms_schema_migrations WHERE version = ?", (VERSION,)
    ).fetchone():
        return
    for statement in STATEMENTS:
        connection.execute(statement)
    connection.execute("INSERT INTO lms_schema_migrations(version) VALUES (?)", (VERSION,))


def apply_access_migrations(connection) -> None:
    from app.repositories.report_access_migrations import apply_report_access_migration

    _apply_authoring_migration(connection)
    apply_report_access_migration(connection)
