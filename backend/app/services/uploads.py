"""PDF upload storage operations independent of HTTP routing."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import BinaryIO

from app.repositories.documents import (
    get_document_by_file_name,
    list_documents,
    save_document,
)
from app.schemas.files import StoredFileResponse, UploadResponse


class UploadService:
    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir.resolve()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        basename = os.path.basename(filename)
        return re.sub(r"[^A-Za-z0-9._-]", "_", basename) or "unnamed.pdf"

    def _trainer_filename(self, trainer_id: str, filename: str) -> str:
        return f"{self.sanitize_filename(trainer_id)}__{filename}"

    @staticmethod
    def display_filename(filename: str) -> str:
        return filename.split("__", 1)[1] if "__" in filename else filename

    def save_pdf(
        self, original_name: str | None, source: BinaryIO, trainer_id: str | None = None
    ) -> UploadResponse:
        if not original_name or not original_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")
        filename = self.sanitize_filename(original_name)
        if trainer_id:
            filename = self._trainer_filename(trainer_id, filename)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        path = self.upload_dir / filename
        with path.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        if not trainer_id:
            raise ValueError("A trainer is required to upload a document.")
        document = save_document(trainer_id, filename, filename)
        return UploadResponse(
            document_id=document["document_id"],
            file_name=document["file_name"],
            message="File uploaded successfully",
        )

    def list_pdfs(self, trainer_id: str | None = None) -> list[StoredFileResponse]:
        files = []
        for document in list_documents(trainer_id):
            path = (self.upload_dir / self.sanitize_filename(document["file_path"])).resolve()
            if path.parent != self.upload_dir or not path.is_file() or path.suffix.lower() != ".pdf":
                continue
            stat = path.stat()
            files.append(
                StoredFileResponse(
                    document_id=document["document_id"],
                    file_name=document["file_name"],
                    display_name=self.display_filename(document["file_name"]),
                    size=stat.st_size,
                    created_at=document["created_at"],
                )
            )
        return sorted(files, key=lambda item: item.created_at, reverse=True)

    def pdf_path(self, filename: str) -> Path | None:
        sanitized = self.sanitize_filename(filename)
        if get_document_by_file_name(sanitized) is None:
            return None
        path = (self.upload_dir / sanitized).resolve()
        if path.parent != self.upload_dir or not path.is_file():
            return None
        return path
