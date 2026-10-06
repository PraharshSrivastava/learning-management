"""Additive course Observer and trusted directory department mapping storage."""

VERSION = "20261006_report_access_v1"
STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS lms_departments (
        department_id TEXT PRIMARY KEY, external_key TEXT UNIQUE NOT NULL,
        name TEXT UNIQUE NOT NULL, source TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE
    )""",
    """CREATE TABLE IF NOT EXISTS hod_department_access (
        hod_employee_id TEXT NOT NULL REFERENCES employees(employee_id), identity_key TEXT NOT NULL,
        department_id TEXT NOT NULL REFERENCES lms_departments(department_id),
        source TEXT NOT NULL CHECK (source = 'directory'), source_key TEXT NOT NULL,
        active BOOLEAN NOT NULL DEFAULT TRUE, synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (hod_employee_id, department_id)
    )""",
    """CREATE TABLE IF NOT EXISTS course_observer_configs (
        course_id TEXT PRIMARY KEY REFERENCES courses(course_id) ON DELETE CASCADE,
        revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0)
    )""",
    """CREATE TABLE IF NOT EXISTS course_observer_grants (
        course_id TEXT NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
        observer_employee_id TEXT NOT NULL REFERENCES employees(employee_id), identity_key TEXT NOT NULL,
        active BOOLEAN NOT NULL DEFAULT FALSE, granted_by_trainer_id TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (course_id, observer_employee_id)
    )""",
    """CREATE TABLE IF NOT EXISTS course_observer_employees (
        course_id TEXT NOT NULL, observer_employee_id TEXT NOT NULL,
        phase TEXT NOT NULL CHECK (phase IN ('active', 'pending')),
        employee_id TEXT NOT NULL REFERENCES employees(employee_id), identity_key TEXT NOT NULL,
        PRIMARY KEY(course_id, observer_employee_id, phase, employee_id),
        FOREIGN KEY(course_id, observer_employee_id) REFERENCES course_observer_grants
            ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS course_observer_departments (
        course_id TEXT NOT NULL, observer_employee_id TEXT NOT NULL,
        phase TEXT NOT NULL CHECK (phase IN ('active', 'pending')),
        department_id TEXT NOT NULL REFERENCES lms_departments(department_id),
        PRIMARY KEY(course_id, observer_employee_id, phase, department_id),
        FOREIGN KEY(course_id, observer_employee_id) REFERENCES course_observer_grants
            ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS lms_report_access_audit (
        audit_id TEXT PRIMARY KEY, course_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL,
        revision INTEGER, before_json JSONB NOT NULL, after_json JSONB NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_observer_employee_active ON course_observer_grants(observer_employee_id, active, course_id)",
)


def apply_report_access_migration(connection):
    if connection.execute("SELECT version FROM lms_schema_migrations WHERE version = ?", (VERSION,)).fetchone():
        return
    for statement in STATEMENTS:
        connection.execute(statement)
    connection.execute("INSERT INTO lms_schema_migrations(version) VALUES (?)", (VERSION,))
