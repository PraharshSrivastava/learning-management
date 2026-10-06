"""Own library and authenticated Admin Trainer course oversight."""

from typing import Literal

from fastapi import APIRouter, Header, Query, Request, Response

from app.core.exceptions import AuthorizationError
from app.repositories import courses
from app.schemas.course import CourseStatus
from app.schemas.course_library import CourseLibraryResponse
from app.schemas.generation import GenerationStatus
from app.schemas.performance_reporting import AssignmentListReport
from app.services import performance_reporting as reports
from app.services.auth import current_trainer_from_request
from app.services.course_authorization import (
    READ_ONLY_MESSAGE,
    course_owner_for_read,
    is_admin_trainer,
)

router = APIRouter(prefix="/api/trainer", tags=["course-library"])


@router.get("/course-library", response_model=CourseLibraryResponse)
def course_library(
    request: Request, response: Response,
    authorization: str | None = Header(default=None),
    scope: Literal["own", "all"] = "own",
    owner_trainer_id: str | None = Query(default=None, min_length=1),
    status: CourseStatus | None = None,
    generation_status: GenerationStatus | None = None,
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
):
    trainer = current_trainer_from_request(request, authorization)
    trainer_id = trainer["trainer_id"]
    if scope == "all" or (owner_trainer_id is not None and owner_trainer_id != trainer_id):
        if not is_admin_trainer(trainer):
            raise AuthorizationError("Admin Trainer access is required for this course library scope")
    if scope == "own" and owner_trainer_id not in (None, trainer_id):
        raise AuthorizationError("The own library scope cannot select another trainer")
    page = courses.course_library_page(
        owner_id=trainer_id if scope == "own" else owner_trainer_id,
        status=status, generation_status=generation_status, search=search,
        limit=limit, offset=offset,
    )
    for item in page["items"]:
        item["can_manage"] = item["trainer_id"] == trainer_id
        item["read_only_reason"] = None if item["can_manage"] else READ_ONLY_MESSAGE
    response.headers["Cache-Control"] = "no-store"
    return page


@router.get("/course-library/{course_id}/assignments", response_model=AssignmentListReport)
def course_library_assignments(
    course_id: str, request: Request, response: Response,
    authorization: str | None = Header(default=None),
    status: Literal["pending", "started", "completed", "overdue"] | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    trainer = current_trainer_from_request(request, authorization)
    owner_id = course_owner_for_read(course_id, trainer)
    response.headers["Cache-Control"] = "no-store"
    # Use the existing report engine, with a fixed course and explicit owner scope.
    # Draft, disabled and revoked assignments follow existing reporting eligibility.
    return reports.assignment_list(
        owner_id, course_id=course_id, status=status, search=search,
        page=page, page_size=page_size,
    )
