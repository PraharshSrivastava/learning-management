"""Course-assignment API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiSchema, RequestSchema
from app.schemas.employee import EmployeeResponse


class AssignmentGroup(ApiSchema):
    employee_ids: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    joined_less_than_days_ago: int | None = Field(default=None, ge=0)


class AssignmentRuleRequest(RequestSchema):
    include_all: bool | None = None
    include_match_mode: Literal["all", "any"] | None = None
    include_groups: list[AssignmentGroup] | None = None
    include_employee_ids: list[str] | None = None
    include_departments: list[str] | None = None
    include_job_titles: list[str] | None = None
    joined_less_than_days_ago: int | None = Field(default=None, ge=0)
    exclude_groups: list[AssignmentGroup] | None = None
    exclude_employee_ids: list[str] | None = None
    exclude_departments: list[str] | None = None
    exclude_job_titles: list[str] | None = None
    deadline_days: int | None = Field(default=None, ge=1)


class AssignmentRuleRecord(ApiSchema):
    course_id: str
    include_all: bool = True
    include_match_mode: Literal["all", "any"] = "all"
    include_groups: list[AssignmentGroup] = Field(default_factory=list)
    include_employee_ids: list[str] = Field(default_factory=list)
    include_departments: list[str] = Field(default_factory=list)
    include_job_titles: list[str] = Field(default_factory=list)
    joined_less_than_days_ago: int | None = Field(default=None, ge=0)
    exclude_groups: list[AssignmentGroup] = Field(default_factory=list)
    exclude_employee_ids: list[str] = Field(default_factory=list)
    exclude_departments: list[str] = Field(default_factory=list)
    exclude_job_titles: list[str] = Field(default_factory=list)
    deadline_days: int = Field(default=7, ge=1)
    applied_deadline_days: int | None = Field(default=None, ge=1)
    published_at: str | None = None
    is_active: bool = True
    disabled_at: str | None = None
    disabled_by_trainer_id: str | None = None
    updated_at: str | None = None


class AssignmentOptionsResponse(ApiSchema):
    departments: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    employees: list[EmployeeResponse] = Field(default_factory=list)


class CourseAssignmentResponse(ApiSchema):
    rule: AssignmentRuleRecord
    match_count: int
    preview_employees: list[EmployeeResponse] = Field(default_factory=list)
    assigned_count: int | None = None
    removed_count: int | None = None
    deadline_update_count: int | None = None
