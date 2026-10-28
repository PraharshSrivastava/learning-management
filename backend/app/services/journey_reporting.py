"""Learning Journey results for the Performance report.

A journey learner is in a report scope when the scope can see at least one of that learner's
course assignments for the journey's courses. So the report views (all courses, my courses,
department heads, Observers) and the report filters work for journeys exactly as for courses.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from app.core.exceptions import NotFoundError
from app.core.settings import settings
from app.repositories import performance_reporting as course_reports
from app.schemas.reporting_scope import TrainerPerformanceScope, TrainerReportScope
from app.services.assignment_conflicts import observer_ids
from app.services.journey_certificates import _certificate_for, certificate_number
from app.services.journeys import _course_availability, _evaluate, _journeys, journeys_enabled
from app.services.performance_reporting import INACTIVE_DAYS, _local_datetime

# Report course availability → the journeys it shows. A disabled journey removes its learners,
# so it only appears with the history choices.
_JOURNEY_STATUSES = {
    "active": {"published"},
    "all": {"published", "disabled"},
    "disabled": {"disabled"},
    "archived": {"disabled"},
}
_STEP_STATES = ("passed", "in_progress", "available", "locked", "unavailable")


def _course_status(scope: TrainerReportScope) -> str:
    return getattr(scope, "course_status", "active")


def _visibility_scope(scope: TrainerReportScope) -> TrainerReportScope:
    """The same people and courses, counting removed course assignments too.

    A learner who finished a step keeps their place in the journey report even when that
    course assignment was later removed.
    """
    if isinstance(scope, str):
        return TrainerPerformanceScope(trainer_id=scope, course_status="all")
    return replace(scope, course_status="all")


def _flags(row: dict, now: datetime) -> dict:
    open_row = row["status"] not in {"completed", "removed", "waiting"}
    deadline = _local_datetime(row["deadline"])
    activity = _local_datetime(row["last_learner_activity_at"])
    opened = _local_datetime(row["available_at"] or row["assigned_at"])
    cutoff = now - timedelta(days=INACTIVE_DAYS)
    return {
        "due_soon": open_row
        and deadline is not None
        and now < deadline <= now + timedelta(days=settings.email_due_soon_days),
        "inactive": open_row
        and (
            (activity is not None and activity < cutoff)
            or (
                activity is None
                and not row["started_at"]
                and opened is not None
                and opened < cutoff
            )
        ),
    }


def _learner_row(
    journey: dict,
    employee: dict,
    evaluation,
    stored: dict,
    removed: bool,
    progress: dict,
    now,
    *,
    snapshot: bool,
):
    """One learner's report row.

    ``snapshot`` marks a removed learner or a disabled journey, evaluated only to show how far
    the learner got: completion then comes from the stored assignment alone. A certificate
    number is shown only for a stored completion, so it always matches a downloadable PDF.
    """
    assignment = evaluation.assignment
    stored_completed_at = stored.get("completed_at")
    steps = evaluation.state.steps
    counted = [step for step in steps if step.is_required and step.state != "unavailable"]
    passed = sum(step.state == "passed" for step in counted)
    current = next((step for step in steps if step.state in {"in_progress", "available"}), None)
    names = {step["course_id"]: step["course_name"] for step in journey["steps"]}
    activities = [
        item["last_learner_activity_at"]
        for course_id, item in progress.items()
        if course_id in names and item.get("last_learner_activity_at")
    ]
    completed_at = stored_completed_at if snapshot else assignment.get("completed_at")
    completed = bool(completed_at)
    status = assignment["status"]
    if snapshot and not completed and status == "completed":
        # Evaluating a removed or disabled journey can finish it in memory; it was not.
        status = "started" if assignment.get("started_at") else "pending"
    row = {
        "journey_id": journey["journey_id"],
        "employee_id": assignment["employee_id"],
        "employee_name": employee.get("employee_name") or assignment["employee_id"],
        "employee_status": employee.get("employee_status") or "active",
        "department": employee.get("department"),
        # A completed journey stays completed, even after the learner was removed from it.
        "status": "completed" if completed else "removed" if removed else status,
        "assigned_at": assignment.get("assigned_at"),
        "available_at": assignment.get("available_at"),
        "started_at": assignment.get("started_at"),
        "completed_at": completed_at,
        "deadline": assignment.get("deadline"),
        "last_learner_activity_at": max(activities) if activities else None,
        "passed_count": passed,
        "required_count": len(counted),
        "completion_percent": round(100 * passed / len(counted)) if counted else 100 * completed,
        "current_step": (current.position + 1) if current and not removed else None,
        "current_course_id": current.course_id if current and not removed else None,
        "current_course_name": names.get(current.course_id) if current and not removed else None,
        "certificate_number": (
            certificate_number(assignment["journey_assignment_id"])
            if journey["certificate_enabled"] and stored_completed_at
            else None
        ),
        "step_states": {step.course_id: step.state for step in steps},
    }
    row.update(_flags(row, now))
    return row


def _report_rows(scope: TrainerReportScope, *, journey_id: str | None = None, **filters: Any):
    """Visible journeys and their learner rows, for the scope and the report filters."""
    statuses = _JOURNEY_STATUSES.get(_course_status(scope), set())
    course_filter = filters.pop("course_id", None)
    every = {journey["journey_id"]: journey for journey in _journeys.list()}
    journeys = {
        jid: journey
        for jid, journey in every.items()
        if journey["status"] in statuses
        and (journey_id is None or journey["journey_id"] == journey_id)
        and (
            course_filter is None
            or any(step["course_id"] == course_filter for step in journey["steps"])
        )
    }
    if not journeys:
        return journeys, []
    course_ids = sorted({step["course_id"] for journey in journeys.values() for step in journey["steps"]})
    visible = course_reports.visible_learner_courses(_visibility_scope(scope), course_ids, **filters)
    # Learners with none of the journey's courses yet (waiting on a prerequisite, say).
    unstarted = course_reports.visible_unstarted_journey_learners(
        _visibility_scope(scope), sorted(journeys), **filters
    )
    employee_ids = sorted({employee_id for employee_id, _ in visible | unstarted})
    all_assignments = _journeys.assignments_for_employees(employee_ids)
    wanted: list[tuple[str, str]] = []
    for employee_id in employee_ids:
        for jid, assignment in all_assignments.get(employee_id, {}).items():
            journey = journeys.get(jid)
            if journey is None:
                continue
            if assignment.get("revoked_at") and _course_status(scope) == "active":
                continue
            if (employee_id, jid) in unstarted or any(
                (employee_id, step["course_id"]) in visible for step in journey["steps"]
            ):
                wanted.append((employee_id, jid))
    if not wanted:
        return journeys, []

    # Prerequisite journeys are evaluated too, so a waiting journey reads the same as for the
    # learner. Preloading keeps this to a few queries however many learners there are.
    published = {jid: journey for jid, journey in every.items() if journey["status"] == "published"}
    all_course_ids = sorted(
        {step["course_id"] for journey in every.values() for step in journey["steps"]}
    )
    availability = _course_availability(all_course_ids)
    observers = {course_id: observer_ids(course_id) for course_id in all_course_ids}
    learners = {employee_id for employee_id, _ in wanted}
    progress = _journeys.course_states_for_employees(sorted(learners), all_course_ids)
    people = course_reports.report_people(sorted(learners))
    now = datetime.now()

    rows = []
    current: dict[str, dict] = {}
    for employee_id, jid in wanted:
        assignments = all_assignments[employee_id]
        mine = progress.get(employee_id, {})
        removed = bool(assignments[jid].get("revoked_at"))
        if removed or jid not in published:
            # Evaluate a removed learner as if still enrolled, only to show how far they got.
            evaluation = _evaluate(
                employee_id,
                {**published, jid: journeys[jid]},
                {**assignments, jid: {**assignments[jid], "revoked_at": None}},
                mine,
                now,
                persist=False,
                availability=availability,
                observers=observers,
            )[jid]
        else:
            if employee_id not in current:
                current[employee_id] = _evaluate(
                    employee_id,
                    published,
                    assignments,
                    mine,
                    now,
                    persist=False,
                    availability=availability,
                    observers=observers,
                )
            evaluation = current[employee_id][jid]
        rows.append(
            _learner_row(
                journeys[jid],
                people.get(employee_id, {}),
                evaluation,
                assignments[jid],
                removed,
                mine,
                now,
                snapshot=removed or jid not in published,
            )
        )
    rows.sort(key=lambda row: (row["employee_name"].casefold(), row["employee_id"]))
    return journeys, rows


def _summary(journey: dict, rows: list[dict]) -> dict:
    counts = {status: 0 for status in ("completed", "started", "pending", "waiting", "overdue", "removed")}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    assigned = len(rows)
    return {
        "journey_id": journey["journey_id"],
        "title": journey["title"],
        "journey_status": journey["status"],
        "step_count": len(journey["steps"]),
        "required_count": sum(step["is_required"] for step in journey["steps"]),
        "certificate_enabled": bool(journey["certificate_enabled"]),
        "assigned": assigned,
        "unique_learners": len({row["employee_id"] for row in rows}),
        **counts,
        "due_soon": sum(row["due_soon"] for row in rows),
        "inactive": sum(row["inactive"] for row in rows),
        "completion_rate": round(100 * counts["completed"] / assigned) if assigned else 0,
        "average_progress": round(sum(row["completion_percent"] for row in rows) / assigned)
        if assigned
        else 0,
        "certificates": sum(row["certificate_number"] is not None for row in rows),
    }


def journey_list(scope: TrainerReportScope, **filters: Any) -> dict:
    now = datetime.now().isoformat()
    if not journeys_enabled():
        return {"enabled": False, "journeys": [], "generated_at": now}
    journeys, rows = _report_rows(scope, **filters)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["journey_id"], []).append(row)
    summaries = [_summary(journeys[jid], items) for jid, items in grouped.items()]
    summaries.sort(key=lambda item: (item["title"].casefold(), item["journey_id"]))
    return {"enabled": True, "journeys": summaries, "generated_at": now}


def journey_detail(scope: TrainerReportScope, journey_id: str, **filters: Any) -> dict | None:
    if not journeys_enabled():
        return None
    journeys, rows = _report_rows(scope, journey_id=journey_id, **filters)
    journey = journeys.get(journey_id)
    if journey is None:
        return None
    # The creator's own journey opens even before anyone is in it; others see only learners.
    owner = isinstance(scope, TrainerPerformanceScope) and scope.trainer_id == journey.get("trainer_id")
    if not rows and not owner:
        return None
    stage_titles = {stage["stage_id"]: stage["title"] for stage in journey["stages"]}
    steps = []
    for index, step in enumerate(journey["steps"]):
        states = [row["step_states"].get(step["course_id"], "locked") for row in rows]
        steps.append(
            {
                "course_id": step["course_id"],
                "course_name": step["course_name"],
                "step_number": index + 1,
                "stage_title": stage_titles.get(step["stage_id"]) if len(journey["stages"]) > 1 else None,
                "is_required": bool(step["is_required"]),
                "unlock_rule": step["unlock_rule"],
                "learners": len(rows),
                **{state: states.count(state) for state in _STEP_STATES},
            }
        )
    return {
        "journey": _summary(journey, rows),
        "steps": steps,
        "learners": [{key: value for key, value in row.items() if key != "step_states"} for row in rows],
        "generated_at": datetime.now().isoformat(),
    }


def journey_certificate(scope: TrainerReportScope, journey_id: str, employee_id: str):
    """A learner's certificate, for anyone whose report scope shows that learner's journey."""
    detail = journey_detail(scope, journey_id, employee_id=employee_id)
    row = next(
        (item for item in (detail or {}).get("learners", []) if item["employee_id"] == employee_id),
        None,
    )
    if row is None or row["certificate_number"] is None:
        raise NotFoundError("Certificate not found")
    assignment = _journeys.assignments_for_employee(employee_id).get(journey_id)
    journey = _journeys.get(journey_id)
    if assignment is None or journey is None:
        raise NotFoundError("Certificate not found")
    return _certificate_for(assignment, journey)
