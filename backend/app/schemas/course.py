"""Course authoring and generation API contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ApiSchema, RequestSchema
from app.schemas.generation import GenerationState
from app.schemas.quiz import Quiz

CourseStatus = Literal["draft", "ready", "published", "archived"]


class ImageRecord(ApiSchema):
    image_id: str | None = None
    path: str | None = None
    url: str | None = None
    caption: str | None = None


class SlideRecord(ApiSchema):
    slide_number: int | None = None
    title: str = ""
    slide_title: str = ""
    layout_type: str = "bullets"
    content: list[Any] = Field(default_factory=list)
    bullets: list[Any] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)
    images: list[ImageRecord] = Field(default_factory=list)
    script: str | None = None
    audio_path: str | None = None


class PublishedQuizQuestion(ApiSchema):
    question_id: str | None = None
    question: str
    options: list[str] = Field(default_factory=list)
    correct: str
    explanation: str = ""


class ModuleUpdate(RequestSchema):
    title: str = ""
    source_text: str = ""
    start_line: int | str | None = None
    num_questions: int = Field(default=3, ge=0)


class CourseUpdateRequest(RequestSchema):
    course_name: str | None = None
    course_description: str | None = None
    course_objective: str | None = None
    course_difficulty: str | None = None
    language: str | None = None
    target_audience: str | None = None
    modules: list[ModuleUpdate | str] | None = None


class GenerateCourseRequest(RequestSchema):
    file_name: str = Field(min_length=1)


class ModuleResponse(ApiSchema):
    module_id: str | None = None
    course_id: str | None = None
    module_number: int | None = None
    title: str = ""
    source_text: str = ""
    num_questions: int = Field(default=0, ge=0)
    quiz: Quiz | list[PublishedQuizQuestion] | None = None
    planned_slides: list[SlideRecord] = Field(default_factory=list)
    slides: list[SlideRecord] = Field(default_factory=list)
    notes: str = ""
    video_path: str | None = None


class CourseResponse(ApiSchema):
    course_id: str
    trainer_id: str
    document_id: str | None = None
    course_name: str = ""
    course_description: str = ""
    course_objective: str = ""
    course_difficulty: str = ""
    language: str = ""
    target_audience: str = ""
    thumbnail_path: str | None = None
    status: CourseStatus
    created_at: str = ""
    updated_at: str = ""
    published_at: str | None = None
    modules: list[ModuleResponse] = Field(default_factory=list)
    thumbnail_prompt_hash: str | None = None
    generation: GenerationState | None = None


class CourseSummaryResponse(ApiSchema):
    course_id: str
    trainer_id: str
    document_id: str | None = None
    course_name: str = ""
    course_description: str = ""
    course_objective: str = ""
    course_difficulty: str = ""
    language: str = ""
    target_audience: str = ""
    thumbnail_path: str | None = None
    status: CourseStatus
    created_at: str = ""
    updated_at: str = ""
    published_at: str | None = None
    module_count: int = 0
    is_assignable: bool = False
    thumbnail_prompt_hash: str | None = None
    generation: GenerationState | None = None


class CourseRecord(ApiSchema):
    """Validated course persistence shape."""

    course_id: str = Field(min_length=1)
    trainer_id: str = Field(min_length=1)
    document_id: str | None = None
    course_name: str = ""
    course_description: str = ""
    course_objective: str = ""
    course_difficulty: str = ""
    language: str = ""
    target_audience: str = ""
    thumbnail_path: str | None = None
    status: CourseStatus = "draft"
    created_at: str = ""
    updated_at: str = ""
    published_at: str | None = None
    modules: list[ModuleResponse] = Field(default_factory=list)
    thumbnail_prompt_hash: str | None = None
    generation: GenerationState | None = None
