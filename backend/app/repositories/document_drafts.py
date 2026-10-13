"""Atomic trainer-owned draft revisions; additive PostgreSQL persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.database import get_connection
from app.schemas.document_workflow import DraftContent, DraftRecord, outline_fingerprint


def create_draft_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_builder_drafts (
            draft_id TEXT PRIMARY KEY,
            trainer_id TEXT NOT NULL REFERENCES trainers(trainer_id) ON DELETE CASCADE,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            content_json JSONB NOT NULL,
            approved_outline TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_builder_revisions (
            draft_id TEXT NOT NULL REFERENCES document_builder_drafts(draft_id) ON DELETE CASCADE,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            content_json JSONB NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (draft_id, revision)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_builder_drafts_trainer
        ON document_builder_drafts(trainer_id, updated_at)
    """)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _content(raw):
    return DraftContent.model_validate(json.loads(raw) if isinstance(raw, str) else raw)


def _record(row):
    if not row:
        raise NotFoundError("Document draft not found")
    return DraftRecord(
        id=row["draft_id"],
        revision=row["revision"],
        content=_content(row["content_json"]),
        approvedOutline=row["approved_outline"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


class DocumentDraftRepository:
    def create(self, trainer_id: str, content: DraftContent) -> DraftRecord:
        draft_id, now = uuid4().hex, _now()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO document_builder_drafts
                (draft_id, trainer_id, revision, content_json, created_at, updated_at)
                VALUES (?, ?, 1, ?::jsonb, ?, ?)
            """,
                (draft_id, trainer_id, content.model_dump_json(), now, now),
            )
            self._snapshot(connection, draft_id, 1, content, "created", now)
            connection.commit()
        return DraftRecord(id=draft_id, revision=1, content=content, createdAt=now, updatedAt=now)

    def get(self, draft_id: str, trainer_id: str) -> DraftRecord:
        with get_connection() as connection:
            return _record(
                connection.execute(
                    """
                SELECT * FROM document_builder_drafts WHERE draft_id = ? AND trainer_id = ?
            """,
                    (draft_id, trainer_id),
                ).fetchone()
            )

    def list(self, trainer_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT draft_id, revision, content_json->'metadata'->>'courseName' AS title,
                       content_json->>'entryMode' AS entry_mode, updated_at
                FROM document_builder_drafts WHERE trainer_id = ?
                ORDER BY updated_at DESC LIMIT 100
            """,
                (trainer_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save(
        self, draft_id: str, trainer_id: str, expected: int, content: DraftContent
    ) -> DraftRecord:
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            if current.content == content:
                return current
            approved = current.approvedOutline
            if outline_fingerprint(current.content) != outline_fingerprint(content):
                approved = None
            updated = self._write(connection, current, content, approved, "manual save")
            connection.commit()
            return updated

    def approve(self, draft_id: str, trainer_id: str, expected: int) -> DraftRecord:
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            if current.content.metadata.missing_fields():
                raise ValueError("Complete course details before approving the outline")
            if not any(module.included for module in current.content.modules):
                raise ValueError("Include at least one module before approval")
            approved = outline_fingerprint(current.content)
            if approved == current.approvedOutline:
                return current
            updated = self._write(
                connection, current, current.content, approved, "outline approved"
            )
            connection.commit()
            return updated

    def revisions(self, draft_id: str, trainer_id: str) -> list[dict]:
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT revision, reason, created_at FROM document_builder_revisions
                WHERE draft_id = ? ORDER BY revision DESC LIMIT 100
            """,
                (draft_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def restore(self, draft_id: str, trainer_id: str, expected: int, revision: int) -> DraftRecord:
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            row = connection.execute(
                """
                SELECT content_json FROM document_builder_revisions WHERE draft_id = ? AND revision = ?
            """,
                (draft_id, revision),
            ).fetchone()
            if not row:
                raise NotFoundError("Document revision not found")
            updated = self._write(
                connection,
                current,
                _content(row["content_json"]),
                None,
                f"restored revision {revision}",
            )
            connection.commit()
            return updated

    @staticmethod
    def _locked(connection, draft_id, trainer_id, expected):
        current = _record(
            connection.execute(
                """
            SELECT * FROM document_builder_drafts
            WHERE draft_id = ? AND trainer_id = ? FOR UPDATE
        """,
                (draft_id, trainer_id),
            ).fetchone()
        )
        if current.revision != expected:
            raise ConflictError("Draft changed in another request. Reload before saving.")
        return current

    @staticmethod
    def _snapshot(connection, draft_id, revision, content, reason, now):
        connection.execute(
            """
            INSERT INTO document_builder_revisions
            (draft_id, revision, content_json, reason, created_at)
            VALUES (?, ?, ?::jsonb, ?, ?)
        """,
            (draft_id, revision, content.model_dump_json(), reason, now),
        )

    def _write(self, connection, current, content, approved, reason):
        revision, now = current.revision + 1, _now()
        connection.execute(
            """
            UPDATE document_builder_drafts SET revision = ?, content_json = ?::jsonb,
                approved_outline = ?, updated_at = ? WHERE draft_id = ?
        """,
            (revision, content.model_dump_json(), approved, now, current.id),
        )
        self._snapshot(connection, current.id, revision, content, reason, now)
        return DraftRecord(
            id=current.id,
            revision=revision,
            content=content,
            approvedOutline=approved,
            createdAt=current.createdAt,
            updatedAt=now,
        )
