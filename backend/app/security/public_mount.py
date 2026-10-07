"""Validated public LMS mounts supplied by the private frontend proxy."""

from fastapi import HTTPException, Request

from app.security.hub_launch import HubApp


def lms_public_mount(request: Request, app: HubApp) -> str:
    """Return a cookie and redirect path from root_path or the internal proxy prefix."""
    prefix = request.scope.get("root_path") or request.headers.get("x-forwarded-prefix", "")
    allowed_prefix = "/lms/trainer" if app == "trainer" else "/lms"
    if prefix not in {"", "/", allowed_prefix, f"{allowed_prefix}/"}:
        raise HTTPException(status_code=400, detail="Invalid LMS public mount")
    return f"{prefix.rstrip('/')}/"
