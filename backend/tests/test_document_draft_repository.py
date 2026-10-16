"""Repository behavior tests with a SQLite SQL adapter, NOT PostgreSQL acceptance.

Real PostgreSQL migration/locking tests remain required before workflow rollout.
The adapter exercises the actual repository methods and transactional snapshots.
"""

import json
import sqlite3
from contextlib import contextmanager

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories import document_drafts
from app.schemas.document_workflow import DraftContent, DraftMetadata, DraftModule, TextBlock


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, args=()):
        return self.raw.execute(sql.replace("::jsonb", "").replace(" FOR UPDATE", ""), args)

    def commit(self):
        self.raw.commit()


@pytest.fixture
def repo(monkeypatch):
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.create_function("jsonb_array_length", 1, lambda value: len(json.loads(value)))
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("CREATE TABLE trainers (trainer_id TEXT PRIMARY KEY)")
    raw.executemany("INSERT INTO trainers VALUES (?)", [("owner",), ("other",)])
    document_drafts.create_draft_tables(Connection(raw))
    raw.commit()

    @contextmanager
    def connect():
        try:
            yield Connection(raw)
            raw.commit()
        except Exception:
            raw.rollback()
            raise

    monkeypatch.setattr(document_drafts, "get_connection", connect)
    yield document_drafts.DocumentDraftRepository()
    raw.close()


def content():
    return DraftContent(
        entryMode="blank",
        metadata=DraftMetadata(
            courseName="Service",
            courseDescription="Service basics",
            courseObjective="Listen first",
            targetAudience="New staff",
        ),
        modules=[
            DraftModule(
                id="module_1", title="Needs", blocks=[TextBlock(id="block_1", text="Listen first.")]
            )
        ],
    )


def test_create_reopen_and_trainer_scoping(repo):
    draft = repo.create("owner", content())
    assert repo.get(draft.id, "owner") == draft
    assert repo.list("owner")[0]["draft_id"] == draft.id
    assert repo.list("other") == []
    with pytest.raises(NotFoundError):
        repo.get(draft.id, "other")


def test_save_and_restore_create_new_immutable_revisions(repo):
    original = repo.create("owner", content())
    edited = original.content.model_copy(deep=True)
    edited.modules[0].blocks[0].text = "Ask a clarifying question."
    saved = repo.save(original.id, "owner", 1, edited)
    assert saved.revision == 2
    restored = repo.restore(original.id, "owner", 2, 1)
    assert restored.revision == 3
    assert restored.content == original.content
    assert [revision["revision"] for revision in repo.revisions(original.id, "owner")] == [3, 2, 1]


def test_stale_save_and_stale_restore_cannot_overwrite(repo):
    original = repo.create("owner", content())
    updated = original.content.model_copy(deep=True)
    updated.modules[0].title = "New title"
    saved = repo.save(original.id, "owner", 1, updated)
    with pytest.raises(ConflictError):
        repo.save(original.id, "owner", 1, original.content)
    with pytest.raises(ConflictError):
        repo.restore(original.id, "owner", 1, 1)
    assert repo.get(original.id, "owner") == saved
    assert len(repo.revisions(original.id, "owner")) == 2


def test_approval_survives_body_only_save_but_not_structure_change(repo):
    original = repo.create("owner", content())
    approved = repo.approve(original.id, "owner", 1)
    assert approved.revision == 2
    assert approved.approvedOutline
    edited = approved.content.model_copy(deep=True)
    edited.modules[0].blocks[0].text = "Revised explanation"
    body = repo.save(original.id, "owner", 2, edited)
    assert body.approvedOutline == approved.approvedOutline
    edited.modules[0].title = "Different scope"
    renamed = repo.save(original.id, "owner", 3, edited)
    assert renamed.approvedOutline is None


def test_no_op_save_does_not_create_revision(repo):
    original = repo.create("owner", content())
    assert repo.save(original.id, "owner", 1, original.content) == original
    assert len(repo.revisions(original.id, "owner")) == 1


def test_invalid_approval_or_missing_restore_leave_state_unchanged(repo):
    original = repo.create("owner", DraftContent(entryMode="ai"))
    with pytest.raises(ValueError):
        repo.approve(original.id, "owner", 1)
    with pytest.raises(NotFoundError):
        repo.restore(original.id, "owner", 1, 99)
    assert repo.get(original.id, "owner").revision == 1


def test_other_trainer_cannot_save_approve_restore_or_read_revisions(repo):
    original = repo.create("owner", content())
    for operation in (
        lambda: repo.save(original.id, "other", 1, content()),
        lambda: repo.approve(original.id, "other", 1),
        lambda: repo.restore(original.id, "other", 1, 1),
        lambda: repo.revisions(original.id, "other"),
    ):
        with pytest.raises(NotFoundError):
            operation()


def test_separate_copy_remaps_owned_source_references(repo):
    original = repo.create("owner", content())
    repo.put_resource(
        original.id,
        "owner",
        "source1",
        "source",
        {
            "spans": [{"id": "span1", "text": "Listen first.", "location": "page 1"}],
            "name": "Source",
            "issues": [],
            "acknowledged": True,
        },
    )
    edited = original.content.model_copy(deep=True)
    from app.schemas.document_workflow import SourceReference

    edited.modules[0].sourceReferences = [SourceReference(sourceId="source1", spanId="span1")]
    edited.modules[0].blocks[0].sourceReferences = [
        SourceReference(sourceId="source1", spanId="span1")
    ]
    copied = repo.copy(original.id, "owner", edited)
    assert copied.id != original.id
    assert copied.content.modules[0].sourceReferences[0].sourceId != "source1"
    repo.validate_resources(copied.id, "owner", copied.content)
    assert repo.get(original.id, "owner") == original


def test_remove_and_undo_preserve_content_revisions_and_owned_resources(repo):
    draft = repo.create("owner", content())
    repo.put_resource(draft.id, "owner", "asset", "asset", {"path": "owned/image.png"})
    assert repo.list("owner")[0]["module_count"] == 1
    repo.remove(draft.id, "owner", draft.revision)
    assert repo.list("owner") == []
    with pytest.raises(NotFoundError):
        repo.get(draft.id, "owner")
    with pytest.raises(NotFoundError):
        repo.save(draft.id, "owner", draft.revision, draft.content)
    restored = repo.undo_remove(draft.id, "owner", draft.revision)
    assert restored == draft
    assert len(repo.revisions(draft.id, "owner")) == 1
    assert repo.resources(draft.id, "owner")[0]["id"] == "asset"
    assert repo.list("owner")[0]["draft_id"] == draft.id


def test_remove_and_undo_are_owner_scoped_and_revision_checked(repo):
    draft = repo.create("owner", content())
    with pytest.raises(NotFoundError):
        repo.remove(draft.id, "other", 1)
    with pytest.raises(ConflictError):
        repo.remove(draft.id, "owner", 99)
    assert repo.get(draft.id, "owner") == draft
    repo.remove(draft.id, "owner", 1)
    with pytest.raises(NotFoundError):
        repo.undo_remove(draft.id, "other", 1)
    with pytest.raises(ConflictError):
        repo.undo_remove(draft.id, "owner", 99)
    assert repo.list("owner") == []
    repo.undo_remove(draft.id, "owner", 1)
    assert repo.get(draft.id, "owner") == draft


def test_remove_rejects_active_generation(repo):
    draft = repo.create("owner", content())
    with document_drafts.get_connection() as connection:
        connection.execute(
            "INSERT INTO document_builder_operations (operation_id, draft_id, request_key, body_json) VALUES (?, ?, ?, ?::jsonb)",
            ("active", draft.id, "active", '{"status":"running"}'),
        )
        connection.commit()
    with pytest.raises(ConflictError, match="generation"):
        repo.remove(draft.id, "owner", 1)
    assert repo.get(draft.id, "owner") == draft
