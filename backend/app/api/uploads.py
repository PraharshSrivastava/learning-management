"""PDF, PPTX, and DOCX upload, retrieval, and preview endpoints."""

from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.settings import settings
from app.documents.conversion import DocumentConversionError, convert_office_to_pdf
from app.repositories.documents import get_document_by_file_name
from app.schemas.files import StoredFileResponse, UploadResponse
from app.services.auth import current_trainer
from app.services.uploads import UploadService

router = APIRouter(prefix="/api", tags=["uploads"])
service = UploadService(settings.upload_dir)
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", response_model=UploadResponse)
def upload_file(
    file: UploadFile = File(...), authorization: str | None = Header(default=None)
) -> UploadResponse:
    try:
        trainer = current_trainer(authorization)
        return service.save_document(file.filename, file.file, trainer["trainer_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save file") from exc


@router.get("/files", response_model=list[StoredFileResponse])
def list_files(authorization: str | None = Header(default=None)) -> list[StoredFileResponse]:
    try:
        trainer = current_trainer(authorization)
        return service.list_documents(trainer["trainer_id"])
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to list files") from exc


@router.get("/files/{file_name}", response_class=FileResponse)
def get_file(file_name: str) -> FileResponse:
    path = service.document_path(file_name)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[path.suffix.lower()],
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.get("/files/{file_name}/preview", response_class=FileResponse)
def preview_file(file_name: str) -> FileResponse:
    path = service.document_path(file_name)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    if path.suffix.lower() == ".pdf":
        preview_path = path
    else:
        document = get_document_by_file_name(path.name)
        if document is None:
            raise HTTPException(status_code=404, detail="Document record not found")
        preview_path = Path(settings.derived_document_dir) / f"{document['document_id']}.pdf"
        try:
            preview_path = convert_office_to_pdf(path, preview_path)
        except DocumentConversionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FileResponse(
        preview_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.stem}.pdf"'},
    )
