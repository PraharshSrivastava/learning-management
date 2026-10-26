"""Learner course access, status, and module-progress use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import Request

from app.core.exceptions import DomainValidationError, NotFoundError
from app.repositories.assignments import AssignmentRepository
from app.repositories.courses import CourseRepository
from app.repositories.database import course_transaction
from app.repositories.employees import EmployeeRepository
from app.repositories.progress import ProgressRepository
from app.schemas.progress import (
    CourseStatusUpdateRequest,
    CourseStatusUpdateResponse,
    ModuleProgressUpdateRequest,
)
from app.services.assignments import (
    ensure_assignments_for_employee,
    reconcile_assignments_for_employee,
)
from app.services.auth import current_employee_from_request
from app.services.journeys import (
    journey_held_courses,
    journeys_enabled,
    learner_course_journeys,
)
from app.services.notifications import (
    broadcast_employee_courses,
    websocket_endpoint,
)

_assignments = AssignmentRepository()
_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()

QUIZ_PASS_NUMERATOR = 2
QUIZ_PASS_DENOMINATOR = 3
QUIZ_PASS_MARK = QUIZ_PASS_NUMERATOR / QUIZ_PASS_DENOMINATOR


def _quiz_questions(module: dict) -> list[dict]:
    quiz = module.get("quiz")
    if isinstance(quiz, dict):
        return [question for question in quiz.get("questions") or [] if isinstance(question, dict)]
    if isinstance(quiz, list):
        return [question for question in quiz if isinstance(question, dict)]
    return []


def _question_options(question: dict) -> tuple[list[str], list[str]]:
    raw_options = question.get("options") or []
    if raw_options and all(isinstance(option, dict) for option in raw_options):
        ordered = sorted(
            raw_options,
            key=lambda option: str(option.get("key") or "").strip().upper(),
        )
        return (
            [str(option.get("key") or "").strip().upper() for option in ordered],
            [str(option.get("text") or "") for option in ordered],
        )
    texts = [str(option) for option in raw_options]
    return ([chr(65 + index) for index in range(len(texts))], texts)


def _question_correct_answer(question: dict) -> str:
    return str(question.get("correct_option") or question.get("correct") or "").strip().upper()


def _question_text(question: dict) -> str:
    return str(question.get("question_text") or question.get("question") or "")


def _grade_quiz(module: dict, selected_answers: dict[str, str]) -> dict:
    questions = _quiz_questions(module)
    if not questions:
        raise DomainValidationError("This module does not have a quiz")

    expected_keys = {str(index) for index in range(len(questions))}
    submitted_keys = {str(key) for key in selected_answers}
    if submitted_keys != expected_keys:
        raise DomainValidationError("Every quiz question must be answered exactly once")

    normalized_answers: dict[str, str] = {}
    answer_results: dict[str, bool] = {}
    correct_count = 0
    for index, question in enumerate(questions):
        key = str(index)
        answer = str(selected_answers[key]).strip().upper()
        option_keys, _ = _question_options(question)
        correct_answer = _question_correct_answer(question)
        if correct_answer not in option_keys:
            raise DomainValidationError(f"Question {index + 1} has an invalid answer key")
        if answer not in option_keys:
            raise DomainValidationError(f"Question {index + 1} has an invalid selected answer")
        normalized_answers[key] = answer
        answer_results[key] = answer == correct_answer
        if answer == correct_answer:
            correct_count += 1

    total_questions = len(questions)
    passed = correct_count * QUIZ_PASS_DENOMINATOR >= total_questions * QUIZ_PASS_NUMERATOR
    return {
        "quiz_passed": passed,
        "quiz_score": correct_count / total_questions,
        "correct_count": correct_count,
        "total_questions": total_questions,
        "pass_mark": QUIZ_PASS_MARK,
        "selected_answers": normalized_answers,
        "answer_results": answer_results,
    }


def _learner_modules(
    modules: list[dict], module_progress: dict[str, dict] | None = None
) -> list[dict]:
    """Expose generated quizzes in the stable learner-facing question shape."""
    learner_modules = []
    for module in modules:
        learner_module = dict(module)
        quiz = module.get("quiz")
        questions_source = _quiz_questions(module)
        if isinstance(quiz, (dict, list)):
            questions = []
            module_id = str(module.get("module_id") or module.get("module_number") or "module")
            module_key = str(module.get("module_number") or "")
            saved_progress = (module_progress or {}).get(module_key, {})
            saved_answers = saved_progress.get("selected_answers") or {}
            for index, question in enumerate(questions_source, start=1):
                _, option_texts = _question_options(question)
                learner_question = {
                    "question_id": question.get("question_id") or f"{module_id}:question:{index}",
                    "question": _question_text(question),
                    "options": option_texts,
                }
                saved_answer = saved_answers.get(str(index - 1))
                if saved_progress.get("quiz_passed") and saved_answer is not None:
                    learner_question["answer_correct"] = (
                        str(saved_answer).strip().upper() == _question_correct_answer(question)
                    )
                questions.append(learner_question)
            learner_module["quiz"] = questions
        learner_module["pass_mark"] = QUIZ_PASS_MARK
        learner_modules.append(learner_module)
    return learner_modules


def get_enriched_employee_courses(employee_id: str) -> list[dict]:
    ensure_assignments_for_employee(employee_id)
    employee = _employees.get(employee_id)
    if not employee:
        return []
    progress_by_course = _progress.get_for_employee(employee_id)
    now = datetime.now()
    employee_courses = []
    course_journeys = learner_course_journeys(employee_id)
    journey_courses = _held_courses_lookup(employee_id)

    for course in _courses.list("published"):
        course_id = course["course_id"]
        rule = _assignments.get_applied(course_id)
        if not _rule_or_journey_grants(employee, course_id, rule, now, journey_courses):
            continue
        course_progress = progress_by_course.get(course_id)
        if not course_progress or course_progress.get("revoked_at") or course_progress.get("status") == "revoked":
            continue

        changed = False
        if "modules" not in course_progress:
            course_progress["modules"] = {}
            changed = True
        if "attempts" not in course_progress:
            course_progress["attempts"] = {}
            changed = True
        if course_progress["status"] in {"pending", "started"}:
            deadline = datetime.fromisoformat(course_progress["deadline"])
            if now > deadline:
                course_progress["status"] = "overdue"
                changed = True
        if changed:
            _progress.save(employee_id, course_id, course_progress)

        enriched = dict(course)
        enriched["modules"] = _learner_modules(
            course.get("modules") or [], course_progress.get("modules", {})
        )
        enriched.update(
            {
                "assignment_id": course_progress["assignment_id"],
                "assignment_status": course_progress["status"],
                "assigned_at": course_progress["assigned_at"],
                "deadline": course_progress["deadline"],
                "started_at": course_progress.get("started_at"),
                "completed_at": course_progress.get("completed_at"),
                "module_progress": course_progress.get("modules", {}),
                "quiz_attempts": course_progress.get("attempts", {}),
                "journeys": course_journeys.get(course_id, []),
            }
        )
        employee_courses.append(enriched)
    return employee_courses


def _held_courses_lookup(employee_id: str) -> Callable[[], set[str]]:
    """Courses a journey already gave the employee, read once and only when needed."""
    cache: list[set[str]] = []

    def held() -> set[str]:
        if not cache:
            cache.append(journey_held_courses(employee_id))
        return cache[0]

    return held


def _rule_or_journey_grants(
    employee: dict,
    course_id: str,
    rule: dict,
    now: datetime,
    journey_courses: Callable[[], set[str]],
) -> bool:
    """A course reaches a learner through its own published rule or an active Learning Journey.
    A Disabled course (published rule switched off) is unavailable either way."""
    if rule.get("published_at") and not rule.get("is_active", True):
        return False
    if rule.get("published_at") and _assignments.matches_employee(employee, rule, now):
        return True
    return course_id in journey_courses()


def my_courses(request: Request | None, authorization: str | None):
    employee = current_employee_from_request(request, authorization)
    return get_enriched_employee_courses(employee["employee_id"])


def _assigned_progress_for_employee(employee: dict, course_id: str, now: datetime) -> dict:
    progress = _progress.get_for_employee(employee["employee_id"])
    if course_id not in progress:
        raise NotFoundError("Course not assigned to employee")
    course_progress = progress[course_id]
    course = next((item for item in _courses.list("published") if item["course_id"] == course_id), None)
    if course is None:
        raise NotFoundError("Course not assigned to employee")
    if course_progress.get("revoked_at") or course_progress.get("status") == "revoked":
        raise NotFoundError("Course not assigned to employee")
    rule = _assignments.get_applied(course_id)
    if not _rule_or_journey_grants(
        employee, course_id, rule, now, _held_courses_lookup(employee["employee_id"])
    ):
        raise NotFoundError("Course not assigned to employee")
    return course_progress


async def update_course_status(
    course_id: str,
    payload: CourseStatusUpdateRequest,
    request: Request | None = None,
    authorization: str | None = None,
) -> CourseStatusUpdateResponse:
    employee = current_employee_from_request(request, authorization)
    employee_id = employee["employee_id"]
    ensure_assignments_for_employee(employee_id)

    with course_transaction(course_id):
        now = datetime.now().isoformat()
        course_progress = _assigned_progress_for_employee(employee, course_id, datetime.now())
        was_completed = course_progress.get("status") == "completed"
        if course_progress.get("status") == "completed" and payload.status != "completed":
            raise DomainValidationError("A completed course cannot be reset through this endpoint")
        if payload.status == "completed":
            published_course = next(
                (course for course in _courses.list("published") if course["course_id"] == course_id),
                None,
            )
            modules = (published_course or {}).get("modules") or []
            if not modules or not all(
                _module_is_complete(
                    module,
                    (course_progress.get("modules") or {}).get(str(module.get("module_number")), {}),
                )
                for module in modules
            ):
                raise DomainValidationError("Complete all modules before marking the course completed")
        course_progress["status"] = payload.status
        course_progress["last_activity_at"] = now
        course_progress["last_learner_activity_at"] = now
        if payload.status == "started" and not course_progress.get("started_at"):
            course_progress["started_at"] = now
        if payload.status == "completed":
            course_progress["completed_at"] = now
        _progress.save(employee_id, course_id, course_progress)
    if payload.status == "completed" and not was_completed:
        _unlock_next_journey_steps(employee_id)
    await broadcast_employee_courses(employee_id)
    return CourseStatusUpdateResponse(message="Status updated", status=payload.status)


def _unlock_next_journey_steps(employee_id: str) -> None:
    """Assign the next Learning Journey course as soon as a course is completed.

    Runs after the course transaction commits, so the completion is visible to the journey rules.
    """
    if journeys_enabled():
        reconcile_assignments_for_employee(employee_id)


def _module_is_complete(module: dict, module_progress: dict) -> bool:
    video_watched = bool(module_progress.get("video_watched"))
    quiz_required = bool(module.get("quiz"))
    quiz_passed = bool(module_progress.get("quiz_passed")) or (not quiz_required and video_watched)
    return video_watched and quiz_passed


async def update_module_progress(
    course_id: str,
    module_number: str,
    payload: ModuleProgressUpdateRequest,
    request: Request | None = None,
    authorization: str | None = None,
):
    employee = current_employee_from_request(request, authorization)
    employee_id = employee["employee_id"]
    ensure_assignments_for_employee(employee_id)

    with course_transaction(course_id):
        now = datetime.now().isoformat()
        course_progress = _assigned_progress_for_employee(employee, course_id, datetime.now())
        was_completed = course_progress.get("status") == "completed"
        course_progress.setdefault("modules", {})
        course_progress.setdefault("attempts", {})
        course_progress["last_activity_at"] = now
        course_progress["last_learner_activity_at"] = now
        if course_progress["status"] == "pending":
            course_progress["status"] = "started"
            course_progress["started_at"] = now

        module_progress = course_progress["modules"].get(module_number, {})
        updates = payload.model_dump(exclude_unset=True)
        if "video_watched" in updates:
            module_progress["video_watched"] = updates["video_watched"]
            module_progress["video_watched_at"] = now if updates["video_watched"] else None
        grading_result = None
        if "selected_answers" in updates:
            if updates["selected_answers"] is None:
                raise DomainValidationError("Selected answers are required for quiz submission")
            published_course = next(
                (course for course in _courses.list("published") if course["course_id"] == course_id),
                None,
            )
            published_module = next(
                (
                    module
                    for module in (published_course or {}).get("modules", [])
                    if str(module.get("module_number")) == str(module_number)
                ),
                None,
            )
            if published_module is None:
                raise NotFoundError("Course module not found")
            if not module_progress.get("video_watched"):
                raise DomainValidationError("Complete the video lesson before submitting the quiz")

            grading_result = _grade_quiz(published_module, updates["selected_answers"])
            module_progress["quiz_passed"] = grading_result["quiz_passed"]
            module_progress["quiz_score"] = grading_result["quiz_score"]
            module_progress["selected_answers"] = (
                grading_result["selected_answers"] if grading_result["quiz_passed"] else None
            )
            if not grading_result["quiz_passed"]:
                module_progress["video_watched"] = False
                module_progress["video_watched_at"] = None

            attempt = course_progress["attempts"].get(module_number, {"count": 0})
            attempt.update(
                {
                    "count": int(attempt.get("count", 0)) + 1,
                    "last_attempt_at": now,
                    "last_score": grading_result["quiz_score"],
                    "last_passed": grading_result["quiz_passed"],
                }
            )
            course_progress["attempts"][module_number] = attempt
        course_progress["modules"][module_number] = module_progress

        published_course = next(
            (course for course in _courses.list("published") if course["course_id"] == course_id),
            None,
        )
        if published_course:
            modules = published_course.get("modules", [])
            completed = sum(
                _module_is_complete(
                    module,
                    course_progress["modules"].get(
                        str(module.get("module_number", "")),
                        {},
                    ),
                )
                for module in modules
            )
            if modules and completed == len(modules):
                course_progress["status"] = "completed"
                course_progress["completed_at"] = now

        _progress.save(employee_id, course_id, course_progress)
    if course_progress.get("status") == "completed" and not was_completed:
        _unlock_next_journey_steps(employee_id)
    await broadcast_employee_courses(employee_id)
    response = {"message": "Module progress updated"}
    if grading_result is not None:
        response.update(
            {
                key: grading_result[key]
                for key in (
                    "quiz_passed",
                    "quiz_score",
                    "correct_count",
                    "total_questions",
                    "pass_mark",
                    "answer_results",
                )
            }
        )
    return response


__all__ = [
    "my_courses",
    "broadcast_employee_courses",
    "get_enriched_employee_courses",
    "update_course_status",
    "update_module_progress",
    "websocket_endpoint",
]
