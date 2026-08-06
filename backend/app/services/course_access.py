"""Shared course identity and readiness rules used by LMS services."""

from __future__ import annotations

from datetime import datetime

from app.generation.thumbnails import course_thumbnail_signature


def course_title(course: dict) -> str:
    return (
        course.get("course_name")
        or course.get("course_id")
        or "Untitled course"
    )


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def course_is_publishable(course: dict) -> bool:
    modules = course.get("modules") or []
    if not modules:
        return False
    if not course.get("thumbnail_path"):
        return False
    if course.get("thumbnail_prompt_hash") != course_thumbnail_signature(course):
        return False
    for module in modules:
        if not module.get("video_path"):
            return False
        try:
            num_questions = int(module.get("num_questions", 0))
        except (TypeError, ValueError):
            num_questions = 0
        if num_questions <= 0:
            continue
        quiz = module.get("quiz")
        if not isinstance(quiz, dict) or not quiz.get("questions"):
            return False
    return True
