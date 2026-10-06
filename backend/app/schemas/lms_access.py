"""Capability discovery contracts; no client-supplied role requests."""

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiSchema


class LmsCapabilities(ApiSchema):
    can_learn: bool = False
    can_author_courses: bool = False
    can_view_all_performance: bool = False
    can_view_other_trainers_courses: bool = False
    can_manage_other_trainers_courses: bool = False
    can_view_department_performance: bool = False
    can_view_observed_performance: bool = False


class LmsAccessResponse(ApiSchema):
    employee_id: str
    trainer_id: str | None = None
    name: str
    app: Literal["trainer", "employee"]
    roles: list[str] = Field(default_factory=list)
    permissions_version: int
    capabilities: LmsCapabilities
    performance_views: list[str] = Field(default_factory=list)
