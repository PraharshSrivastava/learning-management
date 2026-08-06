"""Document catalog persistence for uploaded source PDFs."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.repositories.database import get_connection


def save_document(trainer_id: str, file_name: str, file_path: str) -> dict:
    now = datetime.now().isoformat()
    document_id = str(uuid.uuid4())
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT document_id FROM documents WHERE trainer_id = ? AND file_name = ?",
            (trainer_id, file_name),
        ).fetchone()
        if existing:
            document_id = existing["document_id"]
        connection.execute(
            """
            INSERT INTO documents (
                document_id, trainer_id, file_name, file_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(trainer_id, file_name) DO UPDATE SET
                file_path = excluded.file_path,
                updated_at = excluded.updated_at
            """,
            (document_id, trainer_id, file_name, file_path, now, now),
        )
        connection.commit()
    return {
        "document_id": document_id,
        "trainer_id": trainer_id,
        "file_name": file_name,
        "file_path": file_path,
        "created_at": now,
        "updated_at": now,
    }


def list_documents(trainer_id: str | None = None) -> list[dict]:
    with get_connection() as connection:
        rows = (
            connection.execute(
                "SELECT * FROM documents WHERE trainer_id = ? ORDER BY created_at DESC",
                (trainer_id,),
            ).fetchall()
            if trainer_id
            else connection.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        )
    return [dict(row) for row in rows]


def get_document(document_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
    return dict(row) if row else None


def get_document_by_file_name(file_name: str, trainer_id: str | None = None) -> dict | None:
    with get_connection() as connection:
        row = (
            connection.execute(
                "SELECT * FROM documents WHERE file_name = ? AND trainer_id = ?",
                (file_name, trainer_id),
            ).fetchone()
            if trainer_id
            else connection.execute(
                "SELECT * FROM documents WHERE file_name = ?",
                (file_name,),
            ).fetchone()
        )
    return dict(row) if row else None
