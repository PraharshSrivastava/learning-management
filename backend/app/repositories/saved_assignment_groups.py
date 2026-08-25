"""Trainer-owned reusable assignment-group persistence."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.repositories.database import get_connection


def _loads(value) -> dict:
    if isinstance(value, dict):
        return value
    return json.loads(value or "{}")


def _row_to_saved_group(row) -> dict:
    filters = _loads(row["filters_json"])
    return {
        "saved_group_id": row["saved_group_id"],
        "trainer_id": row["trainer_id"],
        "name": row["name"],
        "group_type": row["group_type"],
        "employee_ids": filters.get("employee_ids") or [],
        "departments": filters.get("departments") or [],
        "mailing_lists": filters.get("mailing_lists") or [],
        "job_titles": filters.get("job_titles") or [],
        "joined_less_than_days_ago": filters.get("joined_less_than_days_ago"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _filters(payload: dict) -> dict:
    return {
        "employee_ids": list(payload.get("employee_ids") or []),
        "departments": list(payload.get("departments") or []),
        "mailing_lists": list(payload.get("mailing_lists") or []),
        "job_titles": list(payload.get("job_titles") or []),
        "joined_less_than_days_ago": payload.get("joined_less_than_days_ago"),
    }


class SavedAssignmentGroupRepository:
    def list(self, trainer_id: str, group_type: str | None = None) -> list[dict]:
        params = [trainer_id]
        where = "WHERE trainer_id = ?"
        if group_type:
            where += " AND group_type = ?"
            params.append(group_type)
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM saved_assignment_groups
                {where}
                ORDER BY lower(name), updated_at DESC
                """,
                params,
            ).fetchall()
        return [_row_to_saved_group(row) for row in rows]

    def upsert(
        self, trainer_id: str, payload: dict, saved_group_id: str | None = None
    ) -> dict:
        now = datetime.now().isoformat()
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValueError("Group name is required")
        group_type = payload.get("group_type")
        if group_type not in {"include", "exclude"}:
            raise ValueError("Group type must be include or exclude")
        filters = _filters(payload)
        group_id = (
            saved_group_id
            or payload.get("saved_group_id")
            or f"saved_group_{uuid4().hex}"
        )
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO saved_assignment_groups (
                    saved_group_id, trainer_id, name, group_type, filters_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trainer_id, group_type, name) DO UPDATE SET
                    filters_json = excluded.filters_json,
                    updated_at = excluded.updated_at
                """,
                (
                    group_id,
                    trainer_id,
                    name,
                    group_type,
                    Jsonb(
                        filters,
                        dumps=lambda item: json.dumps(item, ensure_ascii=False),
                    ),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM saved_assignment_groups
                WHERE trainer_id = ? AND group_type = ? AND name = ?
                """,
                (trainer_id, group_type, name),
            ).fetchone()
            connection.commit()
        return _row_to_saved_group(row)

    def update(
        self, trainer_id: str, saved_group_id: str, payload: dict
    ) -> dict | None:
        now = datetime.now().isoformat()
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValueError("Group name is required")
        group_type = payload.get("group_type")
        if group_type not in {"include", "exclude"}:
            raise ValueError("Group type must be include or exclude")
        filters = _filters(payload)
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE saved_assignment_groups
                SET name = ?, group_type = ?, filters_json = ?, updated_at = ?
                WHERE saved_group_id = ? AND trainer_id = ?
                """,
                (
                    name,
                    group_type,
                    Jsonb(
                        filters,
                        dumps=lambda item: json.dumps(item, ensure_ascii=False),
                    ),
                    now,
                    saved_group_id,
                    trainer_id,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM saved_assignment_groups
                WHERE saved_group_id = ? AND trainer_id = ?
                """,
                (saved_group_id, trainer_id),
            ).fetchone()
            connection.commit()
        return _row_to_saved_group(row) if row else None

    def delete(self, trainer_id: str, saved_group_id: str) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                """
                DELETE FROM saved_assignment_groups
                WHERE saved_group_id = ? AND trainer_id = ?
                RETURNING saved_group_id
                """,
                (saved_group_id, trainer_id),
            ).fetchone()
            connection.commit()
        return row is not None
