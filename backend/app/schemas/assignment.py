"""Course-assignment API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import ApiSchema, RequestSchema
from app.schemas.employee import EmployeeResponse


class AssignmentGroup(ApiSchema):
    saved_group_id: str | None = None
    name: str | None = None
    employee_ids: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    mailing_lists: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    joined_less_than_days_ago: int | None = Field(default=None, ge=0)

    @property
    def has_employee_selection(self) -> bool:
        return bool(self.employee_ids)

    @property
    def has_attribute_filters(self) -> bool:
        return bool(
            self.departments
            or self.mailing_lists
            or self.job_titles
            or self.joined_less_than_days_ago is not None
        )


def _validate_new_assignment_groups(
    groups: list[AssignmentGroup] | None, label: str
) -> None:
    for index, group in enumerate(groups or [], start=1):
        if group.has_employee_selection and group.has_attribute_filters:
            raise ValueError(
                f"{label} group {index} cannot mix specific employees with attribute filters"
            )
        if group.joined_less_than_days_ago == 0:
            raise ValueError(
                f"{label} group {index} joined filter must be at least 1 day"
            )


class AssignmentRuleRequest(RequestSchema):
    include_all: bool | None = None
    include_match_mode: Literal["all", "any"] | None = None
    include_groups: list[AssignmentGroup] | None = None
    include_employee_ids: list[str] | None = None
    include_departments: list[str] | None = None
    include_mailing_lists: list[str] | None = None
    include_job_titles: list[str] | None = None
    joined_less_than_days_ago: int | None = Field(default=None, ge=1)
    exclude_groups: list[AssignmentGroup] | None = None
    exclude_employee_ids: list[str] | None = None
    exclude_departments: list[str] | None = None
    exclude_mailing_lists: list[str] | None = None
    exclude_job_titles: list[str] | None = None
    include_inactive: bool | None = None
    deadline_days: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_group_filters(self):
        _validate_new_assignment_groups(self.include_groups, "Include")
        _validate_new_assignment_groups(self.exclude_groups, "Exclude")
        return self


class AssignmentRuleRecord(ApiSchema):
    course_id: str
    include_all: bool = True
    include_match_mode: Literal["all", "any"] = "all"
    include_groups: list[AssignmentGroup] = Field(default_factory=list)
    include_employee_ids: list[str] = Field(default_factory=list)
    include_departments: list[str] = Field(default_factory=list)
    include_mailing_lists: list[str] = Field(default_factory=list)
    include_job_titles: list[str] = Field(default_factory=list)
    joined_less_than_days_ago: int | None = Field(default=None, ge=0)
    exclude_groups: list[AssignmentGroup] = Field(default_factory=list)
    exclude_employee_ids: list[str] = Field(default_factory=list)
    exclude_departments: list[str] = Field(default_factory=list)
    exclude_mailing_lists: list[str] = Field(default_factory=list)
    exclude_job_titles: list[str] = Field(default_factory=list)
    include_inactive: bool = False
    deadline_days: int = Field(default=7, ge=1)
    applied_deadline_days: int | None = Field(default=None, ge=1)
    published_at: str | None = None
    is_active: bool = True
    disabled_at: str | None = None
    disabled_by_trainer_id: str | None = None
    updated_at: str | None = None


class AssignmentOptionsResponse(ApiSchema):
    departments: list[str] = Field(default_factory=list)
    mailing_lists: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    employees: list[EmployeeResponse] = Field(default_factory=list)


class SavedAssignmentGroupRequest(RequestSchema):
    name: str = Field(min_length=1)
    group_type: Literal["include", "exclude"]
    employee_ids: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    mailing_lists: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    joined_less_than_days_ago: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_group_filters(self):
        group = AssignmentGroup(
            employee_ids=self.employee_ids,
            departments=self.departments,
            mailing_lists=self.mailing_lists,
            job_titles=self.job_titles,
            joined_less_than_days_ago=self.joined_less_than_days_ago,
        )
        _validate_new_assignment_groups([group], "Saved")
        return self


class SavedAssignmentGroupResponse(ApiSchema):
    saved_group_id: str
    trainer_id: str
    name: str
    group_type: Literal["include", "exclude"]
    employee_ids: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    mailing_lists: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    joined_less_than_days_ago: int | None = Field(default=None, ge=0)
    created_at: str | None = None
    updated_at: str | None = None


class CourseAssignmentResponse(ApiSchema):
    rule: AssignmentRuleRecord
    match_count: int
    preview_employees: list[EmployeeResponse] = Field(default_factory=list)
    assigned_count: int | None = None
    removed_count: int | None = None
    reactivated_count: int | None = None
    deadline_update_count: int | None = None
