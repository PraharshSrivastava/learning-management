"""Trainer persistence queries."""

from __future__ import annotations

from datetime import datetime

from app.repositories.database import get_connection
from app.schemas.trainer import TrainerRecord


def _row_to_trainer(row) -> dict:
    return {
        "trainer_id": row["trainer_id"],
        "name": row["name"],
        "status": row["status"],
        "directory_uuid": row.get("directory_uuid"),
        "email": row.get("email"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_trainers() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM trainers ORDER BY lower(name), name").fetchall()
    return [TrainerRecord.model_validate(_row_to_trainer(row)).model_dump() for row in rows]


def get_trainer(trainer_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM trainers WHERE trainer_id = ?", (trainer_id,)).fetchone()
    return TrainerRecord.model_validate(_row_to_trainer(row)).model_dump() if row else None


def get_trainer_by_directory_uuid(directory_uuid: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM trainers WHERE directory_uuid = ?",
            (directory_uuid,),
        ).fetchone()
    return TrainerRecord.model_validate(_row_to_trainer(row)).model_dump() if row else None


def get_trainer_by_email(email: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM trainers WHERE email = ?", (email,)).fetchone()
    return TrainerRecord.model_validate(_row_to_trainer(row)).model_dump() if row else None


def refresh_existing_trainer_from_employee(employee: dict) -> dict | None:
    """Update a trainer projection only when that trainer already exists."""
    existing = None
    if employee.get("directory_uuid"):
        existing = get_trainer_by_directory_uuid(employee["directory_uuid"])
    if existing is None:
        existing = get_trainer(employee.get("employee_id"))
    if existing is None:
        return None
    return upsert_trainer_from_employee(employee, trainer_id=existing["trainer_id"])


def upsert_trainer_from_employee(employee: dict, trainer_id: str | None = None) -> dict:
    now = datetime.now().isoformat()
    resolved_trainer_id = trainer_id or employee.get("employee_id")
    if not resolved_trainer_id:
        raise ValueError("trainer_id or employee_id is required")
    existing = None
    if employee.get("directory_uuid"):
        existing = get_trainer_by_directory_uuid(employee["directory_uuid"])
    if existing is None and employee.get("email"):
        existing = get_trainer_by_email(employee["email"])
    if existing:
        resolved_trainer_id = existing["trainer_id"]
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO trainers (
                trainer_id, name, status, directory_uuid, email, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trainer_id) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                directory_uuid = excluded.directory_uuid,
                email = excluded.email,
                updated_at = excluded.updated_at
            """,
            (
                resolved_trainer_id,
                employee.get("name") or "",
                employee.get("status") or "active",
                employee.get("directory_uuid"),
                employee.get("email"),
                now,
                now,
            ),
        )
        connection.commit()
    return get_trainer(resolved_trainer_id) or {
        "trainer_id": resolved_trainer_id,
        "name": employee.get("name") or "",
        "status": employee.get("status") or "active",
        "directory_uuid": employee.get("directory_uuid"),
        "email": employee.get("email"),
        "created_at": now,
        "updated_at": now,
    }


class TrainerRepository:
    def list(self) -> list[dict]: return list_trainers()
    def get(self, trainer_id: str) -> dict | None: return get_trainer(trainer_id)
    def refresh_existing_from_employee(self, employee: dict) -> dict | None:
        return refresh_existing_trainer_from_employee(employee)
    def upsert_from_employee(self, employee: dict, trainer_id: str | None = None) -> dict:
        return upsert_trainer_from_employee(employee, trainer_id)
