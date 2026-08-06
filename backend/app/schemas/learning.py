"""Learner course response contracts."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema, MessageResponse
from app.schemas.course import ModuleResponse
from app.schemas.progress import ModuleProgressRecord, QuizAttemptRecord


class LearnerCourseResponse(ApiSchema):
    assignment_id: str
    course_id: str
    course_name: str = ""
    course_description: str = ""
    thumbnail_path: str | None = None
    created_at: str = ""
    modules: list[ModuleResponse] = Field(default_factory=list)
    assignment_status: str
    assigned_at: str
    deadline: str
    started_at: str | None = None
    completed_at: str | None = None
    module_progress: dict[str, ModuleProgressRecord] = Field(default_factory=dict)
    quiz_attempts: dict[str, QuizAttemptRecord] = Field(default_factory=dict)


class ModuleProgressUpdateResponse(MessageResponse):
    pass
