from types import SimpleNamespace
from uuid import uuid4

from app.document_builder.workflow_jobs import WorkflowJobs
from app.schemas.document_workflow import (
    DraftContent,
    DraftModule,
    EditResponse,
    OperationRequest,
    RevisionResponse,
    SelectionTarget,
    TableBlock,
    TextBlock,
    fingerprint,
)

pytest_plugins = ["test_document_draft_repository"]


def sample():
    return DraftContent(
        entryMode="blank",
        modules=[
            DraftModule(
                id="m1",
                title="Listening",
                blocks=[
                    TextBlock(id="b1", text="Listen carefully before responding."),
                    TableBlock(id="t1", rows=[["Concern", "Response"], ["Delay", "Check status"]]),
                ],
            ),
            DraftModule(
                id="m2", title="Follow up", blocks=[TextBlock(id="b2", text="Confirm next steps.")]
            ),
            DraftModule(
                id="m3",
                title="Excluded module",
                included=False,
                blocks=[TextBlock(id="b3", text="Excluded notes.")],
            ),
        ],
    )


def test_current_module_only_and_explicit_acceptance(repo):
    original = sample()
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
    model = SimpleNamespace(
        complete=lambda *args, **kwargs: SimpleNamespace(
            content=RevisionResponse(replacements=["Listen before replying."], summary="Simplified")
        )
    )
    jobs = WorkflowJobs(repo, lambda: model)
    jobs.run(draft.id, "owner", operation["id"])
    assert repo.get(draft.id, "owner").content == original
    accepted = repo.accept_operation(draft.id, "owner", operation["id"], 1, jobs.apply)
    assert accepted.content.modules[0].blocks[0].text == "Listen before replying."
    assert accepted.content.modules[0].blocks[1] == original.modules[0].blocks[1]
    assert accepted.content.modules[1:] == original.modules[1:]


def test_selected_text_only_and_explicit_acceptance(repo):
    original = sample()
    draft = repo.create("owner", original)
    request = OperationRequest(
        task="edit",
        instruction="Simplify",
        expectedRevision=1,
        key=uuid4().hex,
        target=SelectionTarget(
            moduleId="m1", blockId="b1", start=0, end=6, textHash=fingerprint("Listen")
        ),
    )
    operation, _ = repo.start_operation(draft.id, "owner", request)

    def complete(*args, **kwargs):
        assert kwargs["context"]["selectedText"] == "Listen"
        return SimpleNamespace(content=EditResponse(replacementText="Hear", summary="Simplified"))

    jobs = WorkflowJobs(repo, lambda: SimpleNamespace(complete=complete))
    jobs.run(draft.id, "owner", operation["id"])
    assert repo.get(draft.id, "owner").content == original
    accepted = repo.accept_operation(draft.id, "owner", operation["id"], 1, jobs.apply)
    assert accepted.content.modules[0].blocks[0].text == "Hear carefully before responding."
    assert accepted.content.modules[0].blocks[1] == original.modules[0].blocks[1]
    assert accepted.content.modules[1:] == original.modules[1:]


def test_whole_document_current_behavior_and_explicit_acceptance(repo):
    original = sample()
    draft = repo.create("owner", original)
    request = OperationRequest(
        task="revise",
        scope="document",
        moduleId="m1",
        instruction="Simplify",
        expectedRevision=1,
        key=uuid4().hex,
    )
    operation, _ = repo.start_operation(draft.id, "owner", request)
    calls = []

    def complete(*args, **kwargs):
        calls.append(kwargs["context"]["module"])
        return SimpleNamespace(
            content=RevisionResponse(
                replacements=[s + " Revised." for s in kwargs["context"]["originalTexts"]],
                summary="Simplified",
            )
        )

    jobs = WorkflowJobs(repo, lambda: SimpleNamespace(complete=complete))
    jobs.run(draft.id, "owner", operation["id"])
    assert repo.get(draft.id, "owner").content == original
    accepted = repo.accept_operation(draft.id, "owner", operation["id"], 1, jobs.apply)
    assert calls == ["Listening", "Follow up"]
    assert accepted.content.modules[2] == original.modules[2]
    assert accepted.content.modules[0].blocks[1] == original.modules[0].blocks[1]
    assert accepted.content.modules[1].blocks[0].text == "Confirm next steps. Revised."


def test_legacy_whole_document_suggestion_cannot_modify_excluded_module():
    import pytest

    from app.core.exceptions import ConflictError

    content = sample()
    request = OperationRequest(
        task="revise",
        scope="document",
        moduleId="m1",
        instruction="Simplify",
        expectedRevision=1,
        key=uuid4().hex,
    )
    legacy = {
        "request": request.model_dump(),
        "result": {
            "changes": [
                {
                    "moduleId": "m3",
                    "blockId": "b3",
                    "originalText": "Excluded notes.",
                    "replacementText": "Changed notes.",
                }
            ]
        },
    }
    with pytest.raises(ConflictError, match="excluded module"):
        WorkflowJobs.apply(content, legacy)
    assert content.modules[2].blocks[0].text == "Excluded notes."
