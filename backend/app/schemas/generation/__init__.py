"""Generation-state and background-job contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiSchema

GenerationStatus = Literal["pending", "running", "completed", "failed"]


class GenerationStage(ApiSchema):
    status: GenerationStatus
    updated_at: str | None = None
    error: str | None = None
    module_number: int | None = None
    slide_number: int | None = None


class GenerationState(ApiSchema):
    status: GenerationStatus = "pending"
    current_checkpoint: str | None = None
    failed_checkpoint: str | None = None
    failed_stages: list[str] = Field(default_factory=list)
    error: str | None = None
    stages: dict[str, GenerationStage] = Field(default_factory=dict)


class GenerationJobResponse(ApiSchema):
    id: str
    course_id: str
    status: GenerationStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
