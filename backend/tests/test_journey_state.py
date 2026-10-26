"""Learning Journey lock rules, without a database."""

from datetime import datetime

from app.services.journey_state import (
    CourseState,
    StepInput,
    evaluate_steps,
    journey_status,
    prerequisite_met,
)


def step(
    position, course_id=None, *, rule="after_previous", required=True, available=True, unlocked=False
):
    course_id = course_id or f"c{position}"
    return StepInput(f"s{position}", course_id, position, rule, required, available, unlocked)


def states(result):
    return [item.state for item in result.steps]


def test_sequence_unlocks_only_the_first_step():
    result = evaluate_steps([step(0), step(1), step(2)], {}, True)
    assert states(result) == ["available", "locked", "locked"]
    assert result.unlocked_course_ids == ["c0"]
    assert result.steps[1].locked_by_course_id == "c0"
    assert result.next_course_id == "c0"
    assert not result.complete and not result.started


def test_passing_a_step_unlocks_the_next_one():
    courses = {"c0": CourseState(active=True, passed=True), "c1": CourseState(active=True, started=True)}
    result = evaluate_steps([step(0), step(1), step(2)], courses, True)
    assert states(result) == ["passed", "in_progress", "locked"]
    assert result.unlocked_course_ids == ["c0", "c1"]
    assert result.started


def test_open_steps_can_be_taken_in_any_order():
    steps = [step(i, rule="open") for i in range(3)]
    result = evaluate_steps(steps, {"c1": CourseState(active=True, passed=True)}, True)
    assert states(result) == ["available", "passed", "available"]
    assert result.unlocked_course_ids == ["c0", "c1", "c2"]


def test_optional_step_does_not_block_and_is_not_needed_for_completion():
    steps = [step(0), step(1, required=False), step(2)]
    courses = {"c0": CourseState(passed=True)}
    result = evaluate_steps(steps, courses, True)
    # The optional step unlocks after c0, and so does c2, because the gate is the last required step.
    assert states(result) == ["passed", "available", "available"]
    done = evaluate_steps(steps, {"c0": CourseState(passed=True), "c2": CourseState(passed=True)}, True)
    assert done.complete


def test_unavailable_step_is_skipped_for_unlocking_and_completion():
    steps = [step(0), step(1, available=False), step(2)]
    result = evaluate_steps(steps, {"c0": CourseState(passed=True)}, True)
    assert states(result) == ["passed", "unavailable", "available"]
    assert "c1" not in result.unlocked_course_ids
    done = evaluate_steps(steps, {"c0": CourseState(passed=True), "c2": CourseState(passed=True)}, True)
    assert done.complete


def test_step_the_journey_unlocked_stays_unlocked_after_a_reorder():
    # c2 was unlocked earlier; a new required step c1 now sits before it.
    courses = {"c0": CourseState(passed=True), "c2": CourseState(active=True, started=True)}
    result = evaluate_steps([step(0), step(1), step(2, unlocked=True)], courses, True)
    assert result.steps[2].unlocked and result.steps[2].state == "in_progress"
    assert result.steps[1].state == "available"


def test_course_from_its_own_rule_does_not_unlock_a_later_step():
    # c2 is assigned to the employee by its own course rule, but the journey has not reached it.
    courses = {"c2": CourseState(active=True)}
    result = evaluate_steps([step(0), step(1), step(2)], courses, True)
    assert result.steps[2].state == "locked" and not result.steps[2].unlocked
    assert result.unlocked_course_ids == ["c0"]


def test_course_passed_before_the_journey_counts_even_if_access_was_revoked():
    result = evaluate_steps([step(0), step(1)], {"c0": CourseState(active=False, passed=True)}, True)
    assert states(result) == ["passed", "available"]


def test_waiting_journey_unlocks_nothing():
    result = evaluate_steps([step(0), step(1)], {}, False)
    assert states(result) == ["locked", "locked"]
    assert result.unlocked_course_ids == []
    assert result.steps[0].locked_by_course_id is None
    assert not result.complete


def test_empty_or_all_unavailable_journey_is_never_complete():
    assert not evaluate_steps([], {}, True).complete
    assert not evaluate_steps([step(0, available=False)], {}, True).complete


def test_prerequisite_binds_only_assigned_employees():
    assert prerequisite_met(None)
    assert prerequisite_met({"revoked_at": "2026-10-01T00:00:00", "completed_at": None})
    assert not prerequisite_met({"revoked_at": None, "completed_at": None})
    assert prerequisite_met({"revoked_at": None, "completed_at": "2026-10-01T00:00:00"})


def test_journey_status():
    now = datetime(2026, 10, 26, 12, 0)
    kwargs = dict(complete=False, started=False, deadline="2026-10-30T00:00:00", now=now)
    assert journey_status(available=False, **kwargs) == "waiting"
    assert journey_status(available=True, **kwargs) == "pending"
    assert journey_status(available=True, **{**kwargs, "started": True}) == "started"
    assert journey_status(available=True, **{**kwargs, "deadline": "2026-10-20T00:00:00"}) == "overdue"
    assert journey_status(available=True, **{**kwargs, "complete": True}) == "completed"
