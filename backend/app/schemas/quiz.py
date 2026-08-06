"""Quiz contracts used by authoring endpoints."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema, RequestSchema


class QuizOption(ApiSchema):
    key: str = Field(min_length=1, max_length=1)
    text: str = Field(min_length=1)


class QuizQuestion(ApiSchema):
    question_text: str = Field(min_length=1)
    # Persisted/imported quizzes can have different option counts. The manual
    # authoring service enforces A-D for newly submitted questions.
    options: list[QuizOption] = Field(min_length=1)
    correct_option: str = Field(min_length=1, max_length=1)
    explanation: str = ""


class Quiz(ApiSchema):
    questions: list[QuizQuestion] = Field(default_factory=list)


class ManualQuizRequest(RequestSchema):
    questions: list[QuizQuestion] = Field(min_length=1)
