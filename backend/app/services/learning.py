"""Learner course access, status, and module-progress use cases."""

from __future__ import annotations

from datetime import datetime

from app.core.exceptions import NotFoundError
from app.repositories.assignments import AssignmentRepository
from app.repositories.courses import CourseRepository
from app.repositories.employees import EmployeeRepository
from app.repositories.progress import ProgressRepository
from app.schemas.progress import (
    CourseStatusUpdateRequest,
    CourseStatusUpdateResponse,
    ModuleProgressUpdateRequest,
)
from app.services.assignments import ensure_assignments_for_employee
from app.services.auth import current_employee
from app.services.notifications import (
    broadcast_employee_courses,
    websocket_endpoint,
)

_assignments = AssignmentRepository()
_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()


def _learner_modules(modules: list[dict]) -> list[dict]:
    """Expose generated quizzes in the stable learner-facing question shape."""
    learner_modules = []
    for module in modules:
        learner_module = dict(module)
        quiz = module.get("quiz")
        if isinstance(quiz, dict):
            questions = []
            module_id = str(module.get("module_id") or module.get("module_number") or "module")
            for index, question in enumerate(quiz.get("questions") or [], start=1):
                options = sorted(
                    question.get("options") or [],
                    key=lambda option: str(option.get("key") or "").strip().upper(),
                )
                questions.append(
                    {
                        "question_id": question.get("question_id")
                        or f"{module_id}:question:{index}",
                        "question": question.get("question_text", ""),
                        "options": [option.get("text", "") for option in options],
                        "correct": question.get("correct_option", "A"),
                        "explanation": question.get("explanation", ""),
                    }
                )
            learner_module["quiz"] = questions
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

    for course in _courses.list("published"):
        course_id = course["course_id"]
        rule = _assignments.get(course_id)
        if (
            not rule.get("published_at")
            or not rule.get("is_active", True)
            or not _assignments.matches_employee(employee, rule, now)
        ):
            continue
        course_progress = progress_by_course.get(course_id)
        if not course_progress:
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
        enriched["modules"] = _learner_modules(course.get("modules") or [])
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
            }
        )
        employee_courses.append(enriched)
    return employee_courses


def my_courses(authorization: str | None):
    employee = current_employee(authorization)
    return get_enriched_employee_courses(employee["employee_id"])


async def update_course_status(
    course_id: str,
    payload: CourseStatusUpdateRequest,
    authorization: str | None = None,
) -> CourseStatusUpdateResponse:
    employee = current_employee(authorization)
    employee_id = employee["employee_id"]
    ensure_assignments_for_employee(employee_id)
    progress = _progress.get_for_employee(employee_id)
    if course_id not in progress:
        raise NotFoundError("Course not assigned to employee")

    now = datetime.now().isoformat()
    course_progress = progress[course_id]
    course_progress["status"] = payload.status
    course_progress["last_activity_at"] = now
    if payload.status == "started" and not course_progress.get("started_at"):
        course_progress["started_at"] = now
    if payload.status == "completed":
        course_progress["completed_at"] = now
    _progress.save(employee_id, course_id, course_progress)
    await broadcast_employee_courses(employee_id)
    return CourseStatusUpdateResponse(message="Status updated", status=payload.status)


def _module_is_complete(module: dict, module_progress: dict) -> bool:
    video_watched = bool(module_progress.get("video_watched"))
    quiz_required = bool(module.get("quiz"))
    quiz_passed = bool(module_progress.get("quiz_passed")) or (not quiz_required and video_watched)
    return video_watched and quiz_passed


async def update_module_progress(
    course_id: str,
    module_number: str,
    payload: ModuleProgressUpdateRequest,
    authorization: str | None = None,
):
    employee = current_employee(authorization)
    employee_id = employee["employee_id"]
    ensure_assignments_for_employee(employee_id)
    progress = _progress.get_for_employee(employee_id)
    if course_id not in progress:
        raise NotFoundError("Course not assigned")

    now = datetime.now().isoformat()
    course_progress = progress[course_id]
    course_progress.setdefault("modules", {})
    course_progress.setdefault("attempts", {})
    course_progress["last_activity_at"] = now
    if course_progress["status"] == "pending":
        course_progress["status"] = "started"
        course_progress["started_at"] = now

    module_progress = course_progress["modules"].get(module_number, {})
    updates = payload.model_dump(exclude_unset=True)
    if "video_watched" in updates:
        module_progress["video_watched"] = updates["video_watched"]
        module_progress["video_watched_at"] = now if updates["video_watched"] else None
    for field in ("quiz_passed", "quiz_score", "selected_answers"):
        if field in updates:
            module_progress[field] = updates[field]
    if "quiz_passed" in updates or "quiz_score" in updates:
        attempt = course_progress["attempts"].get(module_number, {"count": 0})
        attempt.update(
            {
                "count": int(attempt.get("count", 0)) + 1,
                "last_attempt_at": now,
                "last_score": updates.get("quiz_score"),
                "last_passed": updates.get("quiz_passed"),
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
    await broadcast_employee_courses(employee_id)
    return {"message": "Module progress updated"}


__all__ = [
    "my_courses",
    "broadcast_employee_courses",
    "get_enriched_employee_courses",
    "update_course_status",
    "update_module_progress",
    "websocket_endpoint",
]
