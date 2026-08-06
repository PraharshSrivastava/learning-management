"""Course assignment rules, publication, and employee matching use cases."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.exceptions import DomainValidationError, NotFoundError
from app.repositories.assignments import AssignmentRepository
from app.repositories.courses import CourseRepository, update_course_status
from app.repositories.employees import EmployeeRepository
from app.repositories.progress import ProgressRepository
from app.schemas.assignment import AssignmentRuleRequest
from app.services.course_access import course_is_publishable

_assignments = AssignmentRepository()
_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()


def _new_progress(now: datetime, deadline_days: int) -> dict:
    return {
        "status": "pending",
        "assigned_at": now.isoformat(),
        "deadline": (now + timedelta(days=deadline_days)).isoformat(),
        "modules": {},
        "attempts": {},
        "last_activity_at": now.isoformat(),
    }


def ensure_assignments_for_employee(employee_id: str) -> bool:
    employee = _employees.get(employee_id)
    if not employee or employee.get("status") != "active":
        return False
    existing = _progress.get_for_employee(employee_id)
    now = datetime.now()
    updated = False
    for course in _courses.list("published"):
        course_id = course["course_id"]
        if not course_id or course_id in existing:
            continue
        rule = _assignments.get(course_id)
        if not rule.get("published_at") or not rule.get("is_active", True):
            continue
        if not _assignments.matches_employee(employee, rule, now):
            continue
        _progress.save(
            employee_id,
            course_id,
            _new_progress(now, rule["deadline_days"]),
        )
        updated = True
    return updated


def assign_published_courses_to_employees(published_courses=None) -> None:
    from app.services.notifications import schedule_employee_broadcast

    for employee in _employees.list():
        if ensure_assignments_for_employee(employee["employee_id"]):
            schedule_employee_broadcast(employee["employee_id"])


def assign_published_course_to_matching_employees(
    course_id: str,
    reset_assignment_dates: bool = False,
    deadline_changed: bool = False,
) -> dict[str, int]:
    from app.services.notifications import schedule_employee_broadcast

    now = datetime.now()
    rule = _assignments.get(course_id)
    if not rule.get("published_at") or not rule.get("is_active", True):
        return {"assigned": 0, "removed": 0, "deadline_updates": 0}
    published_ids = {course["course_id"] for course in _courses.list("published")}
    if course_id not in published_ids:
        return {"assigned": 0, "removed": 0, "deadline_updates": 0}

    matched_employees = _assignments.matching_employees(rule)
    matched_by_id = {employee["employee_id"]: employee for employee in matched_employees}
    existing_progress = _progress.get_for_course(course_id)
    assigned = 0
    removed = 0
    deadline_updates = 0

    for employee_id in list(existing_progress):
        if employee_id not in matched_by_id:
            removed += 1
            schedule_employee_broadcast(employee_id)

    for employee in matched_employees:
        employee_id = employee["employee_id"]
        if employee_id in existing_progress:
            if reset_assignment_dates or deadline_changed:
                course_progress = existing_progress[employee_id]
                if reset_assignment_dates:
                    course_progress["assigned_at"] = now.isoformat()
                course_progress["deadline"] = (
                    now + timedelta(days=rule["deadline_days"])
                ).isoformat()
                course_progress["last_activity_at"] = now.isoformat()
                _progress.save(employee_id, course_id, course_progress)
                deadline_updates += 1
                schedule_employee_broadcast(employee_id)
            continue
        _progress.save(
            employee_id,
            course_id,
            _new_progress(now, rule["deadline_days"]),
        )
        assigned += 1
        schedule_employee_broadcast(employee_id)
    return {
        "assigned": assigned,
        "removed": removed,
        "deadline_updates": deadline_updates,
    }


def api_assignment_options():
    return _employees.assignment_options()


def _owned_draft_course(course_id: str, trainer_id: str) -> dict:
    course = next(
        (
            course
            for course in _courses.list_for_trainer(trainer_id)
            if course["course_id"] == course_id
        ),
        None,
    )
    if not course:
        raise NotFoundError("Course not found")
    return course


def api_assignable_courses(trainer_id: str | None = None):
    courses = _courses.list_for_trainer(trainer_id) if trainer_id else _courses.list()
    return [
        course
        for course in courses
        if course.get("status") in {"ready", "published"}
        and course_is_publishable(course)
    ]


def _assignment_response(rule: dict) -> dict:
    matches = _assignments.matching_employees(rule, limit=10)
    return {
        "rule": rule,
        "match_count": len(_assignments.matching_employees(rule)),
        "preview_employees": matches,
    }


def api_get_course_assignment(course_id: str, trainer_id: str | None = None):
    if trainer_id:
        _owned_draft_course(course_id, trainer_id)
    return _assignment_response(_assignments.get(course_id))


def api_save_course_assignment(
    course_id: str, payload: AssignmentRuleRequest, trainer_id: str | None = None
):
    if trainer_id:
        _owned_draft_course(course_id, trainer_id)
    rule = _assignments.save(
        course_id,
        payload.model_dump(exclude_unset=True),
    )
    return _assignment_response(rule)


def api_publish_course_assignment(
    course_id: str, payload: AssignmentRuleRequest, trainer_id: str | None = None
):
    if trainer_id:
        _owned_draft_course(course_id, trainer_id)
    previous_rule = _assignments.get(course_id)
    rule = _assignments.save(
        course_id,
        payload.model_dump(exclude_unset=True),
    )
    course = next(
        (course for course in _courses.list() if course["course_id"] == course_id),
        None,
    )
    if not course or course.get("status") not in {"ready", "published"} or not course_is_publishable(course):
        raise DomainValidationError(
            "Course is not ready for assignment. Generate the full course first."
        )
    rule = _assignments.save(course_id, rule, publish=True)
    update_course_status(course_id, "published")
    changes = assign_published_course_to_matching_employees(course_id, reset_assignment_dates=True)
    response = _assignment_response(rule)
    response.update(
        {
            "assigned_count": changes["assigned"],
            "removed_count": changes["removed"],
            "deadline_update_count": changes["deadline_updates"],
        }
    )
    return response


def api_disable_course_assignment(course_id: str, trainer_id: str):
    _owned_draft_course(course_id, trainer_id)
    rule = _assignments.save(
        course_id,
        _assignments.get(course_id),
        disable=True,
        disabled_by_trainer_id=trainer_id,
    )
    from app.services.notifications import schedule_employee_broadcast

    for employee_id in _progress.get_for_course(course_id):
        schedule_employee_broadcast(employee_id)
    response = _assignment_response(rule)
    response.update({"message": "Course disabled for employees."})
    return response


__all__ = [
    "api_assignable_courses",
    "api_assignment_options",
    "api_get_course_assignment",
    "api_publish_course_assignment",
    "api_save_course_assignment",
    "api_disable_course_assignment",
    "assign_published_course_to_matching_employees",
    "assign_published_courses_to_employees",
    "ensure_assignments_for_employee",
]
