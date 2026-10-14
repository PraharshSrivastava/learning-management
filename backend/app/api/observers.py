"""Creator-managed course observers; Admin cross-owner reads only."""

from fastapi import APIRouter, Header, Request, Response

from app.repositories import observers, report_access
from app.schemas.observers import ObserverApplyRequest, ObserverConfigResponse, ObserverSaveRequest
from app.services.auth import current_trainer_from_request
from app.services.course_authorization import course_owner_for_read, require_course_creator

router = APIRouter(prefix="/api", tags=["observers"])


@router.get("/observer/options")
def observer_options(request: Request, response: Response, authorization: str | None = Header(default=None)):
    current_trainer_from_request(request, authorization)
    response.headers["Cache-Control"] = "no-store"
    return {"departments": report_access.department_options()}


@router.get("/courses/{course_id}/observers", response_model=ObserverConfigResponse)
def get_observers(course_id: str, request: Request, response: Response, authorization: str | None = Header(default=None)):
    trainer = current_trainer_from_request(request, authorization)
    course_owner_for_read(course_id, trainer)
    response.headers["Cache-Control"] = "no-store"
    return observers.get_config(course_id)


@router.put("/courses/{course_id}/observers", response_model=ObserverConfigResponse)
def save_observers(course_id: str, payload: ObserverSaveRequest, request: Request, authorization: str | None = Header(default=None)):
    trainer = current_trainer_from_request(request, authorization)
    require_course_creator(course_id, trainer)
    return observers.save_config(course_id, trainer["trainer_id"], payload)


@router.post("/courses/{course_id}/observers/apply", response_model=ObserverConfigResponse)
def apply_observers(course_id: str, payload: ObserverApplyRequest, request: Request, authorization: str | None = Header(default=None)):
    trainer = current_trainer_from_request(request, authorization)
    require_course_creator(course_id, trainer)
    return observers.apply_config(course_id, trainer["trainer_id"], payload.revision)
