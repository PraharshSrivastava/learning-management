"""Bounded authoring library metadata; creator controls are server-derived."""

from app.schemas.common import ApiSchema
from app.schemas.course import CourseResponse, CourseStatus


class CourseLibraryItem(ApiSchema):
    course_id: str
    trainer_id: str
    creator_name: str | None = None
    course_name: str
    course_description: str
    status: CourseStatus
    created_at: str
    updated_at: str
    generation_status: str | None = None
    can_manage: bool
    read_only_reason: str | None = None


class CourseLibraryResponse(ApiSchema):
    items: list[CourseLibraryItem]
    total: int
    limit: int
    offset: int


class CourseInspectionResponse(CourseResponse):
    creator_name: str | None = None
    can_manage: bool
    read_only_reason: str | None = None
