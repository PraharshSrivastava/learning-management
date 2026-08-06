"""Explicitly allowlisted root-level public assets."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.settings import settings

router = APIRouter(tags=["static"])


@router.get("/assets/slides.css", include_in_schema=False, response_class=FileResponse)
def slide_stylesheet() -> FileResponse:
    return FileResponse(settings.template_dir / "slides.css", media_type="text/css")


@router.get("/assets/logo.png", include_in_schema=False, response_class=FileResponse)
def logo() -> FileResponse:
    return FileResponse(settings.static_dir / "brand" / "logo.png", media_type="image/png")
