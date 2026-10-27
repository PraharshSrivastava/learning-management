"""Learning Journeys end to end against isolated real PostgreSQL."""

import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.settings import settings
from app.repositories import database, observers, performance_reporting, schema
from app.repositories.access_migrations import apply_access_migrations
from app.repositories.assignments import (
    employee_matches_assignment_rule,
    get_applied_assignment_rule,
    get_assignment_rule,
    save_assignment_rule,
)
from app.repositories.courses import delete_course_for_trainer
from app.repositories.employees import list_employees
from app.repositories.progress import ProgressRepository
from app.repositories.report_access import report_roles
from app.schemas.assignment import AssignmentRuleRequest
from app.schemas.journey import JourneyCreateRequest, JourneyObserversRequest, JourneySaveRequest
from app.schemas.observers import ObserverSaveRequest
from app.schemas.reporting_scope import EmployeePerformanceScope, TrainerPerformanceScope
from app.services import assignments, email_notifications, journey_reporting, journeys, learning

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated PostgreSQL opt-in"
)

_progress = ProgressRepository()
RECENT = (date.today() - timedelta(days=3)).isoformat()
LONG_AGO = (date.today() - timedelta(days=400)).isoformat()


@pytest.fixture
def journey_db(monkeypatch):
    pool = database._pool_instance()
    name = "learning_journeys_test_" + uuid4().hex
    with database.get_connection() as db:
        assert (
            db.execute("SELECT current_database() AS name").fetchone()["name"]
            == "lms_performance_demo"
        )
        db.execute(f'CREATE SCHEMA "{name}"')
        db.execute(f'SET LOCAL search_path TO "{name}"')
        schema._create_tables(db.cursor())
        apply_access_migrations(db)
        db.commit()

    class ScopedPool:
        @contextmanager
        def connection(self):
            with pool.connection() as raw:
                raw.execute(f'SET LOCAL search_path TO "{name}"')
                yield raw

    monkeypatch.setattr(database, "_pool_instance", lambda: ScopedPool())
    monkeypatch.setattr(settings, "learning_journeys_enabled", True)
    monkeypatch.setattr(settings, "email_delivery_mode", "log")
    monkeypatch.setattr(settings, "email_recipient_allowlist", [])
    monkeypatch.setattr(journeys, "course_is_publishable", lambda _: True)
    monkeypatch.setattr(assignments, "course_is_publishable", lambda _: True)
    with database.get_connection() as db:
        for trainer_id in ("creator", "other"):
            db.execute(
                "INSERT INTO trainers(trainer_id,name) VALUES (?, ?)", (trainer_id, trainer_id)
            )
        for employee_id, joined in (("new", RECENT), ("old", LONG_AGO), ("obs", LONG_AGO)):
            db.execute(
                """INSERT INTO employees(employee_id,name,job_title,department,join_date,
                directory_uuid,email) VALUES (?, ?, 'Associate', 'Sales', ?, ?, ?)""",
                (employee_id, employee_id, joined, "uuid-" + employee_id, f"{employee_id}@example.test"),
            )
        for course_id, trainer_id in (
            ("c1", "creator"), ("c2", "creator"), ("c3", "creator"), ("c4", "creator"), ("x1", "other")
        ):
            db.execute(
                "INSERT INTO courses(course_id,trainer_id,course_name,status) VALUES (?, ?, ?, 'ready')",
                (course_id, trainer_id, f"Course {course_id}"),
            )
        db.execute("INSERT INTO lms_departments VALUES ('sales','dir-sales','Sales','directory',TRUE)")
        db.commit()
    try:
        yield
    finally:
        monkeypatch.setattr(database, "_pool_instance", lambda: pool)
        with database.get_connection() as db:
            db.execute(f'DROP SCHEMA "{name}" CASCADE')
            db.commit()


def make_journey(title, steps, *, rule=None, prerequisite=None, trainer="creator"):
    created = journeys.api_create_journey(trainer, JourneyCreateRequest(title=title))
    payload = JourneySaveRequest(
        title=title,
        prerequisite_journey_id=prerequisite,
        stages=[{"title": "Stage 1", "steps": [{"course_id": c, "unlock_rule": u} for c, u in steps]}],
        rule=rule or {"include_all": True, "deadline_mode": "relative", "deadline_days": 30},
    )
    journeys.api_save_journey(created["journey_id"], trainer, payload)
    return created["journey_id"]


def active_courses(employee_id):
    return sorted(
        course_id
        for course_id, row in _progress.get_for_employee(employee_id).items()
        if not row.get("revoked_at") and row.get("status") != "revoked"
    )


def complete(employee_id, course_id):
    row = _progress.get_for_employee(employee_id)[course_id]
    row.update(status="completed", completed_at=datetime.now().isoformat())
    _progress.save(employee_id, course_id, row)
    learning._unlock_next_journey_steps(employee_id)


def assigned_emails(employee_id, course_id):
    with database.get_connection() as db:
        return db.execute(
            """SELECT count(*) AS n FROM email_notifications n
            JOIN course_assignments a ON a.assignment_id = n.assignment_id
            WHERE a.employee_id = ? AND a.course_id = ? AND n.event_type = 'assigned'
            AND n.recipient_role = 'employee'""",
            (employee_id, course_id),
        ).fetchone()["n"]


def list_employees_by_id():
    return {e["employee_id"]: e for e in list_employees()}


def journey_row(journey_id, employee_id):
    return journeys._journeys.assignments_for_employee(employee_id).get(journey_id)


SEQUENCE = [("c1", "after_previous"), ("c2", "after_previous"), ("c3", "after_previous")]


def report(journey_id, scope=None, **filters):
    return journey_reporting.journey_detail(scope or TrainerPerformanceScope("creator"), journey_id, **filters)


def report_list(scope=None, **filters):
    return journey_reporting.journey_list(scope or TrainerPerformanceScope("creator"), **filters)["journeys"]


def test_publish_assigns_first_step_and_completion_unlocks_the_next(journey_db):
    journey_id = make_journey("Markets Foundation", SEQUENCE)
    result = journeys.api_publish_journey(journey_id, "creator")
    assert result["status"] == "published"
    assert result["newly_assigned_count"] == 3
    with database.get_connection() as db:
        statuses = {r["course_id"]: r["status"] for r in db.execute("SELECT course_id, status FROM courses").fetchall()}
    assert statuses["c1"] == statuses["c2"] == statuses["c3"] == "published"
    # Each course is live with a published rule that assigns nobody directly.
    live = get_applied_assignment_rule("c1")
    assert live["published_at"] and live["is_active"] and live["include_all"] is False
    assert not any(employee_matches_assignment_rule(e, live) for e in list_employees())
    assert active_courses("old") == ["c1"]
    assert assigned_emails("old", "c1") == 1
    # Journey courses appear in reports and get reminder emails like any assigned course.
    rows = performance_reporting.list_assignment_summaries(TrainerPerformanceScope("creator"))
    assert {(r["employee_id"], r["course_id"]) for r in rows} == {("new", "c1"), ("old", "c1"), ("obs", "c1")}
    later = datetime.now() + timedelta(days=settings.email_assignment_reminder_days + 1)
    with pytest.MonkeyPatch.context() as clock:
        clock.setattr(email_notifications, "_now", lambda: later)
        assert email_notifications.enqueue_assignment_reminders() == 3

    complete("old", "c1")
    assert active_courses("old") == ["c1", "c2"]
    assert assigned_emails("old", "c2") == 1
    assert assigned_emails("old", "c1") == 1

    # Reconcile is idempotent.
    assert assignments.reconcile_assignments_for_employee("old") == {"assigned": 0, "removed": 0, "reactivated": 0}

    courses = {c["course_id"]: c for c in learning.get_enriched_employee_courses("old")}
    assert set(courses) == {"c1", "c2"}
    assert courses["c2"]["journeys"] == [
        {"journey_id": journey_id, "title": "Markets Foundation", "step": 2, "step_count": 3}
    ]
    mine = journeys.learner_journeys("old")["journeys"][0]
    states = [step["state"] for step in mine["stages"][0]["steps"]]
    assert states == ["passed", "available", "locked"]
    assert mine["stages"][0]["steps"][2]["locked_by_course_name"] == "Course c2"
    assert mine["status"] == "started"

    complete("old", "c2")
    complete("old", "c3")
    assert journey_row(journey_id, "old")["status"] == "completed"
    learners = report(journey_id)["learners"]
    assert {row["employee_id"]: row["status"] for row in learners}["old"] == "completed"


def test_course_rule_and_reconcile_do_not_revoke_journey_courses(journey_db):
    journey_id = make_journey("Foundation", [("c1", "after_previous")])
    journeys.api_publish_journey(journey_id, "creator")
    assert active_courses("old") == ["c1"]
    # Publishing the course's own rule for someone else must not take c1 away from old.
    assignments.api_publish_course_assignment(
        "c1", AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["new"]}]), "creator"
    )
    assert active_courses("old") == ["c1"]
    assignments.reconcile_time_based_assignments(notify=False)
    assert active_courses("old") == ["c1"]


def test_prerequisite_waits_and_deadline_starts_when_available(journey_db):
    induction = make_journey(
        "New Joiner Induction",
        [("c1", "after_previous")],
        rule={"include_all": False, "include_groups": [{"joined_less_than_days_ago": 30}], "deadline_days": 14},
    )
    journeys.api_publish_journey(induction, "creator")
    foundation = make_journey(
        "Markets Foundation", [("c2", "after_previous"), ("c3", "after_previous")],
        rule={"include_all": True, "deadline_days": 45}, prerequisite=induction,
    )
    journeys.api_publish_journey(foundation, "creator")

    # A new joiner waits for Induction; existing staff were never given Induction and start at once.
    assert active_courses("new") == ["c1"]
    waiting = journey_row(foundation, "new")
    assert waiting["status"] == "waiting" and waiting["deadline"] is None
    assert active_courses("old") == ["c2"]
    assert journey_row(induction, "old") is None

    complete("new", "c1")
    assert journey_row(induction, "new")["status"] == "completed"
    opened = journey_row(foundation, "new")
    assert opened["available_at"] is not None
    deadline = datetime.fromisoformat(opened["deadline"])
    assert timedelta(days=44) < deadline - datetime.now() <= timedelta(days=45)
    assert active_courses("new") == ["c1", "c2"]
    mine = {j["title"]: j for j in journeys.learner_journeys("new")["journeys"]}
    assert mine["Markets Foundation"]["prerequisite"] == {
        "journey_id": induction, "title": "New Joiner Induction", "met": True
    }


def test_time_based_rule_drift_keeps_the_journey(journey_db):
    induction = make_journey(
        "Induction", [("c1", "after_previous")],
        rule={"include_all": False, "include_groups": [{"joined_less_than_days_ago": 30}], "deadline_days": 14},
    )
    journeys.api_publish_journey(induction, "creator")
    assert active_courses("new") == ["c1"]
    with database.get_connection() as db:
        db.execute("UPDATE employees SET join_date = ? WHERE employee_id = 'new'", (LONG_AGO,))
        db.commit()
    assignments.reconcile_assignments_for_employee("new")
    assert journey_row(induction, "new")["revoked_at"] is None
    assert active_courses("new") == ["c1"]


def test_disable_revokes_only_courses_the_journey_alone_gave(journey_db):
    journey_id = make_journey("Compliance", [("c1", "open"), ("c3", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    assignments.api_publish_course_assignment(
        "c3", AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["old"]}]), "creator"
    )
    assert active_courses("old") == ["c1", "c3"]
    result = journeys.api_disable_journey(journey_id, "creator")
    assert result["status"] == "disabled"
    assert active_courses("old") == ["c3"]
    assert journey_row(journey_id, "old")["revoked_reason"] == "journey_disabled"
    # Publishing again restores the journey and its course.
    journeys.api_publish_journey(journey_id, "creator")
    assert active_courses("old") == ["c1", "c3"]


def test_unpublished_course_draft_survives_journey_publish(journey_db):
    save_assignment_rule("c1", {"include_all": False, "include_groups": [{"employee_ids": ["new"]}]})
    journey_id = make_journey(
        "Foundation", [("c1", "after_previous")],
        rule={"include_all": False, "include_groups": [{"employee_ids": ["old"]}], "deadline_days": 30},
    )
    journeys.api_publish_journey(journey_id, "creator")
    assert get_assignment_rule("c1")["include_groups"] == [{"employee_ids": ["new"]}]
    # The draft is not applied: "new" does not get the course directly.
    assert active_courses("new") == []
    assert active_courses("old") == ["c1"]


def test_observer_step_is_unavailable_for_that_employee(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    # The journey's live rule matches nobody, so a course Observer needs no workaround.
    config = observers.save_config(
        "c2", "creator",
        ObserverSaveRequest(revision=0, observers=[{"observer_employee_id": "obs", "employee_ids": ["new"]}]),
    )
    observers.apply_config("c2", "creator", config["revision"])
    complete("obs", "c1")
    assert active_courses("obs") == ["c1", "c3"]
    steps = journeys.learner_journeys("obs")["journeys"][0]["stages"][0]["steps"]
    assert [s["state"] for s in steps] == ["passed", "unavailable", "available"]


def test_switching_the_feature_off_hides_journeys_but_keeps_received_courses(journey_db, monkeypatch):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    assert active_courses("old") == ["c1"]
    monkeypatch.setattr(settings, "learning_journeys_enabled", False)
    assert journeys.api_list_journeys("creator") == {"enabled": False, "journeys": []}
    with pytest.raises(NotFoundError):
        journeys.api_get_journey(journey_id, "creator")
    assert journeys.api_my_journeys({"employee_id": "old"}) == {"enabled": False, "journeys": []}
    # Nothing new unlocks, and the course already received is neither revoked nor hidden.
    complete("old", "c1")
    assignments.reconcile_time_based_assignments(notify=False)
    assert active_courses("old") == ["c1"]
    courses = learning.get_enriched_employee_courses("old")
    assert [c["course_id"] for c in courses] == ["c1"] and courses[0]["journeys"] == []
    monkeypatch.setattr(settings, "learning_journeys_enabled", True)
    assignments.reconcile_assignments_for_employee("old")
    assert active_courses("old") == ["c1", "c2"]


def test_an_opened_journey_stays_open_when_a_prerequisite_is_added(journey_db):
    foundation = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(foundation, "creator")
    complete("new", "c1")
    assert active_courses("new") == ["c1", "c2"]
    induction = make_journey(
        "Induction", [("c4", "open")],
        rule={"include_all": False, "include_groups": [{"employee_ids": ["new"]}], "deadline_days": 14},
    )
    journeys.api_publish_journey(induction, "creator")
    detail = journeys.api_get_journey(foundation, "creator")
    journeys.api_save_journey(
        foundation, "creator",
        JourneySaveRequest(
            title="Foundation", prerequisite_journey_id=induction,
            stages=[{"title": "S", "steps": [{"course_id": c} for c in ("c1", "c2")]}],
            expected_updated_at=detail["updated_at"],
        ),
    )
    # "new" had already started Foundation, so it is not sent back to waiting.
    assert journey_row(foundation, "new")["status"] == "started"
    assert "c2" in active_courses("new")


def test_a_course_from_its_own_rule_does_not_skip_ahead_or_stick(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    # c3 is also given to "old" directly by its own course rule.
    assignments.api_publish_course_assignment(
        "c3", AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["old"]}]), "creator"
    )
    assert active_courses("old") == ["c1", "c3"]
    steps = journeys.learner_journeys("old")["journeys"][0]["stages"][0]["steps"]
    assert [s["state"] for s in steps] == ["available", "locked", "locked"]
    # Narrowing the course rule takes c3 away again: the journey has not unlocked it yet.
    assignments.api_publish_course_assignment(
        "c3", AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["new"]}]), "creator"
    )
    assert active_courses("old") == ["c1"]


def test_owner_checks_and_validation(journey_db):
    journey_id = make_journey("Foundation", [("c1", "after_previous")])
    with pytest.raises(NotFoundError):
        journeys.api_get_journey(journey_id, "other")
    with pytest.raises(DomainValidationError):
        make_journey("Mixed", [("x1", "after_previous")])
    with pytest.raises(ValidationError):
        JourneySaveRequest(title="Twice", stages=[{"title": "S", "steps": [{"course_id": "c1"}, {"course_id": "c1"}]}])
    second = make_journey("Second", [("c2", "after_previous")], prerequisite=journey_id)
    detail = journeys.api_get_journey(journey_id, "creator")
    with pytest.raises(DomainValidationError):
        journeys.api_save_journey(
            journey_id, "creator",
            JourneySaveRequest(
                title="Foundation", prerequisite_journey_id=second,
                stages=[{"title": "S", "steps": [{"course_id": "c1"}]}],
                expected_updated_at=detail["updated_at"],
            ),
        )
    with pytest.raises(DomainValidationError):
        journeys.api_publish_journey(second, "creator")  # its prerequisite is not published yet
    with pytest.raises(ConflictError):
        delete_course_for_trainer("c1", "creator")
    journeys.api_publish_journey(journey_id, "creator")
    with pytest.raises(ConflictError):
        journeys.api_delete_journey(journey_id, "creator")
    assert journeys.api_delete_journey(second, "creator") == {"message": "Learning journey deleted."}


def observed_rows(employee_id):
    scope = EmployeePerformanceScope(employee_id, f"directory:uuid-{employee_id}", "observed")
    return sorted(
        (row["employee_id"], row["course_id"])
        for row in performance_reporting.list_assignment_summaries(scope)
    )


def test_journey_observer_sees_every_journey_course_for_the_people_they_watch(journey_db):
    journey_id = make_journey(
        "Foundation", SEQUENCE,
        rule={"include_all": True, "exclude_groups": [], "deadline_days": 30},
    )
    # Observers are set before publishing, so "obs" is never enrolled in the journey.
    journeys.api_save_journey_observers(
        journey_id, "creator",
        JourneyObserversRequest(observers=[{"observer_employee_id": "obs", "employee_ids": ["old"]}]),
    )
    assert journeys.api_preview_journey(journey_id, "creator")["match_count"] == 2
    assert report_roles(list_employees_by_id()["obs"]) == set()  # not live until published
    journeys.api_publish_journey(journey_id, "creator")
    assert journey_row(journey_id, "obs") is None
    assert active_courses("obs") == []
    assert report_roles(list_employees_by_id()["obs"]) == {"observer"}
    assert observed_rows("obs") == [("old", "c1")]
    complete("old", "c1")
    complete("new", "c1")
    # Each newly unlocked course shows up without any per-course Observer setup; "new" is not watched.
    assert observed_rows("obs") == [("old", "c1"), ("old", "c2")]
    journeys.api_disable_journey(journey_id, "creator")
    assert observed_rows("obs") == []
    assert report_roles(list_employees_by_id()["obs"]) == set()


def test_a_journey_learner_cannot_also_observe_it(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    with pytest.raises(ConflictError):
        journeys.api_save_journey_observers(
            journey_id, "creator",
            JourneyObserversRequest(observers=[{"observer_employee_id": "old", "employee_ids": ["new"]}]),
        )
    assert journeys.api_get_journey_observers(journey_id, "creator")["observers"] == []


def test_journey_observers_are_hidden_when_the_feature_is_off(journey_db, monkeypatch):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_save_journey_observers(
        journey_id, "creator",
        JourneyObserversRequest(observers=[{"observer_employee_id": "obs", "department_ids": ["sales"]}]),
    )
    journeys.api_publish_journey(journey_id, "creator")
    assert observed_rows("obs") == [("new", "c1"), ("old", "c1")]
    monkeypatch.setattr(settings, "learning_journeys_enabled", False)
    assert report_roles(list_employees_by_id()["obs"]) == set()
    assert observed_rows("obs") == []


def resave(journey_id, steps, **changes):
    current = journeys.api_get_journey(journey_id, "creator")
    payload = JourneySaveRequest(
        title=changes.pop("title", current["title"]),
        description=changes.pop("description", current["description"]),
        stages=[{"title": "Stage 1", "steps": [{"course_id": c, "unlock_rule": u} for c, u in steps]}],
        rule=changes.pop("rule", current["rule"]),
        **changes,
    )
    return journeys.api_save_journey(journey_id, "creator", payload)


def start(employee_id, course_id):
    row = _progress.get_for_employee(employee_id)[course_id]
    row.update(status="started", started_at=datetime.now().isoformat())
    _progress.save(employee_id, course_id, row)


OPEN = [("c1", "open"), ("c2", "open"), ("c3", "open")]


def test_removing_a_live_course_keeps_it_for_learners_who_started_it(journey_db):
    journey_id = make_journey("Compliance", OPEN)
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c2")
    start("new", "c2")
    detail = journeys.api_get_journey(journey_id, "creator")
    c2 = next(step for step in detail["stages"][0]["steps"] if step["course_id"] == "c2")
    assert c2["learner_count"] == 3 and c2["started_count"] == 2

    resave(journey_id, [("c1", "open"), ("c3", "open")])
    assert active_courses("old") == ["c1", "c2", "c3"]
    assert active_courses("new") == ["c1", "c2", "c3"]
    # Only the learner who had not started it loses it.
    assert active_courses("obs") == ["c1", "c3"]
    assert assignments.reconcile_assignments_for_employee("old") == {"assigned": 0, "removed": 0, "reactivated": 0}


def test_live_save_applies_at_once_and_rechecks_learners_only_when_needed(journey_db):
    journey_id = make_journey("Markets", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    assert resave(journey_id, SEQUENCE, description="New words")["learners_rechecked"] is False

    narrowed = {"include_all": False, "include_groups": [{"employee_ids": ["new"]}], "deadline_days": 30}
    saved = resave(journey_id, SEQUENCE, rule=narrowed)
    assert saved["learners_rechecked"] is True
    assert saved["applied_rule"]["include_all"] is False
    # Membership is sticky, so people who already had it keep it.
    assert active_courses("old") == ["c1"]

    saved = resave(journey_id, SEQUENCE + [("c4", "after_previous")], rule=narrowed)
    assert saved["learners_rechecked"] is True
    # A draft never rechecks anyone.
    draft = make_journey("Draft", [("c1", "open")])
    assert resave(draft, [("c1", "open"), ("c2", "open")])["learners_rechecked"] is False


def test_preview_uses_the_unsaved_rule_and_observers(journey_db):
    from app.schemas.journey import JourneyPreviewRequest

    journey_id = make_journey("Preview", [("c1", "open")])
    assert journeys.api_preview_journey(journey_id, "creator")["match_count"] == 3
    draft = JourneyPreviewRequest(
        rule={"include_all": False, "include_groups": [{"employee_ids": ["new", "old"]}]},
        observer_employee_ids=["old"],
    )
    preview = journeys.api_preview_journey(journey_id, "creator", draft)
    assert preview["match_count"] == 1
    assert [row["employee_id"] for row in preview["preview_employees"]] == ["new"]


def test_duplicate_copies_courses_and_rule_but_not_people(journey_db):
    journey_id = make_journey("Induction", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    copy = journeys.api_duplicate_journey(journey_id, "creator")
    assert copy["title"] == "Copy of Induction"
    assert copy["status"] == "draft"
    assert [s["course_id"] for s in copy["stages"][0]["steps"]] == ["c1", "c2", "c3"]
    assert copy["assigned_count"] == 0
    with pytest.raises(NotFoundError):
        journeys.api_duplicate_journey(journey_id, "other")


def test_a_damaged_course_does_not_break_the_journeys_tab(journey_db, monkeypatch):
    real = journeys.get_course

    def flaky(course_id, *args, **kwargs):
        if course_id == "c4":
            raise ValueError("broken metadata")
        return real(course_id, *args, **kwargs)

    monkeypatch.setattr(journeys, "get_course", flaky)
    options = {o["course_id"]: o for o in journeys.api_course_options("creator")}
    assert options["c4"]["eligible"] is False
    assert "could not be read" in options["c4"]["reason"]
    assert options["c1"]["eligible"] is True
    assert journeys.api_list_journeys("creator")["enabled"] is True


def test_completion_certificate_pdf_and_verification(journey_db):
    from app.services import journey_certificates

    journey_id = make_journey("Markets Foundation", [("c1", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    with pytest.raises(NotFoundError):
        journey_certificates.learner_certificate("old", journey_id)
    complete("old", "c1")

    filename, pdf = journey_certificates.learner_certificate("old", journey_id)
    number = journey_certificates.certificate_number(journey_row(journey_id, "old")["journey_assignment_id"])
    assert filename == f"{number}.pdf"
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
    assert number.startswith("PCIL-LJ-") and len(number) == len("PCIL-LJ-XXXX-XXXX-XXXX")

    creator = TrainerPerformanceScope("creator")
    assert journey_reporting.journey_certificate(creator, journey_id, "old")[0] == filename
    # Only someone whose report shows the learner can download it, and only once it is earned.
    with pytest.raises(NotFoundError):
        journey_reporting.journey_certificate(TrainerPerformanceScope("other"), journey_id, "old")
    with pytest.raises(NotFoundError):
        journey_reporting.journey_certificate(creator, journey_id, "new")

    checked = journey_certificates.verify_certificate(number.lower())
    assert checked["valid"] is True and checked["learner_name"] == "old"
    assert checked["journey_title"] == "Markets Foundation"
    assert journey_certificates.verify_certificate("PCIL-LJ-0000-0000-0000")["valid"] is False

    mine = journeys.learner_journeys("old")["journeys"][0]
    assert mine["certificate_number"] == number
    row = next(r for r in report(journey_id)["learners"] if r["employee_id"] == "old")
    assert row["certificate_number"] == number
    assert report(journey_id)["journey"]["certificates"] == 1


def test_certificate_text_names_the_company_and_signatory():
    import fitz

    from app.services import journey_certificates

    pdf = journey_certificates.render_certificate_pdf(
        learner_name="Asha Verma",
        journey_title="New Joiner Induction",
        course_names=["Welcome", "Code of Conduct"],
        completed_at="2026-10-20T10:00:00",
        number="PCIL-LJ-AAAA-BBBB-CCCC",
    )
    text = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    for expected in (
        "Asha Verma",
        "New Joiner Induction",
        "20 October 2026",
        "Mr Vineet Bhatnagar",
        "Managing Director",
        "PhillipCapital India Pvt Ltd",
        "PCIL-LJ-AAAA-BBBB-CCCC",
    ):
        assert expected in text


def test_course_emails_name_the_journey_and_step(journey_db):
    from app.services.email_templates import render_individual

    journey_id = make_journey("Markets Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c1")
    with database.get_connection() as db:
        assignment_id = db.execute(
            "SELECT assignment_id FROM course_assignments WHERE employee_id='old' AND course_id='c2'"
        ).fetchone()["assignment_id"]
        context = email_notifications._assignment_context(db, assignment_id)
    assert (context["journey_title"], context["journey_step"], context["journey_step_count"]) == (
        "Markets Foundation", 2, 3,
    )
    _subject, text, _html = render_individual(context, "overdue", "employee")
    assert "Learning journey: Markets Foundation (Step 2 of 3)" in text
    assert "step 2 of 3 in your learning journey Markets Foundation" in text
    _subject, hod_text, _html = render_individual(context, "assigned", "hod")
    assert "Learning journey" not in hod_text


def test_a_kept_course_is_not_brought_back_once_its_creator_disables_it(journey_db):
    journey_id = make_journey("Compliance", OPEN)
    journeys.api_publish_journey(journey_id, "creator")
    start("old", "c2")
    resave(journey_id, [("c1", "open"), ("c3", "open")])
    assert "c2" in active_courses("old")
    with database.get_connection() as db:
        db.execute("UPDATE assignment_rules SET is_active = FALSE WHERE course_id = 'c2'")
        db.commit()
    assignments.reconcile_assignments_for_employee("old")
    assert "c2" not in active_courses("old")
    # Settled: the next reconcile neither removes nor reactivates anything.
    assert assignments.reconcile_assignments_for_employee("old") == {
        "assigned": 0, "removed": 0, "reactivated": 0,
    }


def test_performance_report_shows_journey_progress_like_courses(journey_db):
    journey_id = make_journey("Markets Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c1")
    start("old", "c2")
    # A deadline in the past makes the journey overdue, as for a course.
    row = journey_row(journey_id, "new")
    journeys._journeys.save_assignment({**row, "deadline": (datetime.now() - timedelta(days=1)).isoformat()})

    [summary] = report_list()
    assert (summary["journey_id"], summary["title"], summary["step_count"]) == (journey_id, "Markets Foundation", 3)
    assert (summary["assigned"], summary["completed"], summary["started"], summary["overdue"]) == (3, 0, 1, 1)
    assert summary["completion_rate"] == 0 and summary["average_progress"] == 11

    detail = report(journey_id)
    learners = {row["employee_id"]: row for row in detail["learners"]}
    old = learners["old"]
    assert (old["status"], old["passed_count"], old["required_count"], old["completion_percent"]) == ("started", 1, 3, 33)
    assert (old["current_step"], old["current_course_name"]) == (2, "Course c2")
    assert old["last_learner_activity_at"] is None or isinstance(old["last_learner_activity_at"], str)
    assert learners["new"]["status"] == "overdue"
    steps = {step["course_id"]: step for step in detail["steps"]}
    assert (steps["c1"]["passed"], steps["c1"]["available"]) == (1, 2)
    assert (steps["c2"]["in_progress"], steps["c2"]["locked"]) == (1, 2)
    assert steps["c3"]["locked"] == 3

    # The report filters and views apply to journeys as to courses.
    assert report_list(employee_id="old")[0]["assigned"] == 1
    assert report_list(department="Marketing") == []
    assert report_list(course_id="x1") == []
    assert report_list(course_id="c3")[0]["assigned"] == 3
    assert report_list(joined_less_than_days_ago=30)[0]["assigned"] == 1
    assert report_list(TrainerPerformanceScope("other")) == []
    assert report_list(TrainerPerformanceScope("other", all_courses=True))[0]["assigned"] == 3
    assert report(journey_id, TrainerPerformanceScope("other")) is None


def test_journey_report_for_observers_and_department_heads(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_save_journey_observers(
        journey_id, "creator",
        JourneyObserversRequest(observers=[{"observer_employee_id": "obs", "employee_ids": ["old"]}]),
    )
    journeys.api_publish_journey(journey_id, "creator")
    observed = EmployeePerformanceScope("obs", "directory:uuid-obs", "observed")
    [summary] = report_list(observed)
    assert summary["assigned"] == 1
    assert [row["employee_id"] for row in report(journey_id, observed)["learners"]] == ["old"]
    with database.get_connection() as db:
        db.execute(
            "INSERT INTO hod_department_access(hod_employee_id, identity_key, department_id, source, source_key) VALUES ('obs', 'directory:uuid-obs', 'sales', 'directory', 'dir-sales')"
        )
        db.commit()
    heads = EmployeePerformanceScope("obs", "directory:uuid-obs", "my_departments")
    assert report_list(heads)[0]["assigned"] == 2
    assert report_list(EmployeePerformanceScope("new", "directory:uuid-new", "combined")) == []


def test_a_disabled_journey_shows_only_in_the_history_views(journey_db):
    journey_id = make_journey("Compliance", [("c1", "open"), ("c2", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c1")
    complete("old", "c2")
    journeys.api_disable_journey(journey_id, "creator")
    assert report_list() == []
    everything = TrainerPerformanceScope("creator", course_status="all")
    learners = {row["employee_id"]: row for row in report(journey_id, everything)["learners"]}
    # A completed journey stays completed; the others read as removed.
    assert learners["old"]["status"] == "completed" and learners["old"]["certificate_number"]
    assert learners["new"]["status"] == "removed" and learners["new"]["current_step"] is None
    assert report_list(TrainerPerformanceScope("creator", course_status="disabled"))[0]["removed"] == 2
    assert report_list(TrainerPerformanceScope("creator", course_status="archived"))[0]["removed"] == 2


def test_the_journey_report_is_empty_when_the_feature_is_off(journey_db, monkeypatch):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    monkeypatch.setattr(settings, "learning_journeys_enabled", False)
    result = journey_reporting.journey_list(TrainerPerformanceScope("creator"))
    assert result["enabled"] is False and result["journeys"] == []
    assert report(journey_id) is None
