"""Admin endpoints for Hub directory import."""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import Field

from app.core.exceptions import AuthenticationError, DomainValidationError
from app.core.settings import settings
from app.repositories.employees import list_sync_states
from app.schemas.common import ApiSchema
from app.services.directory_sync import bootstrap_full_directory, sync_directory_changes

router = APIRouter(prefix="/api/directory", tags=["directory"])


class DirectorySyncResponse(ApiSchema):
    mode: str
    pages: int = 0
    received: int = 0
    upserted: int = 0
    changed_employee_ids: list[str] = Field(default_factory=list)
    next_after_id: int | None = None
    has_more: bool = False
    history_complete_from: str | None = None
    managers_resolved: int = 0


class DirectorySyncStateResponse(ApiSchema):
    job_name: str
    cursor: int = 0
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None
    stats_json: dict = Field(default_factory=dict)


class DirectorySyncStatusResponse(ApiSchema):
    enabled: bool
    interval_hours: float
    page_limit: int
    configured: bool
    states: list[DirectorySyncStateResponse] = Field(default_factory=list)


def _require_admin_key(x_directory_sync_key: str | None) -> None:
    if not settings.directory_sync_admin_key:
        raise DomainValidationError("DIRECTORY_SYNC_ADMIN_KEY is not configured")
    if x_directory_sync_key != settings.directory_sync_admin_key:
        raise AuthenticationError("Invalid directory sync key")


@router.get("/sync/status", response_model=DirectorySyncStatusResponse)
def sync_status(x_directory_sync_key: str | None = Header(default=None)):
    _require_admin_key(x_directory_sync_key)
    return {
        "enabled": settings.directory_sync_enabled,
        "interval_hours": settings.directory_sync_interval_hours,
        "page_limit": settings.directory_sync_page_limit,
        "configured": bool(settings.directory_exports_base_url and settings.directory_exports_api_key),
        "states": list_sync_states(),
    }


@router.post("/sync/full", response_model=DirectorySyncResponse)
def full_sync(x_directory_sync_key: str | None = Header(default=None)):
    _require_admin_key(x_directory_sync_key)
    return bootstrap_full_directory()


@router.post("/sync/incremental", response_model=DirectorySyncResponse)
def incremental_sync(
    after_id: int | None = None,
    x_directory_sync_key: str | None = Header(default=None),
):
    _require_admin_key(x_directory_sync_key)
    return sync_directory_changes(after_id=after_id)
