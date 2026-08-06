"""PDF upload and retrieval endpoints."""

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.settings import settings
from app.schemas.files import StoredFileResponse, UploadResponse
from app.services.auth import current_trainer
from app.services.uploads import UploadService

router = APIRouter(prefix="/api", tags=["uploads"])
service = UploadService(settings.upload_dir)


@router.post("/upload", response_model=UploadResponse)
def upload_file(
    file: UploadFile = File(...), authorization: str | None = Header(default=None)
) -> UploadResponse:
    try:
        trainer = current_trainer(authorization)
        return service.save_pdf(file.filename, file.file, trainer["trainer_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save file") from exc


@router.get("/files", response_model=list[StoredFileResponse])
def list_files(authorization: str | None = Header(default=None)) -> list[StoredFileResponse]:
    try:
        trainer = current_trainer(authorization)
        return service.list_pdfs(trainer["trainer_id"])
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to list files") from exc


@router.get("/files/{file_name}", response_class=FileResponse)
def get_file(file_name: str) -> FileResponse:
    path = service.pdf_path(file_name)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )
