"""Overdue email cap and escalation exercised against isolated real PostgreSQL."""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.settings import settings
from app.repositories import database, schema
from app.repositories.access_migrations import apply_access_migrations
from app.services import email_notifications

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated PostgreSQL opt-in"
)

DEADLINE = datetime(2026, 10, 1, 17, 0, 0)


@pytest.fixture
def overdue_db(monkeypatch):
    pool = database._pool_instance()
    name = "overdue_escalation_test_" + uuid4().hex
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
    monkeypatch.setattr(settings, "email_delivery_mode", "log")
    monkeypatch.setattr(settings, "email_recipient_allowlist", ())
    monkeypatch.setattr(settings, "email_test_mode", False)
    monkeypatch.setattr(settings, "email_overdue_repeat_days", 2)
    monkeypatch.setattr(settings, "email_overdue_max_notices", 5)
    with database.get_connection() as db:
        db.execute(
            "INSERT INTO trainers(trainer_id,name,email) VALUES ('creator','Kiran','kiran@example.test')"
        )
        for employee_id, manager in (("hod", None), ("learner", "hod")):
            db.execute(
                """INSERT INTO employees(employee_id,name,job_title,department,directory_uuid,
                email,manager_employee_id) VALUES (?, ?, 'Associate', 'Risk', ?, ?, ?)""",
                (employee_id, employee_id, "uuid-" + employee_id, f"{employee_id}@example.test", manager),
            )
        db.execute(
            "INSERT INTO courses(course_id,trainer_id,course_name,status) VALUES ('course','creator','AML Training','published')"
        )
        db.execute("INSERT INTO assignment_rules(course_id,is_active) VALUES ('course',TRUE)")
        db.execute(
            """INSERT INTO course_assignments(assignment_id,course_id,employee_id,status,assigned_at,deadline)
            VALUES ('a-1','course','learner','pending',?,?)""",
            ((DEADLINE - timedelta(days=7)).isoformat(), DEADLINE.isoformat()),
        )
        db.commit()
    try:
        yield
    finally:
        monkeypatch.setattr(database, "_pool_instance", lambda: pool)
        with database.get_connection() as db:
            db.execute(f'DROP SCHEMA "{name}" CASCADE')
            db.commit()


def _run_cycle_in_period(monkeypatch, period):
    now = DEADLINE + timedelta(days=2 * (period - 1), hours=1)
    monkeypatch.setattr(email_notifications, "_now", lambda: now)
    email_notifications.enqueue_overdue_notifications(as_of=now)
    email_notifications.process_pending_notifications()


def _learner_overdue_emails():
    with database.get_connection() as db:
        return db.execute(
            """SELECT occurrence_key, subject, status FROM email_notifications
            WHERE assignment_id = 'a-1' AND event_type = 'overdue' AND recipient_role = 'employee'
            ORDER BY created_at"""
        ).fetchall()


def _digest_overdue_keys():
    with database.get_connection() as db:
        rows = db.execute(
            """SELECT DISTINCT eni.occurrence_key FROM email_notification_items eni
            JOIN email_notifications en ON en.notification_id = eni.notification_id
            WHERE eni.assignment_id = 'a-1' AND en.event_type = 'overdue'"""
        ).fetchall()
    return {row["occurrence_key"] for row in rows}


def test_overdue_emails_stop_after_the_fifth_escalation_notice(overdue_db, monkeypatch):
    # Periods 3, 6 and 10 are skipped as if the scheduler were down.
    for period in (1, 2, 4, 5, 7, 8, 9, 11, 12):
        _run_cycle_in_period(monkeypatch, period)
        _run_cycle_in_period(monkeypatch, period)  # a second cycle in the same period adds nothing

    emails = _learner_overdue_emails()

    assert [row["occurrence_key"] for row in emails] == [
        "period-1", "period-2", "period-4", "period-5", "period-7"
    ]
    assert all(row["status"] == "sent" for row in emails)
    assert all(row["subject"].startswith("Overdue course:") for row in emails[:4])
    assert emails[4]["subject"] == "Escalation notice: Overdue course AML Training"
    assert _digest_overdue_keys() == {"period-1", "period-2", "period-4", "period-5", "period-7"}


def _seed_sent_overdue_emails(count, first_period):
    """Emails sent before this change, e.g. by UAT test mode's minute-long periods."""
    with database.get_connection() as db:
        db.execute("UPDATE course_assignments SET status = 'overdue' WHERE assignment_id = 'a-1'")
        for offset in range(count):
            sent_at = (DEADLINE + timedelta(minutes=5 * offset)).isoformat()
            db.execute(
                """INSERT INTO email_notifications(
                    notification_id, assignment_id, notification_lifecycle, event_type,
                    occurrence_key, recipient_role, recipient_email, recipient_name, subject,
                    body_text, status, next_attempt_at, sent_at, created_at, updated_at
                ) VALUES (?, 'a-1', 1, 'overdue', ?, 'employee', 'learner@example.test',
                    'learner', 'Overdue course: AML Training', 'Old body', 'sent', ?, ?, ?, ?)""",
                (str(uuid4()), f"period-{first_period + offset}", sent_at, sent_at, sent_at, sent_at),
            )
        db.commit()


def test_employees_already_emailed_five_or_more_times_get_nothing_more(overdue_db, monkeypatch):
    _seed_sent_overdue_emails(7, first_period=40)

    for period in range(1, 13):
        _run_cycle_in_period(monkeypatch, period)

    assert len(_learner_overdue_emails()) == 7
    assert _digest_overdue_keys() == set()


def test_employees_with_earlier_emails_only_get_the_remainder(overdue_db, monkeypatch):
    _seed_sent_overdue_emails(3, first_period=40)

    for period in range(1, 13):
        _run_cycle_in_period(monkeypatch, period)

    new_emails = _learner_overdue_emails()[3:]
    assert [row["subject"] for row in new_emails] == [
        "Overdue course: AML Training",
        "Escalation notice: Overdue course AML Training",
    ]


def test_new_deadline_starts_a_fresh_set_of_overdue_notices(overdue_db, monkeypatch):
    for period in range(1, 8):
        _run_cycle_in_period(monkeypatch, period)
    assert len(_learner_overdue_emails()) == 5

    with database.get_connection() as db:
        db.execute(
            "UPDATE course_assignments SET notification_lifecycle = 2, status = 'pending' WHERE assignment_id = 'a-1'"
        )
        db.commit()
    _run_cycle_in_period(monkeypatch, 8)

    latest = _learner_overdue_emails()[-1]
    assert len(_learner_overdue_emails()) == 6
    assert latest["subject"].startswith("Overdue course:")
