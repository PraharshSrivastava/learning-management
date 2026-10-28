"""Learning Journey endpoints for the Trainer app (authoring) and the Employee app (learning)."""

from fastapi import APIRouter, Header, Request, Response

from app.schemas.common import MessageResponse
from app.schemas.journey import (
    JourneyCreateRequest,
    JourneyDetailResponse,
    JourneyListResponse,
    JourneyObserversRequest,
    JourneyPreviewRequest,
    JourneySaveRequest,
    LearnerJourneyListResponse,
)
from app.services import journey_certificates, journeys
from app.services.auth import current_employee_from_request, current_trainer_from_request

router = APIRouter(prefix="/api", tags=["learning-journeys"])


def _trainer_id(request: Request, authorization: str | None) -> str:
    return current_trainer_from_request(request, authorization)["trainer_id"]


@router.get("/learning-journeys", response_model=JourneyListResponse)
def list_journeys(
    request: Request, response: Response, authorization: str | None = Header(default=None)
):
    trainer_id = _trainer_id(request, authorization)
    response.headers["Cache-Control"] = "no-store"
    return journeys.api_list_journeys(trainer_id)


@router.post("/learning-journeys", response_model=JourneyDetailResponse)
def create_journey(
    payload: JourneyCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return journeys.api_create_journey(_trainer_id(request, authorization), payload)


@router.get("/learning-journeys/course-options", response_model=list[dict])
def course_options(request: Request, authorization: str | None = Header(default=None)):
    return journeys.api_course_options(_trainer_id(request, authorization))


@router.get("/learning-journeys/certificates/{number}", response_model=dict)
def verify_certificate(number: str, request: Request, authorization: str | None = Header(default=None)):
    _trainer_id(request, authorization)
    journeys._require_enabled()
    return journey_certificates.verify_certificate(number)


@router.get("/learning-journeys/{journey_id}", response_model=JourneyDetailResponse)
def get_journey(
    journey_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return journeys.api_get_journey(journey_id, _trainer_id(request, authorization))


@router.put("/learning-journeys/{journey_id}", response_model=JourneyDetailResponse)
def save_journey(
    journey_id: str,
    payload: JourneySaveRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return journeys.api_save_journey(journey_id, _trainer_id(request, authorization), payload)


@router.delete("/learning-journeys/{journey_id}", response_model=MessageResponse)
def delete_journey(
    journey_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return journeys.api_delete_journey(journey_id, _trainer_id(request, authorization))


@router.post("/learning-journeys/{journey_id}/preview", response_model=dict)
def preview_journey(
    journey_id: str,
    request: Request,
    payload: JourneyPreviewRequest | None = None,
    authorization: str | None = Header(default=None),
):
    return journeys.api_preview_journey(journey_id, _trainer_id(request, authorization), payload)


@router.post("/learning-journeys/{journey_id}/duplicate", response_model=JourneyDetailResponse)
def duplicate_journey(
    journey_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return journeys.api_duplicate_journey(journey_id, _trainer_id(request, authorization))


@router.post("/learning-journeys/{journey_id}/publish", response_model=JourneyDetailResponse)
def publish_journey(
    journey_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return journeys.api_publish_journey(journey_id, _trainer_id(request, authorization))


@router.post("/learning-journeys/{journey_id}/disable", response_model=JourneyDetailResponse)
def disable_journey(
    journey_id: str, request: Request, authorization: str | None = Header(default=None)
):
    return journeys.api_disable_journey(journey_id, _trainer_id(request, authorization))


@router.get("/learning-journeys/{journey_id}/observers", response_model=dict)
def get_journey_observers(
    journey_id: str, request: Request, response: Response, authorization: str | None = Header(default=None)
):
    response.headers["Cache-Control"] = "no-store"
    return journeys.api_get_journey_observers(journey_id, _trainer_id(request, authorization))


@router.put("/learning-journeys/{journey_id}/observers", response_model=dict)
def save_journey_observers(
    journey_id: str,
    payload: JourneyObserversRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return journeys.api_save_journey_observers(journey_id, _trainer_id(request, authorization), payload)


@router.get("/me/learning-journeys", response_model=LearnerJourneyListResponse)
def my_journeys(
    request: Request, response: Response, authorization: str | None = Header(default=None)
):
    employee = current_employee_from_request(request, authorization)
    response.headers["Cache-Control"] = "no-store"
    return journeys.api_my_journeys(employee)


def _pdf(filename: str, content: bytes) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/me/learning-journeys/{journey_id}/certificate")
def my_certificate(
    journey_id: str, request: Request, authorization: str | None = Header(default=None)
):
    employee = current_employee_from_request(request, authorization)
    journeys._require_enabled()
    return _pdf(*journey_certificates.learner_certificate(employee["employee_id"], journey_id))
