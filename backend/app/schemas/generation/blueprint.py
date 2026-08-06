"""LLM and pipeline contracts for document blueprint extraction."""

from typing import Any

from pydantic import BaseModel, Field


class ModuleSchema(BaseModel):
    module_number: int
    title: str
    start_line: int
    num_questions: int = 3


class ModuleListSchema(BaseModel):
    chain_of_thought: str
    modules: list[ModuleSchema]


class ExtractedModule(ModuleSchema):
    source_text: str = ""
    end_line: int | None = None
    images: list[dict[str, Any]] = Field(default_factory=list)


class BlueprintExtractionResult(BaseModel):
    course_name: str
    course_description: str
    course_objective: str
    course_difficulty: str
    language: str
    target_audience: str
    modules: list[ExtractedModule] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
