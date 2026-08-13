"""Hub SSO launch and session endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from starlette.responses import RedirectResponse

from app.schemas.common import ApiSchema
from app.security.hub_launch import OPEN_THROUGH_HUB, HubApp, hub_launch_verifier

router = APIRouter(prefix="/api/hub", tags=["hub"])


class HubSessionResponse(ApiSchema):
    authenticated: bool
    app: Literal["trainer", "employee"] | None = None
    app_key: str | None = None
    app_id: int | None = None
    sub: int | None = None
    email: str | None = None
    exp: int | None = None


def _launch(request: Request, app: HubApp) -> RedirectResponse:
    token = request.query_params.get("hub_launch_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=OPEN_THROUGH_HUB)
    session = hub_launch_verifier.verify(token, app)
    if session is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=OPEN_THROUGH_HUB)
    response = RedirectResponse("/", status_code=302)
    hub_launch_verifier.set_cookie(response, app, token)
    return response


def _session(request: Request, app: HubApp) -> HubSessionResponse:
    session = hub_launch_verifier.session_from_request(request, app)
    if session is None:
        return HubSessionResponse(authenticated=False)
    request.state.hub_user = session.as_response()
    return HubSessionResponse.model_validate(session.as_response())


def _logout(app: HubApp) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    hub_launch_verifier.clear_cookie(response, app)
    return response


@router.get("/launch/trainer")
def launch_trainer(request: Request) -> RedirectResponse:
    return _launch(request, "trainer")


@router.get("/launch/employee")
def launch_employee(request: Request) -> RedirectResponse:
    return _launch(request, "employee")


@router.get("/session/trainer", response_model=HubSessionResponse)
def trainer_session(request: Request) -> HubSessionResponse:
    return _session(request, "trainer")


@router.get("/session/employee", response_model=HubSessionResponse)
def employee_session(request: Request) -> HubSessionResponse:
    return _session(request, "employee")


@router.post("/logout/trainer", status_code=status.HTTP_204_NO_CONTENT)
def logout_trainer() -> Response:
    return _logout("trainer")


@router.post("/logout/employee", status_code=status.HTTP_204_NO_CONTENT)
def logout_employee() -> Response:
    return _logout("employee")
