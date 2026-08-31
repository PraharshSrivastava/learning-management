"""Learner assignment and module-progress persistence queries."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from psycopg.types.json import Jsonb

from app.repositories.database import get_connection
from app.schemas.progress import EmployeeCourseProgressRecord


def _loads(value: str | None, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _assignment_from_row(row) -> dict:
    return {
        "assignment_id": row["assignment_id"],
        "employee_id": row["employee_id"],
        "course_id": row["course_id"],
        "status": row["status"],
        "assigned_at": row["assigned_at"],
        "deadline": row["deadline"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "modules": {},
        "attempts": {},
        "last_activity_at": row["last_activity_at"],
        "revoked_at": row["revoked_at"],
        "assigned_department": row.get("assigned_department"),
        "revoked_reason": row.get("revoked_reason"),
        "notification_lifecycle": row.get("notification_lifecycle") or 1,
    }


def _progress_from_assignment(connection, row) -> dict:
    progress = _assignment_from_row(row)
    module_rows = connection.execute(
        """
        SELECT mp.*, cm.module_number
        FROM module_progress mp
        JOIN course_modules cm ON cm.module_id = mp.module_id
        WHERE mp.assignment_id = ?
        ORDER BY cm.module_number
        """,
        (row["assignment_id"],),
    ).fetchall()
    for module_row in module_rows:
        key = str(module_row["module_number"])
        selected_answers = _loads(module_row["selected_answers_json"], None)
        module = {}
        if module_row["video_watched"]:
            module["video_watched"] = True
        if module_row["video_watched_at"]:
            module["video_watched_at"] = module_row["video_watched_at"]
        if module_row["quiz_passed"]:
            module["quiz_passed"] = True
        if module_row["quiz_score"] is not None:
            module["quiz_score"] = module_row["quiz_score"]
        if selected_answers is not None:
            module["selected_answers"] = selected_answers
        progress["modules"][key] = module
        if module_row["attempt_count"] or module_row["last_attempt_at"]:
            progress["attempts"][key] = {
                "count": module_row["attempt_count"],
                "last_attempt_at": module_row["last_attempt_at"],
                "last_score": module_row["quiz_score"],
                "last_passed": bool(module_row["quiz_passed"]) if module_row["last_attempt_at"] else None,
            }
    return progress


def get_employee_course_progress(employee_id: str, course_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT ca.*
            FROM course_assignments ca
            WHERE ca.employee_id = ?
              AND ca.course_id = ?
            """,
            (employee_id, course_id),
        ).fetchone()
        return _progress_from_assignment(connection, row) if row else None


def get_employee_progress(employee_id: str) -> dict:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT ca.*
            FROM course_assignments ca
            WHERE ca.employee_id = ?
            """,
            (employee_id,),
        ).fetchall()
        return {row["course_id"]: _progress_from_assignment(connection, row) for row in rows}


def get_course_employee_progress(course_id: str) -> dict[str, dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT ca.*
            FROM course_assignments ca
            WHERE ca.course_id = ?
            """,
            (course_id,),
        ).fetchall()
        return {row["employee_id"]: _progress_from_assignment(connection, row) for row in rows}


def list_employee_course_progress() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT ca.*
            FROM course_assignments ca
            """
        ).fetchall()
        return [
            {
                "employee_id": row["employee_id"],
                "course_id": row["course_id"],
                **_progress_from_assignment(connection, row),
            }
            for row in rows
        ]


def _module_id_by_number(connection, course_id: str) -> dict[str, str]:
    rows = connection.execute(
        """
        SELECT cm.module_id, cm.module_number
        FROM course_modules cm
        WHERE cm.course_id = ?
        """,
        (course_id,),
    ).fetchall()
    return {str(row["module_number"]): row["module_id"] for row in rows}


def _assignment_course_id(connection, course_id: str) -> str:
    row = connection.execute(
        """
        SELECT course_id
        FROM courses
        WHERE course_id = ?
        LIMIT 1
        """,
        (course_id,),
    ).fetchone()
    if row:
        return row["course_id"]
    raise ValueError(f"Course ID '{course_id}' not found in courses database.")


def save_employee_course_progress(employee_id: str, course_id: str, data: dict) -> dict:
    now = datetime.now().isoformat()
    with get_connection() as connection:
        storage_course_id = _assignment_course_id(connection, course_id)
        existing = connection.execute(
            """
            SELECT assignment_id, status, notification_lifecycle
            FROM course_assignments
            WHERE employee_id = ? AND course_id = ?
            """,
            (employee_id, storage_course_id),
        ).fetchone()
        assignment_id = existing["assignment_id"] if existing else str(uuid.uuid4())
        previous_status = existing["status"] if existing else None
        lifecycle = int(existing["notification_lifecycle"] or 1) if existing else 1
        next_status = data.get("status", "pending")
        if previous_status == "revoked" and next_status != "revoked":
            lifecycle += 1
        connection.execute(
            """
            INSERT INTO course_assignments (
                assignment_id, course_id, employee_id, status, assigned_at, deadline,
                started_at, completed_at, last_activity_at, revoked_at,
                assigned_department, revoked_reason, notification_lifecycle, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_id, employee_id) DO UPDATE SET
                status = excluded.status,
                assigned_at = excluded.assigned_at,
                deadline = excluded.deadline,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                last_activity_at = excluded.last_activity_at,
                revoked_at = excluded.revoked_at,
                assigned_department = excluded.assigned_department,
                revoked_reason = excluded.revoked_reason,
                notification_lifecycle = excluded.notification_lifecycle,
                updated_at = excluded.updated_at
            """,
            (
                assignment_id,
                storage_course_id,
                employee_id,
                data.get("status", "pending"),
                data.get("assigned_at", now),
                data.get("deadline", now),
                data.get("started_at"),
                data.get("completed_at"),
                data.get("last_activity_at", now),
                data.get("revoked_at"),
                data.get("assigned_department"),
                data.get("revoked_reason"),
                lifecycle,
                now,
            ),
        )
        module_ids = _module_id_by_number(connection, course_id)
        for module_number, module_progress in (data.get("modules") or {}).items():
            module_id = module_ids.get(str(module_number))
            if not module_id:
                continue
            attempt = (data.get("attempts") or {}).get(str(module_number), {})
            connection.execute(
                """
                INSERT INTO module_progress (
                    assignment_id, module_id, video_watched, quiz_passed, quiz_score,
                    attempt_count, last_attempt_at, selected_answers_json,
                    video_watched_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(assignment_id, module_id) DO UPDATE SET
                    video_watched = excluded.video_watched,
                    quiz_passed = excluded.quiz_passed,
                    quiz_score = excluded.quiz_score,
                    attempt_count = excluded.attempt_count,
                    last_attempt_at = excluded.last_attempt_at,
                    selected_answers_json = excluded.selected_answers_json,
                    video_watched_at = excluded.video_watched_at,
                    updated_at = excluded.updated_at
                """,
                (
                    assignment_id,
                    module_id,
                    bool(module_progress.get("video_watched")),
                    bool(module_progress.get("quiz_passed")),
                    module_progress.get("quiz_score"),
                    int(attempt.get("count", 0)),
                    attempt.get("last_attempt_at"),
                    Jsonb(
                        module_progress.get("selected_answers", None),
                        dumps=lambda item: json.dumps(item, ensure_ascii=False),
                    ),
                    module_progress.get("video_watched_at"),
                    now,
                ),
            )
        connection.commit()
        return {
            "assignment_id": assignment_id,
            "notification_lifecycle": lifecycle,
            "previous_status": previous_status,
            "status": next_status,
        }


def delete_employee_course_progress(employee_id: str, course_id: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM course_assignments
            WHERE employee_id = ?
              AND course_id = ?
            """,
            (employee_id, course_id),
        )
        connection.commit()


class ProgressRepository:
    @staticmethod
    def _validated(progress: dict) -> dict:
        EmployeeCourseProgressRecord.model_validate(progress)
        return progress

    def get_for_employee(self, employee_id: str) -> dict:
        return {key: self._validated(value) for key, value in get_employee_progress(employee_id).items()}

    def get_for_course(self, course_id: str) -> dict[str, dict]:
        return {key: self._validated(value) for key, value in get_course_employee_progress(course_id).items()}

    def list(self) -> list[dict]:
        return [self._validated(progress) for progress in list_employee_course_progress()]

    def save(self, employee_id: str, course_id: str, progress: dict) -> dict:
        self._validated(progress)
        return save_employee_course_progress(employee_id, course_id, progress)

    def delete(self, employee_id: str, course_id: str) -> None:
        delete_employee_course_progress(employee_id, course_id)
