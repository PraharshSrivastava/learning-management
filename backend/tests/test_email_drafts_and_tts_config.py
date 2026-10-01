"""Corporate draft, assignment digest and configurable TTS regression tests."""

import sqlite3
from datetime import datetime, timedelta

import pytest

from app.core.settings import Settings
from app.services import email_notifications as notifications
from app.services.email_templates import render_digest, render_individual


@pytest.mark.parametrize("event", ["assigned", "due_soon", "completed", "overdue"])
def test_hod_digests_are_self_contained_and_never_truncated(monkeypatch, event):
    monkeypatch.setattr(notifications.settings, "lms_hub_login_url", "https://hub.example.com/login")
    rows = [
        {"employee_id": str(i), "employee_name": f"Learner-{i:03}", "course_name": "AML",
         "assigned_at": "2026-09-01T10:00:00", "deadline": "2026-09-20T10:00:00",
         "completed_at": "2026-09-19T10:00:00", "completion_percent": 60}
        for i in range(50)
    ]
    _, text, markup = render_digest(event, "hod", rows, {}, recipient_name="Manager,Rohit")
    assert "Dear Rohit," in text
    assert "Segoe UI,Arial,sans-serif" in markup
    for row in rows:
        assert row["employee_name"] in text
        assert row["employee_name"] in markup
    assert "href=" not in markup
    assert "https://" not in text
    assert "Sign in" not in text
    assert "report link" not in text
    assert "first 25" not in text


@pytest.mark.parametrize("event", ["assigned", "assignment_reminder", "due_soon", "completed", "overdue"])
def test_employee_greetings_and_general_login_link(monkeypatch, event):
    monkeypatch.setattr(notifications.settings, "lms_hub_login_url", "https://hub.example.com/login")
    _, text, markup = render_individual({"employee_name": "Ananya Mehta", "course_id": "private-id"}, event, "employee")
    assert ("Congratulations, Ananya!" if event == "completed" else "Dear Ananya,") in text
    assert "Open LMS: https://hub.example.com/login" in text
    assert "private-id" not in markup
    if event == "overdue":
        assert "You will continue receiving reminders every 48 hours until the course is completed." in text


def test_missing_login_url_omits_button(monkeypatch):
    monkeypatch.setattr(notifications.settings, "lms_hub_login_url", None)
    _, text, markup = render_individual({}, "assigned", "employee")
    assert "href=" not in markup
    assert "Open the LMS from the Hub dashboard" in text


def test_trainer_digest_uses_general_login_and_greeting(monkeypatch):
    monkeypatch.setattr(notifications.settings, "lms_hub_login_url", "https://hub.example.com/login")
    _, text, markup = render_digest("due_soon", "trainer", [], {}, recipient_name="Kiran Shah")
    assert "Dear Kiran," in text
    assert "Open LMS: https://hub.example.com/login" in text
    assert "open Performance" in text
    assert "view=performance" not in markup


def test_invalid_hub_login_url_is_rejected():
    with pytest.raises(ValueError):
        Settings(lms_hub_login_url="javascript:alert(1)")


@pytest.mark.parametrize("test_mode", [True, False])
def test_assignment_digest_groups_batch_and_separates_managers(monkeypatch, test_mode):
    # Exercise the actual outbox SQL with a lightweight compatible test database.
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE email_notifications (
            notification_id TEXT PRIMARY KEY, assignment_id TEXT, notification_lifecycle INTEGER,
            event_type TEXT, occurrence_key TEXT, recipient_role TEXT, recipient_email TEXT,
            recipient_name TEXT, subject TEXT, body_text TEXT, body_html TEXT, message_kind TEXT,
            digest_key TEXT, digest_scope_type TEXT, digest_scope_id TEXT, status TEXT,
            next_attempt_at TEXT, created_at TEXT, updated_at TEXT, sent_at TEXT);
        CREATE UNIQUE INDEX digest_key_unique ON email_notifications(digest_key) WHERE digest_key IS NOT NULL;
        CREATE TABLE email_notification_items (
            notification_id TEXT, assignment_id TEXT, notification_lifecycle INTEGER,
            occurrence_key TEXT, created_at TEXT,
            UNIQUE(notification_id, assignment_id, notification_lifecycle, occurrence_key));
    """)
    monkeypatch.setattr(notifications.settings, "email_test_mode", test_mode)
    monkeypatch.setattr(notifications.settings, "email_recipient_allowlist", ())
    now = datetime(2026, 10, 1, 10)
    monkeypatch.setattr(notifications, "_now", lambda: now)
    context = {"assignment_id": "a1", "notification_lifecycle": 1,
               "hod_employee_id": "m1", "hod_email": "manager@example.com", "hod_name": "Manager"}
    enqueue = notifications._enqueue_digest_item
    assert enqueue(connection, context, "assigned", "hod", "once") == 1
    now += timedelta(seconds=10)
    assert enqueue(connection, {**context, "assignment_id": "a2"}, "assigned", "hod", "once") == 1
    assert connection.execute("SELECT COUNT(*) FROM email_notifications").fetchone()[0] == 1
    assert enqueue(connection, context, "assigned", "hod", "once") == 0
    # Retry scheduling must not change the identity of an open batch.
    connection.execute("UPDATE email_notifications SET status='failed', next_attempt_at='2026-10-02T12:00:00'")
    assert enqueue(connection, {**context, "assignment_id": "a-retry"}, "assigned", "hod", "once") == 1
    assert connection.execute("SELECT COUNT(*) FROM email_notifications").fetchone()[0] == 1
    other = {**context, "assignment_id": "a3", "hod_employee_id": "m2", "hod_email": "other@example.com"}
    assert enqueue(connection, other, "assigned", "hod", "once") == 1
    assert connection.execute("SELECT COUNT(*) FROM email_notifications").fetchone()[0] == 2
    connection.execute("INSERT INTO email_notifications (notification_id,assignment_id,notification_lifecycle,event_type,recipient_role,status) VALUES ('old','a4',1,'assigned','hod','sent')")
    assert enqueue(connection, {**context, "assignment_id": "a4"}, "assigned", "hod", "once") == 0
    connection.close()
