"""Course assignment rules, publication, and employee matching use cases."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.repositories.assignments import AssignmentRepository
from app.repositories.courses import CourseRepository, update_course_status
from app.repositories.database import atomic_course, course_transaction, get_connection
from app.repositories.employees import EmployeeRepository
from app.repositories.progress import ProgressRepository
from app.repositories.saved_assignment_groups import SavedAssignmentGroupRepository
from app.schemas.assignment import AssignmentRuleRequest, SavedAssignmentGroupRequest
from app.services.assignment_conflicts import (
    observer_ids,
    validate_separation,
)
from app.services.assignment_deadlines import deadline_expired, resolve_deadline, validate_deadline
from app.services.course_access import course_is_publishable

_assignments = AssignmentRepository()
_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()
_saved_groups = SavedAssignmentGroupRepository()


def _save_progress(
    employee_id: str,
    course_id: str,
    progress: dict,
) -> None:
    _progress.save(employee_id, course_id, progress)


def _new_progress(now: datetime, deadline_days: int, rule=None) -> dict:
    return {
        "status": "pending",
        "assigned_at": now.isoformat(),
        "deadline": resolve_deadline(rule or {"deadline_days": deadline_days}, now),
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


def _reactivated_progress(progress: dict, employee: dict, now: datetime, deadline_days: int, rule=None) -> dict:
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
    if rule and rule.get("deadline_mode") == "fixed":
        next_progress["deadline"] = resolve_deadline(rule, now)
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
            _save_progress(
                employee_id,
                course_id,
                _revoked_progress(course_progress, now, reason),
            )
            removed += 1
            if notify:
                schedule_employee_broadcast(employee_id)

    if not employee or employee.get("status") != "active":
        return {"assigned": assigned, "removed": removed, "reactivated": reactivated}

    for course in _courses.list("published"):
        course_id = course["course_id"]
        if not course_id:
            continue
        with course_transaction(course_id):
            rule = _assignments.get(course_id)
            if not rule.get("published_at") or not rule.get("is_active", True):
                continue
            rule = {**rule, "deadline_mode": rule.get("applied_deadline_mode", "relative"), "deadline_date": rule.get("applied_deadline_date")}
            if employee_id in observer_ids(course_id) or deadline_expired(rule):
                continue
            if not _assignments.matches_employee(employee, rule, now):
                continue
            if course_id in existing:
                course_progress = existing[course_id]
                if course_progress.get("status") == "revoked":
                    _save_progress(
                        employee_id,
                        course_id,
                        _reactivated_progress(course_progress, employee, now, rule["deadline_days"], rule),
                    )
                    reactivated += 1
                    if notify:
                        schedule_employee_broadcast(employee_id)
                continue
            _save_progress(
                employee_id,
                course_id,
                {
                    **_new_progress(now, rule["deadline_days"], rule),
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


def reconcile_time_based_assignments(*, notify: bool = True) -> dict[str, int]:
    totals = {"assigned": 0, "removed": 0, "reactivated": 0}
    for employee in _employees.list():
        changes = reconcile_assignments_for_employee(
            employee["employee_id"],
            notify=notify,
        )
        for key in totals:
            totals[key] += changes.get(key, 0)
    return totals


@atomic_course
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

    validate_separation(course_id, rule)
    validate_deadline(rule)
    matched_employees = _assignments.matching_employees(rule)
    matched_by_id = {employee["employee_id"]: employee for employee in matched_employees}
    existing_progress = _progress.get_for_course(course_id)
    assigned = 0
    removed = 0
    reactivated = 0
    deadline_updates = 0

    for employee_id, course_progress in list(existing_progress.items()):
        if employee_id not in matched_by_id and course_progress.get("status") != "revoked":
            _save_progress(
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
                _save_progress(
                    employee_id,
                    course_id,
                    _reactivated_progress(course_progress, employee, now, rule["deadline_days"], rule),
                )
                reactivated += 1
                schedule_employee_broadcast(employee_id)
                continue
            if deadline_changed:
                if reset_assignment_dates:
                    course_progress["assigned_at"] = now.isoformat()
                if course_progress.get("status") == "completed":
                    continue
                course_progress["deadline"] = resolve_deadline(rule, now)
                course_progress["last_activity_at"] = now.isoformat()
                _save_progress(employee_id, course_id, course_progress)
                deadline_updates += 1
                schedule_employee_broadcast(employee_id)
            continue
        _save_progress(
            employee_id,
            course_id,
            {
                **_new_progress(now, rule["deadline_days"], rule),
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
        "total_assigned_count": assignment_total(rule["course_id"]),
        "blocked_employee_count": len({e["employee_id"] for e in _assignments.matching_employees(rule)} & observer_ids(rule["course_id"])),
    }


def api_get_course_assignment(course_id: str, trainer_id: str | None = None):
    if trainer_id:
        _owned_draft_course(course_id, trainer_id)
    return _assignment_response(_assignments.get(course_id))


@atomic_course
def api_save_course_assignment(
    course_id: str, payload: AssignmentRuleRequest, trainer_id: str | None = None
):
    if trainer_id:
        _owned_draft_course(course_id, trainer_id)
    existing = _assignments.get(course_id)
    if payload.expected_updated_at is not None and payload.expected_updated_at != existing.get("updated_at"):
        raise ConflictError("The saved employee rule changed. Refresh and review the saved version before saving or publishing.")
    proposed = {**existing, **payload.model_dump(exclude_unset=True, exclude={"expected_updated_at"})}
    validate_deadline(proposed)
    validate_separation(course_id, proposed)
    rule = _assignments.save(course_id, proposed)
    return _assignment_response(rule)


@atomic_course
def api_publish_course_assignment(
    course_id: str, payload: AssignmentRuleRequest, trainer_id: str | None = None
):
    if trainer_id:
        _owned_draft_course(course_id, trainer_id)
    existing = _assignments.get(course_id)
    if payload.expected_updated_at is not None and payload.expected_updated_at != existing.get("updated_at"):
        raise ConflictError("The saved employee rule changed. Refresh and review the saved version before saving or publishing.")
    proposed = {**existing, **payload.model_dump(exclude_unset=True, exclude={"expected_updated_at"})}
    validate_deadline(proposed)
    validate_separation(course_id, proposed)
    rule = _assignments.save(course_id, proposed)
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
    deadline_changed = (
        existing.get("applied_deadline_days") != rule["deadline_days"]
        or existing.get("applied_deadline_mode", "relative") != rule.get("deadline_mode", "relative")
        or existing.get("applied_deadline_date") != rule.get("deadline_date")
    )
    changes = assign_published_course_to_matching_employees(course_id, deadline_changed=deadline_changed)
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


@atomic_course
def api_disable_course_assignment(course_id: str, trainer_id: str):
    _owned_draft_course(course_id, trainer_id)
    rule = _assignments.save(
        course_id,
        _assignments.get(course_id),
        disable=True,
        disabled_by_trainer_id=trainer_id,
    )
    from app.repositories.observers import suspend_course
    from app.services.notifications import schedule_employee_broadcast

    suspend_course(course_id, trainer_id)
    now = datetime.now()
    for employee_id, course_progress in _progress.get_for_course(course_id).items():
        if course_progress.get("status") != "revoked":
            _save_progress(
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
    "reconcile_time_based_assignments",
    "reconcile_assignments_for_employee",
]


_ASSIGNED_WHERE = "ca.course_id = ? AND ca.status <> 'revoked' AND ca.revoked_at IS NULL"

def assignment_total(course_id):
    with get_connection() as db:
        return db.execute(f"SELECT COUNT(*) AS n FROM course_assignments ca WHERE {_ASSIGNED_WHERE}", (course_id,)).fetchone()["n"]

def assignment_employee_page(course_id, payload, view="matching", search="", page=1, page_size=25):
    """Read-only draft preview or persisted assignments; never reconcile on read."""
    rule = {**_assignments.get(course_id), **payload.model_dump(exclude_unset=True)}
    needle = search.strip().casefold()
    with get_connection() as db:
        total_assigned = assignment_total(course_id)
        if view == "assigned":
            term = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where = _ASSIGNED_WHERE + " AND (e.name ILIKE ? OR e.department ILIKE ? OR e.employee_id ILIKE ?)"
            params = (course_id, term, term, term)
            total = db.execute(f"SELECT COUNT(*) AS n FROM course_assignments ca JOIN employees e USING(employee_id) WHERE {where}", params).fetchone()["n"]
            rows = db.execute(f"SELECT e.employee_id, e.name, e.department, e.job_title, e.status FROM course_assignments ca JOIN employees e USING(employee_id) WHERE {where} ORDER BY lower(e.name), e.employee_id LIMIT ? OFFSET ?", (*params, page_size, (page-1)*page_size)).fetchall()
        else:
            employees = _assignments.matching_employees(rule)
            employees = sorted((e for e in employees if not needle or any(needle in str(e.get(k) or "").casefold() for k in ("name", "department", "employee_id"))), key=lambda e: (e["name"].casefold(), e["employee_id"]))
            total = len(employees)
            rows = [{k: e.get(k) for k in ("employee_id", "name", "department", "job_title", "status")} for e in employees[(page-1)*page_size:page*page_size]]
    designated = observer_ids(course_id) | set(getattr(payload, "observer_employee_ids", []))
    matching_ids = {e["employee_id"] for e in _assignments.matching_employees(rule)}
    with get_connection() as db:
        assigned_ids = {r["employee_id"] for r in db.execute("SELECT employee_id FROM course_assignments ca WHERE " + _ASSIGNED_WHERE, (course_id,)).fetchall()}
    conflicts = sorted(designated & (matching_ids | assigned_ids))
    blocked = len(designated & matching_ids)
    return {"total": total, "total_assigned_count": total_assigned, "employees": rows, "page": page, "page_size": page_size, "blocked_employee_count": blocked, "conflicting_observer_ids": conflicts}
