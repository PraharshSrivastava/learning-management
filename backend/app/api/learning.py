"""Authenticated learner course and progress endpoints."""

from fastapi import APIRouter, Header

from app.schemas.learning import LearnerCourseResponse, ModuleProgressUpdateResponse
from app.schemas.progress import (
    CourseStatusUpdateRequest,
    CourseStatusUpdateResponse,
    ModuleProgressUpdateRequest,
)
from app.services import learning

router = APIRouter(prefix="/api", tags=["learning"])


@router.get("/me/courses", response_model=list[LearnerCourseResponse])
def my_courses(authorization: str | None = Header(default=None)):
    return learning.my_courses(authorization)


router.add_api_websocket_route("/me/courses/ws", learning.websocket_endpoint)


@router.put(
    "/me/courses/{course_id}/status",
    response_model=CourseStatusUpdateResponse,
)
async def update_course_status(
    course_id: str,
    payload: CourseStatusUpdateRequest,
    authorization: str | None = Header(default=None),
):
    return await learning.update_course_status(course_id, payload, authorization)


@router.put(
    "/me/courses/{course_id}/modules/{module_number}",
    response_model=ModuleProgressUpdateResponse,
)
async def update_module_progress(
    course_id: str,
    module_number: str,
    payload: ModuleProgressUpdateRequest,
    authorization: str | None = Header(default=None),
):
    return await learning.update_module_progress(course_id, module_number, payload, authorization)
