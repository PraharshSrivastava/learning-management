"""LLM contracts for generated module quizzes."""

from pydantic import BaseModel


class MCQOption(BaseModel):
    key: str
    text: str


class MCQQuestion(BaseModel):
    question_text: str
    options: list[MCQOption]
    correct_option: str
    explanation: str


class ModuleQuiz(BaseModel):
    questions: list[MCQQuestion]
