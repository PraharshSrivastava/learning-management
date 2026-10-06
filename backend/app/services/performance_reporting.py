"""Trainer performance metrics shared by dashboard, detail views, and exports."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.settings import settings
from app.repositories import performance_reporting as reports
from app.schemas.reporting_scope import TrainerReportScope
from app.services.course_access import parse_datetime

INACTIVE_DAYS = 14
FAILURE_THRESHOLD = 2


def _score_percent(value: Any) -> float | None:
    if value is None:
        return None
    score = float(value)
    return round(score * 100 if score <= 1 else score, 1)


def _local_datetime(value: str | None) -> datetime | None:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(ZoneInfo(settings.email_notification_timezone)).replace(
            tzinfo=None
        )
    return parsed


def _decorate(row: dict, now: datetime) -> dict[str, Any]:
    deadline = _local_datetime(row.get("deadline"))
    completed_at = _local_datetime(row.get("completed_at"))
    learner_activity = _local_datetime(row.get("last_learner_activity_at"))
    assigned_at = _local_datetime(row.get("assigned_at"))
    completed = row["status"] == "completed"
    overdue = not completed and deadline is not None and now > deadline
    due_soon = (
        not completed
        and deadline is not None
        and now < deadline <= now + timedelta(days=settings.email_due_soon_days)
    )
    inactive = not completed and (
        (learner_activity is not None and learner_activity < now - timedelta(days=INACTIVE_DAYS))
        or (
            learner_activity is None
            and row.get("started_at") is None
            and assigned_at is not None
            and assigned_at < now - timedelta(days=INACTIVE_DAYS)
        )
    )
    status = (
        "completed"
        if completed
        else "overdue"
        if overdue
        else "started"
        if row["status"] == "started" or row.get("started_at")
        else "pending"
    )
    total = int(row.get("total_modules") or 0)
    done = int(row.get("completed_modules") or 0)
    return {
        "assignment_id": row["assignment_id"],
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "employee_status": row["employee_status"],
        "department": row.get("department"),
        "mailing_lists": row.get("mailing_lists") or [],
        "course_id": row["course_id"],
        "course_name": row["course_name"],
        "status": status,
        "due_soon": due_soon,
        "inactive": inactive,
        "repeated_failures": not completed
        and int(row.get("failed_attempts") or 0) >= FAILURE_THRESHOLD,
        "failed_attempts": int(row.get("failed_attempts") or 0),
        "assigned_at": row.get("assigned_at"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "deadline": row.get("deadline"),
        "last_learner_activity_at": row.get("last_learner_activity_at"),
        "total_modules": total,
        "completed_modules": done,
        "completion_percent": round(100 * done / total) if total else 0,
        "total_attempts": int(row.get("total_attempts") or 0),
        "average_score": _score_percent(row.get("average_score")),
        "scored_modules": int(row.get("scored_modules") or 0),
        "on_time": completed
        and deadline is not None
        and completed_at is not None
        and completed_at <= deadline,
    }


def scoped_rows(
    trainer_id: TrainerReportScope, *, now: datetime | None = None, **filters: Any
) -> list[dict]:
    current = now or datetime.now()
    return [
        _decorate(row, current) for row in reports.list_assignment_summaries(trainer_id, **filters)
    ]


def _summary(rows: list[dict], now: datetime) -> dict:
    counts = Counter(row["status"] for row in rows)
    assigned = len(rows)
    due = [
        row for row in rows if (deadline := _local_datetime(row["deadline"])) and deadline <= now
    ]
    scored = [
        (row["average_score"], row["scored_modules"])
        for row in rows
        if row["average_score"] is not None
    ]
    score_count = sum(count for _, count in scored)
    return {
        "assigned": assigned,
        "unique_learners": len({row["employee_id"] for row in rows}),
        "pending": counts["pending"],
        "started": counts["started"],
        "completed": counts["completed"],
        "overdue": counts["overdue"],
        "due_soon": sum(row["due_soon"] for row in rows),
        "inactive": sum(row["inactive"] for row in rows),
        "repeated_failures": sum(row["repeated_failures"] for row in rows),
        "completion_rate": round(100 * counts["completed"] / assigned) if assigned else 0,
        "on_time_compliance": round(100 * sum(row["on_time"] for row in due) / len(due))
        if due
        else None,
        "on_time_denominator": len(due),
        "average_score": round(sum(score * count for score, count in scored) / score_count, 1)
        if score_count
        else None,
        "scored_modules": score_count,
    }


def _breakdown(rows: list[dict], key: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if key == "course_name":
            labels = [row["course_id"]]
        elif key == "mailing_lists":
            labels = row["mailing_lists"] or ["No mailing list"]
        else:
            labels = [row.get(key) or "Unassigned"]
        for label in labels:
            grouped[label].append(row)
    return sorted(
        (
            {
                "label": items[0]["course_name"] if key == "course_name" else label,
                **({"course_id": label} if key == "course_name" else {}),
                "assigned": len(items),
                "completed": sum(item["status"] == "completed" for item in items),
                "overdue": sum(item["status"] == "overdue" for item in items),
                "completion_rate": round(
                    100 * sum(item["status"] == "completed" for item in items) / len(items)
                ),
            }
            for label, items in grouped.items()
        ),
        key=lambda item: (-item["assigned"], item["label"]),
    )


def overview(trainer_id: TrainerReportScope, *, trend_days: int = 30, **filters: Any) -> dict:
    now = datetime.now()
    rows = scoped_rows(trainer_id, now=now, **filters)
    completions = Counter(
        date.date().isoformat()
        for row in rows
        if (date := _local_datetime(row["completed_at"])) is not None
    )
    start = now.date() - timedelta(days=trend_days - 1)
    trend = [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "completed": completions[(start + timedelta(days=index)).isoformat()],
        }
        for index in range(trend_days)
    ]
    return {
        "summary": _summary(rows, now),
        "breakdowns": {
            "courses": _breakdown(rows, "course_name"),
            "departments": _breakdown(rows, "department"),
            "mailing_lists": _breakdown(rows, "mailing_lists"),
        },
        "completion_trend": trend,
        "watchlist": sorted(
            [
                row
                for row in rows
                if row["status"] == "overdue"
                or row["due_soon"]
                or row["inactive"]
                or row["repeated_failures"]
            ],
            key=lambda row: (
                row["status"] != "overdue",
                row["deadline"] or "",
                row["employee_name"],
            ),
        )[:8],
        "generated_at": now.isoformat(),
        "due_soon_days": settings.email_due_soon_days,
        "inactive_days": INACTIVE_DAYS,
    }


def course_list(trainer_id: TrainerReportScope, **filters: Any) -> dict:
    now = datetime.now()
    rows = scoped_rows(trainer_id, now=now, **filters)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["course_id"]].append(row)
    courses = [
        {"course_id": course_id, "course_name": items[0]["course_name"], **_summary(items, now)}
        for course_id, items in grouped.items()
    ]
    return {
        "courses": sorted(courses, key=lambda item: item["course_name"].lower()),
        "generated_at": now.isoformat(),
    }


def course_detail(trainer_id: TrainerReportScope, course_id: str, **filters: Any) -> dict | None:
    courses = course_list(trainer_id, course_id=course_id, **filters)["courses"]
    if not courses:
        return None
    modules = reports.course_module_summary(trainer_id, course_id, **filters)
    for module in modules:
        module["average_score"] = _score_percent(module.get("average_score"))
    return {
        "course": courses[0],
        "modules": modules,
        "generated_at": datetime.now().isoformat(),
    }


def assignment_list(
    trainer_id: TrainerReportScope,
    *,
    status: str | None = None,
    search: str | None = None,
    sort: str = "deadline",
    descending: bool = False,
    page: int = 1,
    page_size: int = 25,
    **filters: Any,
) -> dict:
    now = datetime.now()
    total, rows = reports.assignment_page(
        trainer_id,
        status=status,
        search=search,
        sort=sort,
        descending=descending,
        page=page,
        page_size=page_size,
        now=now,
        **filters,
    )
    return {
        "rows": [_decorate(row, now) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "generated_at": now.isoformat(),
    }


def assignment_detail(trainer_id: TrainerReportScope, assignment_id: str) -> dict | None:
    detail = reports.get_assignment_detail(trainer_id, assignment_id)
    if detail is None:
        return None
    now = datetime.now()
    rows = scoped_rows(
        trainer_id,
        now=now,
        course_id=detail["assignment"]["course_id"],
        employee_id=detail["assignment"]["employee_id"],
    )
    if not rows:
        return None
    for module in detail["modules"]:
        module["latest_score"] = _score_percent(module.get("latest_score"))
    for attempt in detail["attempts"]:
        attempt["score"] = _score_percent(attempt.get("score"))
    return {
        "assignment": rows[0],
        "modules": detail["modules"],
        "attempts": detail["attempts"],
        "generated_at": now.isoformat(),
    }


def _employee_summary(rows: list[dict], now: datetime) -> dict:
    """Aggregate all scoped courses; overdue is a flag, not a progress category."""
    summary = _summary(rows, now)
    in_progress = sum(
        row["status"] != "completed"
        and bool(row["started_at"] or row["completed_modules"] or row["status"] == "started")
        for row in rows
    )
    activities = [
        (parsed, row["last_learner_activity_at"])
        for row in rows
        if (parsed := _local_datetime(row["last_learner_activity_at"])) is not None
    ]
    first = rows[0]
    return {
        "employee_id": first["employee_id"],
        "employee_name": first["employee_name"],
        "employee_status": first["employee_status"],
        "department": first["department"],
        "assigned": len(rows),
        "completed": summary["completed"],
        "in_progress": in_progress,
        "not_started": len(rows) - summary["completed"] - in_progress,
        "completion_rate": round(100 * summary["completed"] / len(rows), 1),
        **{
            key: summary[key]
            for key in (
                "overdue",
                "due_soon",
                "inactive",
                "repeated_failures",
                "average_score",
                "scored_modules",
            )
        },
        "last_learner_activity_at": max(activities)[1] if activities else None,
        "needs_attention": any(
            row["status"] == "overdue"
            or row["due_soon"]
            or row["inactive"]
            or row["repeated_failures"]
            for row in rows
        ),
    }


def employee_list(
    trainer_id: TrainerReportScope,
    *,
    search: str | None = None,
    attention: str | None = None,
    sort: str = "employee",
    descending: bool = False,
    page: int = 1,
    page_size: int = 25,
    **filters: Any,
) -> dict:
    now = datetime.now()
    summary, employees = reports.employee_page(
        trainer_id,
        search=search,
        attention=attention,
        sort=sort,
        descending=descending,
        page=page,
        page_size=page_size,
        now=now,
        **filters,
    )
    return {
        "rows": employees,
        "total": summary["employees"],
        "page": page,
        "page_size": page_size,
        "summary": summary,
        "generated_at": now.isoformat(),
    }


def employee_detail(
    trainer_id: TrainerReportScope, employee_id: str, **filters: Any
) -> dict | None:
    now = datetime.now()
    rows = scoped_rows(trainer_id, now=now, employee_id=employee_id, **filters)
    if not rows:
        return None
    return {
        "employee": _employee_summary(rows, now),
        "assignments": sorted(
            rows, key=lambda row: (row["deadline"] or "9999", row["assignment_id"])
        ),
        "generated_at": now.isoformat(),
    }
