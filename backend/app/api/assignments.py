"""Course assignment authoring and publication endpoints."""

from typing import Literal

from fastapi import APIRouter, Header, Query, Request, Response

from app.schemas.assignment import (
    AssignmentOptionsResponse,
    AssignmentPreviewRequest,
    AssignmentRuleRequest,
    CourseAssignmentResponse,
    SavedAssignmentGroupRequest,
    SavedAssignmentGroupResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.course import CourseResponse
from app.services.assignments import (
    api_assignable_courses,
    api_assignment_options,
    api_create_saved_assignment_group,
    api_delete_saved_assignment_group,
    api_disable_course_assignment,
    api_get_course_assignment,
    api_publish_course_assignment,
    api_save_course_assignment,
    api_saved_assignment_groups,
    api_update_saved_assignment_group,
    assignment_employee_page,
)
from app.services.auth import current_trainer_from_request
from app.services.course_authorization import course_owner_for_read, require_course_creator

router = APIRouter(prefix="/api", tags=["assignments"])


@router.get("/assignment/options", response_model=AssignmentOptionsResponse)
def assignment_options(
    request: Request, response: Response, authorization: str | None = Header(default=None)
):
    current_trainer_from_request(request, authorization)
    response.headers["Cache-Control"] = "no-store"
    return api_assignment_options()


@router.get(
    "/assignment/saved-groups", response_model=list[SavedAssignmentGroupResponse]
)
def saved_assignment_groups(
    request: Request,
    authorization: str | None = Header(default=None),
    group_type: Literal["include", "exclude"] | None = Query(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return api_saved_assignment_groups(trainer["trainer_id"], group_type)


@router.post(
    "/assignment/saved-groups", response_model=SavedAssignmentGroupResponse
)
def create_saved_assignment_group(
    payload: SavedAssignmentGroupRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return api_create_saved_assignment_group(trainer["trainer_id"], payload)


@router.put(
    "/assignment/saved-groups/{saved_group_id}",
    response_model=SavedAssignmentGroupResponse,
)
def update_saved_assignment_group(
    saved_group_id: str,
    payload: SavedAssignmentGroupRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return api_update_saved_assignment_group(
        trainer["trainer_id"], saved_group_id, payload
    )


@router.delete(
    "/assignment/saved-groups/{saved_group_id}", response_model=MessageResponse
)
def delete_saved_assignment_group(
    saved_group_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return api_delete_saved_assignment_group(trainer["trainer_id"], saved_group_id)


@router.get("/assignment/courses", response_model=list[CourseResponse])
def assignable_courses(
    request: Request, authorization: str | None = Header(default=None)
):
    trainer = current_trainer_from_request(request, authorization)
    return api_assignable_courses(trainer["trainer_id"])


@router.get("/courses/{course_id}/assignment", response_model=CourseAssignmentResponse)
def get_course_assignment(
    course_id: str,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    response.headers["Cache-Control"] = "no-store"
    owner_id = course_owner_for_read(course_id, trainer)
    return api_get_course_assignment(course_id, owner_id)


@router.put("/courses/{course_id}/assignment", response_model=CourseAssignmentResponse)
def save_course_assignment(
    course_id: str,
    payload: AssignmentRuleRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    require_course_creator(course_id, trainer)
    return api_save_course_assignment(course_id, payload, trainer["trainer_id"])


@router.post("/courses/{course_id}/publish-assignment", response_model=CourseAssignmentResponse)
def publish_course_assignment(
    course_id: str,
    payload: AssignmentRuleRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    require_course_creator(course_id, trainer)
    return api_publish_course_assignment(course_id, payload, trainer["trainer_id"])


@router.post("/courses/{course_id}/disable-assignment", response_model=CourseAssignmentResponse)
def disable_course_assignment(
    course_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    require_course_creator(course_id, trainer)
    return api_disable_course_assignment(course_id, trainer["trainer_id"])


@router.post("/courses/{course_id}/assignment/employee-preview")
def employee_assignment_preview(course_id: str, payload: AssignmentPreviewRequest, request: Request, response: Response,
    authorization: str | None = Header(default=None), view: Literal["matching", "assigned"] = Query("matching"),
    search: str = Query("", max_length=200), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    trainer = current_trainer_from_request(request, authorization)
    require_course_creator(course_id, trainer)
    response.headers["Cache-Control"] = "no-store"
    return assignment_employee_page(course_id, payload, view, search, page, page_size)
