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


class GenerationConfigResponse(ApiSchema):
    video_generation_mode: Literal["local", "external"]


class ModuleVideoServiceState(ApiSchema):
    """Trainer-visible progress of one module's Video Generator run."""

    status: str | None = None
    stage: str | None = None
    progress: int | float | None = None
    error: str | None = None
    run_id: str | None = None
    updated_at: str | None = None


class GenerationJobResponse(ApiSchema):
    id: str
    course_id: str
    status: GenerationStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
