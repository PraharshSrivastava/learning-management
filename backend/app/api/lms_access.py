"""Audience-specific permission discovery using existing authentication."""

from fastapi import APIRouter, Header, Request

from app.schemas.lms_access import LmsAccessResponse
from app.security.hub_launch import HubApp
from app.services.lms_access import current_lms_access

router = APIRouter(prefix="/api/lms", tags=["lms-access"])


@router.get("/me", response_model=LmsAccessResponse)
def lms_me(request: Request, app: HubApp, authorization: str | None = Header(default=None)):
    return current_lms_access(request, authorization, app)
