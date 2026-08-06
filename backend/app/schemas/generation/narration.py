"""LLM contracts for slide narration."""

from pydantic import BaseModel, Field, create_model


class SlideScriptSchema(BaseModel):
    script: str


class ModuleScriptSchema(BaseModel):
    slides: list[SlideScriptSchema]


def batch_script_schema(slide_count: int):
    """Return a schema requiring exactly one narration per batch slide."""
    return create_model(
        f"BatchScriptSchema{slide_count}",
        slides=(
            list[SlideScriptSchema],
            Field(min_length=slide_count, max_length=slide_count),
        ),
    )
