"""Course assignment rules, publication, and employee matching use cases."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.exceptions import DomainValidationError, NotFoundError
from app.repositories.assignments import AssignmentRepository
from app.repositories.courses import CourseRepository, update_course_status
from app.repositories.employees import EmployeeRepository
from app.repositories.progress import ProgressRepository
from app.repositories.saved_assignment_groups import SavedAssignmentGroupRepository
from app.schemas.assignment import AssignmentRuleRequest, SavedAssignmentGroupRequest
from app.services.course_access import course_is_publishable

_assignments = AssignmentRepository()
_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()
_saved_groups = SavedAssignmentGroupRepository()


def _new_progress(now: datetime, deadline_days: int) -> dict:
    return {
        "status": "pending",
        "assigned_at": now.isoformat(),
        "deadline": (now + timedelta(days=deadline_days)).isoformat(),
        "modules": {},
        "attempts": {},
        "last_activity_at": now.isoformat(),
    }


def _status_for_reactivation(progress: dict, now: datetime) -> str:
    if progress.get("completed_at") or progress.get("status") == "completed":
        return "completed"
    if progress.get("started_at") or progress.get("modules"):
        deadline = progress.get("deadline")
        if deadline:
            try:
                if now > datetime.fromisoformat(deadline):
                    return "overdue"
            except ValueError:
                pass
        return "started"
    return "pending"


def _reactivated_progress(progress: dict, employee: dict, now: datetime, deadline_days: int) -> dict:
    next_progress = dict(progress)
    next_progress.setdefault("modules", {})
    next_progress.setdefault("attempts", {})
    revoked_at = next_progress.get("revoked_at")
    deadline = next_progress.get("deadline")
    if revoked_at and deadline:
        try:
            remaining = datetime.fromisoformat(deadline) - datetime.fromisoformat(revoked_at)
            if remaining.total_seconds() < 0:
                remaining = timedelta(0)
            next_progress["deadline"] = (now + remaining).isoformat()
        except ValueError:
            next_progress["deadline"] = (now + timedelta(days=deadline_days)).isoformat()
    elif not deadline:
        next_progress["deadline"] = (now + timedelta(days=deadline_days)).isoformat()
    next_progress["status"] = _status_for_reactivation(next_progress, now)
    next_progress["revoked_at"] = None
    next_progress["revoked_reason"] = None
    next_progress["last_activity_at"] = now.isoformat()
    next_progress["assigned_department"] = employee.get("department")
    return next_progress


def _revoked_progress(progress: dict, now: datetime, reason: str) -> dict:
    next_progress = dict(progress)
    if next_progress.get("status") == "completed":
        return next_progress
    next_progress["status"] = "revoked"
    next_progress["revoked_at"] = next_progress.get("revoked_at") or now.isoformat()
    next_progress["revoked_reason"] = reason
    next_progress["last_activity_at"] = now.isoformat()
    return next_progress


def reconcile_assignments_for_employee(employee_id: str, *, notify: bool = False) -> dict[str, int]:
    from app.services.notifications import schedule_employee_broadcast

    employee = _employees.get(employee_id)
    existing = _progress.get_for_employee(employee_id)
    now = datetime.now()
    assigned = 0
    removed = 0
    reactivated = 0
    published_courses = {
        course["course_id"]: course
        for course in _courses.list("published")
        if course.get("course_id")
    }

    for course_id, course_progress in list(existing.items()):
        if course_progress.get("status") in {"completed", "revoked"}:
            continue
        reason = None
        if not employee or employee.get("status") != "active":
            reason = "directory_leaver" if employee and employee.get("source") == "hub" else "employee_inactive"
        elif course_id not in published_courses:
            reason = "course_no_longer_published"
        else:
            rule = _assignments.get(course_id)
            if (
                not rule.get("published_at")
                or not rule.get("is_active", True)
                or not _assignments.matches_employee(employee, rule, now)
            ):
                reason = "assignment_rule_no_longer_matches"
        if reason:
            _progress.save(employee_id, course_id, _revoked_progress(course_progress, now, reason))
            removed += 1
            if notify:
                schedule_employee_broadcast(employee_id)

    if not employee or employee.get("status") != "active":
        return {"assigned": assigned, "removed": removed, "reactivated": reactivated}

    for course in _courses.list("published"):
        course_id = course["course_id"]
        if not course_id:
            continue
        rule = _assignments.get(course_id)
        if not rule.get("published_at") or not rule.get("is_active", True):
            continue
        if not _assignments.matches_employee(employee, rule, now):
            continue
        if course_id in existing:
            course_progress = existing[course_id]
            if course_progress.get("status") == "revoked":
                _progress.save(
                    employee_id,
                    course_id,
                    _reactivated_progress(course_progress, employee, now, rule["deadline_days"]),
                )
                reactivated += 1
                if notify:
                    schedule_employee_broadcast(employee_id)
            continue
        _progress.save(
            employee_id,
            course_id,
            {
                **_new_progress(now, rule["deadline_days"]),
                "assigned_department": employee.get("department"),
            },
        )
        assigned += 1
        if notify:
            schedule_employee_broadcast(employee_id)
    return {"assigned": assigned, "removed": removed, "reactivated": reactivated}


def ensure_assignments_for_employee(employee_id: str) -> bool:
    changes = reconcile_assignments_for_employee(employee_id)
    return any(changes.values())


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
        return {"assigned": 0, "removed": 0, "reactivated": 0, "deadline_updates": 0}
    published_ids = {course["course_id"] for course in _courses.list("published")}
    if course_id not in published_ids:
        return {"assigned": 0, "removed": 0, "reactivated": 0, "deadline_updates": 0}

    matched_employees = _assignments.matching_employees(rule)
    matched_by_id = {employee["employee_id"]: employee for employee in matched_employees}
    existing_progress = _progress.get_for_course(course_id)
    assigned = 0
    removed = 0
    reactivated = 0
    deadline_updates = 0

    for employee_id, course_progress in list(existing_progress.items()):
        if employee_id not in matched_by_id and course_progress.get("status") != "revoked":
            _progress.save(
                employee_id,
                course_id,
                _revoked_progress(course_progress, now, "assignment_rule_no_longer_matches"),
            )
            removed += 1
            schedule_employee_broadcast(employee_id)

    for employee in matched_employees:
        employee_id = employee["employee_id"]
        if employee_id in existing_progress:
            course_progress = existing_progress[employee_id]
            if course_progress.get("status") == "revoked":
                _progress.save(
                    employee_id,
                    course_id,
                    _reactivated_progress(course_progress, employee, now, rule["deadline_days"]),
                )
                reactivated += 1
                schedule_employee_broadcast(employee_id)
                continue
            if deadline_changed:
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
            {
                **_new_progress(now, rule["deadline_days"]),
                "assigned_department": employee.get("department"),
            },
        )
        assigned += 1
        schedule_employee_broadcast(employee_id)
    return {
        "assigned": assigned,
        "removed": removed,
        "reactivated": reactivated,
        "deadline_updates": deadline_updates,
    }


def api_assignment_options():
    return _employees.assignment_options()


def api_saved_assignment_groups(trainer_id: str, group_type: str | None = None):
    return _saved_groups.list(trainer_id, group_type)


def api_create_saved_assignment_group(
    trainer_id: str, payload: SavedAssignmentGroupRequest
):
    return _saved_groups.upsert(trainer_id, payload.model_dump())


def api_update_saved_assignment_group(
    trainer_id: str, saved_group_id: str, payload: SavedAssignmentGroupRequest
):
    group = _saved_groups.update(trainer_id, saved_group_id, payload.model_dump())
    if not group:
        raise NotFoundError("Saved group not found")
    return group


def api_delete_saved_assignment_group(trainer_id: str, saved_group_id: str):
    if not _saved_groups.delete(trainer_id, saved_group_id):
        raise NotFoundError("Saved group not found")
    return {"message": "Saved group deleted."}


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
    changes = assign_published_course_to_matching_employees(course_id)
    response = _assignment_response(rule)
    response.update(
        {
            "assigned_count": changes["assigned"],
            "removed_count": changes["removed"],
            "reactivated_count": changes["reactivated"],
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

    now = datetime.now()
    for employee_id, course_progress in _progress.get_for_course(course_id).items():
        if course_progress.get("status") != "revoked":
            _progress.save(
                employee_id,
                course_id,
                _revoked_progress(course_progress, now, "assignment_rule_disabled"),
            )
        schedule_employee_broadcast(employee_id)
    response = _assignment_response(rule)
    response.update({"message": "Course disabled for employees."})
    return response


__all__ = [
    "api_assignable_courses",
    "api_assignment_options",
    "api_get_course_assignment",
    "api_saved_assignment_groups",
    "api_create_saved_assignment_group",
    "api_update_saved_assignment_group",
    "api_delete_saved_assignment_group",
    "api_publish_course_assignment",
    "api_save_course_assignment",
    "api_disable_course_assignment",
    "assign_published_course_to_matching_employees",
    "assign_published_courses_to_employees",
    "ensure_assignments_for_employee",
    "reconcile_assignments_for_employee",
]
