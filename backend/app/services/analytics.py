"""Trainer performance analytics use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.repositories.assignments import AssignmentRepository
from app.repositories.courses import CourseRepository
from app.repositories.employees import EmployeeRepository
from app.repositories.progress import ProgressRepository
from app.services.course_access import course_title, parse_datetime

_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()
_assignments = AssignmentRepository()


def _performance_status(progress: dict, now: datetime) -> dict[str, str]:
    status = (progress.get("status") or "pending").lower()
    deadline = parse_datetime(progress.get("deadline"))
    if status == "completed":
        return {"key": "completed", "label": "Completed"}
    if deadline and now > deadline:
        return {"key": "overdue", "label": "Overdue"}
    if status == "started":
        return {"key": "started", "label": "Started"}
    return {"key": "pending", "label": "Pending"}


def _module_performance(course: dict, progress: dict) -> dict[str, Any]:
    modules = course.get("modules") or []
    progress_by_module = progress.get("modules") or {}
    attempts_by_module = progress.get("attempts") or {}
    details = []
    completed = 0
    total_attempts = 0
    scores = []
    latest_score = None
    latest_attempt_at = None

    for module in modules:
        module_number = str(module.get("module_number", len(details) + 1))
        module_progress = progress_by_module.get(module_number, {})
        attempt = attempts_by_module.get(module_number, {})
        attempt_count = int(attempt.get("count") or 0)
        total_attempts += attempt_count
        score = module_progress.get("quiz_score", attempt.get("last_score"))
        if isinstance(score, (int, float)):
            scores.append(float(score))
        attempt_at = parse_datetime(attempt.get("last_attempt_at"))
        if attempt_at and (latest_attempt_at is None or attempt_at > latest_attempt_at):
            latest_attempt_at = attempt_at
            latest_score = score
        video_watched = bool(module_progress.get("video_watched"))
        quiz_required = bool(module.get("quiz"))
        quiz_passed = bool(module_progress.get("quiz_passed")) or (
            not quiz_required and video_watched
        )
        if video_watched and quiz_passed:
            completed += 1
        details.append(
            {
                "module_number": int(module.get("module_number", len(details) + 1)),
                "title": module.get("title", f"Module {module_number}"),
                "video_watched": video_watched,
                "quiz_passed": quiz_passed,
                "quiz_score": score,
                "attempt_count": attempt_count,
                "last_score": attempt.get("last_score"),
                "last_passed": attempt.get("last_passed"),
                "last_attempt_at": attempt.get("last_attempt_at"),
            }
        )

    total = len(modules)
    return {
        "total_modules": total,
        "completed_modules": completed,
        "completion_percent": round((completed / total) * 100) if total else 0,
        "total_attempts": total_attempts,
        "latest_score": latest_score,
        "best_score": max(scores) if scores else None,
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "modules": details,
    }


def _new_breakdown(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "assigned": 0,
        "pending": 0,
        "started": 0,
        "completed": 0,
        "overdue": 0,
        "completion_rate": 0,
    }


def _add_breakdown_count(
    groups: dict[str, dict[str, Any]],
    label: str,
    status_key: str,
) -> None:
    group = groups.setdefault(label, _new_breakdown(label))
    group["assigned"] += 1
    group[status_key] += 1


def _finalize_breakdowns(
    groups: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    values = list(groups.values())
    for group in values:
        assigned = group["assigned"]
        group["completion_rate"] = round((group["completed"] / assigned) * 100) if assigned else 0
    return sorted(values, key=lambda item: (-item["assigned"], str(item["label"])))


def api_trainer_performance(
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    job_title: str | None = None,
    status: str | None = None,
    joined_less_than_days_ago: int | None = None,
):
    now = datetime.now()
    employees = {employee["employee_id"]: employee for employee in _employees.list(include_inactive=True)}
    courses = {
        course["course_id"]: course
        for course in _courses.list("published")
    }
    rows = []
    summary = {
        "assigned": 0,
        "pending": 0,
        "started": 0,
        "completed": 0,
        "overdue": 0,
        "completion_rate": 0,
        "average_attempts": 0,
        "average_score": None,
    }
    course_groups: dict[str, dict[str, Any]] = {}
    department_groups: dict[str, dict[str, Any]] = {}
    job_title_groups: dict[str, dict[str, Any]] = {}
    total_attempts = 0
    scores = []

    for progress in _progress.list():
        employee = employees.get(progress["employee_id"])
        course = courses.get(progress["course_id"])
        if not employee or not course:
            continue
        rule = _assignments.get(progress["course_id"])
        if rule.get("published_at") and not rule.get("is_active", True):
            continue
        status_info = _performance_status(progress, now)
        if course_id and progress["course_id"] != course_id:
            continue
        if employee_id and progress["employee_id"] != employee_id:
            continue
        if department and employee.get("department") != department:
            continue
        if job_title and employee.get("job_title") != job_title:
            continue
        if joined_less_than_days_ago is not None:
            try:
                join_date = datetime.fromisoformat(employee["join_date"]).date()
            except (KeyError, TypeError, ValueError):
                continue
            if (now.date() - join_date).days >= joined_less_than_days_ago:
                continue
        if status and status_info["key"] != status:
            continue

        metrics = _module_performance(course, progress)
        total_attempts += int(metrics["total_attempts"])
        if isinstance(metrics["average_score"], (int, float)):
            scores.append(float(metrics["average_score"]))
        summary["assigned"] += 1
        summary[status_info["key"]] += 1
        _add_breakdown_count(course_groups, course_title(course), status_info["key"])
        _add_breakdown_count(
            department_groups,
            employee.get("department") or "Unassigned",
            status_info["key"],
        )
        _add_breakdown_count(
            job_title_groups,
            employee.get("job_title") or "Unassigned",
            status_info["key"],
        )
        rows.append(
            {
                "employee": {
                    key: employee[key]
                    for key in (
                        "employee_id",
                        "name",
                        "department",
                        "job_title",
                        "join_date",
                        "status",
                    )
                },
                "course": {
                    "course_id": progress["course_id"],
                    "course_name": course_title(course),
                    "module_count": len(course.get("modules") or []),
                },
                "status": status_info,
                "assigned_at": progress.get("assigned_at"),
                "deadline": progress.get("deadline"),
                "started_at": progress.get("started_at"),
                "completed_at": progress.get("completed_at"),
                "last_activity_at": progress.get("last_activity_at"),
                **metrics,
            }
        )

    if summary["assigned"]:
        summary["completion_rate"] = round((summary["completed"] / summary["assigned"]) * 100)
        summary["average_attempts"] = round(
            total_attempts / summary["assigned"],
            2,
        )
    if scores:
        summary["average_score"] = round(sum(scores) / len(scores), 2)
    rows.sort(
        key=lambda item: (
            item["status"]["key"] != "overdue",
            item["deadline"] or "",
            item["employee"]["name"],
        )
    )

    options = _employees.assignment_options()
    options["courses"] = [
        {"course_id": identifier, "course_name": course_title(course)}
        for identifier, course in sorted(
            courses.items(),
            key=lambda item: course_title(item[1]),
        )
    ]
    options["statuses"] = [
        {"key": "pending", "label": "Pending"},
        {"key": "started", "label": "Started"},
        {"key": "completed", "label": "Completed"},
        {"key": "overdue", "label": "Overdue"},
    ]
    return {
        "summary": summary,
        "breakdowns": {
            "courses": _finalize_breakdowns(course_groups),
            "departments": _finalize_breakdowns(department_groups),
            "job_titles": _finalize_breakdowns(job_title_groups),
        },
        "rows": rows,
        "options": options,
        "generated_at": now.isoformat(),
    }
