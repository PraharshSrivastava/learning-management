import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


TARGET_EMPLOYEES = [
    {
        "id": "emp_krish_garg",
        "employee_code": "KRISH001",
        "name": "Krish Garg",
        "email": "krish.garg@phillipcapital.example",
        "department": "AI Learning",
        "role": "Learner",
        "level": "Associate",
        "manager_id": None,
        "location": "Mumbai",
    },
    {
        "id": "emp_praharsh_srivastava",
        "employee_code": "PRAHARSH001",
        "name": "Praharsh Srivastava",
        "email": "praharsh.srivastava@phillipcapital.example",
        "department": "AI Learning",
        "role": "Learner",
        "level": "Associate",
        "manager_id": None,
        "location": "Mumbai",
    },
]


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_bundle(bundle_path: Path) -> List[Dict[str, Any]]:
    with bundle_path.open("r", encoding="utf-8") as handle:
        bundle = json.load(handle)
    courses = bundle.get("courses")
    if not isinstance(courses, list) or not courses:
        raise ValueError("Bundle must contain a non-empty 'courses' list.")

    normalized = []
    for row in courses:
        if not isinstance(row, dict):
            raise ValueError("Every bundled course row must be an object.")
        status = row.get("status")
        data = row.get("data")
        if status not in {"draft", "published"}:
            raise ValueError("Every bundled course must have status 'draft' or 'published'.")
        if not isinstance(data, dict):
            raise ValueError("Every bundled course must include object field 'data'.")
        course_id = row.get("id") or _course_public_id(data)
        if not course_id:
            raise ValueError("Every bundled course must have an id or data.course_id/data.id.")
        normalized.append({"id": course_id, "status": status, "data": data})
    return normalized


def _course_public_id(course: Dict[str, Any]) -> Optional[str]:
    return course.get("course_id") or course.get("id")


def _course_title(course: Dict[str, Any]) -> str:
    return str(course.get("title") or course.get("course_name") or "").strip()


def _is_intro_ai(course: Dict[str, Any]) -> bool:
    title = _course_title(course).casefold()
    return "introduction" in title and "artificial intelligence" in title


def _asset_path(value: str) -> Optional[str]:
    cleaned = value.split("?", 1)[0].lstrip("/")
    if cleaned.startswith("assets/") or cleaned.startswith("uploads/"):
        return cleaned
    return None


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _collect_asset_paths(course: Dict[str, Any]) -> Set[str]:
    paths = set()
    for value in _walk_strings(course):
        path = _asset_path(value)
        if path:
            paths.add(path)
    return paths


def _safe_remove_assets(backend_dir: Path, relative_paths: Iterable[str]) -> List[str]:
    removed = []
    backend_root = backend_dir.resolve()
    for relative_path in sorted(set(relative_paths)):
        target = (backend_dir / relative_path).resolve()
        try:
            target.relative_to(backend_root)
        except ValueError:
            continue
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.append(str(target))
    return removed


def _backup_db(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_{stamp}{db_path.suffix}.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _fetch_courses(cursor: sqlite3.Cursor) -> List[Tuple[str, str, Dict[str, Any]]]:
    rows = cursor.execute("SELECT id, status, data FROM courses").fetchall()
    return [(row["id"], row["status"], json.loads(row["data"])) for row in rows]


def _ensure_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employee_progress (
            course_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
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
        CREATE TABLE IF NOT EXISTS employee_course_progress (
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
            PRIMARY KEY (employee_id, course_id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS course_assignment_rules (
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
    cursor.execute("PRAGMA table_info(course_assignment_rules)")
    assignment_columns = {row["name"] for row in cursor.fetchall()}
    if "include_employee_ids_json" not in assignment_columns:
        cursor.execute("ALTER TABLE course_assignment_rules ADD COLUMN include_employee_ids_json TEXT NOT NULL DEFAULT '[]'")
    if "include_match_mode" not in assignment_columns:
        cursor.execute("ALTER TABLE course_assignment_rules ADD COLUMN include_match_mode TEXT NOT NULL DEFAULT 'all'")
    if "include_groups_json" not in assignment_columns:
        cursor.execute("ALTER TABLE course_assignment_rules ADD COLUMN include_groups_json TEXT NOT NULL DEFAULT '[]'")
    if "exclude_groups_json" not in assignment_columns:
        cursor.execute("ALTER TABLE course_assignment_rules ADD COLUMN exclude_groups_json TEXT NOT NULL DEFAULT '[]'")
    if "applied_deadline_days" not in assignment_columns:
        cursor.execute("ALTER TABLE course_assignment_rules ADD COLUMN applied_deadline_days INTEGER")

    cursor.execute("PRAGMA table_info(employee_course_progress)")
    progress_columns = {row["name"] for row in cursor.fetchall()}
    if "started_at" not in progress_columns:
        cursor.execute("ALTER TABLE employee_course_progress ADD COLUMN started_at TEXT")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employees_role ON employees(role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_course_progress_employee ON employee_course_progress(employee_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_course_progress_course ON employee_course_progress(course_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_course_progress_status ON employee_course_progress(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_course_assignment_rules_course ON course_assignment_rules(course_id)")


def apply_migration(
    db_path: Path,
    bundle_path: Path,
    backend_dir: Path,
    backup_dir: Optional[Path] = None,
    delete_removed_intro_assets: bool = False,
    deadline_days: int = 7,
) -> Dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    if deadline_days < 1:
        raise ValueError("deadline_days must be at least 1.")

    bundled_courses = _load_bundle(bundle_path)
    bundled_ids = {row["id"] for row in bundled_courses}
    bundled_public_ids = {
        public_id
        for public_id in (_course_public_id(row["data"]) for row in bundled_courses)
        if public_id
    }
    backup_path = _backup_db(db_path, backup_dir or db_path.parent / "backups")
    old_intro_asset_paths: Set[str] = set()
    now = datetime.now()
    deadline = now + timedelta(days=deadline_days)

    with _connect(db_path) as conn:
        cursor = conn.cursor()
        _ensure_schema(cursor)
        existing_courses = _fetch_courses(cursor)
        removed_intro_ids = []

        for db_id, _status, course in existing_courses:
            public_id = _course_public_id(course)
            if _is_intro_ai(course) and db_id not in bundled_ids and public_id not in bundled_public_ids:
                removed_intro_ids.append(db_id)
                old_intro_asset_paths.update(_collect_asset_paths(course))

        cursor.execute("DELETE FROM employee_course_progress")
        cursor.execute("DELETE FROM employee_progress")
        cursor.execute("DELETE FROM course_assignment_rules")
        cursor.execute("DELETE FROM employees")

        for course_id in removed_intro_ids:
            cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))

        for row in bundled_courses:
            cursor.execute(
                "INSERT OR REPLACE INTO courses (id, status, data) VALUES (?, ?, ?)",
                (row["id"], row["status"], json.dumps(row["data"], ensure_ascii=False)),
            )

        for employee in TARGET_EMPLOYEES:
            cursor.execute(
                """
                INSERT INTO employees (
                    id, employee_code, name, email, department, role, level,
                    manager_id, join_date, location, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    employee["id"],
                    employee["employee_code"],
                    employee["name"],
                    employee["email"],
                    employee["department"],
                    employee["role"],
                    employee["level"],
                    employee["manager_id"],
                    now.date().isoformat(),
                    employee["location"],
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

        published_courses = [
            course
            for _db_id, status, course in _fetch_courses(cursor)
            if status == "published" and _course_public_id(course)
        ]
        employee_ids = [employee["id"] for employee in TARGET_EMPLOYEES]

        for course in published_courses:
            course_id = _course_public_id(course)
            cursor.execute(
                """
                INSERT OR REPLACE INTO course_assignment_rules (
                    course_id, include_all, include_match_mode, include_groups_json,
                    include_employee_ids_json, include_departments_json, include_roles_json,
                    joined_less_than_days_ago, exclude_groups_json, exclude_employee_ids_json,
                    exclude_departments_json, exclude_roles_json, deadline_days,
                    applied_deadline_days, published_at, updated_at
                ) VALUES (?, 0, 'any', '[]', ?, '[]', '[]', NULL, '[]', '[]', '[]', '[]', ?, ?, ?, ?)
                """,
                (
                    course_id,
                    json.dumps(employee_ids),
                    deadline_days,
                    deadline_days,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            for employee_id in employee_ids:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO employee_course_progress (
                        employee_id, course_id, status, assigned_at, deadline,
                        started_at, completed_at, modules_json, attempts_json, last_activity_at
                    ) VALUES (?, ?, 'pending', ?, ?, NULL, NULL, '{}', '{}', ?)
                    """,
                    (employee_id, course_id, now.isoformat(), deadline.isoformat(), now.isoformat()),
                )

        conn.commit()

    removed_assets = []
    if delete_removed_intro_assets:
        removed_assets = _safe_remove_assets(backend_dir, old_intro_asset_paths)

    return {
        "backup_path": str(backup_path),
        "removed_intro_course_ids": removed_intro_ids,
        "imported_course_rows": len(bundled_courses),
        "final_published_course_count": len(published_courses),
        "employees": [employee["name"] for employee in TARGET_EMPLOYEES],
        "assignment_rows": len(published_courses) * len(TARGET_EMPLOYEES),
        "removed_asset_paths": removed_assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset deployed LMS demo data while keeping non-Intro deployed courses."
    )
    parser.add_argument("--db", required=True, type=Path, help="Path to the VM SQLite lms.db.")
    parser.add_argument("--bundle", required=True, type=Path, help="JSON bundle exported from local LMS courses.")
    parser.add_argument("--backend-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--delete-removed-intro-assets", action="store_true")
    parser.add_argument("--deadline-days", type=int, default=7)
    args = parser.parse_args()

    result = apply_migration(
        db_path=args.db,
        bundle_path=args.bundle,
        backend_dir=args.backend_dir,
        backup_dir=args.backup_dir,
        delete_removed_intro_assets=args.delete_removed_intro_assets,
        deadline_days=args.deadline_days,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
