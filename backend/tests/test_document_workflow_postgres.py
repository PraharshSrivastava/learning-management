"""Opt-in acceptance against ONLY the isolated document_builder_test database."""

import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.settings import settings
from app.document_builder.import_source import SourceImporter
from app.document_builder.workflow_export import WorkflowExport
from app.document_builder.workflow_jobs import WorkflowJobs
from app.repositories.database import get_connection
from app.repositories.document_drafts import DocumentDraftRepository
from app.repositories.schema import init_db
from app.schemas.document_workflow import (
    DraftContent,
    DraftMetadata,
    DraftModule,
    EditResponse,
    ImportRequest,
    OperationRequest,
    SelectionTarget,
    TextBlock,
    fingerprint,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("DOCUMENT_BUILDER_PG_TEST") != "1",
    reason="isolated PostgreSQL acceptance is opt-in",
)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    assert settings.database_url and settings.database_url.endswith("/document_builder_test"), (
        "Refusing to use a live LMS database"
    )
    init_db()
    init_db()  # Upgrade must be repeatable.
    owner = uuid4().hex
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO trainers(trainer_id, name) VALUES (?, ?)",
            (owner, "Synthetic document test"),
        )
        connection.commit()
    monkeypatch.setattr(settings, "derived_document_dir", tmp_path / "derived")
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "image_dir", tmp_path / "images")
    return DocumentDraftRepository(), owner


def content():
    return DraftContent(
        entryMode="blank",
        metadata=DraftMetadata(
            courseName="Service",
            courseDescription="Support training",
            courseObjective="Listen first",
            targetAudience="New staff",
        ),
        modules=[
            DraftModule(id="m", title="Needs", blocks=[TextBlock(id="b", text="Listen first.")])
        ],
    )


def test_real_postgres_revision_lock_has_exactly_one_winner(repository):
    repo, owner = repository
    draft = repo.create(owner, content())

    def save(number):
        changed = draft.content.model_copy(deep=True)
        changed.modules[0].title = f"Revision {number}"
        try:
            return repo.save(draft.id, owner, 1, changed).revision
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [1, 2]))
    assert sorted(map(str, results)) == ["2", "conflict"]
    assert len(repo.revisions(draft.id, owner)) == 2


def test_postgres_scoped_ai_acceptance_and_stale_proposal(repository):
    repo, owner = repository
    draft = repo.create(owner, content())
    request = OperationRequest(
        task="edit",
        expectedRevision=1,
        key=uuid4().hex,
        instruction="Simplify",
        target=SelectionTarget(
            moduleId="m", blockId="b", start=0, end=6, textHash=fingerprint("Listen")
        ),
    )
    operation, _ = repo.start_operation(draft.id, owner, request)
    fake = SimpleNamespace(
        complete=lambda *args, **kwargs: SimpleNamespace(
            content=EditResponse(replacementText="Hear", summary="Simplified")
        )
    )
    jobs = WorkflowJobs(repo, lambda: fake)
    jobs.run(draft.id, owner, operation["id"])
    assert repo.get(draft.id, owner).content.modules[0].blocks[0].text == "Listen first."
    accepted = repo.accept_operation(draft.id, owner, operation["id"], 1, jobs.apply)
    assert accepted.content.modules[0].blocks[0].text == "Hear first."
    with pytest.raises(ConflictError):
        repo.accept_operation(draft.id, owner, operation["id"], 2, jobs.apply)
    assert repo.restore(draft.id, owner, 2, 1).content.modules[0].blocks[0].text == "Listen first."


def test_pasted_source_preserves_text_and_direct_course_handoff(repository, monkeypatch):
    repo, owner = repository
    empty = content().model_copy(deep=True)
    empty.modules = []
    draft = repo.create(owner, empty)
    imported = SourceImporter(repo).load(
        draft.id,
        owner,
        ImportRequest(
            expectedRevision=1,
            text="Module 1: Needs\nListen first.\n\nModule 2: Follow-up\nConfirm the next step.",
        ),
    )
    approved = repo.approve(draft.id, owner, imported.revision)
    exporter = WorkflowExport(repo)
    course = exporter.create_course(draft.id, owner, approved.revision)
    assert [m["title"] for m in course["modules"]] == ["Needs", "Follow-up"]
    assert "Listen first." in course["modules"][0]["source_text"]
    assert "Confirm the next step." in course["modules"][1]["source_text"]
    assert course["document_builder"]["revision"] == approved.revision
    assert (
        exporter.create_course(draft.id, owner, approved.revision)["course_id"]
        == course["course_id"]
    )
    import pdfplumber

    with pdfplumber.open(BytesIO(exporter.pdf(draft.id, owner, approved.revision))) as pdf:
        assert "Listen first." in "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_source_reference_spoofing_and_cancelled_operation_cannot_write(repository):
    repo, owner = repository
    draft = repo.create(owner, content())
    with pytest.raises(NotFoundError):
        repo.resources(draft.id, "another_trainer")
    request = OperationRequest(task="outline", expectedRevision=1, key=uuid4().hex)
    operation, _ = repo.start_operation(draft.id, owner, request)
    assert repo.claim_operation(draft.id, owner, operation["id"])
    repo.update_operation(draft.id, owner, operation["id"], status="cancelled")
    with pytest.raises(ConflictError):
        repo.save_generated(draft.id, owner, 1, content(), operation["id"])
    assert repo.get(draft.id, owner).revision == 1


def test_background_import_commits_completed_state_atomically(repository):
    repo, owner = repository
    initial = content().model_copy(deep=True)
    initial.modules = []
    draft = repo.create(owner, initial)
    request = OperationRequest(
        task="import",
        expectedRevision=1,
        key=uuid4().hex,
        sourceImport=ImportRequest(
            expectedRevision=1, text="Module 1: Listening\nListen before offering a solution."
        ),
    )
    operation, _ = repo.start_operation(draft.id, owner, request)
    WorkflowJobs(repo, lambda: (_ for _ in ()).throw(AssertionError("No model needed"))).run(
        draft.id, owner, operation["id"]
    )
    completed = repo.operation(draft.id, owner, operation["id"])
    assert completed["status"] == "completed"
    assert completed["result"]["revision"] == repo.get(draft.id, owner).revision == 2
    assert (
        repo.get(draft.id, owner).content.modules[0].blocks[0].text
        == "Listen before offering a solution."
    )
    assert len(repo.resources(draft.id, owner, "source")) == 1


def test_postgres_remove_undo_preserves_draft_and_owner_scope(repository):
    repo, owner = repository
    draft = repo.create(owner, content())
    repo.remove(draft.id, owner, draft.revision)
    assert all(item["draft_id"] != draft.id for item in repo.list(owner))
    with pytest.raises(NotFoundError):
        repo.get(draft.id, owner)
    with pytest.raises(NotFoundError):
        repo.undo_remove(draft.id, "other", draft.revision)
    with pytest.raises(NotFoundError):
        repo.save(draft.id, owner, draft.revision, draft.content)
    assert repo.undo_remove(draft.id, owner, draft.revision) == draft
    assert len(repo.revisions(draft.id, owner)) == 1
