"""Feature-gated draft foundation; model operations are added in later phases."""

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response

from app.core.settings import settings
from app.document_builder.import_source import SourceImporter
from app.document_builder.workflow_export import WorkflowExport, owned_path
from app.document_builder.workflow_jobs import WorkflowJobs
from app.repositories.document_drafts import DocumentDraftRepository
from app.schemas.document_workflow import (
    AcceptProposal,
    CopyDraft,
    DraftContent,
    DraftRecord,
    ImageBlock,
    ImportRequest,
    OperationRequest,
    RestoreDraft,
    RevisionRequest,
    SaveDraft,
    SourceAcknowledgement,
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
jobs = WorkflowJobs(repository)
exports = WorkflowExport(repository)


@router.post("/{draft_id}/assets", status_code=201)
def upload_asset(
    draft_id: str,
    request: Request,
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    from io import BytesIO
    from uuid import uuid4

    from PIL import Image

    owner = _owner(request, authorization)
    repository.get(draft_id, owner)
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Image exceeds 10 MB")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 25000000:
                raise ValueError("Image dimensions exceed the limit")
            asset_id = uuid4().hex
            path = (
                settings.derived_document_dir
                / "builder"
                / draft_id
                / "manual"
                / (asset_id + ".png")
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(path, "PNG")
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=422, detail="Unsupported or oversized image") from exc
    repository.put_resource(
        draft_id,
        owner,
        asset_id,
        "asset",
        {"path": str(path), "mime": "image/png", "caption": file.filename or "Image"},
    )
    return {"assetId": asset_id}


def _owner(request: Request, authorization: str | None):
    return current_trainer_from_request(request, authorization)["trainer_id"]


def _manual_content(content: DraftContent):
    # Until source/asset catalogs land, clients cannot claim owned provenance or
    # attach an arbitrary file path/URL. Reject rather than persisting fake IDs.
    if len(content.model_dump_json().encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=422, detail="Document exceeds the draft size limit")
    for module in content.modules:
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
    if any(
        module.sourceReferences
        or any(isinstance(block, ImageBlock) or block.sourceReferences for block in module.blocks)
        for module in payload.modules
    ):
        raise HTTPException(
            status_code=422, detail="Attach owned sources/images after creating the draft"
        )
    return repository.create(owner, payload)


@router.get("")
def list_drafts(request: Request, authorization: str | None = Header(default=None)):
    return repository.list(_owner(request, authorization))


@router.post("/{draft_id}/remove", status_code=204)
def remove_draft(
    draft_id: str,
    payload: RevisionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    repository.remove(draft_id, _owner(request, authorization), payload.expectedRevision)
    return Response(status_code=204)


@router.post("/{draft_id}/undo-remove", response_model=DraftRecord)
def undo_remove_draft(
    draft_id: str,
    payload: RevisionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.undo_remove(
        draft_id, _owner(request, authorization), payload.expectedRevision
    )


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
    repository.validate_resources(draft_id, owner, payload.content)
    return repository.save(draft_id, owner, payload.expectedRevision, payload.content)


@router.post("/{draft_id}/copy", response_model=DraftRecord, status_code=201)
def copy_draft(
    draft_id: str,
    payload: CopyDraft,
    request: Request,
    authorization: str | None = Header(default=None),
):
    _manual_content(payload.content)
    return repository.copy(draft_id, _owner(request, authorization), payload.content)


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


@router.post("/{draft_id}/import", response_model=DraftRecord)
def import_source(
    draft_id: str,
    payload: ImportRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return SourceImporter(repository).load(draft_id, _owner(request, authorization), payload)


@router.get("/{draft_id}/sources")
def list_sources(draft_id: str, request: Request, authorization: str | None = Header(default=None)):
    return [
        {key: value for key, value in source.items() if key not in {"path", "kind"}}
        for source in repository.resources(draft_id, _owner(request, authorization), "source")
    ]


@router.post("/{draft_id}/sources/{source_id}/acknowledge", response_model=DraftRecord)
def acknowledge_source(
    draft_id: str,
    source_id: str,
    payload: SourceAcknowledgement,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.acknowledge(
        draft_id,
        _owner(request, authorization),
        source_id,
        payload.expectedRevision,
        payload.acknowledged,
    )


@router.get("/{draft_id}/assets/{asset_id}")
def get_asset(
    draft_id: str, asset_id: str, request: Request, authorization: str | None = Header(default=None)
):
    resource = next(
        (
            r
            for r in repository.resources(draft_id, _owner(request, authorization), "asset")
            if r["id"] == asset_id
        ),
        None,
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Document image not found")
    return FileResponse(
        owned_path(resource),
        media_type=resource["mime"],
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{draft_id}/sources/{source_id}/original")
def get_original(
    draft_id: str,
    source_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    resource = next(
        (
            r
            for r in repository.resources(draft_id, _owner(request, authorization), "source")
            if r["id"] == source_id
        ),
        None,
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Source not found")
    return FileResponse(
        owned_path(resource),
        filename=resource["name"],
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/{draft_id}/operations", status_code=202)
def start_operation(
    draft_id: str,
    payload: OperationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return jobs.start(draft_id, _owner(request, authorization), payload)


@router.get("/{draft_id}/operations")
def list_operations(
    draft_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return repository.operations(draft_id, _owner(request, authorization))


@router.get("/{draft_id}/operations/{operation_id}")
def get_operation(
    draft_id: str,
    operation_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.operation(draft_id, _owner(request, authorization), operation_id)


@router.post("/{draft_id}/operations/{operation_id}/cancel")
def cancel_operation(
    draft_id: str,
    operation_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.update_operation(
        draft_id, _owner(request, authorization), operation_id, status="cancelled"
    )


@router.post("/{draft_id}/proposals/{operation_id}/accept", response_model=DraftRecord)
def accept_proposal(
    draft_id: str,
    operation_id: str,
    payload: AcceptProposal,
    request: Request,
    authorization: str | None = Header(default=None),
):
    def apply_reviewed(content, operation):
        if payload.outline is not None:
            if operation["request"]["task"] != "outline":
                raise ValueError("Edited outline is valid only for an outline proposal")
            operation = {**operation, "result": payload.outline.model_dump()}
        return jobs.apply(content, operation)

    return repository.accept_operation(
        draft_id,
        _owner(request, authorization),
        operation_id,
        payload.expectedRevision,
        apply_reviewed,
    )


@router.post("/{draft_id}/proposals/{operation_id}/reject")
def reject_proposal(
    draft_id: str,
    operation_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return repository.update_operation(
        draft_id, _owner(request, authorization), operation_id, status="rejected"
    )


@router.post("/{draft_id}/render-pdf")
def render_draft(
    draft_id: str,
    payload: RevisionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return Response(
        exports.pdf(draft_id, _owner(request, authorization), payload.expectedRevision),
        media_type="application/pdf",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/{draft_id}/create-course")
def create_course(
    draft_id: str,
    payload: RevisionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return exports.create_course(draft_id, _owner(request, authorization), payload.expectedRevision)
