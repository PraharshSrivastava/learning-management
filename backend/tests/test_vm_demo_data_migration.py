import json
import sqlite3
from pathlib import Path

from scripts.apply_vm_demo_data import apply_migration


def _init_schema(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE courses (id TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL)")
        cursor.execute("CREATE TABLE employee_progress (course_id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        cursor.execute(
            """
            CREATE TABLE employees (
                id TEXT PRIMARY KEY,
                employee_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                role TEXT NOT NULL,
                level TEXT NOT NULL,
                manager_id TEXT,
                join_date TEXT NOT NULL,
                location TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE employee_course_progress (
                employee_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                deadline TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                modules_json TEXT NOT NULL DEFAULT '{}',
                attempts_json TEXT NOT NULL DEFAULT '{}',
                last_activity_at TEXT,
                PRIMARY KEY (employee_id, course_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE course_assignment_rules (
                course_id TEXT PRIMARY KEY,
                include_all INTEGER NOT NULL DEFAULT 1,
                include_match_mode TEXT NOT NULL DEFAULT 'all',
                include_groups_json TEXT NOT NULL DEFAULT '[]',
                include_employee_ids_json TEXT NOT NULL DEFAULT '[]',
                include_departments_json TEXT NOT NULL DEFAULT '[]',
                include_roles_json TEXT NOT NULL DEFAULT '[]',
                joined_less_than_days_ago INTEGER,
                exclude_groups_json TEXT NOT NULL DEFAULT '[]',
                exclude_employee_ids_json TEXT NOT NULL DEFAULT '[]',
                exclude_departments_json TEXT NOT NULL DEFAULT '[]',
                exclude_roles_json TEXT NOT NULL DEFAULT '[]',
                deadline_days INTEGER NOT NULL DEFAULT 7,
                applied_deadline_days INTEGER,
                published_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )


def _insert_course(cursor, course_id, status, title):
    cursor.execute(
        "INSERT INTO courses (id, status, data) VALUES (?, ?, ?)",
        (
            course_id,
            status,
            json.dumps(
                {
                    "id": course_id,
                    "course_id": course_id,
                    "title": title,
                    "thumbnail": "assets/images/course_thumbnails/old-intro.png",
                    "modules": [{"video_url": "assets/videos/old-intro/module_1.mp4"}],
                }
            ),
        ),
    )


def test_apply_migration_keeps_two_deployed_courses_and_assigns_final_five(tmp_path):
    db_path = tmp_path / "lms.db"
    bundle_path = tmp_path / "bundle.json"
    backend_dir = tmp_path / "backend"
    (backend_dir / "assets" / "videos" / "old-intro").mkdir(parents=True)
    (backend_dir / "assets" / "videos" / "old-intro" / "module_1.mp4").write_text("video")
    (backend_dir / "assets" / "images" / "course_thumbnails").mkdir(parents=True)
    (backend_dir / "assets" / "images" / "course_thumbnails" / "old-intro.png").write_text("thumb")
    _init_schema(db_path)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        _insert_course(cursor, "vm-course-1", "published", "Existing VM Course One")
        _insert_course(cursor, "vm-course-2", "published", "Existing VM Course Two")
        _insert_course(cursor, "old-intro", "published", "Introduction to Artificial Intelligence")
        cursor.execute(
            """
            INSERT INTO employees (
                id, employee_code, name, email, department, role, level,
                manager_id, join_date, location, status, created_at, updated_at
            ) VALUES ('dummy', 'DUMMY001', 'Dummy User', 'dummy@example.com', 'Sales',
                'Associate', 'Associate', NULL, '2026-01-01', 'Mumbai', 'active',
                '2026-01-01', '2026-01-01')
            """
        )

    bundle_path.write_text(
        json.dumps(
            {
                "courses": [
                    {
                        "id": "local-intro",
                        "status": "published",
                        "data": {"course_id": "local-intro", "title": "Introduction to Artificial Intelligence"},
                    },
                    {
                        "id": "local-prompting",
                        "status": "published",
                        "data": {"course_id": "local-prompting", "title": "Prompting AI"},
                    },
                    {
                        "id": "local-workflows",
                        "status": "published",
                        "data": {"course_id": "local-workflows", "title": "Building AI Powered Workflows"},
                    },
                ]
            }
        )
    )

    result = apply_migration(
        db_path=db_path,
        bundle_path=bundle_path,
        backend_dir=backend_dir,
        delete_removed_intro_assets=True,
    )

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        course_ids = {row[0] for row in cursor.execute("SELECT id FROM courses")}
        employees = [row[0] for row in cursor.execute("SELECT name FROM employees ORDER BY name")]
        assignment_count = cursor.execute("SELECT COUNT(*) FROM employee_course_progress").fetchone()[0]
        rule_count = cursor.execute("SELECT COUNT(*) FROM course_assignment_rules").fetchone()[0]

    assert course_ids == {"vm-course-1", "vm-course-2", "local-intro", "local-prompting", "local-workflows"}
    assert employees == ["Krish Garg", "Praharsh Srivastava"]
    assert assignment_count == 10
    assert rule_count == 5
    assert result["removed_intro_course_ids"] == ["old-intro"]
    assert not (backend_dir / "assets" / "videos" / "old-intro" / "module_1.mp4").exists()
