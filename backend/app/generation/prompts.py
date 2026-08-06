"""Prompt templates loaded from Markdown files.

Set LMS_PROMPTS_DIR to a mounted directory in Docker to update prompts without
rebuilding the application image. The constants below intentionally keep the old
import names stable for the generation pipeline.
"""

from __future__ import annotations

from pathlib import Path

from app.core.settings import settings

_PROMPTS_DIR = settings.prompt_dir


class PromptTemplate:
    """Markdown-backed prompt that reloads when used."""

    def __init__(self, filename: str) -> None:
        self.filename = filename

    @property
    def path(self) -> Path:
        return _PROMPTS_DIR / self.filename

    def read(self) -> str:
        prompt_path = self.path
        if not prompt_path.is_file():
            raise FileNotFoundError(
                f"Prompt file '{self.filename}' was not found in '{_PROMPTS_DIR}'. "
                "Set LMS_PROMPTS_DIR to the mounted prompt directory or restore the default prompt files."
            )
        return prompt_path.read_text(encoding="utf-8").strip()

    def format(self, *args: object, **kwargs: object) -> str:
        return self.read().format(*args, **kwargs)

    def __str__(self) -> str:
        return self.read()


def load_prompt(filename: str) -> str:
    prompt_path = _PROMPTS_DIR / filename
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Prompt file '{filename}' was not found in '{_PROMPTS_DIR}'. "
            "Set LMS_PROMPTS_DIR to the mounted prompt directory or restore the default prompt files."
        )
    return prompt_path.read_text(encoding="utf-8").strip()


MODULE_EXTRACTION_PROMPT = PromptTemplate("module_extraction.md")
QUIZ_GENERATION_PROMPT = PromptTemplate("quiz_generation.md")
SCRIPT_GENERATION_PROMPT = PromptTemplate("script_generation.md")

# --- SLIDE PLANNER PROMPTS ---
MODULE_SLIDE_PLANNER_PROMPT = PromptTemplate("module_slide_planner.md")
SLIDE_TITLES_PROMPT = PromptTemplate("slide_titles.md")
IMAGE_SLIDE_MAPPING_PROMPT = PromptTemplate("image_slide_mapping.md")
ART_DIRECTOR_PROMPT = PromptTemplate("art_director.md")
COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT = PromptTemplate(
    "course_thumbnail_prompt_planner_system.md"
)
