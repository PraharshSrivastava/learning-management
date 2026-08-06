"""Upload and stored-file API contracts."""

from app.schemas.common import ApiSchema


class UploadResponse(ApiSchema):
    document_id: str
    file_name: str
    message: str


class StoredFileResponse(ApiSchema):
    document_id: str
    file_name: str
    display_name: str | None = None
    size: int
    created_at: str
