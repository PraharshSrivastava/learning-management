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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_builder_resources (
            resource_id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL REFERENCES document_builder_drafts(draft_id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK(kind IN ('source', 'asset')),
            body_json JSONB NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_builder_operations (
            operation_id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL REFERENCES document_builder_drafts(draft_id) ON DELETE CASCADE,
            request_key TEXT NOT NULL,
            body_json JSONB NOT NULL,
            UNIQUE(draft_id, request_key)
        )
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
    def import_content(self, draft_id, trainer_id, expected, content, resources):
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            for resource in resources:
                connection.execute(
                    "INSERT INTO document_builder_resources (resource_id, draft_id, kind, body_json) VALUES (?, ?, ?, ?::jsonb)",
                    (resource["id"], draft_id, resource["kind"], json.dumps(resource["body"])),
                )
            updated = self._write(connection, current, content, None, "source imported")
            connection.commit()
            return updated

    def resources(self, draft_id, trainer_id, kind=None):
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM document_builder_resources WHERE draft_id = ?", (draft_id,)
            ).fetchall()
        return [
            {
                "id": row["resource_id"],
                "kind": row["kind"],
                **(
                    json.loads(row["body_json"])
                    if isinstance(row["body_json"], str)
                    else row["body_json"]
                ),
            }
            for row in rows
            if kind is None or kind == row["kind"]
        ]

    def put_resource(self, draft_id, trainer_id, resource_id, kind, body):
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO document_builder_resources (resource_id, draft_id, kind, body_json) VALUES (?, ?, ?, ?::jsonb)",
                (resource_id, draft_id, kind, json.dumps(body)),
            )
            connection.commit()

    def validate_resources(self, draft_id, trainer_id, content):
        resources = self.resources(draft_id, trainer_id)
        assets = {r["id"] for r in resources if r["kind"] == "asset"}
        spans = {
            (r["id"], span["id"]) for r in resources if r["kind"] == "source" for span in r["spans"]
        }
        for module in content.modules:
            if any(
                (ref.sourceId, ref.spanId) not in spans
                for ref in [
                    *module.sourceReferences,
                    *(ref for block in module.blocks for ref in block.sourceReferences),
                ]
            ):
                raise ValueError("Source reference does not belong to this draft")
            if any(
                block.type == "image" and block.assetId not in assets for block in module.blocks
            ):
                raise ValueError("Image does not belong to this draft")

    def copy(self, draft_id, trainer_id, content):
        self.validate_resources(draft_id, trainer_id, content)
        resources = self.resources(draft_id, trainer_id)
        mapping = {resource["id"]: uuid4().hex for resource in resources}
        copied = content.model_copy(deep=True)
        for module in copied.modules:
            for ref in [
                *module.sourceReferences,
                *(ref for block in module.blocks for ref in block.sourceReferences),
            ]:
                ref.sourceId = mapping.get(ref.sourceId, ref.sourceId)
            for block in module.blocks:
                if block.type == "image":
                    block.assetId = mapping[block.assetId]
        new_id, now = uuid4().hex, _now()
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO document_builder_drafts (draft_id, trainer_id, revision, content_json, created_at, updated_at) VALUES (?, ?, 1, ?::jsonb, ?, ?)",
                (new_id, trainer_id, copied.model_dump_json(), now, now),
            )
            self._snapshot(connection, new_id, 1, copied, "separate copy", now)
            for resource in resources:
                body = {key: value for key, value in resource.items() if key not in {"id", "kind"}}
                if resource["kind"] == "source":
                    body["id"] = mapping[resource["id"]]
                connection.execute(
                    "INSERT INTO document_builder_resources (resource_id, draft_id, kind, body_json) VALUES (?, ?, ?, ?::jsonb)",
                    (mapping[resource["id"]], new_id, resource["kind"], json.dumps(body)),
                )
            connection.commit()
        return DraftRecord(id=new_id, revision=1, content=copied, createdAt=now, updatedAt=now)

    def acknowledge(self, draft_id, trainer_id, source_id, expected, acknowledged):
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            row = connection.execute(
                "SELECT body_json FROM document_builder_resources WHERE draft_id = ? AND resource_id = ? AND kind = 'source' FOR UPDATE",
                (draft_id, source_id),
            ).fetchone()
            if not row:
                raise NotFoundError("Source not found")
            body = (
                json.loads(row["body_json"])
                if isinstance(row["body_json"], str)
                else row["body_json"]
            )
            body["acknowledged"] = acknowledged
            connection.execute(
                "UPDATE document_builder_resources SET body_json = ?::jsonb WHERE resource_id = ?",
                (json.dumps(body), source_id),
            )
            updated = self._write(
                connection, current, current.content, None, "source review updated"
            )
            connection.commit()
            return updated

    def claim_operation(self, draft_id, trainer_id, operation_id):
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE operation_id = ? AND draft_id = ? FOR UPDATE",
                (operation_id, draft_id),
            ).fetchone()
            if not row:
                return False
            body = (
                json.loads(row["body_json"])
                if isinstance(row["body_json"], str)
                else row["body_json"]
            )
            if body["status"] != "queued":
                return False
            body.update(status="running", updatedAt=_now())
            connection.execute(
                "UPDATE document_builder_operations SET body_json = ?::jsonb WHERE operation_id = ?",
                (json.dumps(body), operation_id),
            )
            connection.commit()
            return True

    def save_generated(self, draft_id, trainer_id, expected, content, operation_id):
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            row = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE operation_id = ? AND draft_id = ? FOR UPDATE",
                (operation_id, draft_id),
            ).fetchone()
            value = (
                json.loads(row["body_json"])
                if isinstance(row["body_json"], str)
                else row["body_json"]
            )
            if value["status"] != "running":
                raise ConflictError("Generation was cancelled; draft was not changed")
            updated = self._write(
                connection, current, content, current.approvedOutline, "module drafted"
            )
            connection.commit()
            return updated

    def start_operation(self, draft_id, trainer_id, request):
        with get_connection() as connection:
            self._locked(connection, draft_id, trainer_id, request.expectedRevision)
            existing = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE draft_id = ? AND request_key = ?",
                (draft_id, request.key),
            ).fetchone()
            if existing:
                body = existing["body_json"]
                result = json.loads(body) if isinstance(body, str) else body
                if result["request"] != request.model_dump():
                    raise ConflictError("Request key was already used for a different operation")
                return result, False
            running = connection.execute(
                "SELECT operation_id FROM document_builder_operations WHERE draft_id = ? AND body_json->>'status' IN ('queued', 'running')",
                (draft_id,),
            ).fetchone()
            if running:
                raise ConflictError("This draft already has a running operation")
            pending = connection.execute(
                "SELECT count(*) AS total FROM document_builder_operations o JOIN document_builder_drafts d ON d.draft_id = o.draft_id WHERE d.trainer_id = ? AND o.body_json->>'status' IN ('queued', 'running')",
                (trainer_id,),
            ).fetchone()
            if pending["total"] >= 8:
                raise ConflictError(
                    "Too many queued document operations; finish or cancel one first"
                )
            result = {
                "id": uuid4().hex,
                "draftId": draft_id,
                "status": "queued",
                "request": request.model_dump(),
                "createdAt": _now(),
                "result": None,
                "error": None,
            }
            connection.execute(
                "INSERT INTO document_builder_operations (operation_id, draft_id, request_key, body_json) VALUES (?, ?, ?, ?::jsonb)",
                (result["id"], draft_id, request.key, json.dumps(result)),
            )
            connection.commit()
            return result, True

    def operation(self, draft_id, trainer_id, operation_id):
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE operation_id = ? AND draft_id = ?",
                (operation_id, draft_id),
            ).fetchone()
        if not row:
            raise NotFoundError("Document operation not found")
        value = (
            json.loads(row["body_json"]) if isinstance(row["body_json"], str) else row["body_json"]
        )
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        if value["status"] == "running" and value.get("updatedAt", value["createdAt"]) < cutoff:
            return self.update_operation(
                draft_id,
                trainer_id,
                operation_id,
                status="failed",
                error="Worker interrupted. Completed modules are saved; retry the remaining task.",
            )
        return value

    def operations(self, draft_id, trainer_id):
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE draft_id = ? ORDER BY body_json->>'createdAt' DESC LIMIT 20",
                (draft_id,),
            ).fetchall()
        return [
            json.loads(row["body_json"]) if isinstance(row["body_json"], str) else row["body_json"]
            for row in rows
        ]

    def recover_operations(self):
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT o.operation_id, o.draft_id, d.trainer_id, o.body_json FROM document_builder_operations o JOIN document_builder_drafts d ON d.draft_id = o.draft_id WHERE o.body_json->>'status' IN ('queued', 'running')"
            ).fetchall()
        queued = []
        for row in rows:
            body = (
                json.loads(row["body_json"])
                if isinstance(row["body_json"], str)
                else row["body_json"]
            )
            if body["status"] == "queued":
                queued.append((row["draft_id"], row["trainer_id"], row["operation_id"]))
            elif body.get("updatedAt", body["createdAt"]) < cutoff:
                self.update_operation(
                    row["draft_id"],
                    row["trainer_id"],
                    row["operation_id"],
                    status="failed",
                    error="Worker interrupted. Completed modules are saved; retry the remaining task.",
                )
        return queued

    def update_operation(self, draft_id, trainer_id, operation_id, **changes):
        self.get(draft_id, trainer_id)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE operation_id = ? AND draft_id = ? FOR UPDATE",
                (operation_id, draft_id),
            ).fetchone()
            if not row:
                raise NotFoundError("Document operation not found")
            value = (
                json.loads(row["body_json"])
                if isinstance(row["body_json"], str)
                else row["body_json"]
            )
            if value["status"] in {"cancelled", "accepted", "rejected"}:
                return value
            value.update(changes, updatedAt=_now())
            connection.execute(
                "UPDATE document_builder_operations SET body_json = ?::jsonb WHERE operation_id = ?",
                (json.dumps(value), operation_id),
            )
            connection.commit()
            return value

    def accept_operation(self, draft_id, trainer_id, operation_id, expected, transform):
        with get_connection() as connection:
            current = self._locked(connection, draft_id, trainer_id, expected)
            row = connection.execute(
                "SELECT body_json FROM document_builder_operations WHERE draft_id = ? AND operation_id = ? FOR UPDATE",
                (draft_id, operation_id),
            ).fetchone()
            if not row:
                raise NotFoundError("Suggestion not found")
            value = (
                json.loads(row["body_json"])
                if isinstance(row["body_json"], str)
                else row["body_json"]
            )
            if value["status"] != "proposed" or value["request"]["expectedRevision"] != expected:
                raise ConflictError("Suggestion is stale or already resolved")
            content = transform(current.content.model_copy(deep=True), value)
            approved = (
                current.approvedOutline
                if outline_fingerprint(content) == outline_fingerprint(current.content)
                else None
            )
            updated = self._write(connection, current, content, approved, "AI suggestion accepted")
            value["status"] = "accepted"
            connection.execute(
                "UPDATE document_builder_operations SET body_json = ?::jsonb WHERE operation_id = ?",
                (json.dumps(value), operation_id),
            )
            connection.commit()
            return updated

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
        if any(
            resource["issues"] and not resource["acknowledged"]
            for resource in self.resources(draft_id, trainer_id, "source")
        ):
            raise ValueError("Review and acknowledge source extraction issues before approval")
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
