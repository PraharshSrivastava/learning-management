"""Acceptance boundaries for the simplified product flows."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import ConflictError
from app.document_builder.workflow_export import WorkflowExport
from app.document_builder.workflow_jobs import WorkflowJobs
from app.schemas.document_workflow import (
    AcceptProposal,
    DraftContent,
    DraftMetadata,
    DraftModule,
    OperationRequest,
    TextBlock,
)

pytest_plugins = ["test_document_draft_repository"]


def test_title_only_blank_outline_can_be_approved_without_final_course_metadata(repo):
    draft = repo.create(
        "owner",
        DraftContent(
            entryMode="blank",
            metadata=DraftMetadata(courseName="Onboarding"),
            modules=[DraftModule(id="intro", title="Introduction")],
        ),
    )
    approved = repo.approve(draft.id, "owner", draft.revision)
    assert approved.approvedOutline
    assert approved.content.metadata.missing_fields()  # Final handoff remains incomplete.


def test_import_outline_approval_does_not_require_invented_audience(repo):
    draft = repo.create(
        "owner",
        DraftContent(
            entryMode="existing",
            metadata=DraftMetadata(courseName="Guide"),
            modules=[
                DraftModule(
                    id="intro",
                    title="Introduction",
                    blocks=[TextBlock(id="text", text="Original wording")],
                )
            ],
        ),
    )
    assert repo.approve(draft.id, "owner", draft.revision).approvedOutline


def test_ai_approval_still_requires_audience_and_learning_outcomes(repo):
    draft = repo.create(
        "owner",
        DraftContent(
            entryMode="ai",
            metadata=DraftMetadata(courseName="Training"),
            modules=[DraftModule(id="intro", title="Introduction")],
        ),
    )
    with pytest.raises(ValueError, match="targetAudience"):
        repo.approve(draft.id, "owner", draft.revision)


def test_reviewed_outline_accepts_edited_titles_order_and_objectives(repo):
    draft = repo.create(
        "owner", DraftContent(entryMode="ai", metadata=DraftMetadata(courseName="Training"))
    )
    request = OperationRequest(task="outline", key=uuid4().hex, expectedRevision=draft.revision)
    operation, _ = repo.start_operation(draft.id, "owner", request)
    repo.update_operation(
        draft.id,
        "owner",
        operation["id"],
        status="proposed",
        result={
            "modules": [
                {
                    "title": "Original one",
                    "objective": "Understand one",
                    "sections": ["Explanation"],
                },
                {"title": "Original two", "objective": "Understand two", "sections": ["Practice"]},
            ]
        },
    )
    payload = AcceptProposal(
        expectedRevision=draft.revision,
        outline={
            "modules": [
                {
                    "title": "Reviewed second",
                    "objective": "Practise the second action",
                    "sections": ["Practice"],
                },
                {
                    "title": "Reviewed first",
                    "objective": "Apply the first action",
                    "sections": ["Explanation"],
                },
            ]
        },
    )
    from app.api import document_drafts

    monkey_owner = document_drafts._owner
    monkey_repo = document_drafts.repository
    try:
        document_drafts._owner = lambda *_: "owner"
        document_drafts.repository = repo
        result = document_drafts.accept_proposal(draft.id, operation["id"], payload, None, None)
    finally:
        document_drafts._owner = monkey_owner
        document_drafts.repository = monkey_repo
    assert [m.title for m in result.content.modules] == ["Reviewed second", "Reviewed first"]
    assert result.content.modules[0].objective == "Practise the second action"
    assert result.approvedOutline is None  # Acceptance is not approval.
    assert len({m.id for m in result.content.modules}) == 2


def test_reviewed_outline_rejects_duplicate_titles_and_untrusted_ids():
    outline = {
        "modules": [
            {"title": "One", "objective": "Apply one", "sections": ["Practice"]},
            {"title": "one", "objective": "Apply two", "sections": ["Practice"]},
        ]
    }
    with pytest.raises(ValidationError):
        AcceptProposal(expectedRevision=1, outline=outline)
    outline["modules"][1]["title"] = "Two"
    outline["modules"][0]["id"] = "untrusted"
    with pytest.raises(ValidationError):
        AcceptProposal(expectedRevision=1, outline=outline)


def test_scoped_draft_module_is_proposed_and_applies_only_to_empty_target():
    content = DraftContent(
        entryMode="blank",
        modules=[
            DraftModule(id="empty", title="Empty", blocks=[TextBlock(id="placeholder", text="")]),
            DraftModule(
                id="written",
                title="Written",
                blocks=[TextBlock(id="original", text="Keep my wording")],
            ),
        ],
    )
    operation = {
        "request": OperationRequest(
            task="draft_module",
            moduleId="empty",
            scope="module",
            expectedRevision=1,
            key="request1",
        ).model_dump(),
        "result": {
            "blocks": [{"type": "paragraph", "text": "Proposed draft"}],
            "sourceReferences": [],
        },
    }
    accepted = WorkflowJobs.apply(content.model_copy(deep=True), operation)
    assert not content.modules[0].blocks[0].text
    assert accepted.modules[0].blocks[0].text == "Proposed draft"
    assert accepted.modules[1].blocks[0].text == "Keep my wording"
    operation["request"]["moduleId"] = "written"
    with pytest.raises(ConflictError):
        WorkflowJobs.apply(content.model_copy(deep=True), operation)


def test_preview_accepts_title_only_draft_without_relaxing_course_creation(repo):
    draft = repo.create(
        "owner",
        DraftContent(
            entryMode="blank",
            metadata=DraftMetadata(courseName="Draft guide"),
            modules=[
                DraftModule(
                    id="intro", title="Introduction", blocks=[TextBlock(id="text", text="Welcome")]
                )
            ],
        ),
    )
    assert WorkflowExport(repo).pdf(draft.id, "owner", draft.revision).startswith(b"%PDF")


def test_metadata_changes_invalidate_explicit_approval(repo):
    draft = repo.create(
        "owner",
        DraftContent(
            entryMode="blank",
            metadata=DraftMetadata(courseName="Guide"),
            modules=[DraftModule(id="intro", title="Introduction")],
        ),
    )
    approved = repo.approve(draft.id, "owner", draft.revision)
    content = approved.content.model_copy(deep=True)
    content.metadata.targetAudience = "New employees"
    assert repo.save(draft.id, "owner", approved.revision, content).approvedOutline is None
