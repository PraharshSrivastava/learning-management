"""Hub launch-token verification and request gating."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.settings import Settings, settings

HubApp = Literal["trainer", "employee"]

OPEN_THROUGH_HUB = "Open this application from the Hub dashboard."


@dataclass(frozen=True)
class HubSession:
    app: HubApp
    app_key: str
    app_id: int | None
    sub: int
    email: str
    exp: int

    @classmethod
    def from_payload(cls, app: HubApp, payload: dict) -> "HubSession":
        return cls(
            app=app,
            app_key=str(payload["app_key"]),
            app_id=int(payload["app_id"]) if payload.get("app_id") is not None else None,
            sub=int(payload["sub"]),
            email=str(payload["email"]),
            exp=int(payload["exp"]),
        )

    def as_response(self) -> dict[str, object]:
        return {
            "authenticated": True,
            "app": self.app,
            "app_key": self.app_key,
            "app_id": self.app_id,
            "sub": self.sub,
            "email": self.email,
            "exp": self.exp,
        }


def _b64decode(value: str) -> bytes:
    value += "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value.encode("ascii"))


class HubLaunchVerifier:
    def __init__(self, config: Settings = settings):
        self.config = config

    def app_key(self, app: HubApp) -> str:
        if app == "trainer":
            return self.config.hub_trainer_app_key
        return self.config.hub_employee_app_key

    def cookie_name(self, app: HubApp) -> str:
        if app == "trainer":
            return self.config.hub_trainer_cookie_name
        return self.config.hub_employee_cookie_name

    def verify(self, token: str, app: HubApp) -> HubSession | None:
        if not self.config.hub_launch_secret or "." not in token:
            return None
        payload_b64, sig_b64 = token.rsplit(".", 1)
        expected = hmac.new(
            self.config.hub_launch_secret.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        try:
            actual = _b64decode(sig_b64)
            payload = json.loads(_b64decode(payload_b64))
        except (ValueError, TypeError, json.JSONDecodeError):
            return None
        if not hmac.compare_digest(actual, expected):
            return None
        if payload.get("app_key") != self.app_key(app):
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if not payload.get("email") or payload.get("sub") is None:
            return None
        return HubSession.from_payload(app, payload)

    def session_from_request(self, request: Request, app: HubApp) -> HubSession | None:
        if self.config.hub_launch_dev_mode:
            return HubSession(
                app=app,
                app_key=self.app_key(app),
                app_id=None,
                sub=0,
                email="local-dev@phillipcapital.in",
                exp=int(time.time()) + self.config.hub_launch_session_seconds,
            )
        token = request.cookies.get(self.cookie_name(app))
        if not token:
            return None
        return self.verify(token, app)

    def require_session(self, request: Request, app: HubApp) -> HubSession:
        if not self.config.hub_launch_secret and not self.config.hub_launch_dev_mode:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=OPEN_THROUGH_HUB,
            )
        session = self.session_from_request(request, app)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=OPEN_THROUGH_HUB,
            )
        request.state.hub_user = session.as_response()
        return session

    def set_cookie(self, response: Response, app: HubApp, token: str) -> None:
        response.set_cookie(
            self.cookie_name(app),
            token,
            max_age=self.config.hub_launch_session_seconds,
            httponly=True,
            samesite="lax",
            secure=self.config.hub_cookie_secure,
        )

    def clear_cookie(self, response: Response, app: HubApp) -> None:
        response.delete_cookie(
            self.cookie_name(app),
            httponly=True,
            samesite="lax",
            secure=self.config.hub_cookie_secure,
        )


hub_launch_verifier = HubLaunchVerifier()


def hub_app_from_header(value: str | None) -> HubApp | None:
    normalized = (value or "").strip().lower()
    if normalized in {"trainer", "employee"}:
        return normalized  # type: ignore[return-value]
    return None


class HubLaunchMiddleware(BaseHTTPMiddleware):
    """Protect API requests that arrive from the trainer or employee app."""

    def __init__(self, app, verifier: HubLaunchVerifier = hub_launch_verifier):
        super().__init__(app)
        self.verifier = verifier
        self.public_api_paths = {
            "/api/hub/launch/trainer",
            "/api/hub/launch/employee",
            "/api/hub/session/trainer",
            "/api/hub/session/employee",
            "/api/hub/logout/trainer",
            "/api/hub/logout/employee",
        }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or path == "/health"
            or path in self.public_api_paths
        ):
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)

        app = hub_app_from_header(request.headers.get("x-lms-app"))
        if app is None:
            return JSONResponse({"detail": OPEN_THROUGH_HUB}, status_code=403)
        if not self.configured:
            return JSONResponse({"detail": OPEN_THROUGH_HUB}, status_code=403)

        session = self.verifier.session_from_request(request, app)
        if session is None:
            return JSONResponse({"detail": OPEN_THROUGH_HUB}, status_code=403)
        request.state.hub_user = session.as_response()
        return await call_next(request)

    @property
    def configured(self) -> bool:
        return (
            bool(self.verifier.config.hub_launch_secret)
            or self.verifier.config.hub_launch_dev_mode
        )
