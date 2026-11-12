"""LLM contracts for slide planning and art direction."""

from typing import Literal

from pydantic import BaseModel, Field


class SlidePlan(BaseModel):
    title: str
    content: list[str]


class ModuleSlidesSchema(BaseModel):
    chain_of_thought: str
    slides: list[SlidePlan]


class SlideTitle(BaseModel):
    title: str = Field(max_length=60)


class SlideTitlesSchema(BaseModel):
    titles: list[SlideTitle]


class ImageMapping(BaseModel):
    image_id: str
    bullet_index: int


class ImageMappingResult(BaseModel):
    mappings: list[ImageMapping]


class StepItem(BaseModel):
    title: str
    description: str


class StepsLayoutData(BaseModel):
    steps: list[StepItem]


class ComparisonLayoutData(BaseModel):
    left_column_title: str
    left_column_points: list[str] = Field(min_length=2)
    right_column_title: str
    right_column_points: list[str] = Field(min_length=2)


class GridColumnItem(BaseModel):
    header: str
    points: list[str]


class GridLayoutData(BaseModel):
    columns: list[GridColumnItem]


class ArtDirectorSlidePlan(BaseModel):
    layout_type: Literal["steps", "comparison", "grid", "bullets"]
    steps_data: StepsLayoutData | None = None
    comparison_data: ComparisonLayoutData | None = None
    grid_data: GridLayoutData | None = None
    bullets: list[str] | None = None


class ArtDirectorResponse(BaseModel):
    chain_of_thought: str
    slides: list[ArtDirectorSlidePlan]
