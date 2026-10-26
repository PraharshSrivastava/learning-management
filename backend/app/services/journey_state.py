"""Learning Journey lock rules for one employee and one journey.

Pure functions with no database access, so the unlock behaviour is tested directly.
A step's course is assigned only when the step unlocks; these rules decide which steps those are.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StepInput:
    step_id: str
    course_id: str
    position: int
    unlock_rule: str  # "open" or "after_previous"
    is_required: bool
    # False when the course is unpublished or Disabled, or the employee observes it.
    available: bool
    # True when this journey already unlocked the step for the employee. It stays unlocked.
    previously_unlocked: bool = False


@dataclass(frozen=True)
class CourseState:
    """The employee's assignment for a step's course, from any source."""

    active: bool = False  # an assignment exists and is not revoked
    started: bool = False
    passed: bool = False  # completed results count even after access was revoked


@dataclass(frozen=True)
class StepState:
    step_id: str
    course_id: str
    position: int
    is_required: bool
    unlock_rule: str
    # passed | in_progress | available | locked | unavailable
    state: str
    unlocked: bool
    locked_by_course_id: str | None = None


@dataclass(frozen=True)
class JourneyState:
    steps: tuple[StepState, ...]
    complete: bool
    started: bool
    next_course_id: str | None

    @property
    def unlocked_course_ids(self) -> list[str]:
        return [step.course_id for step in self.steps if step.unlocked]


def evaluate_steps(
    steps: list[StepInput],
    courses: dict[str, CourseState],
    journey_available: bool,
) -> JourneyState:
    """Walk steps in order and decide what is unlocked, passed and complete.

    A step unlocks when the journey is available and the step is first, is `open`, or the
    nearest earlier required, available step is passed. A step this journey unlocked before
    stays unlocked, so a later journey edit never takes a course away. A course the employee
    has from its own course rule does not unlock a step: only the journey's own order does.
    """
    results: list[StepState] = []
    gate_course_id: str | None = None  # nearest earlier required, available step
    gate_passed = True
    for step in sorted(steps, key=lambda item: item.position):
        course = courses.get(step.course_id, CourseState())
        if not step.available:
            results.append(
                StepState(
                    step.step_id,
                    step.course_id,
                    step.position,
                    step.is_required,
                    step.unlock_rule,
                    "passed" if course.passed else "unavailable",
                    False,
                )
            )
            continue
        by_rule = journey_available and (step.unlock_rule == "open" or gate_passed)
        unlocked = by_rule or step.previously_unlocked
        if course.passed:
            state = "passed"
        elif unlocked:
            state = "in_progress" if course.started else "available"
        else:
            state = "locked"
        results.append(
            StepState(
                step.step_id,
                step.course_id,
                step.position,
                step.is_required,
                step.unlock_rule,
                state,
                unlocked,
                None if unlocked or not journey_available else gate_course_id,
            )
        )
        if step.is_required:
            gate_course_id = step.course_id
            gate_passed = course.passed

    required = [step for step in results if step.is_required and step.state != "unavailable"]
    complete = journey_available and bool(required) and all(
        step.state == "passed" for step in required
    )
    started = any(step.state in {"passed", "in_progress"} for step in results)
    next_step = next((step for step in results if step.state in {"in_progress", "available"}), None)
    return JourneyState(
        tuple(results), complete, started, next_step.course_id if next_step else None
    )


def prerequisite_met(prerequisite_assignment: dict | None) -> bool:
    """A prerequisite binds only employees who are assigned that journey."""
    if prerequisite_assignment is None or prerequisite_assignment.get("revoked_at"):
        return True
    return bool(prerequisite_assignment.get("completed_at"))


def journey_status(
    *, available: bool, complete: bool, started: bool, deadline: str | None, now: datetime
) -> str:
    if not available:
        return "waiting"
    if complete:
        return "completed"
    if deadline:
        try:
            if now > datetime.fromisoformat(deadline):
                return "overdue"
        except ValueError:
            pass
    return "started" if started else "pending"
