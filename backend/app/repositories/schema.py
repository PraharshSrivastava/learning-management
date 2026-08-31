"""PostgreSQL schema initialization for the LMS data model."""

from __future__ import annotations

from app.repositories.database import get_connection

TABLES = (
    "module_progress",
    "email_notifications",
    "course_generation_status",
    "course_generation_state",
    "course_assignments",
    "assignment_rules",
    "saved_assignment_groups",
    "course_modules",
    "courses",
    "documents",
    "employee_groups",
    "employees",
    "trainers",
    "directory_sync_state",
)


def init_db() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        _create_tables(cursor)
        _create_indexes(cursor)
        connection.commit()


def recreate_db() -> None:
    """Drop LMS tables and recreate a clean schema without seeded identities."""
    with get_connection() as connection:
        cursor = connection.cursor()
        for table in TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        _create_tables(cursor)
        _create_indexes(cursor)
        connection.commit()


def _create_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trainers (
            trainer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            directory_uuid TEXT UNIQUE,
            email TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            department TEXT,
            join_date TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            directory_uuid TEXT UNIQUE,
            hub_user_id INTEGER,
            email TEXT UNIQUE,
            sam_account_name TEXT,
            company TEXT,
            manager_directory_uuid TEXT,
            manager_employee_id TEXT,
            directory_status TEXT NOT NULL DEFAULT 'active',
            source TEXT NOT NULL DEFAULT 'hub',
            directory_changed_at TEXT,
            synced_at TEXT,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            CHECK (status IN ('active', 'inactive')),
            CHECK (directory_status IN ('active', 'inactive', 'unknown')),
            CHECK (source IN ('hub', 'manual')),
            FOREIGN KEY (manager_employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employee_groups (
            employee_id TEXT NOT NULL,
            group_dn TEXT NOT NULL,
            group_cn TEXT,
            synced_at TEXT NOT NULL DEFAULT (now()::text),
            PRIMARY KEY (employee_id, group_dn),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS directory_sync_state (
            job_name TEXT PRIMARY KEY,
            cursor INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            last_success_at TEXT,
            last_status TEXT NOT NULL DEFAULT 'never_run',
            last_error TEXT,
            stats_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            CHECK (last_status IN ('never_run', 'success', 'partial', 'failed'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            trainer_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            UNIQUE (trainer_id, file_name),
            FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY,
            trainer_id TEXT NOT NULL,
            document_id TEXT,
            course_name TEXT NOT NULL,
            course_description TEXT NOT NULL DEFAULT '',
            course_objective TEXT NOT NULL DEFAULT '',
            course_difficulty TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT '',
            target_audience TEXT NOT NULL DEFAULT '',
            thumbnail_path TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            published_at TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            CHECK (status IN ('draft', 'ready', 'published', 'archived')),
            FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT,
            FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS course_modules (
            module_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            module_number INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            source_text TEXT NOT NULL DEFAULT '',
            num_questions INTEGER NOT NULL DEFAULT 0 CHECK (num_questions >= 0),
            notes TEXT NOT NULL DEFAULT '',
            slides_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            quiz_json JSONB NOT NULL DEFAULT 'null'::jsonb,
            video_path TEXT,
            planned_slides_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            UNIQUE (course_id, module_number),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS assignment_rules (
            course_id TEXT PRIMARY KEY,
            include_filters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            exclude_filters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            deadline_days INTEGER NOT NULL DEFAULT 7 CHECK (deadline_days >= 1),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            include_inactive BOOLEAN NOT NULL DEFAULT FALSE,
            applied_deadline_days INTEGER CHECK (applied_deadline_days IS NULL OR applied_deadline_days >= 1),
            published_at TEXT,
            disabled_at TEXT,
            disabled_by_trainer_id TEXT,
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY (disabled_by_trainer_id) REFERENCES trainers(trainer_id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_assignment_groups (
            saved_group_id TEXT PRIMARY KEY,
            trainer_id TEXT NOT NULL,
            name TEXT NOT NULL,
            group_type TEXT NOT NULL,
            filters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            UNIQUE (trainer_id, group_type, name),
            CHECK (group_type IN ('include', 'exclude')),
            FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS course_assignments (
            assignment_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            assigned_at TEXT NOT NULL,
            deadline TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            last_activity_at TEXT,
            revoked_at TEXT,
            assigned_department TEXT,
            revoked_reason TEXT,
            notification_lifecycle INTEGER NOT NULL DEFAULT 1 CHECK (notification_lifecycle >= 1),
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            UNIQUE (course_id, employee_id),
            CHECK (status IN ('pending', 'started', 'completed', 'overdue', 'revoked')),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE RESTRICT
        )
        """
    )
    cursor.execute(
        """
        ALTER TABLE course_assignments
        ADD COLUMN IF NOT EXISTS notification_lifecycle INTEGER NOT NULL DEFAULT 1
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS email_notifications (
            notification_id TEXT PRIMARY KEY,
            assignment_id TEXT NOT NULL,
            notification_lifecycle INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            recipient_role TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT,
            subject TEXT NOT NULL,
            body_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            next_attempt_at TEXT NOT NULL,
            locked_at TEXT,
            sent_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            UNIQUE (assignment_id, notification_lifecycle, event_type, recipient_role),
            CHECK (event_type IN ('assigned', 'reactivated', 'due_soon', 'completed', 'overdue')),
            CHECK (recipient_role IN ('employee', 'hod', 'trainer')),
            CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'cancelled')),
            FOREIGN KEY (assignment_id) REFERENCES course_assignments(assignment_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS module_progress (
            assignment_id TEXT NOT NULL,
            module_id TEXT NOT NULL,
            video_watched BOOLEAN NOT NULL DEFAULT FALSE,
            quiz_passed BOOLEAN NOT NULL DEFAULT FALSE,
            quiz_score REAL,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            last_attempt_at TEXT,
            selected_answers_json JSONB NOT NULL DEFAULT 'null'::jsonb,
            video_watched_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            PRIMARY KEY (assignment_id, module_id),
            CHECK (quiz_score IS NULL OR (quiz_score >= 0 AND quiz_score <= 100)),
            FOREIGN KEY (assignment_id) REFERENCES course_assignments(assignment_id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES course_modules(module_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS course_generation_status (
            course_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            checkpoint TEXT,
            stages_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error TEXT,
            worker_id TEXT,
            locked_until TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            CHECK (status IN ('pending', 'running', 'failed', 'completed')),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
        """
    )


def _create_indexes(cursor) -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_trainers_status ON trainers(status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_directory_uuid ON employees(directory_uuid)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_hub_user_id ON employees(hub_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_email ON employees(email)",
        "CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department)",
        "CREATE INDEX IF NOT EXISTS idx_employees_manager ON employees(manager_employee_id)",
        "CREATE INDEX IF NOT EXISTS idx_employees_dir_status ON employees(directory_status)",
        "CREATE INDEX IF NOT EXISTS idx_employees_dept_active ON employees(department, directory_status)",
        "CREATE INDEX IF NOT EXISTS idx_employee_groups_cn ON employee_groups(group_cn)",
        "CREATE INDEX IF NOT EXISTS idx_documents_trainer ON documents(trainer_id)",
        "CREATE INDEX IF NOT EXISTS idx_courses_trainer_status ON courses(trainer_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_courses_document ON courses(document_id)",
        "CREATE INDEX IF NOT EXISTS idx_course_modules_course_number ON course_modules(course_id, module_number)",
        "CREATE INDEX IF NOT EXISTS idx_assignment_rules_active ON assignment_rules(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_saved_assignment_groups_trainer "
        "ON saved_assignment_groups(trainer_id, group_type)",
        "CREATE INDEX IF NOT EXISTS idx_assignments_employee ON course_assignments(employee_id)",
        "CREATE INDEX IF NOT EXISTS idx_assignments_status ON course_assignments(status)",
        "CREATE INDEX IF NOT EXISTS idx_course_assignments_deadline ON course_assignments(deadline)",
        "CREATE INDEX IF NOT EXISTS idx_email_notifications_status_next "
        "ON email_notifications(status, next_attempt_at)",
        "CREATE INDEX IF NOT EXISTS idx_email_notifications_assignment "
        "ON email_notifications(assignment_id)",
        "CREATE INDEX IF NOT EXISTS idx_module_progress_assignment ON module_progress(assignment_id)",
        "CREATE INDEX IF NOT EXISTS idx_course_generation_status_worker ON course_generation_status(status, locked_until)",
    )
    for statement in statements:
        cursor.execute(statement)
