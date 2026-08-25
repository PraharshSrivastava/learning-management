"""Course blueprint and authoring endpoints."""

from fastapi import APIRouter, Header, Request, Response

from app.schemas.course import (
    CourseResponse,
    CourseSummaryResponse,
    CourseUpdateRequest,
    GenerateCourseRequest,
)
from app.schemas.quiz import ManualQuizRequest
from app.services.auth import current_trainer_from_request
from app.services.courses import CourseService

router = APIRouter(prefix="/api/courses", tags=["courses"])
service = CourseService()


@router.post("/generate", response_model=CourseResponse)
def generate_course(
    payload: GenerateCourseRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return service.generate_outline(payload.file_name, trainer["trainer_id"])


@router.get("", response_model=list[CourseSummaryResponse])
def list_courses(
    response: Response,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Expires": "0"})
    return service.list_course_summaries(trainer["trainer_id"])


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: str,
    response: Response,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Expires": "0"})
    return service.get_course(course_id, trainer["trainer_id"])


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    payload: CourseUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return service.update_course(course_id, payload, trainer["trainer_id"])


@router.put("/{course_id}/modules/{module_number}/quiz", response_model=CourseResponse)
def update_module_quiz(
    course_id: str,
    module_number: int,
    payload: ManualQuizRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return service.update_module_quiz(course_id, module_number, payload, trainer["trainer_id"])
