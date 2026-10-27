"""Learning Journey persistence: journeys, their ordered steps, rules and per-employee state."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from psycopg.types.json import Jsonb

from app.repositories.database import get_connection


def _jsonb(value) -> Jsonb:
    return Jsonb(value, dumps=lambda item: json.dumps(item, ensure_ascii=False))


def create_journey_tables(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journeys (
            journey_id TEXT PRIMARY KEY,
            trainer_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            target_audience TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            prerequisite_journey_id TEXT,
            certificate_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            published_at TEXT,
            disabled_at TEXT,
            created_at TEXT NOT NULL DEFAULT (now()::text),
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            CHECK (status IN ('draft', 'published', 'disabled')),
            CHECK (prerequisite_journey_id IS NULL OR prerequisite_journey_id <> journey_id),
            FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT,
            FOREIGN KEY (prerequisite_journey_id) REFERENCES learning_journeys(journey_id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_stages (
            stage_id TEXT PRIMARY KEY,
            journey_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            title TEXT NOT NULL,
            UNIQUE (journey_id, position),
            FOREIGN KEY (journey_id) REFERENCES learning_journeys(journey_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_steps (
            step_id TEXT PRIMARY KEY,
            journey_id TEXT NOT NULL,
            stage_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            unlock_rule TEXT NOT NULL DEFAULT 'after_previous',
            is_required BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (journey_id, course_id),
            UNIQUE (journey_id, position),
            CHECK (unlock_rule IN ('open', 'after_previous')),
            FOREIGN KEY (journey_id) REFERENCES learning_journeys(journey_id) ON DELETE CASCADE,
            FOREIGN KEY (stage_id) REFERENCES learning_journey_stages(stage_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE RESTRICT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_rules (
            journey_id TEXT PRIMARY KEY,
            rule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            applied_rule_json JSONB,
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            FOREIGN KEY (journey_id) REFERENCES learning_journeys(journey_id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_assignments (
            journey_assignment_id TEXT PRIMARY KEY,
            journey_id TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            assigned_at TEXT NOT NULL,
            available_at TEXT,
            deadline TEXT,
            started_at TEXT,
            completed_at TEXT,
            revoked_at TEXT,
            revoked_reason TEXT,
            -- Courses this journey has unlocked for the employee. They stay unlocked.
            unlocked_course_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            UNIQUE (journey_id, employee_id),
            CHECK (status IN ('waiting', 'pending', 'started', 'completed', 'overdue')),
            FOREIGN KEY (journey_id) REFERENCES learning_journeys(journey_id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE RESTRICT
        )
        """
    )
    # Journey Observers see every course of the journey for the people they watch.
    # department_id refers to lms_departments, which the access migrations create after this
    # runs, so it is validated on save instead of by a foreign key.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_observers (
            journey_id TEXT NOT NULL,
            observer_employee_id TEXT NOT NULL,
            identity_key TEXT NOT NULL,
            granted_by_trainer_id TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (now()::text),
            PRIMARY KEY (journey_id, observer_employee_id),
            FOREIGN KEY (journey_id) REFERENCES learning_journeys(journey_id) ON DELETE CASCADE,
            FOREIGN KEY (observer_employee_id) REFERENCES employees(employee_id) ON DELETE RESTRICT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_observer_employees (
            journey_id TEXT NOT NULL,
            observer_employee_id TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            identity_key TEXT NOT NULL,
            PRIMARY KEY (journey_id, observer_employee_id, employee_id),
            FOREIGN KEY (journey_id, observer_employee_id)
                REFERENCES learning_journey_observers ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE RESTRICT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_journey_observer_departments (
            journey_id TEXT NOT NULL,
            observer_employee_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            PRIMARY KEY (journey_id, observer_employee_id, department_id),
            FOREIGN KEY (journey_id, observer_employee_id)
                REFERENCES learning_journey_observers ON DELETE CASCADE
        )
        """
    )
    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_learning_journey_observers_employee "
        "ON learning_journey_observers(observer_employee_id)",
        "CREATE INDEX IF NOT EXISTS idx_learning_journeys_trainer ON learning_journeys(trainer_id)",
        "CREATE INDEX IF NOT EXISTS idx_learning_journeys_status ON learning_journeys(status)",
        "CREATE INDEX IF NOT EXISTS idx_learning_journey_steps_course ON learning_journey_steps(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_learning_journey_assignments_employee "
        "ON learning_journey_assignments(employee_id)",
    ):
        cursor.execute(statement)


def _journeys_with_parts(connection, rows) -> list[dict]:
    journeys = [dict(row) for row in rows]
    if not journeys:
        return []
    ids = [journey["journey_id"] for journey in journeys]
    stages = connection.execute(
        "SELECT * FROM learning_journey_stages WHERE journey_id = ANY(?) ORDER BY position",
        (ids,),
    ).fetchall()
    steps = connection.execute(
        """
        SELECT s.*, c.course_name, c.status AS course_status, c.trainer_id AS course_trainer_id,
               (SELECT COUNT(*) FROM course_modules m WHERE m.course_id = s.course_id) AS module_count
        FROM learning_journey_steps s
        JOIN courses c ON c.course_id = s.course_id
        WHERE s.journey_id = ANY(?)
        ORDER BY s.position
        """,
        (ids,),
    ).fetchall()
    rules = connection.execute(
        "SELECT * FROM learning_journey_rules WHERE journey_id = ANY(?)", (ids,)
    ).fetchall()
    rules_by_id = {row["journey_id"]: row for row in rules}
    for journey in journeys:
        journey_id = journey["journey_id"]
        journey["stages"] = [
            {"stage_id": row["stage_id"], "position": row["position"], "title": row["title"]}
            for row in stages
            if row["journey_id"] == journey_id
        ]
        journey["steps"] = [
            {
                "step_id": row["step_id"],
                "stage_id": row["stage_id"],
                "course_id": row["course_id"],
                "course_name": row["course_name"],
                "course_status": row["course_status"],
                "course_trainer_id": row["course_trainer_id"],
                "module_count": int(row["module_count"] or 0),
                "position": row["position"],
                "unlock_rule": row["unlock_rule"],
                "is_required": bool(row["is_required"]),
            }
            for row in steps
            if row["journey_id"] == journey_id
        ]
        rule_row = rules_by_id.get(journey_id)
        journey["rule"] = dict(rule_row["rule_json"]) if rule_row else {}
        journey["applied_rule"] = (
            dict(rule_row["applied_rule_json"])
            if rule_row and rule_row["applied_rule_json"] is not None
            else None
        )
        journey["rule_updated_at"] = rule_row["updated_at"] if rule_row else None
    return journeys


def list_journeys(trainer_id: str | None = None, status: str | None = None) -> list[dict]:
    clauses, params = [], []
    if trainer_id is not None:
        clauses.append("trainer_id = ?")
        params.append(trainer_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT * FROM learning_journeys {where} ORDER BY lower(title), journey_id",
            tuple(params),
        ).fetchall()
        return _journeys_with_parts(connection, rows)


def get_journey(journey_id: str) -> dict | None:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM learning_journeys WHERE journey_id = ?", (journey_id,)
        ).fetchall()
        journeys = _journeys_with_parts(connection, rows)
    return journeys[0] if journeys else None


def create_journey(trainer_id: str, title: str) -> str:
    journey_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO learning_journeys (journey_id, trainer_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (journey_id, trainer_id, title, now, now),
        )
        connection.execute(
            "INSERT INTO learning_journey_stages (stage_id, journey_id, position, title) VALUES (?, ?, 0, ?)",
            (str(uuid.uuid4()), journey_id, "Section 1"),
        )
        connection.execute(
            "INSERT INTO learning_journey_rules (journey_id, rule_json, updated_at) VALUES (?, ?, ?)",
            (journey_id, _jsonb({}), now),
        )
        connection.commit()
    return journey_id


def save_journey(journey_id: str, details: dict, stages: list[dict], rule: dict) -> None:
    """Replace details, stages, steps and the editable rule in one transaction.

    `stages` is `[{"title": str, "steps": [{"course_id", "unlock_rule", "is_required"}]}]`.
    Step positions run across the whole journey in the given order.
    """
    now = datetime.now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE learning_journeys
            SET title = ?, description = ?, target_audience = ?, prerequisite_journey_id = ?,
                certificate_enabled = ?, updated_at = ?
            WHERE journey_id = ?
            """,
            (
                details["title"],
                details["description"],
                details["target_audience"],
                details["prerequisite_journey_id"],
                bool(details["certificate_enabled"]),
                now,
                journey_id,
            ),
        )
        connection.execute("DELETE FROM learning_journey_stages WHERE journey_id = ?", (journey_id,))
        position = 0
        for stage_position, stage in enumerate(stages):
            stage_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO learning_journey_stages (stage_id, journey_id, position, title) VALUES (?, ?, ?, ?)",
                (stage_id, journey_id, stage_position, stage["title"]),
            )
            for step in stage["steps"]:
                connection.execute(
                    """
                    INSERT INTO learning_journey_steps (
                        step_id, journey_id, stage_id, course_id, position, unlock_rule, is_required
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        journey_id,
                        stage_id,
                        step["course_id"],
                        position,
                        step["unlock_rule"],
                        bool(step["is_required"]),
                    ),
                )
                position += 1
        connection.execute(
            """
            INSERT INTO learning_journey_rules (journey_id, rule_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT (journey_id) DO UPDATE SET rule_json = excluded.rule_json,
                updated_at = excluded.updated_at
            """,
            (journey_id, _jsonb(rule), now),
        )
        connection.commit()


def set_journey_published(journey_id: str, applied_rule: dict) -> None:
    now = datetime.now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE learning_journeys
            SET status = 'published', published_at = ?, disabled_at = NULL, updated_at = ?
            WHERE journey_id = ?
            """,
            (now, now, journey_id),
        )
        connection.execute(
            "UPDATE learning_journey_rules SET applied_rule_json = ? WHERE journey_id = ?",
            (_jsonb(applied_rule), journey_id),
        )
        connection.commit()


def apply_journey_rule(journey_id: str, rule: dict) -> None:
    """Make the saved rule the live one on an already published journey."""
    with get_connection() as connection:
        connection.execute(
            "UPDATE learning_journey_rules SET applied_rule_json = ? WHERE journey_id = ?",
            (_jsonb(rule), journey_id),
        )
        connection.commit()


def journeys_by_course(trainer_id: str) -> dict[str, list[dict]]:
    """For each of this trainer's courses, the journeys it appears in."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT s.course_id, j.journey_id, j.title, j.status
            FROM learning_journey_steps s JOIN learning_journeys j ON j.journey_id = s.journey_id
            WHERE j.trainer_id = ?
            ORDER BY lower(j.title)
            """,
            (trainer_id,),
        ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["course_id"], []).append(
            {"journey_id": row["journey_id"], "title": row["title"], "status": row["status"]}
        )
    return result


def step_learner_counts(journey_id: str, course_ids: list[str]) -> dict[str, dict]:
    """Per course: how many of the journey's current learners hold it, and how many started it."""
    if not course_ids:
        return {}
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT ca.course_id,
                   COUNT(*) AS active,
                   COUNT(*) FILTER (
                       WHERE ca.started_at IS NOT NULL OR ca.completed_at IS NOT NULL
                          OR ca.status IN ('started', 'completed')
                   ) AS started
            FROM course_assignments ca
            JOIN learning_journey_assignments ja
              ON ja.employee_id = ca.employee_id AND ja.journey_id = ? AND ja.revoked_at IS NULL
            WHERE ca.course_id = ANY(?) AND ca.revoked_at IS NULL AND ca.status <> 'revoked'
            GROUP BY ca.course_id
            """,
            (journey_id, list(course_ids)),
        ).fetchall()
    return {row["course_id"]: {"active": int(row["active"]), "started": int(row["started"])} for row in rows}


def completed_assignments() -> list[dict]:
    """Every completed journey assignment, for certificate verification."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM learning_journey_assignments WHERE completed_at IS NOT NULL"
        ).fetchall()
    return [dict(row) for row in rows]


def set_journey_disabled(journey_id: str) -> None:
    now = datetime.now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE learning_journeys SET status = 'disabled', disabled_at = ?, updated_at = ?
            WHERE journey_id = ?
            """,
            (now, now, journey_id),
        )
        connection.commit()


def delete_journey(journey_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM learning_journeys WHERE journey_id = ?", (journey_id,))
        connection.commit()


def journeys_containing_course(course_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT j.journey_id, j.title, j.status
            FROM learning_journey_steps s JOIN learning_journeys j ON j.journey_id = s.journey_id
            WHERE s.course_id = ?
            ORDER BY lower(j.title)
            """,
            (course_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def journeys_requiring(journey_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT journey_id, title FROM learning_journeys WHERE prerequisite_journey_id = ?",
            (journey_id,),
        ).fetchall()
    return [dict(row) for row in rows]


_ASSIGNMENT_FIELDS = (
    "status",
    "assigned_at",
    "available_at",
    "deadline",
    "started_at",
    "completed_at",
    "revoked_at",
    "revoked_reason",
    "unlocked_course_ids",
)


def assignments_for_employee(employee_id: str) -> dict[str, dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM learning_journey_assignments WHERE employee_id = ?", (employee_id,)
        ).fetchall()
    return {row["journey_id"]: dict(row) for row in rows}


def assignments_for_journey(journey_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM learning_journey_assignments WHERE journey_id = ? ORDER BY assigned_at",
            (journey_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def assignments_for_employees(employee_ids: list[str]) -> dict[str, dict[str, dict]]:
    """Every journey assignment of these employees, by employee and then journey."""
    result: dict[str, dict[str, dict]] = {}
    if not employee_ids:
        return result
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM learning_journey_assignments WHERE employee_id = ANY(?)",
            (list(employee_ids),),
        ).fetchall()
    for row in rows:
        result.setdefault(row["employee_id"], {})[row["journey_id"]] = dict(row)
    return result


def course_states_for_employees(
    employee_ids: list[str], course_ids: list[str]
) -> dict[str, dict[str, dict]]:
    """The course assignment fields journey rules read, by employee and then course."""
    result: dict[str, dict[str, dict]] = {}
    if not employee_ids or not course_ids:
        return result
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT employee_id, course_id, status, started_at, completed_at, revoked_at,
                   last_learner_activity_at
            FROM course_assignments
            WHERE employee_id = ANY(?) AND course_id = ANY(?)
            """,
            (list(employee_ids), list(course_ids)),
        ).fetchall()
    for row in rows:
        result.setdefault(row["employee_id"], {})[row["course_id"]] = dict(row)
    return result


def has_assignment_history(journey_id: str) -> bool:
    with get_connection() as connection:
        return (
            connection.execute(
                "SELECT 1 FROM learning_journey_assignments WHERE journey_id = ? LIMIT 1",
                (journey_id,),
            ).fetchone()
            is not None
        )


def save_assignment(assignment: dict) -> dict:
    """Insert or update one employee's journey state. Returns the stored row."""
    now = datetime.now().isoformat()
    values = {field: assignment.get(field) for field in _ASSIGNMENT_FIELDS}
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO learning_journey_assignments (
                journey_assignment_id, journey_id, employee_id, status, assigned_at, available_at,
                deadline, started_at, completed_at, revoked_at, revoked_reason,
                unlocked_course_ids, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (journey_id, employee_id) DO UPDATE SET
                status = excluded.status,
                assigned_at = excluded.assigned_at,
                available_at = excluded.available_at,
                deadline = excluded.deadline,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                revoked_at = excluded.revoked_at,
                revoked_reason = excluded.revoked_reason,
                unlocked_course_ids = excluded.unlocked_course_ids,
                updated_at = excluded.updated_at
            RETURNING *
            """,
            (
                assignment.get("journey_assignment_id") or str(uuid.uuid4()),
                assignment["journey_id"],
                assignment["employee_id"],
                values["status"] or "waiting",
                values["assigned_at"] or now,
                values["available_at"],
                values["deadline"],
                values["started_at"],
                values["completed_at"],
                values["revoked_at"],
                values["revoked_reason"],
                _jsonb(sorted(set(values["unlocked_course_ids"] or []))),
                now,
            ),
        ).fetchone()
        connection.commit()
    return dict(row)


def assignment_changed(before: dict | None, after: dict) -> bool:
    if before is None:
        return True

    def value(row: dict, field: str):
        item = row.get(field)
        return sorted(set(item or [])) if field == "unlocked_course_ids" else item

    return any(value(before, field) != value(after, field) for field in _ASSIGNMENT_FIELDS)


def journey_observers(journey_id: str) -> list[dict]:
    with get_connection() as connection:
        observers = connection.execute(
            """
            SELECT o.observer_employee_id, e.name, e.department
            FROM learning_journey_observers o JOIN employees e ON e.employee_id = o.observer_employee_id
            WHERE o.journey_id = ? ORDER BY lower(e.name), o.observer_employee_id
            """,
            (journey_id,),
        ).fetchall()
        employees = connection.execute(
            "SELECT observer_employee_id, employee_id FROM learning_journey_observer_employees WHERE journey_id = ? ORDER BY employee_id",
            (journey_id,),
        ).fetchall()
        departments = connection.execute(
            "SELECT observer_employee_id, department_id FROM learning_journey_observer_departments WHERE journey_id = ? ORDER BY department_id",
            (journey_id,),
        ).fetchall()
    return [
        {
            "observer_employee_id": row["observer_employee_id"],
            "name": row["name"],
            "department": row["department"] or "",
            "employee_ids": [
                r["employee_id"] for r in employees if r["observer_employee_id"] == row["observer_employee_id"]
            ],
            "department_ids": [
                r["department_id"] for r in departments if r["observer_employee_id"] == row["observer_employee_id"]
            ],
        }
        for row in observers
    ]


def journey_observer_ids(journey_id: str) -> set[str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT observer_employee_id FROM learning_journey_observers WHERE journey_id = ?",
            (journey_id,),
        ).fetchall()
    return {row["observer_employee_id"] for row in rows}


def observed_journey_ids(employee_id: str) -> set[str]:
    """Journeys this employee observes. An Observer is never enrolled in that journey."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT journey_id FROM learning_journey_observers WHERE observer_employee_id = ?",
            (employee_id,),
        ).fetchall()
    return {row["journey_id"] for row in rows}


def bump_access_versions(connection, employee_ids) -> None:
    """Report access changed for these people, so their apps refresh their Performance views."""
    for employee_id in sorted(set(employee_ids)):
        connection.execute(
            """INSERT INTO lms_access_versions(employee_id, permissions_version) VALUES (?, 1)
            ON CONFLICT(employee_id) DO UPDATE SET
                permissions_version = lms_access_versions.permissions_version + 1""",
            (employee_id,),
        )


def replace_journey_observers(journey_id: str, trainer_id: str, observers: list[dict]) -> None:
    """Replace a journey's Observers in one transaction, with an audit record.

    Each item: observer_employee_id, identity_key, employees [(employee_id, identity_key)],
    department_ids.
    """
    before = journey_observers(journey_id)
    with get_connection() as connection:
        connection.execute("DELETE FROM learning_journey_observers WHERE journey_id = ?", (journey_id,))
        for observer in observers:
            connection.execute(
                """INSERT INTO learning_journey_observers
                (journey_id, observer_employee_id, identity_key, granted_by_trainer_id) VALUES (?, ?, ?, ?)""",
                (journey_id, observer["observer_employee_id"], observer["identity_key"], trainer_id),
            )
            for employee_id, key in observer["employees"]:
                connection.execute(
                    "INSERT INTO learning_journey_observer_employees VALUES (?, ?, ?, ?)",
                    (journey_id, observer["observer_employee_id"], employee_id, key),
                )
            for department_id in observer["department_ids"]:
                connection.execute(
                    "INSERT INTO learning_journey_observer_departments VALUES (?, ?, ?)",
                    (journey_id, observer["observer_employee_id"], department_id),
                )
        after = [
            {
                "observer_employee_id": o["observer_employee_id"],
                "employee_ids": sorted(e for e, _ in o["employees"]),
                "department_ids": sorted(o["department_ids"]),
            }
            for o in observers
        ]
        connection.execute(
            """INSERT INTO lms_report_access_audit(audit_id, course_id, actor, action, revision, before_json, after_json)
            VALUES (?, NULL, ?, 'journey_observers_save', NULL, ?, ?)""",
            (
                str(uuid.uuid4()),
                trainer_id,
                _jsonb({"journey_id": journey_id, "observers": before}),
                _jsonb({"journey_id": journey_id, "observers": after}),
            ),
        )
        bump_access_versions(
            connection,
            {o["observer_employee_id"] for o in before} | {o["observer_employee_id"] for o in observers},
        )
        connection.commit()


def bump_journey_observer_access(journey_id: str) -> None:
    """A journey was published or disabled, so its Observers' report access changed."""
    observer_ids = journey_observer_ids(journey_id)
    if not observer_ids:
        return
    with get_connection() as connection:
        bump_access_versions(connection, observer_ids)
        connection.commit()


class JourneyRepository:
    list = staticmethod(list_journeys)
    get = staticmethod(get_journey)
    create = staticmethod(create_journey)
    save = staticmethod(save_journey)
    publish = staticmethod(set_journey_published)
    apply_rule = staticmethod(apply_journey_rule)
    journeys_by_course = staticmethod(journeys_by_course)
    step_learner_counts = staticmethod(step_learner_counts)
    completed_assignments = staticmethod(completed_assignments)
    disable = staticmethod(set_journey_disabled)
    delete = staticmethod(delete_journey)
    containing_course = staticmethod(journeys_containing_course)
    requiring = staticmethod(journeys_requiring)
    assignments_for_employee = staticmethod(assignments_for_employee)
    assignments_for_journey = staticmethod(assignments_for_journey)
    assignments_for_employees = staticmethod(assignments_for_employees)
    course_states_for_employees = staticmethod(course_states_for_employees)
    has_assignment_history = staticmethod(has_assignment_history)
    save_assignment = staticmethod(save_assignment)
    observers = staticmethod(journey_observers)
    observer_ids = staticmethod(journey_observer_ids)
    observed_by = staticmethod(observed_journey_ids)
    replace_observers = staticmethod(replace_journey_observers)
    bump_observer_access = staticmethod(bump_journey_observer_access)
