"""Course assignment authoring and publication endpoints."""

from fastapi import APIRouter, Header

from app.schemas.assignment import (
    AssignmentOptionsResponse,
    AssignmentRuleRequest,
    CourseAssignmentResponse,
)
from app.schemas.course import CourseResponse
from app.services.auth import current_trainer
from app.services.assignments import (
    api_assignable_courses,
    api_assignment_options,
    api_disable_course_assignment,
    api_get_course_assignment,
    api_publish_course_assignment,
    api_save_course_assignment,
)

router = APIRouter(prefix="/api", tags=["assignments"])
router.add_api_route(
    "/assignment/options",
    api_assignment_options,
    methods=["GET"],
    response_model=AssignmentOptionsResponse,
)

@router.get("/assignment/courses", response_model=list[CourseResponse])
def assignable_courses(authorization: str | None = Header(default=None)):
    trainer = current_trainer(authorization)
    return api_assignable_courses(trainer["trainer_id"])


@router.get("/courses/{course_id}/assignment", response_model=CourseAssignmentResponse)
def get_course_assignment(course_id: str, authorization: str | None = Header(default=None)):
    trainer = current_trainer(authorization)
    return api_get_course_assignment(course_id, trainer["trainer_id"])


@router.put("/courses/{course_id}/assignment", response_model=CourseAssignmentResponse)
def save_course_assignment(
    course_id: str,
    payload: AssignmentRuleRequest,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer(authorization)
    return api_save_course_assignment(course_id, payload, trainer["trainer_id"])


@router.post("/courses/{course_id}/publish-assignment", response_model=CourseAssignmentResponse)
def publish_course_assignment(
    course_id: str,
    payload: AssignmentRuleRequest,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer(authorization)
    return api_publish_course_assignment(course_id, payload, trainer["trainer_id"])


@router.post("/courses/{course_id}/disable-assignment", response_model=CourseAssignmentResponse)
def disable_course_assignment(course_id: str, authorization: str | None = Header(default=None)):
    trainer = current_trainer(authorization)
    return api_disable_course_assignment(course_id, trainer["trainer_id"])
