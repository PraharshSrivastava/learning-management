"""Typed trainer analytics response contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiSchema
from app.schemas.employee import EmployeeResponse


class PerformanceSummary(ApiSchema):
    assigned: int = 0
    pending: int = 0
    started: int = 0
    completed: int = 0
    overdue: int = 0
    completion_rate: float = 0
    average_attempts: float = 0
    average_score: float | None = None


class PerformanceBreakdown(ApiSchema):
    label: str
    assigned: int = 0
    pending: int = 0
    started: int = 0
    completed: int = 0
    overdue: int = 0
    completion_rate: float = 0


class PerformanceStatus(ApiSchema):
    key: Literal["pending", "started", "completed", "overdue"]
    label: str


class PerformanceCourse(ApiSchema):
    course_id: str
    course_name: str
    module_count: int = 0


class ModulePerformance(ApiSchema):
    module_number: int
    title: str
    video_watched: bool
    quiz_passed: bool
    quiz_score: float | None = None
    attempt_count: int = 0
    last_score: float | None = None
    last_passed: bool | None = None
    last_attempt_at: str | None = None


class PerformanceRow(ApiSchema):
    employee: EmployeeResponse
    course: PerformanceCourse
    status: PerformanceStatus
    assigned_at: str | None = None
    deadline: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    last_activity_at: str | None = None
    total_modules: int = 0
    completed_modules: int = 0
    completion_percent: float = 0
    total_attempts: int = 0
    latest_score: float | None = None
    best_score: float | None = None
    average_score: float | None = None
    modules: list[ModulePerformance] = Field(default_factory=list)


class SelectOption(ApiSchema):
    course_id: str
    course_name: str


class StatusOption(ApiSchema):
    key: str
    label: str


class PerformanceOptions(ApiSchema):
    departments: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    employees: list[EmployeeResponse] = Field(default_factory=list)
    courses: list[SelectOption] = Field(default_factory=list)
    statuses: list[StatusOption] = Field(default_factory=list)


class PerformanceBreakdowns(ApiSchema):
    courses: list[PerformanceBreakdown] = Field(default_factory=list)
    departments: list[PerformanceBreakdown] = Field(default_factory=list)
    job_titles: list[PerformanceBreakdown] = Field(default_factory=list)


class TrainerPerformanceResponse(ApiSchema):
    summary: PerformanceSummary
    breakdowns: PerformanceBreakdowns
    rows: list[PerformanceRow] = Field(default_factory=list)
    options: PerformanceOptions
    generated_at: str
