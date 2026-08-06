"""LLM contract for learner notes."""

from pydantic import BaseModel


class ModuleSummarySchema(BaseModel):
    notes: list[str]
