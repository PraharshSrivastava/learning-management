"""Document upload storage operations independent of HTTP routing."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import BinaryIO

from app.repositories.documents import get_document_by_file_name
from app.repositories.documents import list_documents as list_document_records
from app.repositories.documents import save_document as save_document_record
from app.schemas.files import StoredFileResponse, UploadResponse

SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx"}


class UploadService:
    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir.resolve()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        basename = os.path.basename(filename)
        return re.sub(r"[^A-Za-z0-9._-]", "_", basename) or "unnamed"

    def _trainer_filename(self, trainer_id: str, filename: str) -> str:
        return f"{self.sanitize_filename(trainer_id)}__{filename}"

    @staticmethod
    def display_filename(filename: str) -> str:
        return filename.split("__", 1)[1] if "__" in filename else filename

    def save_document(
        self, original_name: str | None, source: BinaryIO, trainer_id: str | None = None
    ) -> UploadResponse:
        if not original_name or Path(original_name).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("Only PDF, PPTX, and DOCX files are supported.")
        if not trainer_id:
            raise ValueError("A trainer is required to upload a document.")

        filename = self._trainer_filename(
            trainer_id,
            self.sanitize_filename(original_name),
        )
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        path = self.upload_dir / filename
        with path.open("wb") as destination:
            shutil.copyfileobj(source, destination)

        document = save_document_record(trainer_id, filename, filename)
        return UploadResponse(
            document_id=document["document_id"],
            file_name=document["file_name"],
            message="File uploaded successfully",
        )

    def list_documents(self, trainer_id: str | None = None) -> list[StoredFileResponse]:
        files = []
        for document in list_document_records(trainer_id):
            path = (self.upload_dir / self.sanitize_filename(document["file_path"])).resolve()
            suffix = path.suffix.lower()
            if (
                path.parent != self.upload_dir
                or not path.is_file()
                or suffix not in SUPPORTED_EXTENSIONS
            ):
                continue
            stat = path.stat()
            files.append(
                StoredFileResponse(
                    document_id=document["document_id"],
                    file_name=document["file_name"],
                    display_name=self.display_filename(document["file_name"]),
                    file_type=suffix.lstrip("."),
                    size=stat.st_size,
                    created_at=document["created_at"],
                )
            )
        return sorted(files, key=lambda item: item.created_at, reverse=True)

    def document_path(self, filename: str) -> Path | None:
        sanitized = self.sanitize_filename(filename)
        if Path(sanitized).suffix.lower() not in SUPPORTED_EXTENSIONS:
            return None
        if get_document_by_file_name(sanitized) is None:
            return None
        path = (self.upload_dir / sanitized).resolve()
        if path.parent != self.upload_dir or not path.is_file():
            return None
        return path
