from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.core.exceptions import DomainValidationError
from app.schemas.progress import CourseStatusUpdateRequest, ModuleProgressUpdateRequest
from app.services import learning
from app.services.learning import QUIZ_PASS_MARK, _grade_quiz, _learner_modules


def _module(question_count: int = 3) -> dict:
    return {
        "module_number": 1,
        "quiz": {
            "questions": [
                {
                    "question_id": f"question-{index + 1}",
                    "question_text": f"Question {index + 1}",
                    "options": [
                        {"key": "A", "text": "Correct"},
                        {"key": "B", "text": "Incorrect"},
                    ],
                    "correct_option": "A",
                    "explanation": "A is correct.",
                }
                for index in range(question_count)
            ]
        },
    }


def test_exactly_two_out_of_three_passes() -> None:
    result = _grade_quiz(_module(3), {"0": "A", "1": "A", "2": "B"})

    assert result["quiz_passed"] is True
    assert result["quiz_score"] == pytest.approx(2 / 3)
    assert result["pass_mark"] == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    ("answers", "passed"),
    [
        ({"0": "A", "1": "A", "2": "A", "3": "B", "4": "B"}, False),
        ({"0": "A", "1": "A", "2": "A", "3": "A", "4": "B"}, True),
    ],
)
def test_five_question_quiz_requires_four_correct(answers: dict[str, str], passed: bool) -> None:
    assert _grade_quiz(_module(5), answers)["quiz_passed"] is passed


def test_exact_two_thirds_scales_without_decimal_rounding() -> None:
    answers = {str(index): "A" if index < 4 else "B" for index in range(6)}

    assert _grade_quiz(_module(6), answers)["quiz_passed"] is True


def test_rejects_incomplete_or_invalid_answers() -> None:
    with pytest.raises(DomainValidationError, match="Every quiz question"):
        _grade_quiz(_module(3), {"0": "A", "1": "A"})

    with pytest.raises(DomainValidationError, match="invalid selected answer"):
        _grade_quiz(_module(3), {"0": "A", "1": "A", "2": "Z"})


def test_learner_payload_hides_answers_until_quiz_is_passed() -> None:
    hidden = _learner_modules([_module(3)], {"1": {"quiz_passed": False}})
    revealed = _learner_modules([_module(3)], {"1": {"quiz_passed": True}})

    assert hidden[0]["pass_mark"] == pytest.approx(QUIZ_PASS_MARK)
    assert "correct" not in hidden[0]["quiz"][0]
    assert "explanation" not in hidden[0]["quiz"][0]
    assert revealed[0]["quiz"][0]["correct"] == "A"
    assert revealed[0]["quiz"][0]["explanation"] == "A is correct."


def test_client_cannot_submit_its_own_quiz_result() -> None:
    with pytest.raises(ValidationError):
        ModuleProgressUpdateRequest(
            selected_answers={"0": "A"},
            quiz_passed=True,
            quiz_score=1.0,
        )


class _Courses:
    def __init__(self, course: dict):
        self.course = course

    def list(self, status: str | None = None) -> list[dict]:
        assert status == "published"
        return [self.course]


class _Progress:
    def __init__(self) -> None:
        self.saved: dict | None = None

    def save(self, employee_id: str, course_id: str, progress: dict) -> None:
        assert employee_id == "employee-1"
        assert course_id == "course-1"
        self.saved = progress


def test_course_cannot_be_manually_completed_before_modules_pass(monkeypatch) -> None:
    course_progress = {"status": "started", "modules": {"1": {"video_watched": True}}}
    monkeypatch.setattr(
        learning,
        "current_employee_from_request",
        lambda request, authorization: {"employee_id": "employee-1"},
    )
    monkeypatch.setattr(learning, "ensure_assignments_for_employee", lambda _: None)
    monkeypatch.setattr(
        learning,
        "_assigned_progress_for_employee",
        lambda employee, course_id, now: course_progress,
    )
    monkeypatch.setattr(
        learning,
        "_courses",
        _Courses({"course_id": "course-1", "modules": [_module(3)]}),
    )

    with pytest.raises(DomainValidationError, match="Complete all modules"):
        asyncio.run(
            learning.update_course_status("course-1", CourseStatusUpdateRequest(status="completed"))
        )


def test_module_progress_uses_backend_grading_and_persists_pass(monkeypatch) -> None:
    course = {
        "course_id": "course-1",
        "status": "published",
        "modules": [_module(3)],
    }
    course_progress = {
        "status": "started",
        "modules": {"1": {"video_watched": True}},
        "attempts": {},
    }
    progress_repository = _Progress()

    monkeypatch.setattr(learning, "ensure_assignments_for_employee", lambda _: None)
    monkeypatch.setattr(
        learning,
        "current_employee_from_request",
        lambda request, authorization: {"employee_id": "employee-1"},
    )
    monkeypatch.setattr(
        learning,
        "_assigned_progress_for_employee",
        lambda employee, course_id, now: course_progress,
    )
    monkeypatch.setattr(learning, "_courses", _Courses(course))
    monkeypatch.setattr(learning, "_progress", progress_repository)

    async def no_broadcast(employee_id: str) -> None:
        assert employee_id == "employee-1"

    monkeypatch.setattr(learning, "broadcast_employee_courses", no_broadcast)

    response = asyncio.run(
        learning.update_module_progress(
            "course-1",
            "1",
            ModuleProgressUpdateRequest(selected_answers={"0": "A", "1": "A", "2": "B"}),
        )
    )

    saved_module = course_progress["modules"]["1"]
    assert response["quiz_passed"] is True
    assert response["correct_count"] == 2
    assert saved_module["quiz_passed"] is True
    assert saved_module["quiz_score"] == pytest.approx(2 / 3)
    assert saved_module["selected_answers"] == {"0": "A", "1": "A", "2": "B"}
    assert course_progress["attempts"]["1"]["count"] == 1
    assert course_progress["status"] == "completed"
    assert progress_repository.saved is course_progress


def test_quiz_submission_requires_completed_video(monkeypatch) -> None:
    course = {
        "course_id": "course-1",
        "status": "published",
        "modules": [_module(3)],
    }
    course_progress = {
        "status": "started",
        "modules": {"1": {"video_watched": False}},
        "attempts": {},
    }

    monkeypatch.setattr(learning, "ensure_assignments_for_employee", lambda _: None)
    monkeypatch.setattr(
        learning,
        "current_employee_from_request",
        lambda request, authorization: {"employee_id": "employee-1"},
    )
    monkeypatch.setattr(
        learning,
        "_assigned_progress_for_employee",
        lambda employee, course_id, now: course_progress,
    )
    monkeypatch.setattr(learning, "_courses", _Courses(course))

    with pytest.raises(DomainValidationError, match="Complete the video lesson"):
        asyncio.run(
            learning.update_module_progress(
                "course-1",
                "1",
                ModuleProgressUpdateRequest(selected_answers={"0": "A", "1": "A", "2": "B"}),
            )
        )
