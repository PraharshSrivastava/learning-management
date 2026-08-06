"""SQLite schema initialization for the production-shaped LMS data model."""

from __future__ import annotations

from app.repositories.database import get_connection
from app.repositories.seed import seed_demo_employees, seed_demo_trainers

def init_db() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        _create_tables(cursor)
        _create_indexes(cursor)
        cursor.execute("SELECT COUNT(*) AS count FROM employees")
        if cursor.fetchone()["count"] == 0:
            seed_demo_employees(cursor)
        cursor.execute("SELECT COUNT(*) AS count FROM trainers")
        if cursor.fetchone()["count"] == 0:
            seed_demo_trainers(cursor)
        connection.commit()

def _create_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trainers (
            trainer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            department TEXT NOT NULL,
            join_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
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
            course_name TEXT NOT NULL DEFAULT '',
            course_description TEXT NOT NULL DEFAULT '',
            course_objective TEXT NOT NULL DEFAULT '',
            course_difficulty TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT '',
            target_audience TEXT NOT NULL DEFAULT '',
            thumbnail_path TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            published_at TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            CHECK (status IN ('draft', 'ready', 'published', 'archived')),
            CHECK (json_valid(metadata_json)),
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
            slides_json TEXT NOT NULL DEFAULT '[]',
            quiz_json TEXT NOT NULL DEFAULT 'null',
            video_path TEXT,
            planned_slides_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (course_id, module_number),
            CHECK (json_valid(slides_json)),
            CHECK (json_valid(quiz_json)),
            CHECK (json_valid(planned_slides_json)),
            CHECK (json_valid(metadata_json)),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS assignment_rules (
            course_id TEXT PRIMARY KEY,
            include_filters_json TEXT NOT NULL DEFAULT '{}',
            exclude_filters_json TEXT NOT NULL DEFAULT '{}',
            deadline_days INTEGER NOT NULL DEFAULT 7 CHECK (deadline_days >= 1),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            applied_deadline_days INTEGER CHECK (applied_deadline_days IS NULL OR applied_deadline_days >= 1),
            published_at TEXT,
            disabled_at TEXT,
            disabled_by_trainer_id TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (json_valid(include_filters_json)),
            CHECK (json_valid(exclude_filters_json)),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY (disabled_by_trainer_id) REFERENCES trainers(trainer_id) ON DELETE SET NULL
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
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (course_id, employee_id),
            CHECK (status IN ('pending', 'started', 'completed', 'overdue', 'revoked')),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE RESTRICT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS module_progress (
            assignment_id TEXT NOT NULL,
            module_id TEXT NOT NULL,
            video_watched INTEGER NOT NULL DEFAULT 0 CHECK (video_watched IN (0, 1)),
            quiz_passed INTEGER NOT NULL DEFAULT 0 CHECK (quiz_passed IN (0, 1)),
            quiz_score REAL,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            last_attempt_at TEXT,
            selected_answers_json TEXT NOT NULL DEFAULT 'null',
            video_watched_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (assignment_id, module_id),
            CHECK (quiz_score IS NULL OR (quiz_score >= 0 AND quiz_score <= 100)),
            CHECK (json_valid(selected_answers_json)),
            FOREIGN KEY (assignment_id) REFERENCES course_assignments(assignment_id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES course_modules(module_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS course_generation_state (
            course_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            checkpoint TEXT,
            stages_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            worker_id TEXT,
            locked_until TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (status IN ('pending', 'running', 'failed', 'completed')),
            CHECK (json_valid(stages_json)),
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
        """
    )


def _create_indexes(cursor) -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_trainers_status ON trainers(status)",
        "CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status)",
        "CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department)",
        "CREATE INDEX IF NOT EXISTS idx_employees_job_title ON employees(job_title)",
        "CREATE INDEX IF NOT EXISTS idx_documents_trainer ON documents(trainer_id)",
        "CREATE INDEX IF NOT EXISTS idx_courses_trainer_status ON courses(trainer_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_courses_document ON courses(document_id)",
        "CREATE INDEX IF NOT EXISTS idx_course_modules_course_number ON course_modules(course_id, module_number)",
        "CREATE INDEX IF NOT EXISTS idx_assignment_rules_active ON assignment_rules(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_course_assignments_employee_status ON course_assignments(employee_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_course_assignments_course_status ON course_assignments(course_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_course_assignments_deadline ON course_assignments(deadline)",
        "CREATE INDEX IF NOT EXISTS idx_module_progress_assignment ON module_progress(assignment_id)",
        "CREATE INDEX IF NOT EXISTS idx_course_generation_state_worker ON course_generation_state(status, locked_until)",
    )
    for statement in statements:
        cursor.execute(statement)
