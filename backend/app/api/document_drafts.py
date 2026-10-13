"""Feature-gated draft foundation; model operations are added in later phases."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.settings import settings
from app.repositories.document_drafts import DocumentDraftRepository
from app.schemas.document_workflow import (
    DraftContent,
    DraftRecord,
    ImageBlock,
    RestoreDraft,
    RevisionRequest,
    SaveDraft,
)
from app.services.auth import current_trainer_from_request


def _enabled():
    if not settings.document_builder_workflow_enabled:
        raise HTTPException(status_code=404, detail="Document workflow is not enabled")


router = APIRouter(
    prefix="/api/document-builder/drafts",
    tags=["document-workflow"],
    dependencies=[Depends(_enabled)],
)
repository = DocumentDraftRepository()


def _owner(request: Request, authorization: str | None):
    return current_trainer_from_request(request, authorization)["trainer_id"]


def _manual_content(content: DraftContent):
    # Until source/asset catalogs land, clients cannot claim owned provenance or
    # attach an arbitrary file path/URL. Reject rather than persisting fake IDs.
    if len(content.model_dump_json().encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=422, detail="Document exceeds the draft size limit")
    for module in content.modules:
        if module.sourceReferences or any(isinstance(block, ImageBlock) for block in module.blocks):
            raise HTTPException(
                status_code=422, detail="Source and image attachment is not enabled yet"
            )
        if module.status in {"generating", "failed"}:
            raise HTTPException(
                status_code=422, detail="Generation status is controlled by the server"
            )


@router.post("", response_model=DraftRecord, status_code=201)
def create_draft(
    payload: DraftContent, request: Request, authorization: str | None = Header(default=None)
):
    owner = _owner(request, authorization)
    _manual_content(payload)
    return repository.create(owner, payload)


@router.get("")
def list_drafts(request: Request, authorization: str | None = Header(default=None)):
    return repository.list(_owner(request, authorization))


@router.get("/{draft_id}", response_model=DraftRecord)
def get_draft(draft_id: str, request: Request, authorization: str | None = Header(default=None)):
    return repository.get(draft_id, _owner(request, authorization))


@router.patch("/{draft_id}", response_model=DraftRecord)
def save_draft(
    draft_id: str,
    payload: SaveDraft,
    request: Request,
    authorization: str | None = Header(default=None),
):
    owner = _owner(request, authorization)
    _manual_content(payload.content)
    return repository.save(draft_id, owner, payload.expectedRevision, payload.content)


@router.post("/{draft_id}/approve-outline", response_model=DraftRecord)
def approve_outline(
    draft_id: str,
    payload: RevisionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.approve(draft_id, _owner(request, authorization), payload.expectedRevision)


@router.get("/{draft_id}/revisions")
def list_revisions(
    draft_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return repository.revisions(draft_id, _owner(request, authorization))


@router.post("/{draft_id}/restore", response_model=DraftRecord)
def restore_draft(
    draft_id: str,
    payload: RestoreDraft,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.restore(
        draft_id, _owner(request, authorization), payload.expectedRevision, payload.restoreRevision
    )
