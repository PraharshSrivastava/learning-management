"""Learning Journey API contracts."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.assignment import AssignmentGroup, _validate_new_assignment_groups
from app.schemas.common import ApiSchema, RequestSchema


class JourneyCreateRequest(RequestSchema):
    title: str = Field(default="Untitled journey", min_length=1, max_length=200)


class JourneyStepRequest(RequestSchema):
    course_id: str = Field(min_length=1)
    unlock_rule: Literal["open", "after_previous"] = "after_previous"
    is_required: bool = True


class JourneyStageRequest(RequestSchema):
    title: str = Field(min_length=1, max_length=200)
    steps: list[JourneyStepRequest] = Field(default_factory=list)


class JourneyRuleRequest(RequestSchema):
    """Who gets the journey: the same include/exclude groups and deadline as a course rule."""

    include_all: bool = True
    include_groups: list[AssignmentGroup] = Field(default_factory=list)
    exclude_groups: list[AssignmentGroup] = Field(default_factory=list)
    deadline_mode: Literal["relative", "fixed"] = "relative"
    deadline_days: int = Field(default=30, ge=1, le=3650)
    deadline_date: date | None = None

    @model_validator(mode="after")
    def validate_groups(self):
        _validate_new_assignment_groups(self.include_groups, "Include")
        _validate_new_assignment_groups(self.exclude_groups, "Exclude")
        return self


class JourneySaveRequest(RequestSchema):
    expected_updated_at: str | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    target_audience: str = Field(default="", max_length=200)
    prerequisite_journey_id: str | None = None
    certificate_enabled: bool = True
    stages: list[JourneyStageRequest] = Field(min_length=1)
    rule: JourneyRuleRequest = Field(default_factory=JourneyRuleRequest)

    @model_validator(mode="after")
    def validate_unique_courses(self):
        course_ids = [step.course_id for stage in self.stages for step in stage.steps]
        if len(course_ids) != len(set(course_ids)):
            raise ValueError("A course can appear only once in a journey")
        return self


class JourneyObserverSelection(RequestSchema):
    observer_employee_id: str = Field(min_length=1)
    employee_ids: list[str] = Field(default_factory=list, max_length=1000)
    department_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def nonempty_scope(self):
        if not self.employee_ids and not self.department_ids:
            raise ValueError("Select employees or departments for each observer")
        return self


class JourneyObserversRequest(RequestSchema):
    observers: list[JourneyObserverSelection] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_observers(self):
        ids = [item.observer_employee_id for item in self.observers]
        if len(ids) != len(set(ids)):
            raise ValueError("An observer can only appear once per journey")
        return self


class JourneyListResponse(ApiSchema):
    enabled: bool
    journeys: list[dict] = Field(default_factory=list)


class JourneyDetailResponse(ApiSchema):
    journey_id: str
    title: str
    status: str


class LearnerJourneyListResponse(ApiSchema):
    enabled: bool
    journeys: list[dict] = Field(default_factory=list)
