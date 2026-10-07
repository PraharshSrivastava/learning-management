"""Validated public LMS mounts supplied by the private frontend proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from starlette.requests import HTTPConnection

if TYPE_CHECKING:
    from app.security.hub_launch import HubApp

def validated_public_mount(connection: HTTPConnection, app: HubApp) -> str | None:
    """Return the normalized mount path ("/", "/lms/", "/lms/trainer/") or None if invalid."""
    prefix = connection.scope.get("root_path") or connection.headers.get("x-forwarded-prefix", "")
    allowed_prefix = "/lms/trainer" if app == "trainer" else "/lms"
    if prefix not in {"", "/", allowed_prefix, f"{allowed_prefix}/"}:
        return None
    return f"{prefix.rstrip('/')}/"

def lms_public_mount(request: HTTPConnection, app: HubApp) -> str:
    """Return a cookie and redirect path from root_path or the internal proxy prefix."""
    mount = validated_public_mount(request, app)
    if mount is None:
        raise HTTPException(status_code=400, detail="Invalid LMS public mount")
    return mount
