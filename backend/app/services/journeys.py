"""Learning Journey use cases: trainer authoring, per-employee sync and learner views.

A journey never copies course content. It decides which existing courses an employee is
assigned, and when: a step's course gets a normal course assignment only once the step
unlocks, so progress, the course player, emails and reports keep working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.settings import settings
from app.repositories.assignments import (
    employee_matches_assignment_rule,
    get_assignment_rule,
    matching_employees_for_assignment_rule,
)
from app.repositories.courses import CourseRepository, update_course_status
from app.repositories.database import advisory_lock, get_connection
from app.repositories.employees import EmployeeRepository
from app.repositories.journeys import JourneyRepository, assignment_changed
from app.repositories.progress import ProgressRepository
from app.schemas.journey import JourneyCreateRequest, JourneyObserversRequest, JourneySaveRequest
from app.services.assignment_conflicts import observer_ids
from app.services.assignment_deadlines import deadline_expired, resolve_deadline, validate_deadline
from app.services.course_access import course_is_publishable
from app.services.journey_state import (
    CourseState,
    JourneyState,
    StepInput,
    evaluate_steps,
    journey_status,
    prerequisite_met,
)

_journeys = JourneyRepository()
_courses = CourseRepository()
_employees = EmployeeRepository()
_progress = ProgressRepository()

DEFAULT_RULE = {
    "include_all": True,
    "include_groups": [],
    "exclude_groups": [],
    "deadline_mode": "relative",
    "deadline_days": 30,
    "deadline_date": None,
}


def journeys_enabled() -> bool:
    return bool(settings.learning_journeys_enabled)


def _require_enabled() -> None:
    if not journeys_enabled():
        raise NotFoundError("Learning journeys are not enabled")


def _rule(rule: dict | None) -> dict:
    return {**DEFAULT_RULE, **(rule or {})}


def _now_iso(now: datetime) -> str:
    return now.isoformat()


# ---------------------------------------------------------------------------
# Course availability
# ---------------------------------------------------------------------------


def _course_availability(course_ids) -> dict[str, dict]:
    """Learner-side availability: published and not Disabled by its creator."""
    ids = sorted(set(course_ids))
    if not ids:
        return {}
    with get_connection() as db:
        rows = db.execute(
            """
            SELECT c.course_id, c.status, ar.published_at AS rule_published_at,
                   ar.is_active AS rule_active
            FROM courses c LEFT JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE c.course_id = ANY(?)
            """,
            (ids,),
        ).fetchall()
    return {
        row["course_id"]: {
            "status": row["status"],
            "published": row["status"] == "published",
            # A course is Disabled when its published rule was switched off (course_lifecycle).
            "disabled": bool(row["rule_published_at"]) and row["rule_active"] is False,
        }
        for row in rows
    }


def _course_state(progress: dict | None) -> CourseState:
    if not progress:
        return CourseState()
    revoked = bool(progress.get("revoked_at")) or progress.get("status") == "revoked"
    passed = progress.get("status") == "completed" or bool(progress.get("completed_at"))
    started = bool(progress.get("started_at")) or progress.get("status") == "started"
    return CourseState(active=not revoked, started=started, passed=passed)


# ---------------------------------------------------------------------------
# Per-employee evaluation
# ---------------------------------------------------------------------------


@dataclass
class _Evaluation:
    journey: dict
    assignment: dict
    state: JourneyState
    available: bool


def _evaluate(
    employee_id: str,
    journeys: dict[str, dict],
    assignments: dict[str, dict],
    progress: dict[str, dict],
    now: datetime,
    *,
    persist: bool,
) -> dict[str, _Evaluation]:
    """Evaluate every active journey assignment, prerequisites first."""
    active = {
        journey_id: assignment
        for journey_id, assignment in assignments.items()
        if journey_id in journeys and not assignment.get("revoked_at")
    }
    course_ids = {step["course_id"] for jid in active for step in journeys[jid]["steps"]}
    availability = _course_availability(course_ids)
    observed: dict[str, bool] = {}

    def step_available(course_id: str) -> bool:
        info = availability.get(course_id)
        if not info or not info["published"] or info["disabled"]:
            return False
        if course_id not in observed:
            observed[course_id] = employee_id in observer_ids(course_id)
        return not observed[course_id]

    results: dict[str, _Evaluation] = {}

    def visit(journey_id: str, trail: frozenset[str]) -> _Evaluation:
        if journey_id in results:
            return results[journey_id]
        journey = journeys[journey_id]
        stored = active[journey_id]
        assignment = dict(stored)
        prerequisite_id = journey.get("prerequisite_journey_id")
        prerequisite_assignment = None
        if prerequisite_id and prerequisite_id in active and prerequisite_id not in trail:
            prerequisite_assignment = visit(prerequisite_id, trail | {journey_id}).assignment
        # Once a journey has opened for someone it stays open, even if its prerequisite later
        # changes or a prerequisite journey is assigned again.
        available = bool(assignment.get("available_at")) or prerequisite_met(prerequisite_assignment)
        if available and not assignment.get("available_at"):
            assignment["available_at"] = _now_iso(now)
            assignment["deadline"] = resolve_deadline(_rule(journey.get("applied_rule")), now)
        unlocked_before = set(assignment.get("unlocked_course_ids") or [])
        steps = [
            StepInput(
                step_id=step["step_id"],
                course_id=step["course_id"],
                position=step["position"],
                unlock_rule=step["unlock_rule"],
                is_required=step["is_required"],
                available=step_available(step["course_id"]),
                previously_unlocked=step["course_id"] in unlocked_before,
            )
            for step in journey["steps"]
        ]
        courses = {step.course_id: _course_state(progress.get(step.course_id)) for step in steps}
        state = evaluate_steps(steps, courses, available)
        assignment["unlocked_course_ids"] = sorted(unlocked_before | set(state.unlocked_course_ids))
        if state.complete and not assignment.get("completed_at"):
            assignment["completed_at"] = _now_iso(now)
        if state.started and not assignment.get("started_at"):
            assignment["started_at"] = _now_iso(now)
        # A completed journey stays completed, so its certificate is never withdrawn.
        assignment["status"] = (
            "completed"
            if assignment.get("completed_at")
            else journey_status(
                available=available,
                complete=state.complete,
                started=state.started,
                deadline=assignment.get("deadline"),
                now=now,
            )
        )
        if persist and assignment_changed(stored, assignment):
            assignment = _journeys.save_assignment(assignment)
        evaluation = _Evaluation(journey, assignment, state, available)
        results[journey_id] = evaluation
        return evaluation

    for journey_id in active:
        visit(journey_id, frozenset())
    return results


def _sync_membership(
    employee: dict, assignments: dict[str, dict], journeys: dict[str, dict], now: datetime
) -> dict[str, dict]:
    """Give matching employees their journeys and withdraw journeys that are no longer published.

    Membership is sticky: once assigned, a journey stays while the employee is active and the
    journey is published, even when a time-based filter such as "joined in the last 30 days"
    stops matching.
    """
    employee_id = employee["employee_id"]
    observed = _journeys.observed_by(employee_id)
    for journey_id, journey in journeys.items():
        rule = journey.get("applied_rule")
        # A journey's Observers are never enrolled as its learners.
        if rule is None or journey_id in observed:
            continue
        existing = assignments.get(journey_id)
        if existing is not None and not existing.get("revoked_at"):
            continue
        if not employee_matches_assignment_rule(employee, _rule(rule), now):
            continue
        if existing is None and deadline_expired(_rule(rule)):
            continue
        if existing is None:
            row = {
                "journey_id": journey_id,
                "employee_id": employee_id,
                "status": "waiting",
                "assigned_at": _now_iso(now),
            }
        else:
            row = {**existing, "revoked_at": None, "revoked_reason": None}
            if not existing.get("completed_at") and existing.get("available_at"):
                # Coming back to an opened journey: it stays open with a fresh deadline.
                row["deadline"] = resolve_deadline(_rule(rule), now)
        assignments[journey_id] = _journeys.save_assignment(row)
    for journey_id, assignment in list(assignments.items()):
        if journey_id not in journeys and not assignment.get("revoked_at"):
            assignments[journey_id] = _journeys.save_assignment(
                {**assignment, "revoked_at": _now_iso(now), "revoked_reason": "journey_disabled"}
            )
    return assignments


def journey_wanted_courses(
    employee_id: str, employee: dict | None, progress: dict[str, dict], now: datetime
) -> dict[str, str]:
    """Sync one employee's journeys and return each unlocked course with its deadline.

    Called by `reconcile_assignments_for_employee`, which creates, keeps or reactivates the
    matching course assignments.
    """
    if not journeys_enabled():
        return {}
    assignments = _journeys.assignments_for_employee(employee_id)
    if not employee or employee.get("status") != "active":
        for assignment in assignments.values():
            if not assignment.get("revoked_at"):
                _journeys.save_assignment(
                    {**assignment, "revoked_at": _now_iso(now), "revoked_reason": "employee_inactive"}
                )
        return {}
    journeys = {journey["journey_id"]: journey for journey in _journeys.list(status="published")}
    if not journeys and not assignments:
        return {}
    assignments = _sync_membership(employee, assignments, journeys, now)
    evaluations = _evaluate(employee_id, journeys, assignments, progress, now, persist=True)
    wanted: dict[str, str] = {}
    for evaluation in evaluations.values():
        if not evaluation.available:
            continue
        deadline = evaluation.assignment.get("deadline") or (now + timedelta(days=30)).isoformat()
        for step in evaluation.state.steps:
            if not step.unlocked:
                continue
            current = wanted.get(step.course_id)
            wanted[step.course_id] = deadline if current is None else min(current, deadline)
    return wanted


def learner_course_journeys(employee_id: str) -> dict[str, list[dict]]:
    """Read-only: the active journeys that contain each course, with the course's step number."""
    if not journeys_enabled():
        return {}
    assignments = _journeys.assignments_for_employee(employee_id)
    active_ids = {jid for jid, row in assignments.items() if not row.get("revoked_at")}
    if not active_ids:
        return {}
    result: dict[str, list[dict]] = {}
    for journey in _journeys.list(status="published"):
        if journey["journey_id"] not in active_ids:
            continue
        steps = journey["steps"]
        for index, step in enumerate(steps, start=1):
            result.setdefault(step["course_id"], []).append(
                {
                    "journey_id": journey["journey_id"],
                    "title": journey["title"],
                    "step": index,
                    "step_count": len(steps),
                }
            )
    return result


def journey_held_courses(employee_id: str) -> set[str]:
    """Courses an active, published journey has already unlocked for this employee.

    Read-only, and deliberately independent of the feature switch: turning Learning Journeys
    off must not take away courses people already received through a journey.
    """
    assignments = _journeys.assignments_for_employee(employee_id)
    active = {jid: row for jid, row in assignments.items() if not row.get("revoked_at")}
    if not active:
        return set()
    published = {journey["journey_id"] for journey in _journeys.list(status="published")}
    return {
        course_id
        for journey_id, row in active.items()
        if journey_id in published
        for course_id in row.get("unlocked_course_ids") or []
    }


def journeys_hold_course(employee_id: str, course_id: str) -> bool:
    """Read-only check used before a course rule revokes an assignment."""
    return course_id in journey_held_courses(employee_id)


# ---------------------------------------------------------------------------
# Trainer authoring
# ---------------------------------------------------------------------------


def _owned_journey(journey_id: str, trainer_id: str) -> dict:
    journey = _journeys.get(journey_id)
    if not journey or journey["trainer_id"] != trainer_id:
        raise NotFoundError("Learning journey not found")
    return journey


def _course_disabled(course_id: str) -> bool:
    rule = get_assignment_rule(course_id)
    return bool(rule.get("published_at")) and not rule.get("is_active", True)


def _course_option(course: dict) -> dict:
    status = course.get("status")
    reason = None
    if status not in {"ready", "published"}:
        reason = "Generate the full course first."
    elif not course_is_publishable(course):
        reason = "Generate all videos, quizzes and the thumbnail first."
    elif _course_disabled(course["course_id"]):
        reason = "This course is Disabled. Enable it from the Assign tab first."
    return {
        "course_id": course["course_id"],
        "course_name": course.get("course_name") or "",
        "course_description": course.get("course_description") or "",
        "status": status,
        "module_count": len(course.get("modules") or []),
        "eligible": reason is None,
        "reason": reason,
    }


def _course_options_by_id(trainer_id: str) -> dict[str, dict]:
    # Draft courses are listed as not eligible, so a step whose course went back to draft shows
    # a warning instead of making the journey impossible to save.
    return {
        course["course_id"]: _course_option(course)
        for course in _courses.list_for_trainer(trainer_id)
    }


def api_course_options(trainer_id: str) -> list[dict]:
    _require_enabled()
    options = _course_options_by_id(trainer_id)
    return sorted(options.values(), key=lambda item: item["course_name"].casefold())


def _warnings(journey: dict, options: dict[str, dict]) -> list[str]:
    warnings = []
    if not journey["steps"]:
        warnings.append("Add at least one course.")
    for step in journey["steps"]:
        option = options.get(step["course_id"])
        if option is None:
            warnings.append(f"{step['course_name']} is not one of your courses.")
        elif not option["eligible"]:
            warnings.append(f"{step['course_name']}: {option['reason']}")
    return warnings


def _summary(journey: dict, options: dict[str, dict]) -> dict:
    assignments = _journeys.assignments_for_journey(journey["journey_id"])
    active = [row for row in assignments if not row.get("revoked_at")]
    return {
        "journey_id": journey["journey_id"],
        "title": journey["title"],
        "description": journey["description"],
        "target_audience": journey["target_audience"],
        "status": journey["status"],
        "prerequisite_journey_id": journey["prerequisite_journey_id"],
        "certificate_enabled": journey["certificate_enabled"],
        "published_at": journey["published_at"],
        "updated_at": journey["updated_at"],
        "stage_count": len(journey["stages"]),
        "course_count": len(journey["steps"]),
        "assigned_count": len(active),
        "completed_count": sum(1 for row in active if row.get("completed_at")),
        "warnings": _warnings(journey, options),
    }


def _detail(journey: dict, options: dict[str, dict]) -> dict:
    stages = []
    for stage in journey["stages"]:
        stages.append(
            {
                "stage_id": stage["stage_id"],
                "title": stage["title"],
                "steps": [
                    {
                        **step,
                        "eligible": bool(options.get(step["course_id"], {}).get("eligible")),
                        "reason": options.get(step["course_id"], {}).get(
                            "reason", "This course is not one of your courses."
                        ),
                    }
                    for step in journey["steps"]
                    if step["stage_id"] == stage["stage_id"]
                ],
            }
        )
    return {
        **_summary(journey, options),
        "stages": stages,
        "rule": _rule(journey["rule"]),
        "applied_rule": journey["applied_rule"],
        "rule_updated_at": journey["rule_updated_at"],
    }


def api_list_journeys(trainer_id: str) -> dict:
    if not journeys_enabled():
        return {"enabled": False, "journeys": []}
    options = _course_options_by_id(trainer_id)
    return {
        "enabled": True,
        "journeys": [_summary(journey, options) for journey in _journeys.list(trainer_id=trainer_id)],
    }


def api_create_journey(trainer_id: str, payload: JourneyCreateRequest) -> dict:
    _require_enabled()
    journey_id = _journeys.create(trainer_id, payload.title.strip() or "Untitled journey")
    return api_get_journey(journey_id, trainer_id)


def api_get_journey(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    journey = _owned_journey(journey_id, trainer_id)
    return _detail(journey, _course_options_by_id(trainer_id))


def _validate_prerequisite(journey_id: str, prerequisite_id: str | None, trainer_id: str) -> None:
    if not prerequisite_id:
        return
    if prerequisite_id == journey_id:
        raise DomainValidationError("A journey cannot start after itself.")
    seen = {journey_id}
    current = _journeys.get(prerequisite_id)
    if current is None or current["trainer_id"] != trainer_id:
        raise DomainValidationError("Choose one of your own journeys as the prerequisite.")
    while current is not None:
        if current["journey_id"] in seen:
            raise DomainValidationError("These journeys would wait for each other. Choose another prerequisite.")
        seen.add(current["journey_id"])
        next_id = current.get("prerequisite_journey_id")
        current = _journeys.get(next_id) if next_id else None


def api_save_journey(journey_id: str, trainer_id: str, payload: JourneySaveRequest) -> dict:
    _require_enabled()
    with advisory_lock(f"learning_journey:{journey_id}"):
        journey = _owned_journey(journey_id, trainer_id)
        if payload.expected_updated_at is not None and payload.expected_updated_at != journey["updated_at"]:
            raise ConflictError("This journey changed. Refresh and review the saved version before saving.")
        options = _course_options_by_id(trainer_id)
        existing_ids = {step["course_id"] for step in journey["steps"]}
        for stage in payload.stages:
            for step in stage.steps:
                option = options.get(step.course_id)
                if option is None:
                    raise DomainValidationError("Add only courses you created.")
                # Steps already in the journey may stay while ineligible; they show as warnings.
                if not option["eligible"] and step.course_id not in existing_ids:
                    raise DomainValidationError(f"{option['course_name']}: {option['reason']}")
        _validate_prerequisite(journey_id, payload.prerequisite_journey_id, trainer_id)
        rule = payload.rule.model_dump(mode="json")
        if rule["deadline_mode"] == "fixed":
            validate_deadline(rule)
        else:
            rule["deadline_date"] = None
        _journeys.save(
            journey_id,
            {
                "title": payload.title.strip(),
                "description": payload.description.strip(),
                "target_audience": payload.target_audience.strip(),
                "prerequisite_journey_id": payload.prerequisite_journey_id or None,
                "certificate_enabled": payload.certificate_enabled,
            },
            [
                {
                    "title": stage.title.strip() or f"Stage {index + 1}",
                    "steps": [step.model_dump() for step in stage.steps],
                }
                for index, stage in enumerate(payload.stages)
            ],
            rule,
        )
        saved = _journeys.get(journey_id)
        if saved["status"] == "published":
            _publish_ready_courses(saved, trainer_id)
    if saved["status"] == "published":
        # Step changes apply at once; the rule applies at the next Publish, as for courses.
        _reconcile_journey_employees(journey_id)
    return api_get_journey(journey_id, trainer_id)


def api_delete_journey(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    with advisory_lock(f"learning_journey:{journey_id}"):
        journey = _owned_journey(journey_id, trainer_id)
        if journey["published_at"] or _journeys.has_assignment_history(journey_id):
            raise ConflictError("A journey that was published cannot be deleted. Disable it instead.")
        _journeys.delete(journey_id)
    return {"message": "Learning journey deleted."}


def api_preview_journey(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    journey = _owned_journey(journey_id, trainer_id)
    observer_ids = _journeys.observer_ids(journey_id)
    matches = [
        employee
        for employee in matching_employees_for_assignment_rule(_rule(journey["rule"]))
        if employee["employee_id"] not in observer_ids
    ]
    return {
        "match_count": len(matches),
        "preview_employees": [
            {key: employee.get(key) for key in ("employee_id", "name", "department", "job_title")}
            for employee in matches[:10]
        ],
    }


# Fields of a course rule that describe who gets it and when (not its publication state).
_RULE_DRAFT_FIELDS = (
    "include_all",
    "include_match_mode",
    "include_groups",
    "include_employee_ids",
    "include_departments",
    "include_mailing_lists",
    "include_job_titles",
    "joined_less_than_days_ago",
    "exclude_groups",
    "exclude_employee_ids",
    "exclude_departments",
    "exclude_mailing_lists",
    "exclude_job_titles",
    "include_inactive",
    "deadline_days",
    "deadline_mode",
    "deadline_date",
)


def _publish_ready_courses(journey: dict, trainer_id: str) -> None:
    """Make every course in the journey a live course that assigns nobody directly.

    Reports, Observers, reminder emails and Disable all require a course with a published,
    active course rule. A journey course without one gets a published rule that matches nobody,
    so people still receive it only through the journey. A trainer's unpublished draft rule is
    kept as the draft; only the applied (live) rule matches nobody.
    """
    from app.repositories.assignments import get_assignment_rule, save_assignment_rule
    from app.repositories.database import course_transaction
    from app.services.course_lifecycle import record_action

    for step in journey["steps"]:
        if step["course_trainer_id"] != trainer_id:
            continue
        course_id = step["course_id"]
        with course_transaction(course_id):
            changed = False
            if step["course_status"] == "ready":
                update_course_status(course_id, "published")
                changed = True
            rule = get_assignment_rule(course_id)
            if not rule.get("published_at"):
                save_assignment_rule(
                    course_id,
                    {"include_all": False, "include_groups": [], "exclude_groups": []},
                    publish=True,
                )
                if rule.get("updated_at") is not None:
                    save_assignment_rule(
                        course_id, {key: rule[key] for key in _RULE_DRAFT_FIELDS if key in rule}
                    )
                changed = True
            if changed:
                record_action(course_id, trainer_id, "journey_publish")


def api_publish_journey(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    with advisory_lock(f"learning_journey:{journey_id}"):
        journey = _owned_journey(journey_id, trainer_id)
        options = _course_options_by_id(trainer_id)
        if not journey["steps"]:
            raise DomainValidationError("Add at least one course before publishing.")
        problems = [
            warning for warning in _warnings(journey, options) if warning != "Add at least one course."
        ]
        if problems:
            raise DomainValidationError("Fix these courses before publishing: " + " ".join(problems))
        prerequisite_id = journey["prerequisite_journey_id"]
        if prerequisite_id:
            prerequisite = _journeys.get(prerequisite_id)
            if prerequisite is None or prerequisite["status"] != "published":
                raise DomainValidationError("Publish the journey it starts after first.")
        rule = _rule(journey["rule"])
        validate_deadline(rule)
        _publish_ready_courses(journey, trainer_id)
        before = {
            row["employee_id"]
            for row in _journeys.assignments_for_journey(journey_id)
            if not row.get("revoked_at")
        }
        _journeys.publish(journey_id, rule)
        _journeys.bump_observer_access(journey_id)
    changes = _reconcile_journey_employees(journey_id)
    after = {
        row["employee_id"]
        for row in _journeys.assignments_for_journey(journey_id)
        if not row.get("revoked_at")
    }
    detail = api_get_journey(journey_id, trainer_id)
    detail.update(
        {
            "newly_assigned_count": len(after - before),
            "course_assignments_created": changes["assigned"] + changes["reactivated"],
        }
    )
    return detail


def api_disable_journey(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    with advisory_lock(f"learning_journey:{journey_id}"):
        journey = _owned_journey(journey_id, trainer_id)
        if journey["status"] != "published":
            raise ConflictError("Only a published journey can be disabled.")
        _journeys.disable(journey_id)
        _journeys.bump_observer_access(journey_id)
        now = datetime.now()
        for row in _journeys.assignments_for_journey(journey_id):
            if not row.get("revoked_at"):
                _journeys.save_assignment(
                    {**row, "revoked_at": _now_iso(now), "revoked_reason": "journey_disabled"}
                )
    changes = _reconcile_journey_employees(journey_id)
    detail = api_get_journey(journey_id, trainer_id)
    detail.update({"course_assignments_removed": changes["removed"]})
    return detail


def _reconcile_journey_employees(journey_id: str) -> dict[str, int]:
    """Reconcile everyone the journey may now affect: rule matches and current or past assignees."""
    from app.services.assignments import reconcile_assignments_for_employee

    journey = _journeys.get(journey_id)
    employee_ids = {row["employee_id"] for row in _journeys.assignments_for_journey(journey_id)}
    if journey and journey["status"] == "published" and journey["applied_rule"] is not None:
        employee_ids |= {
            employee["employee_id"]
            for employee in matching_employees_for_assignment_rule(_rule(journey["applied_rule"]))
        }
    # Journeys that start after this one may open or close for the same people.
    for dependent in _journeys.requiring(journey_id):
        employee_ids |= {
            row["employee_id"] for row in _journeys.assignments_for_journey(dependent["journey_id"])
        }
    totals = {"assigned": 0, "removed": 0, "reactivated": 0}
    for employee_id in sorted(employee_ids):
        changes = reconcile_assignments_for_employee(employee_id, notify=True)
        for key in totals:
            totals[key] += changes.get(key, 0)
    return totals


def _active_synced_employee(db, employee_id: str) -> dict:
    """The same eligibility as course Observers: an active employee synced from the directory."""
    row = db.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
    if (
        not row
        or row["status"] != "active"
        or row.get("directory_status", "active") != "active"
        or row.get("source") != "hub"
    ):
        raise DomainValidationError("Choose an active synced employee")
    return dict(row)


def api_get_journey_observers(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    _owned_journey(journey_id, trainer_id)
    return {"journey_id": journey_id, "observers": _journeys.observers(journey_id)}


def api_save_journey_observers(
    journey_id: str, trainer_id: str, payload: JourneyObserversRequest
) -> dict:
    """Journey Observers see every course in the journey for the people they watch.

    They take effect at once while the journey is published. An Observer is never enrolled in
    the journey, so someone who already has it as a learner cannot be made its Observer.
    """
    from app.repositories.lms_access import identity_key

    _require_enabled()
    with advisory_lock(f"learning_journey:{journey_id}"):
        _owned_journey(journey_id, trainer_id)
        learners = {
            row["employee_id"]
            for row in _journeys.assignments_for_journey(journey_id)
            if not row.get("revoked_at")
        }
        prepared, conflicts = [], []
        with get_connection() as db:
            for selection in payload.observers:
                observer = _active_synced_employee(db, selection.observer_employee_id)
                if observer["employee_id"] in learners:
                    conflicts.append(observer["name"] or observer["employee_id"])
                targets = [
                    _active_synced_employee(db, employee_id)
                    for employee_id in sorted(set(selection.employee_ids))
                ]
                for department_id in set(selection.department_ids):
                    if not db.execute(
                        "SELECT 1 FROM lms_departments WHERE department_id = ? AND active",
                        (department_id,),
                    ).fetchone():
                        raise DomainValidationError("Choose a current directory department")
                prepared.append(
                    {
                        "observer_employee_id": observer["employee_id"],
                        "identity_key": identity_key(observer),
                        "employees": [(t["employee_id"], identity_key(t)) for t in targets],
                        "department_ids": sorted(set(selection.department_ids)),
                    }
                )
        if conflicts:
            raise ConflictError(
                f"{', '.join(conflicts[:10])} already {'has' if len(conflicts) == 1 else 'have'} "
                "this journey as a learner, so cannot also observe it. Choose someone else."
            )
        _journeys.replace_observers(journey_id, trainer_id, prepared)
    return api_get_journey_observers(journey_id, trainer_id)


def api_journey_progress(journey_id: str, trainer_id: str) -> dict:
    _require_enabled()
    journey = _owned_journey(journey_id, trainer_id)
    journeys = {item["journey_id"]: item for item in _journeys.list(status="published")}
    journeys[journey_id] = journey
    now = datetime.now()
    rows = []
    for assignment in _journeys.assignments_for_journey(journey_id):
        if assignment.get("revoked_at"):
            continue
        employee = _employees.get(assignment["employee_id"]) or {}
        evaluation = _evaluate(
            assignment["employee_id"],
            journeys,
            _journeys.assignments_for_employee(assignment["employee_id"]),
            _progress.get_for_employee(assignment["employee_id"]),
            now,
            persist=False,
        ).get(journey_id)
        steps = evaluation.state.steps if evaluation else ()
        counted = [step for step in steps if step.is_required and step.state != "unavailable"]
        passed = sum(1 for step in counted if step.state == "passed")
        current = next((step for step in steps if step.state in {"in_progress", "available"}), None)
        names = {step["course_id"]: step["course_name"] for step in journey["steps"]}
        rows.append(
            {
                "employee_id": assignment["employee_id"],
                "name": employee.get("name") or assignment["employee_id"],
                "department": employee.get("department") or "",
                "status": evaluation.assignment["status"] if evaluation else assignment["status"],
                "assigned_at": assignment["assigned_at"],
                "deadline": evaluation.assignment.get("deadline") if evaluation else assignment.get("deadline"),
                "completed_at": assignment.get("completed_at"),
                "passed_count": passed,
                "required_count": len(counted),
                "current_course_id": current.course_id if current else None,
                "current_course_name": names.get(current.course_id) if current else None,
                "current_step": (current.position + 1) if current else None,
            }
        )
    rows.sort(key=lambda row: (row["name"].casefold(), row["employee_id"]))
    return {"journey_id": journey_id, "rows": rows}


# ---------------------------------------------------------------------------
# Learner views
# ---------------------------------------------------------------------------


def learner_journeys(employee_id: str) -> dict:
    """The employee's journeys with every step's state. Call after reconciling the employee."""
    if not journeys_enabled():
        return {"enabled": False, "journeys": []}
    assignments = _journeys.assignments_for_employee(employee_id)
    journeys = {journey["journey_id"]: journey for journey in _journeys.list(status="published")}
    progress = _progress.get_for_employee(employee_id)
    evaluations = _evaluate(employee_id, journeys, assignments, progress, datetime.now(), persist=False)
    result = []
    for journey_id, evaluation in evaluations.items():
        journey = evaluation.journey
        names = {step["course_id"]: step for step in journey["steps"]}
        states = {step.course_id: step for step in evaluation.state.steps}
        stages = []
        for stage in journey["stages"]:
            steps = []
            for step in journey["steps"]:
                if step["stage_id"] != stage["stage_id"]:
                    continue
                state = states[step["course_id"]]
                locked_by = state.locked_by_course_id
                steps.append(
                    {
                        "course_id": step["course_id"],
                        "course_name": step["course_name"],
                        "module_count": step["module_count"],
                        "step_number": step["position"] + 1,
                        "is_required": step["is_required"],
                        "unlock_rule": step["unlock_rule"],
                        "state": state.state,
                        "locked_by_course_name": names[locked_by]["course_name"] if locked_by else None,
                    }
                )
            stages.append({"title": stage["title"], "steps": steps})
        counted = [s for s in evaluation.state.steps if s.is_required and s.state != "unavailable"]
        prerequisite = journeys.get(journey.get("prerequisite_journey_id") or "")
        prerequisite_assignment = assignments.get(prerequisite["journey_id"]) if prerequisite else None
        result.append(
            {
                "journey_id": journey_id,
                "title": journey["title"],
                "description": journey["description"],
                "certificate_enabled": journey["certificate_enabled"],
                "status": evaluation.assignment["status"],
                "assigned_at": evaluation.assignment["assigned_at"],
                "available_at": evaluation.assignment.get("available_at"),
                "deadline": evaluation.assignment.get("deadline"),
                "completed_at": evaluation.assignment.get("completed_at"),
                "step_count": len(journey["steps"]),
                "passed_count": sum(1 for s in counted if s.state == "passed"),
                "required_count": len(counted),
                "next_course_id": evaluation.state.next_course_id,
                "prerequisite": (
                    {
                        "journey_id": prerequisite["journey_id"],
                        "title": prerequisite["title"],
                        "met": prerequisite_met(prerequisite_assignment),
                    }
                    if prerequisite and prerequisite_assignment and not prerequisite_assignment.get("revoked_at")
                    else None
                ),
                "stages": stages,
            }
        )
    result.sort(key=lambda item: (item["status"] == "completed", item["title"].casefold()))
    return {"enabled": True, "journeys": result}


def api_my_journeys(employee: dict) -> dict:
    if not journeys_enabled():
        return {"enabled": False, "journeys": []}
    from app.services.assignments import ensure_assignments_for_employee

    ensure_assignments_for_employee(employee["employee_id"])
    return learner_journeys(employee["employee_id"])


__all__ = [
    "api_course_options",
    "api_create_journey",
    "api_delete_journey",
    "api_disable_journey",
    "api_get_journey",
    "api_get_journey_observers",
    "api_journey_progress",
    "api_save_journey_observers",
    "api_list_journeys",
    "api_my_journeys",
    "api_preview_journey",
    "api_publish_journey",
    "api_save_journey",
    "journey_wanted_courses",
    "journeys_enabled",
    "journeys_hold_course",
    "learner_course_journeys",
    "learner_journeys",
]
