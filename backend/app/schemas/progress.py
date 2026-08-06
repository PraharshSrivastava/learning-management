"""Learner progress API contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import ApiSchema, MessageResponse, RequestSchema


class CourseStatusUpdateRequest(RequestSchema):
    status: Literal["pending", "started", "completed", "overdue"]


class ModuleProgressUpdateRequest(RequestSchema):
    video_watched: bool | None = None
    quiz_passed: bool | None = None
    quiz_score: float | None = Field(default=None, ge=0, le=100)
    selected_answers: dict[str, Any] | list[Any] | None = None

    @model_validator(mode="after")
    def require_progress_change(self) -> "ModuleProgressUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one progress field is required")
        return self


class CourseStatusUpdateResponse(MessageResponse):
    status: Literal["pending", "started", "completed", "overdue"]


class ModuleProgressRecord(ApiSchema):
    video_watched: bool = False
    video_watched_at: str | None = None
    quiz_passed: bool = False
    quiz_score: float | None = Field(default=None, ge=0, le=100)
    selected_answers: dict[str, Any] | list[Any] | None = None


class QuizAttemptRecord(ApiSchema):
    count: int = Field(default=0, ge=0)
    last_attempt_at: str | None = None
    last_score: float | None = None
    last_passed: bool | None = None


class EmployeeCourseProgressRecord(ApiSchema):
    employee_id: str | None = None
    course_id: str | None = None
    status: Literal["pending", "started", "completed", "overdue"] = "pending"
    assigned_at: str
    deadline: str
    started_at: str | None = None
    completed_at: str | None = None
    modules: dict[str, ModuleProgressRecord] = Field(default_factory=dict)
    attempts: dict[str, QuizAttemptRecord] = Field(default_factory=dict)
    last_activity_at: str | None = None
