from types import SimpleNamespace
from uuid import uuid4

from app.core.exceptions import ProviderError
from app.document_builder.workflow_jobs import WorkflowJobs
from app.schemas.document_workflow import (
    DraftContent,
    DraftMetadata,
    DraftModule,
    GeneratedTextBlock,
    ImportRequest,
    ModuleResponse,
    OperationRequest,
    RevisionResponse,
    TextBlock,
)

pytest_plugins = ["test_document_draft_repository"]


def test_background_import_commits_source_revision_and_operation_together(
    repo, monkeypatch, tmp_path
):
    from app.core.settings import settings

    monkeypatch.setattr(settings, "derived_document_dir", tmp_path)
    draft = repo.create("owner", DraftContent(entryMode="existing"))
    request = OperationRequest(
        task="import",
        expectedRevision=1,
        key=uuid4().hex,
        sourceImport=ImportRequest(
            expectedRevision=1, text="Module 1: Listening\nListen before offering a solution."
        ),
    )
    operation, _ = repo.start_operation(draft.id, "owner", request)
    WorkflowJobs(
        repo, lambda: (_ for _ in ()).throw(AssertionError("Import must not call a model"))
    ).run(draft.id, "owner", operation["id"])
    assert repo.operation(draft.id, "owner", operation["id"])["status"] == "completed"
    assert repo.get(draft.id, "owner").revision == 2
    assert repo.get(draft.id, "owner").content.modules[0].title == "Listening"
    assert len(repo.resources(draft.id, "owner", "source")) == 1
    repo.update_operation(draft.id, "owner", operation["id"], status="cancelled")
    assert repo.operation(draft.id, "owner", operation["id"])["status"] == "completed"


def test_cancelled_import_cannot_commit_extracted_resources(repo):
    draft = repo.create("owner", DraftContent(entryMode="existing"))
    operation, _ = repo.start_operation(
        draft.id,
        "owner",
        OperationRequest(
            task="import",
            expectedRevision=1,
            key=uuid4().hex,
            sourceImport=ImportRequest(expectedRevision=1, text="Listen first."),
        ),
    )
    repo.update_operation(draft.id, "owner", operation["id"], status="cancelled")
    import pytest

    from app.core.exceptions import ConflictError

    with pytest.raises(ConflictError):
        repo.import_content(
            draft.id,
            "owner",
            1,
            draft.content,
            [{"id": "source1", "kind": "source", "body": {"spans": []}}],
            operation["id"],
        )
    assert repo.get(draft.id, "owner").revision == 1
    assert repo.resources(draft.id, "owner") == []


def test_revision_is_proposal_until_accept_and_preserves_other_modules(repo):
    original = DraftContent(
        entryMode="blank",
        modules=[
            DraftModule(
                id="m1",
                title="Listen",
                blocks=[TextBlock(id="b1", type="paragraph", text="Listen carefully.")],
            ),
            DraftModule(
                id="m2",
                title="Follow up",
                blocks=[TextBlock(id="b2", type="paragraph", text="Confirm next steps.")],
            ),
        ],
    )
    draft = repo.create("owner", original)
    request = OperationRequest(
        task="revise",
        scope="module",
        moduleId="m1",
        instruction="Simplify",
        expectedRevision=1,
        key=uuid4().hex,
    )
    operation, _ = repo.start_operation(draft.id, "owner", request)

    def generate(task, **kwargs):
        assert task == "revise"
        assert kwargs["context"]["originalTexts"] == ["Listen carefully."]
        return SimpleNamespace(
            content=RevisionResponse(replacements=["Listen closely."], summary="Simplified")
        )

    WorkflowJobs(repo, lambda: SimpleNamespace(complete=generate)).run(
        draft.id, "owner", operation["id"]
    )
    proposal = repo.operation(draft.id, "owner", operation["id"])
    assert proposal["status"] == "proposed"
    assert repo.get(draft.id, "owner").content == original
    applied = WorkflowJobs.apply(original.model_copy(deep=True), proposal)
    assert applied.modules[0].blocks[0].text == "Listen closely."
    assert applied.modules[1] == original.modules[1]


def test_insert_scenario_keeps_original_blocks():
    original = DraftContent(
        entryMode="blank",
        modules=[
            DraftModule(
                id="m1",
                title="Listen",
                blocks=[TextBlock(id="b1", type="paragraph", text="Listen carefully.")],
            )
        ],
    )
    operation = {
        "request": OperationRequest(
            task="insert",
            moduleId="m1",
            scope="module",
            expectedRevision=1,
            key="insert1",
            instruction="Practice",
        ).model_dump(),
        "result": {
            "replacementText": "Illustrative scenario: a customer calls.",
            "sourceReferences": [],
        },
    }
    applied = WorkflowJobs.apply(original.model_copy(deep=True), operation)
    assert applied.modules[0].blocks[0] == original.modules[0].blocks[0]
    assert applied.modules[0].blocks[1].type == "scenario"


def test_partial_generation_retry_keeps_completed_module(repo):
    content = DraftContent(
        entryMode="ai",
        metadata=DraftMetadata(
            courseName="Service",
            courseDescription="Basics",
            courseObjective="Listen",
            targetAudience="New staff",
        ),
        modules=[DraftModule(id="m1", title="Listen"), DraftModule(id="m2", title="Follow-up")],
    )
    draft = repo.create("owner", content)
    draft = repo.approve(draft.id, "owner", 1)
    request = OperationRequest(task="draft", expectedRevision=draft.revision, key=uuid4().hex)
    operation, _ = repo.start_operation(draft.id, "owner", request)
    calls = []

    def generate(task, **kwargs):
        calls.append(kwargs["context"]["module"]["title"])
        if len(calls) == 2:
            raise ProviderError("Synthetic provider unavailable")
        return SimpleNamespace(
            content=ModuleResponse(
                blocks=[GeneratedTextBlock(type="paragraph", text="Listen without interrupting.")]
            )
        )

    jobs = WorkflowJobs(repo, lambda: SimpleNamespace(complete=generate))
    jobs.run(draft.id, "owner", operation["id"])
    partial = repo.get(draft.id, "owner")
    assert partial.content.modules[0].blocks[0].text == "Listen without interrupting."
    assert partial.content.modules[1].blocks == []
    assert repo.operation(draft.id, "owner", operation["id"])["status"] == "failed"
    retry, _ = repo.start_operation(
        draft.id,
        "owner",
        OperationRequest(task="draft", expectedRevision=partial.revision, key=uuid4().hex),
    )

    def remaining(task, **kwargs):
        assert kwargs["context"]["module"]["title"] == "Follow-up"
        return SimpleNamespace(
            content=ModuleResponse(
                blocks=[GeneratedTextBlock(type="paragraph", text="Confirm the next step.")]
            )
        )

    WorkflowJobs(repo, lambda: SimpleNamespace(complete=remaining)).run(
        draft.id, "owner", retry["id"]
    )
    completed = repo.get(draft.id, "owner")
    assert completed.content.modules[0].blocks == partial.content.modules[0].blocks
    assert completed.content.modules[1].blocks[0].text == "Confirm the next step."
    assert repo.operation(draft.id, "owner", retry["id"])["status"] == "completed"


def test_cancelled_operation_is_never_claimed_or_written(repo):
    draft = repo.create("owner", DraftContent(entryMode="ai"))
    operation, _ = repo.start_operation(
        draft.id, "owner", OperationRequest(task="outline", expectedRevision=1, key=uuid4().hex)
    )
    repo.update_operation(draft.id, "owner", operation["id"], status="cancelled")
    WorkflowJobs(repo, lambda: (_ for _ in ()).throw(AssertionError("Must not call model"))).run(
        draft.id, "owner", operation["id"]
    )
    assert repo.get(draft.id, "owner").revision == 1
