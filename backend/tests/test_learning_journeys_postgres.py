"""Learning Journeys end to end against isolated real PostgreSQL."""

import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.settings import settings
from app.db import database, schema
from app.db.migrations.access import apply_access_migrations
from app.modules.access.report_access_repository import report_roles
from app.modules.access.reporting_scope import EmployeePerformanceScope, TrainerPerformanceScope
from app.modules.assignments import service as assignments
from app.modules.assignments.repository import (
    employee_matches_assignment_rule,
    get_applied_assignment_rule,
    get_assignment_rule,
    save_assignment_rule,
)
from app.modules.assignments.schemas import AssignmentRuleRequest
from app.modules.courses.repository import delete_course_for_trainer
from app.modules.directory.employees_repository import list_employees
from app.modules.journeys import reporting as journey_reporting
from app.modules.journeys import service as journeys
from app.modules.journeys.repository import create_journey_tables
from app.modules.journeys.schemas import (
    JourneyCreateRequest,
    JourneyObserversRequest,
    JourneySaveRequest,
)
from app.modules.learning import service as learning
from app.modules.learning.progress_repository import ProgressRepository
from app.modules.observers import repository as observers
from app.modules.observers.schemas import ObserverSaveRequest
from app.modules.reporting import repository as performance_reporting
from app.services import email_notifications

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
# Everyone except "obs": as for a course, an Observer cannot match the rule.
WITHOUT_OBS = {"include_all": True, "exclude_groups": [{"employee_ids": ["obs"]}], "deadline_days": 30}


def save_observers(journey_id, observers):
    revision = journeys.api_get_journey_observers(journey_id, "creator")["revision"]
    return journeys.api_save_journey_observers(
        journey_id, "creator", JourneyObserversRequest(revision=revision, observers=observers)
    )


def apply_observers(journey_id):
    revision = journeys.api_get_journey_observers(journey_id, "creator")["revision"]
    return journeys.api_apply_journey_observers(journey_id, "creator", revision)


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
    # Journeys are optional: one journey email instead of course emails.
    assert assigned_emails("old", "c1") == 0
    assert len(journey_emails("old", "journey_assigned")) == 1
    # Journey courses appear in reports, but send no reminders.
    rows = performance_reporting.list_assignment_summaries(TrainerPerformanceScope("creator"))
    assert {(r["employee_id"], r["course_id"]) for r in rows} == {("new", "c1"), ("old", "c1"), ("obs", "c1")}
    later = datetime.now() + timedelta(days=settings.email_assignment_reminder_days + 1)
    with pytest.MonkeyPatch.context() as clock:
        clock.setattr(email_notifications, "_now", lambda: later)
        assert email_notifications.enqueue_assignment_reminders() == 0

    complete("old", "c1")
    assert active_courses("old") == ["c1", "c2"]
    assert assigned_emails("old", "c2") == 0
    assert len(journey_emails("old", "journey_assigned")) == 1

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
    assert mine["closed"] is False
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
    journey_id = make_journey("Foundation", SEQUENCE, rule=WITHOUT_OBS)
    save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old"]}])
    assert journeys.api_preview_journey(journey_id, "creator")["match_count"] == 2
    # As for a course: Apply needs a published journey, and saved Observers wait for it.
    with pytest.raises(DomainValidationError):
        apply_observers(journey_id)
    journeys.api_publish_journey(journey_id, "creator")
    assert journey_row(journey_id, "obs") is None
    assert active_courses("obs") == []
    assert report_roles(list_employees_by_id()["obs"]) == set()
    assert observed_rows("obs") == []
    applied = apply_observers(journey_id)
    assert applied["observers"][0]["is_active"] is True
    assert applied["observers"][0]["active"] == {"employee_ids": ["old"], "department_ids": []}
    assert report_roles(list_employees_by_id()["obs"]) == {"observer"}
    assert observed_rows("obs") == [("old", "c1")]
    complete("old", "c1")
    complete("new", "c1")
    # Each newly unlocked course shows up without any per-course Observer setup; "new" is not watched.
    assert observed_rows("obs") == [("old", "c1"), ("old", "c2")]
    # Disabling suspends the Observers, as for a course: publishing again needs a new Apply.
    journeys.api_disable_journey(journey_id, "creator")
    assert observed_rows("obs") == []
    assert report_roles(list_employees_by_id()["obs"]) == set()
    suspended = journeys.api_get_journey_observers(journey_id, "creator")["observers"][0]
    assert suspended["is_active"] is False
    assert suspended["pending"] == {"employee_ids": ["old"], "department_ids": []}


def test_a_journey_learner_cannot_also_observe_it(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    with pytest.raises(ConflictError):
        save_observers(journey_id, [{"observer_employee_id": "old", "employee_ids": ["new"]}])
    assert journeys.api_get_journey_observers(journey_id, "creator")["observers"] == []


def test_an_observer_cannot_match_the_rule_even_before_publishing(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE)
    with pytest.raises(ConflictError, match="both an employee and an Observer"):
        save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old"]}])
    resave(journey_id, SEQUENCE, rule=WITHOUT_OBS)
    save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old"]}])
    # Widening the rule to take in the Observer is refused, as for a course.
    with pytest.raises(ConflictError, match="both an employee and an Observer"):
        resave(journey_id, SEQUENCE, rule={"include_all": True, "deadline_days": 30})
    assert journeys.api_get_journey(journey_id, "creator")["rule"]["exclude_groups"]


def test_saving_removes_access_at_once_but_adds_only_on_apply(journey_db):
    journey_id = make_journey("Foundation", [("c1", "open")], rule=WITHOUT_OBS)
    journeys.api_publish_journey(journey_id, "creator")
    save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old", "new"]}])
    apply_observers(journey_id)
    assert observed_rows("obs") == [("new", "c1"), ("old", "c1")]
    saved = save_observers(
        journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old"], "department_ids": ["sales"]}]
    )
    # "new" is gone at once; the Sales department waits for Apply.
    assert observed_rows("obs") == [("old", "c1")]
    assert saved["observers"][0]["active"] == {"employee_ids": ["old"], "department_ids": []}
    assert saved["observers"][0]["pending"] == {"employee_ids": ["old"], "department_ids": ["sales"]}
    apply_observers(journey_id)
    assert observed_rows("obs") == [("new", "c1"), ("old", "c1")]
    # Removing the Observer takes effect without Apply.
    save_observers(journey_id, [])
    assert observed_rows("obs") == []
    assert journeys.api_get_journey_observers(journey_id, "creator")["observers"] == []


def test_an_older_revision_cannot_overwrite_observers(journey_db):
    journey_id = make_journey("Foundation", SEQUENCE, rule=WITHOUT_OBS)
    save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old"]}])
    stale = JourneyObserversRequest(revision=0, observers=[])
    with pytest.raises(ConflictError, match="changed"):
        journeys.api_save_journey_observers(journey_id, "creator", stale)
    with pytest.raises(ConflictError, match="changed"):
        journeys.api_apply_journey_observers(journey_id, "creator", 0)
    with pytest.raises(NotFoundError):
        journeys.api_get_journey_observers(journey_id, "other")
    with database.get_connection() as db:
        actions = [r["action"] for r in db.execute(
            "SELECT action FROM lms_report_access_audit WHERE course_id IS NULL"
        ).fetchall()]
    assert actions == ["journey_observers_save"]


def test_observers_saved_before_apply_existed_stay_live_after_the_upgrade(journey_db):
    journey_id = make_journey("Foundation", [("c1", "open")], rule=WITHOUT_OBS)
    journeys.api_publish_journey(journey_id, "creator")
    draft_id = make_journey("Draft", [("c2", "open")], rule=WITHOUT_OBS)
    with database.get_connection() as db:
        # The tables as they were: a selection was live as soon as its journey was published.
        for table in ("learning_journey_observer_departments", "learning_journey_observer_employees",
                      "learning_journey_observers", "learning_journey_observer_configs"):
            db.execute(f"DROP TABLE {table}")
        db.execute("""CREATE TABLE learning_journey_observers (journey_id TEXT NOT NULL,
            observer_employee_id TEXT NOT NULL, identity_key TEXT NOT NULL,
            granted_by_trainer_id TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT (now()::text),
            PRIMARY KEY (journey_id, observer_employee_id))""")
        db.execute("""CREATE TABLE learning_journey_observer_employees (journey_id TEXT NOT NULL,
            observer_employee_id TEXT NOT NULL, employee_id TEXT NOT NULL, identity_key TEXT NOT NULL,
            PRIMARY KEY (journey_id, observer_employee_id, employee_id),
            FOREIGN KEY (journey_id, observer_employee_id) REFERENCES learning_journey_observers ON DELETE CASCADE)""")
        db.execute("""CREATE TABLE learning_journey_observer_departments (journey_id TEXT NOT NULL,
            observer_employee_id TEXT NOT NULL, department_id TEXT NOT NULL,
            PRIMARY KEY (journey_id, observer_employee_id, department_id),
            FOREIGN KEY (journey_id, observer_employee_id) REFERENCES learning_journey_observers ON DELETE CASCADE)""")
        for saved in (journey_id, draft_id):
            db.execute(
                "INSERT INTO learning_journey_observers VALUES (?, 'obs', 'directory:uuid-obs', 'creator')",
                (saved,),
            )
            db.execute(
                "INSERT INTO learning_journey_observer_employees VALUES (?, 'obs', 'old', 'directory:uuid-old')",
                (saved,),
            )
            db.execute("INSERT INTO learning_journey_observer_departments VALUES (?, 'obs', 'sales')", (saved,))
        create_journey_tables(db.cursor())
        create_journey_tables(db.cursor())  # running it again changes nothing
        db.commit()
    [observer] = journeys.api_get_journey_observers(journey_id, "creator")["observers"]
    both = {"employee_ids": ["old"], "department_ids": ["sales"]}
    assert observer == {"observer_employee_id": "obs", "is_active": True, "active": both, "pending": both}
    assert observed_rows("obs") == [("new", "c1"), ("old", "c1")]
    # On a journey that was not published, they wait for Apply after publishing, as for a course.
    [waiting] = journeys.api_get_journey_observers(draft_id, "creator")["observers"]
    assert waiting["is_active"] is False and waiting["pending"] == both
    journeys.api_publish_journey(draft_id, "creator")
    assert ("old", "c2") not in observed_rows("obs")
    apply_observers(draft_id)
    assert ("old", "c2") in observed_rows("obs")
    # The upgraded journey works as a new one: a save narrows access at once, adds on Apply.
    save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["new"]}])
    assert [row for row in observed_rows("obs") if row[1] == "c1"] == []


def test_journey_observers_are_hidden_when_the_feature_is_off(journey_db, monkeypatch):
    journey_id = make_journey("Foundation", SEQUENCE, rule=WITHOUT_OBS)
    save_observers(journey_id, [{"observer_employee_id": "obs", "department_ids": ["sales"]}])
    journeys.api_publish_journey(journey_id, "creator")
    apply_observers(journey_id)
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


def test_a_new_deadline_on_a_live_journey_reaches_learners_and_their_courses(journey_db):
    from app.modules.assignments.deadlines import resolve_deadline

    journey_id = make_journey("Markets Foundation", SEQUENCE[:2])
    journeys.api_publish_journey(journey_id, "creator")
    complete("obs", "c1")
    complete("obs", "c2")
    complete("old", "c1")
    before = {name: journey_row(journey_id, name)["deadline"] for name in ("new", "old", "obs")}
    finished = journey_row(journey_id, "obs")["completed_at"]
    assert _progress.get_for_employee("old")["c2"]["deadline"] == before["old"]

    # A course that also has a deadline of its own keeps it.
    own = (datetime.now() + timedelta(days=90)).isoformat()
    row = _progress.get_for_employee("new")["c1"]
    _progress.save("new", "c1", {**row, "deadline": own})

    fixed = {
        "include_all": True,
        "deadline_mode": "fixed",
        "deadline_date": (date.today() + timedelta(days=60)).isoformat(),
    }
    saved = resave(journey_id, SEQUENCE[:2], rule=fixed)
    assert saved["learners_rechecked"] is True
    expected = resolve_deadline({**fixed, "deadline_days": 30}, datetime.now())

    for name in ("new", "old"):
        assert journey_row(journey_id, name)["deadline"] == expected
    courses = _progress.get_for_employee("old")
    assert courses["c2"]["deadline"] == expected
    # A finished course and a finished journey keep their deadlines.
    assert courses["c1"]["status"] == "completed" and courses["c1"]["deadline"] == before["old"]
    assert journey_row(journey_id, "obs")["deadline"] == before["obs"]
    assert journey_row(journey_id, "obs")["completed_at"] == finished
    assert _progress.get_for_employee("new")["c1"]["deadline"] == own
    # The learner and the report see the new date.
    [mine] = journeys.learner_journeys("old")["journeys"]
    assert mine["deadline"] == expected
    rows = {row["employee_id"]: row for row in report(journey_id)["learners"]}
    assert rows["new"]["deadline"] == expected

    # Saving again without a deadline change leaves everything as it is.
    resave(journey_id, SEQUENCE[:2], title="Markets Foundation 2026")
    assert journey_row(journey_id, "old")["deadline"] == expected


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
    from app.modules.journeys.schemas import JourneyPreviewRequest

    journey_id = make_journey("Preview", [("c1", "open")])
    assert journeys.api_preview_journey(journey_id, "creator")["match_count"] == 3
    draft = JourneyPreviewRequest(
        rule={"include_all": False, "include_groups": [{"employee_ids": ["new", "old"]}]},
        observer_employee_ids=["old"],
    )
    preview = journeys.api_preview_journey(journey_id, "creator", draft)
    # As for a course, an unsaved Observer who matches is counted and reported as a conflict.
    assert preview["match_count"] == 2
    assert [row["employee_id"] for row in preview["preview_employees"]] == ["new", "old"]
    assert preview["blocked_employee_count"] == 1
    assert preview["conflicting_observer_ids"] == ["old"]


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
    from app.modules.journeys import certificates as journey_certificates

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


def test_certificate_is_stored_at_completion_and_never_changes(journey_db):
    import fitz

    from app.modules.journeys import certificates as journey_certificates

    journey_id = make_journey("Markets Foundation", [("c1", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    assignment_id = journey_row(journey_id, "old")["journey_assignment_id"]
    assert journeys._journeys.certificate_for_assignment(assignment_id) is None
    complete("old", "c1")

    stored = journeys._journeys.certificate_for_assignment(assignment_id)
    number = journey_certificates.certificate_number(assignment_id)
    assert stored["certificate_number"] == number
    assert stored["journey_title"] == "Markets Foundation"
    assert stored["learner_name"] == "old" and stored["course_names"] == ["Course c1"]
    assert stored["completed_at"] == journey_row(journey_id, "old")["completed_at"]

    # The trainer renames the journey and the learner's name changes afterwards.
    resave(journey_id, [("c1", "open"), ("c2", "open")], title="Markets Foundation 2027")
    with database.get_connection() as db:
        db.execute("UPDATE employees SET name = 'Renamed' WHERE employee_id = 'old'")
        db.commit()

    _filename, pdf = journey_certificates.learner_certificate("old", journey_id)
    text = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "Markets Foundation" in text and "2027" not in text and "Renamed" not in text
    checked = journey_certificates.verify_certificate(number)
    assert (checked["journey_title"], checked["learner_name"]) == ("Markets Foundation", "old")
    assert checked["issued_at"] == stored["issued_at"]
    assert journeys._journeys.certificate_for_assignment(assignment_id) == stored


def test_a_completion_from_before_stored_certificates_is_issued_on_first_check(journey_db):
    from app.modules.journeys import certificates as journey_certificates

    journey_id = make_journey("Markets Foundation", [("c1", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c1")
    assignment_id = journey_row(journey_id, "old")["journey_assignment_id"]
    with database.get_connection() as db:
        db.execute("DELETE FROM learning_journey_certificates")
        db.commit()

    number = journey_certificates.certificate_number(assignment_id)
    assert journey_certificates.verify_certificate(number)["valid"] is True
    assert journeys._journeys.get_certificate(number)["journey_assignment_id"] == assignment_id


def test_certificate_text_names_the_issuing_team_without_a_signatory():
    import fitz

    from app.modules.journeys import certificates as journey_certificates

    pdf = journey_certificates.render_certificate_pdf(
        learner_name="Asha Verma",
        journey_title="New Joiner Induction",
        course_names=["Welcome (Varsity)", "Code of Conduct (SB, C1)"],
        completed_at="2026-10-20T10:00:00",
        number="PCIL-LJ-AAAA-BBBB-CCCC",
    )
    document = fitz.open(stream=pdf, filetype="pdf")
    assert document.page_count == 1
    text = document[0].get_text()
    for expected in (
        "Asha Verma",
        "New Joiner Induction",
        "2 courses: Welcome · Code of Conduct",
        "20 October 2026",
        "Learning & Development",
        "PhillipCapital India Pvt Ltd",
        "PCIL-LJ-AAAA-BBBB-CCCC",
        "This is a computer-generated certificate",
        "is not a regulatory certification",
    ):
        assert expected in text
    for absent in ("Vineet Bhatnagar", "Managing Director", "Varsity", "signature"):
        assert absent not in text


def test_a_long_course_list_moves_to_a_course_record_page():
    import fitz

    from app.modules.journeys import certificates as journey_certificates

    courses = [f"A fairly long course name about markets, number {n}" for n in range(1, 41)]
    pdf = journey_certificates.render_certificate_pdf(
        learner_name="Asha Verma",
        journey_title="New Joiner Induction",
        course_names=courses,
        completed_at="2026-10-20T10:00:00",
        number="PCIL-LJ-AAAA-BBBB-CCCC",
    )
    document = fitz.open(stream=pdf, filetype="pdf")
    assert document.page_count == 2
    assert "40 courses · full list on page 2" in document[0].get_text()
    record = document[1].get_text()
    assert "C O U R S E   R E C O R D" in record and "40 courses completed" in record
    assert "number 1\n" in record and "number 40\n" in record, record


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
    journey_id = make_journey("Foundation", SEQUENCE, rule=WITHOUT_OBS)
    save_observers(journey_id, [{"observer_employee_id": "obs", "employee_ids": ["old"]}])
    journeys.api_publish_journey(journey_id, "creator")
    apply_observers(journey_id)
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


def test_learners_waiting_on_a_prerequisite_are_in_the_report(journey_db):
    induction = make_journey(
        "Induction",
        [("c1", "after_previous")],
        rule={"include_all": False, "include_groups": [{"joined_less_than_days_ago": 30}], "deadline_days": 14},
    )
    journeys.api_publish_journey(induction, "creator")
    foundation = make_journey(
        "Foundation", [("c2", "after_previous"), ("c3", "after_previous")], prerequisite=induction
    )
    journeys.api_publish_journey(foundation, "creator")
    assert journey_row(foundation, "new")["status"] == "waiting"

    learners = {row["employee_id"]: row for row in report(foundation)["learners"]}
    assert learners["new"]["status"] == "waiting" and learners["new"]["current_step"] is None
    summary = {item["title"]: item for item in report_list()}["Foundation"]
    assert (summary["assigned"], summary["waiting"]) == (3, 1)
    # The same views and filters apply to waiting learners as to everyone else.
    assert report_list(employee_id="new", course_id="c3")[0]["waiting"] == 1
    assert {item["title"] for item in report_list(department="Marketing")} == set()
    assert {item["title"] for item in report_list(TrainerPerformanceScope("other"))} == set()
    with database.get_connection() as db:
        db.execute(
            "INSERT INTO hod_department_access(hod_employee_id, identity_key, department_id, source, source_key) VALUES ('obs', 'directory:uuid-obs', 'sales', 'directory', 'dir-sales')"
        )
        db.commit()
    heads = EmployeePerformanceScope("obs", "directory:uuid-obs", "my_departments")
    assert {item["title"]: item for item in report_list(heads)}["Foundation"]["waiting"] == 1


def test_the_creator_can_open_a_journey_report_before_anyone_is_in_it(journey_db):
    journey_id = make_journey(
        "Dealers only",
        [("c1", "open")],
        rule={"include_all": False, "include_groups": [{"department": "Dealing"}], "deadline_days": 30},
    )
    journeys.api_publish_journey(journey_id, "creator")
    detail = report(journey_id)
    assert detail["learners"] == [] and detail["journey"]["assigned"] == 0
    assert [step["course_id"] for step in detail["steps"]] == ["c1"]
    assert report_list() == []
    assert report(journey_id, TrainerPerformanceScope("other", all_courses=True)) is None


def test_a_learner_is_shown_completed_only_once_the_journey_was_completed(journey_db):
    journey_id = make_journey("Compliance", [("c1", "open"), ("c2", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c1")
    journeys.api_disable_journey(journey_id, "creator")
    # With c2 disabled by its creator, c1 alone would finish the journey in a fresh evaluation.
    with database.get_connection() as db:
        db.execute("UPDATE assignment_rules SET is_active = FALSE WHERE course_id = 'c2'")
        db.commit()
    everything = TrainerPerformanceScope("creator", course_status="all")
    old = next(row for row in report(journey_id, everything)["learners"] if row["employee_id"] == "old")
    assert journey_row(journey_id, "old")["completed_at"] is None
    assert (old["status"], old["completed_at"], old["certificate_number"]) == ("removed", None, None)
    assert report(journey_id, everything)["journey"]["certificates"] == 0
    with pytest.raises(NotFoundError):
        journey_reporting.journey_certificate(everything, journey_id, "old")


def test_learners_see_the_cover_image_of_every_course_in_their_journey(journey_db, monkeypatch):
    from app.modules.directory.employees_repository import EmployeeRepository
    from app.modules.learning.media_access import MediaPrincipal, journey_thumbnail_visible

    with database.get_connection() as db:
        for course_id in ("c1", "c2"):
            db.execute(
                "UPDATE courses SET thumbnail_path = ? WHERE course_id = ?",
                (f"assets/images/{course_id}.png", course_id),
            )
        db.commit()
    journey_id = make_journey(
        "Foundation",
        SEQUENCE[:2],
        rule={"include_all": False, "include_groups": [{"joined_less_than_days_ago": 30}], "deadline_days": 30},
    )
    journeys.api_publish_journey(journey_id, "creator")
    [mine] = journeys.learner_journeys("new")["journeys"]
    steps = mine["stages"][0]["steps"]
    assert [(step["state"], step["thumbnail_path"]) for step in steps] == [
        ("available", "assets/images/c1.png"),
        ("locked", "assets/images/c2.png"),
    ]

    people = EmployeeRepository()
    learner = MediaPrincipal("employee", people.get("new"))
    outsider = MediaPrincipal("employee", people.get("old"))
    # Locked course c2 is not assigned yet, but its cover shows in the journey.
    assert journey_thumbnail_visible(learner, "/assets/images/c2.png")
    assert not journey_thumbnail_visible(outsider, "/assets/images/c2.png")
    # Only the cover image: no other file of the course.
    assert not journey_thumbnail_visible(learner, "/assets/videos/c2/module_1.mp4")
    trainer = MediaPrincipal("trainer", people.get("old"), {"trainer_id": "creator"})
    assert not journey_thumbnail_visible(trainer, "/assets/images/c2.png")
    monkeypatch.setattr(settings, "learning_journeys_enabled", False)
    assert not journey_thumbnail_visible(learner, "/assets/images/c2.png")
    monkeypatch.setattr(settings, "learning_journeys_enabled", True)
    journeys.api_disable_journey(journey_id, "creator")
    assert not journey_thumbnail_visible(learner, "/assets/images/c2.png")


def test_a_completed_journey_and_its_certificate_stay_with_the_learner(journey_db):
    from app.modules.journeys import certificates as journey_certificates

    journey_id = make_journey("Compliance", [("c1", "open"), ("c2", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    complete("old", "c1")
    complete("old", "c2")
    number = journey_certificates.certificate_number(journey_row(journey_id, "old")["journey_assignment_id"])
    journeys.api_disable_journey(journey_id, "creator")

    [mine] = journeys.learner_journeys("old")["journeys"]
    assert (mine["journey_id"], mine["status"], mine["certificate_number"]) == (journey_id, "completed", number)
    assert mine["completed_at"] == journey_row(journey_id, "old")["completed_at"]
    assert mine["next_course_id"] is None and mine["next_course_state"] is None
    assert mine["closed"] is True
    assert journey_certificates.learner_certificate("old", journey_id)[0] == f"{number}.pdf"
    # A learner who had not finished it no longer sees the disabled journey.
    assert journeys.learner_journeys("new")["journeys"] == []


def test_the_journey_report_is_empty_when_the_feature_is_off(journey_db, monkeypatch):
    journey_id = make_journey("Foundation", SEQUENCE)
    journeys.api_publish_journey(journey_id, "creator")
    monkeypatch.setattr(settings, "learning_journeys_enabled", False)
    result = journey_reporting.journey_list(TrainerPerformanceScope("creator"))
    assert result["enabled"] is False and result["journeys"] == []
    assert report(journey_id) is None


def journey_emails(employee_id, event_type):
    with database.get_connection() as db:
        return db.execute(
            """SELECT n.notification_id, n.status, n.subject, n.occurrence_key, a.course_id
            FROM email_notifications n JOIN course_assignments a ON a.assignment_id = n.assignment_id
            WHERE a.employee_id = ? AND n.event_type = ?""",
            (employee_id, event_type),
        ).fetchall()


def journey_completed_emails(employee_id):
    return journey_emails(employee_id, "journey_completed")


def employee_email_events(employee_id):
    with database.get_connection() as db:
        rows = db.execute(
            """SELECT n.event_type FROM email_notifications n
            JOIN course_assignments a ON a.assignment_id = n.assignment_id
            WHERE a.employee_id = ? AND n.recipient_role = 'employee'
            ORDER BY n.created_at""",
            (employee_id,),
        ).fetchall()
    return [row["event_type"] for row in rows]


def test_a_journey_sends_only_its_assigned_and_certificate_emails(journey_db, monkeypatch):
    journey_id = make_journey("Markets Foundation", [("c1", "open"), ("c2", "after_previous")])
    journeys.api_publish_journey(journey_id, "creator")
    [assigned] = journey_emails("old", "journey_assigned")
    assert assigned["course_id"] == "c1"
    assert assigned["subject"] == "Learning journey assigned: Markets Foundation"
    complete("old", "c1")
    assert journey_completed_emails("old") == []

    complete("old", "c2")
    learning._unlock_next_journey_steps("old")  # a later recheck must not queue it again

    emails = journey_completed_emails("old")
    assert len(emails) == 1
    assert emails[0]["course_id"] == "c2"
    assert emails[0]["occurrence_key"] == journey_row(journey_id, "old")["journey_assignment_id"]
    assert emails[0]["subject"] == "Learning journey completed: Markets Foundation"
    # No course emails (assigned, completed) for courses the employee has only via the journey,
    # and nothing for the HOD or trainer either.
    assert employee_email_events("old") == ["journey_assigned", "journey_completed"]
    with database.get_connection() as db:
        assert db.execute(
            "SELECT count(*) AS n FROM email_notifications WHERE recipient_role <> 'employee'"
        ).fetchone()["n"] == 0

    delivered = []
    monkeypatch.setattr(email_notifications, "_send_notification", delivered.append)
    email_notifications.process_pending_notifications()

    journey_email = next(n for n in delivered if n["event_type"] == "journey_completed")
    [(filename, pdf)] = journey_email["attachments"]
    assert filename.startswith("PCIL-LJ-") and pdf.startswith(b"%PDF")
    assert journey_completed_emails("old")[0]["status"] == "sent"
    assert "attachments" not in next(n for n in delivered if n["event_type"] == "journey_assigned")


def test_a_journey_course_the_course_rule_also_assigns_keeps_its_emails(journey_db):
    journey_id = make_journey("Foundation", [("c1", "open")])
    assignments.api_publish_course_assignment(
        "c1", AssignmentRuleRequest(include_all=False, include_groups=[{"employee_ids": ["old"]}]), "creator"
    )
    journeys.api_publish_journey(journey_id, "creator")

    assert assigned_emails("old", "c1") == 1
    complete("old", "c1")
    assert "completed" in employee_email_events("old")


def test_no_certificate_email_when_the_journey_has_certificates_off(journey_db):
    journey_id = make_journey("No Certificate", [("c1", "open")])
    journeys.api_publish_journey(journey_id, "creator")
    with database.get_connection() as db:
        db.execute(
            "UPDATE learning_journeys SET certificate_enabled = FALSE WHERE journey_id = ?",
            (journey_id,),
        )
        db.commit()

    complete("old", "c1")

    assert journey_row(journey_id, "old")["completed_at"]
    assert journey_completed_emails("old") == []
