"""Trainer persistence queries."""

from __future__ import annotations

from app.repositories.database import get_connection
from app.schemas.trainer import TrainerRecord


def _row_to_trainer(row) -> dict:
    return {
        "trainer_id": row["trainer_id"],
        "name": row["name"],
        "status": row["status"],
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

class TrainerRepository:
    def list(self) -> list[dict]: return list_trainers()
    def get(self, trainer_id: str) -> dict | None: return get_trainer(trainer_id)
