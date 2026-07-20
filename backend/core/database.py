import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from core.config import DB_PATH

def get_connection():
    # check_same_thread=False allows FastAPI async defs to use the connection if needed,
    # though it's better to open/close short-lived connections anyway.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _seed_dummy_employees(cursor):
    departments = ["Sales", "Operations", "Compliance", "Risk", "Finance", "HR", "IT", "Research"]
    roles_by_level = [
        ("Associate", "Associate"),
        ("Senior Associate", "Senior Associate"),
        ("Manager", "Manager"),
        ("Director", "Director"),
        ("VP", "Leadership"),
    ]
    locations = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune"]
    today = date.today()
    employees = []

    for idx in range(1, 121):
        department = departments[(idx - 1) % len(departments)]
        role, level = roles_by_level[(idx - 1) % len(roles_by_level)]
        join_offset_days = (idx * 17) % 1095
        if idx % 19 == 0:
            join_offset_days = idx % 30
        join_date = today - timedelta(days=join_offset_days)
        employee_code = f"EMP{idx:04d}"
        first_name = [
            "Aarav", "Ananya", "Rohit", "Sneha", "Vikram", "Neha",
            "Ishaan", "Priya", "Kabir", "Meera", "Arjun", "Riya",
        ][(idx - 1) % 12]
        last_name = [
            "Mehta", "Khanna", "Iyer", "Shah", "Kapoor", "Rao",
            "Nair", "Patel", "Menon", "Gupta",
        ][(idx - 1) % 10]
        name = f"{first_name} {last_name}"
        employees.append({
            "id": f"emp_{idx:04d}",
            "employee_code": employee_code,
            "name": name,
            "email": f"{employee_code.lower()}@phillipcapital.example",
            "department": department,
            "role": role,
            "level": level,
            "manager_id": None if level in ["Leadership", "Director"] else f"emp_{(((idx - 1) // 10) * 10) + 3:04d}",
            "join_date": join_date.isoformat(),
            "location": locations[(idx - 1) % len(locations)],
            "status": "inactive" if idx % 37 == 0 else "active",
        })

    now = datetime.now().isoformat()
    for employee in employees:
        cursor.execute(
            """
            INSERT OR IGNORE INTO employees (
                id, employee_code, name, email, department, role, level,
                manager_id, join_date, location, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                employee["join_date"],
                employee["location"],
                employee["status"],
                now,
                now,
            ),
        )

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                data TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employee_progress (
                course_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        ''')
        cursor.execute('''
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
        ''')
        cursor.execute('''
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
        ''')
        cursor.execute('''
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
        ''')
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
        cursor.execute("SELECT COUNT(*) AS count FROM employees")
        if cursor.fetchone()["count"] == 0:
            _seed_dummy_employees(cursor)
        conn.commit()

# Initialize immediately on import
init_db()


# ==========================================
# Course Operations
# ==========================================

def get_all_courses(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT data FROM courses WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT data FROM courses")
        rows = cursor.fetchall()
        return [json.loads(row['data']) for row in rows]

def get_course(course_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM courses WHERE id = ?", (course_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None

def save_course(course: Dict[str, Any], status: str):
    """Save or update a course"""
    if "id" not in course:
        course["id"] = str(uuid.uuid4())
    course_id = course["id"]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO courses (id, status, data) VALUES (?, ?, ?)",
            (course_id, status, json.dumps(course, ensure_ascii=False))
        )
        conn.commit()

def save_all_courses(courses: List[Dict[str, Any]], status: str):
    """Save an entire list of courses"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Delete existing courses of this status to mimic replacing the entire file
        cursor.execute("DELETE FROM courses WHERE status = ?", (status,))
        for course in courses:
            if "id" not in course:
                course["id"] = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO courses (id, status, data) VALUES (?, ?, ?)",
                (course["id"], status, json.dumps(course, ensure_ascii=False))
            )
        conn.commit()

def update_course_status(course_id: str, new_status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE courses SET status = ? WHERE id = ?", (new_status, course_id))
        conn.commit()

def delete_course(course_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        cursor.execute("DELETE FROM employee_progress WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM employee_course_progress WHERE course_id = ?", (course_id,))
        conn.commit()


# ==========================================
# Employee Operations
# ==========================================

def _row_to_employee(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "employee_code": row["employee_code"],
        "name": row["name"],
        "email": row["email"],
        "department": row["department"],
        "role": row["role"],
        "level": row["level"],
        "manager_id": row["manager_id"],
        "join_date": row["join_date"],
        "location": row["location"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

def list_employees(include_inactive: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if include_inactive:
            cursor.execute("SELECT * FROM employees ORDER BY department, name")
        else:
            cursor.execute("SELECT * FROM employees WHERE status = 'active' ORDER BY department, name")
        return [_row_to_employee(row) for row in cursor.fetchall()]

def get_employee_assignment_options() -> Dict[str, Any]:
    employees = list_employees()
    departments = sorted({employee["department"] for employee in employees if employee.get("department")})
    roles = sorted({employee["role"] for employee in employees if employee.get("role")})
    return {
        "employees": employees,
        "departments": departments,
        "roles": roles,
    }

def get_employee(employee_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        row = cursor.fetchone()
        return _row_to_employee(row) if row else None

def get_employee_by_code(employee_code: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))
        row = cursor.fetchone()
        return _row_to_employee(row) if row else None


# ==========================================
# Employee Progress Operations
# ==========================================

def get_all_progress() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT course_id, data FROM employee_progress")
        rows = cursor.fetchall()
        return {row['course_id']: json.loads(row['data']) for row in rows}

def get_progress(course_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM employee_progress WHERE course_id = ?", (course_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None

def save_progress(course_id: str, progress_data: Dict[str, Any]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO employee_progress (course_id, data) VALUES (?, ?)",
            (course_id, json.dumps(progress_data, ensure_ascii=False))
        )
        conn.commit()

def get_employee_course_progress(employee_id: str, course_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM employee_course_progress
            WHERE employee_id = ? AND course_id = ?
            """,
            (employee_id, course_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "status": row["status"],
            "assigned_at": row["assigned_at"],
            "deadline": row["deadline"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "modules": json.loads(row["modules_json"] or "{}"),
            "attempts": json.loads(row["attempts_json"] or "{}"),
            "last_activity_at": row["last_activity_at"],
        }

def get_employee_progress(employee_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM employee_course_progress WHERE employee_id = ?",
            (employee_id,),
        )
        rows = cursor.fetchall()
        return {
            row["course_id"]: {
                "status": row["status"],
                "assigned_at": row["assigned_at"],
                "deadline": row["deadline"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "modules": json.loads(row["modules_json"] or "{}"),
                "attempts": json.loads(row["attempts_json"] or "{}"),
                "last_activity_at": row["last_activity_at"],
            }
            for row in rows
        }

def get_course_employee_progress(course_id: str) -> Dict[str, Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM employee_course_progress WHERE course_id = ?",
            (course_id,),
        )
        rows = cursor.fetchall()
        return {
            row["employee_id"]: {
                "status": row["status"],
                "assigned_at": row["assigned_at"],
                "deadline": row["deadline"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "modules": json.loads(row["modules_json"] or "{}"),
                "attempts": json.loads(row["attempts_json"] or "{}"),
                "last_activity_at": row["last_activity_at"],
            }
            for row in rows
        }

def list_employee_course_progress() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employee_course_progress")
        rows = cursor.fetchall()
        return [
            {
                "employee_id": row["employee_id"],
                "course_id": row["course_id"],
                "status": row["status"],
                "assigned_at": row["assigned_at"],
                "deadline": row["deadline"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "modules": json.loads(row["modules_json"] or "{}"),
                "attempts": json.loads(row["attempts_json"] or "{}"),
                "last_activity_at": row["last_activity_at"],
            }
            for row in rows
        ]

def save_employee_course_progress(employee_id: str, course_id: str, progress_data: Dict[str, Any]):
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO employee_course_progress (
                employee_id, course_id, status, assigned_at, deadline, started_at, completed_at,
                modules_json, attempts_json, last_activity_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee_id,
                course_id,
                progress_data.get("status", "pending"),
                progress_data.get("assigned_at", now),
                progress_data.get("deadline", now),
                progress_data.get("started_at"),
                progress_data.get("completed_at"),
                json.dumps(progress_data.get("modules", {}), ensure_ascii=False),
                json.dumps(progress_data.get("attempts", {}), ensure_ascii=False),
                progress_data.get("last_activity_at", now),
            ),
        )
        conn.commit()

def delete_employee_course_progress(employee_id: str, course_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM employee_course_progress WHERE employee_id = ? AND course_id = ?",
            (employee_id, course_id),
        )
        conn.commit()


# ==========================================
# Course Assignment Rule Operations
# ==========================================

def default_assignment_rule(course_id: str) -> Dict[str, Any]:
    return {
        "course_id": course_id,
        "include_all": True,
        "include_match_mode": "all",
        "include_groups": [],
        "include_employee_ids": [],
        "include_departments": [],
        "include_roles": [],
        "joined_less_than_days_ago": None,
        "exclude_groups": [],
        "exclude_employee_ids": [],
        "exclude_departments": [],
        "exclude_roles": [],
        "deadline_days": 7,
        "applied_deadline_days": None,
        "published_at": None,
        "updated_at": None,
    }

def _row_to_assignment_rule(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "course_id": row["course_id"],
        "include_all": bool(row["include_all"]),
        "include_match_mode": row["include_match_mode"] or "all",
        "include_groups": json.loads(row["include_groups_json"] or "[]"),
        "include_employee_ids": json.loads(row["include_employee_ids_json"] or "[]"),
        "include_departments": json.loads(row["include_departments_json"] or "[]"),
        "include_roles": json.loads(row["include_roles_json"] or "[]"),
        "joined_less_than_days_ago": row["joined_less_than_days_ago"],
        "exclude_groups": json.loads(row["exclude_groups_json"] or "[]"),
        "exclude_employee_ids": json.loads(row["exclude_employee_ids_json"] or "[]"),
        "exclude_departments": json.loads(row["exclude_departments_json"] or "[]"),
        "exclude_roles": json.loads(row["exclude_roles_json"] or "[]"),
        "deadline_days": row["deadline_days"],
        "applied_deadline_days": row["applied_deadline_days"],
        "published_at": row["published_at"],
        "updated_at": row["updated_at"],
    }

def get_assignment_rule(course_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM course_assignment_rules WHERE course_id = ?",
            (course_id,),
        )
        row = cursor.fetchone()
        return _row_to_assignment_rule(row) if row else default_assignment_rule(course_id)

def save_assignment_rule(course_id: str, rule: Dict[str, Any], publish: bool = False) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    existing = get_assignment_rule(course_id)
    normalized = default_assignment_rule(course_id)
    normalized.update(existing)
    normalized.update({
        "include_all": bool(rule.get("include_all", normalized["include_all"])),
        "include_match_mode": rule.get("include_match_mode", normalized["include_match_mode"]),
        "include_groups": list(rule.get("include_groups") or []),
        "include_employee_ids": list(rule.get("include_employee_ids") or []),
        "include_departments": list(rule.get("include_departments") or []),
        "include_roles": list(rule.get("include_roles") or []),
        "joined_less_than_days_ago": rule.get("joined_less_than_days_ago"),
        "exclude_groups": list(rule.get("exclude_groups") or []),
        "exclude_employee_ids": list(rule.get("exclude_employee_ids") or []),
        "exclude_departments": list(rule.get("exclude_departments") or []),
        "exclude_roles": list(rule.get("exclude_roles") or []),
        "deadline_days": int(rule.get("deadline_days") or normalized["deadline_days"]),
        "applied_deadline_days": existing.get("applied_deadline_days"),
        "published_at": rule.get("published_at", existing.get("published_at")),
        "updated_at": now,
    })
    if normalized["deadline_days"] < 1:
        normalized["deadline_days"] = 1
    if normalized["include_match_mode"] not in ["all", "any"]:
        normalized["include_match_mode"] = "all"
    if publish and not normalized.get("published_at"):
        normalized["published_at"] = now
    if publish:
        normalized["applied_deadline_days"] = normalized["deadline_days"]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO course_assignment_rules (
                course_id, include_all, include_match_mode, include_groups_json, include_employee_ids_json,
                include_departments_json, include_roles_json,
                joined_less_than_days_ago, exclude_groups_json, exclude_employee_ids_json,
                exclude_departments_json, exclude_roles_json, deadline_days,
                applied_deadline_days, published_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                1 if normalized["include_all"] else 0,
                normalized["include_match_mode"],
                json.dumps(normalized["include_groups"], ensure_ascii=False),
                json.dumps(normalized["include_employee_ids"], ensure_ascii=False),
                json.dumps(normalized["include_departments"], ensure_ascii=False),
                json.dumps(normalized["include_roles"], ensure_ascii=False),
                normalized["joined_less_than_days_ago"],
                json.dumps(normalized["exclude_groups"], ensure_ascii=False),
                json.dumps(normalized["exclude_employee_ids"], ensure_ascii=False),
                json.dumps(normalized["exclude_departments"], ensure_ascii=False),
                json.dumps(normalized["exclude_roles"], ensure_ascii=False),
                normalized["deadline_days"],
                normalized["applied_deadline_days"],
                normalized["published_at"],
                normalized["updated_at"],
            ),
        )
        conn.commit()
    return normalized

def _normalize_assignment_groups(rule: Dict[str, Any], prefix: str) -> List[Dict[str, Any]]:
    groups = list(rule.get(f"{prefix}_groups") or [])
    if groups:
        return groups
    if prefix == "exclude":
        flat_groups = []
        for employee_id in rule.get("exclude_employee_ids") or []:
            flat_groups.append({"employee_ids": [employee_id]})
        for department in rule.get("exclude_departments") or []:
            flat_groups.append({"departments": [department]})
        for role in rule.get("exclude_roles") or []:
            flat_groups.append({"roles": [role]})
        return flat_groups
    group = {
        "employee_ids": list(rule.get(f"{prefix}_employee_ids") or []),
        "departments": list(rule.get(f"{prefix}_departments") or []),
        "roles": list(rule.get(f"{prefix}_roles") or []),
        "joined_less_than_days_ago": rule.get("joined_less_than_days_ago") if prefix == "include" else None,
    }
    return [group] if any(group.values()) else []

def _employee_matches_group(employee: Dict[str, Any], group: Dict[str, Any], as_of: Optional[datetime] = None) -> bool:
    employee_ids = set(group.get("employee_ids") or [])
    departments = set(group.get("departments") or [])
    roles = set(group.get("roles") or [])
    joined_less_than_days_ago = group.get("joined_less_than_days_ago")

    if employee_ids and employee.get("id") not in employee_ids:
        return False
    if departments and employee.get("department") not in departments:
        return False
    if roles and employee.get("role") not in roles:
        return False
    if joined_less_than_days_ago is not None:
        try:
            join_date = date.fromisoformat(employee.get("join_date"))
        except (TypeError, ValueError):
            return False
        today = (as_of or datetime.now()).date()
        if (today - join_date).days >= int(joined_less_than_days_ago):
            return False
    return True

def employee_matches_assignment_rule(employee: Dict[str, Any], rule: Dict[str, Any], as_of: Optional[datetime] = None) -> bool:
    if employee.get("status") != "active":
        return False

    exclude_groups = _normalize_assignment_groups(rule, "exclude")
    if any(_employee_matches_group(employee, group, as_of) for group in exclude_groups):
        return False

    include_all = bool(rule.get("include_all", True))
    include_groups = _normalize_assignment_groups(rule, "include")
    if not include_all and not include_groups:
        return False

    return True if include_all else any(
        _employee_matches_group(employee, group, as_of) for group in include_groups
    )

def matching_employees_for_assignment_rule(rule: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    matches = [
        employee
        for employee in list_employees()
        if employee_matches_assignment_rule(employee, rule)
    ]
    return matches[:limit] if limit is not None else matches
