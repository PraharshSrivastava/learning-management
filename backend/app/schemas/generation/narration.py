"""LLM contracts for slide narration."""

from pydantic import BaseModel, Field, create_model


class SlideScriptSchema(BaseModel):
    script: str


class ModuleScriptSchema(BaseModel):
    slides: list[SlideScriptSchema]


class BatchSlideScriptSchema(BaseModel):
    """Narration anchored to its screen so scripts cannot drift onto a neighbour."""

    slide_number: int
    slide_title: str
    script: str


def batch_script_schema(slide_count: int):
    """Return a schema requiring exactly one narration per batch slide."""
    return create_model(
        f"BatchScriptSchema{slide_count}",
        slides=(
            list[BatchSlideScriptSchema],
            Field(min_length=slide_count, max_length=slide_count),
        ),
    )
