"""Integrated scratch document-builder endpoints."""

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import Response

from app.core.settings import settings
from app.services.auth import current_trainer_from_request
from app.services.document_builder import DocumentBuilderService
from app.services.uploads import UploadService

router = APIRouter(prefix="/api/document-builder", tags=["document-builder"])
service = DocumentBuilderService(UploadService(settings.upload_dir))


def _trainer(request: Request, authorization: str | None) -> dict:
    return current_trainer_from_request(request, authorization)


@router.post("/build-document")
def build_document(
    request: Request,
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
) -> dict:
    _trainer(request, authorization)
    try:
        return service.build(payload)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/render-pdf")
def render_document_pdf(
    request: Request,
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
) -> Response:
    _trainer(request, authorization)
    try:
        pdf, filename = service.render(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/save-pdf")
def save_document_pdf(
    request: Request,
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
) -> dict:
    trainer = _trainer(request, authorization)
    try:
        return service.save(payload, trainer["trainer_id"])
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
