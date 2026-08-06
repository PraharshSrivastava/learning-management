"""Course blueprint and authoring endpoints."""

from fastapi import APIRouter, Header, Response

from app.schemas.course import CourseResponse, CourseUpdateRequest, GenerateCourseRequest
from app.schemas.quiz import ManualQuizRequest
from app.services.auth import current_trainer
from app.services.courses import CourseService

router = APIRouter(prefix="/api/courses", tags=["courses"])
service = CourseService()


@router.post("/generate", response_model=CourseResponse)
def generate_course(request: GenerateCourseRequest, authorization: str | None = Header(default=None)):
    trainer = current_trainer(authorization)
    return service.generate_outline(request.file_name, trainer["trainer_id"])


@router.get("", response_model=list[CourseResponse])
def list_courses(response: Response, authorization: str | None = Header(default=None)):
    trainer = current_trainer(authorization)
    response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache", "Expires": "0"})
    return service.list_courses(trainer["trainer_id"])


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    payload: CourseUpdateRequest,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer(authorization)
    return service.update_course(course_id, payload, trainer["trainer_id"])


@router.put("/{course_id}/modules/{module_number}/quiz", response_model=CourseResponse)
def update_module_quiz(
    course_id: str,
    module_number: int,
    payload: ManualQuizRequest,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer(authorization)
    return service.update_module_quiz(course_id, module_number, payload, trainer["trainer_id"])
