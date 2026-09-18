from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app.core.settings import Settings
from app.repositories.progress import _notification_transition
from app.services import email_notifications


def _production_settings(**overrides):
    values = {
        "app_env": "production",
        "database_url": "postgresql://lms:password@postgres:5432/lms",
        "cors_allowed_origins": ("https://hub.example.com",),
        "llm_base_url": "https://llm.example.com/v1",
        "llm_api_key": "llm-key",
        "tts_endpoint": "https://tts.example.com",
        "hub_launch_secret": "hub-secret",
        "directory_sync_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_allows_email_log_mode_without_smtp():
    settings = _production_settings(email_delivery_mode="log")

    assert settings.email_delivery_mode == "log"


def test_production_requires_smtp_host_and_from_email_for_smtp_mode():
    try:
        _production_settings(email_delivery_mode="smtp")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected SMTP production settings to fail")

    assert "SMTP_HOST" in message
    assert "EMAIL_FROM_EMAIL" in message


def test_recipient_rows_use_employee_manager_as_hod():
    context = {
        "assignment_id": "assignment-1",
        "employee_email": "learner@example.com",
        "employee_name": "Learner",
        "hod_email": "manager@example.com",
        "hod_name": "Manager",
        "trainer_email": "trainer@example.com",
        "trainer_name": "Trainer",
    }

    recipients = email_notifications._recipient_rows(context, "completed")

    assert [recipient["role"] for recipient in recipients] == ["employee", "hod", "trainer"]
    assert recipients[1]["email"] == "manager@example.com"


def test_event_is_stale_when_assignment_lifecycle_changes():
    context = {
        "assignment_status": "pending",
        "notification_lifecycle": 3,
        "completed_at": None,
    }

    assert not email_notifications._event_is_current(context, "assigned", 2)
    assert email_notifications._event_is_current(context, "assigned", 3)


def test_recipient_matrix_limits_routine_email_noise():
    context = {
        "assignment_id": "assignment-1",
        "employee_email": "learner@example.com",
        "hod_email": "manager@example.com",
        "trainer_email": "trainer@example.com",
    }

    assert [item["role"] for item in email_notifications._recipient_rows(context, "assigned")] == [
        "employee"
    ]
    assert [item["role"] for item in email_notifications._recipient_rows(context, "overdue")] == [
        "employee",
        "hod",
    ]


def test_due_soon_event_must_still_be_inside_current_window(monkeypatch):
    now = datetime(2026, 9, 18, 12, 0, 0)
    monkeypatch.setattr(email_notifications, "_now", lambda: now)
    context = {
        "assignment_status": "pending",
        "notification_lifecycle": 2,
        "deadline": (now + timedelta(days=5)).isoformat(),
        "course_status": "published",
        "assignment_rule_active": True,
    }

    assert not email_notifications._event_is_current(context, "due_soon", 2)
    context["deadline"] = (now + timedelta(days=1)).isoformat()
    assert email_notifications._event_is_current(context, "due_soon", 2)


def test_deadline_change_increments_notification_version():
    existing = {
        "status": "pending",
        "deadline": "2026-09-20T12:00:00",
        "notification_lifecycle": 4,
    }
    data = {"status": "pending", "deadline": "2026-09-25T12:00:00"}

    assert _notification_transition(existing, data) == (5, None)


def test_completion_increments_version_and_emits_once():
    existing = {
        "status": "started",
        "deadline": "2026-09-20T12:00:00",
        "notification_lifecycle": 1,
    }
    completed = {
        "status": "completed",
        "deadline": "2026-09-20T12:00:00",
    }

    assert _notification_transition(existing, completed) == (2, "completed")
    existing.update({"status": "completed", "notification_lifecycle": 2})
    assert _notification_transition(existing, completed) == (2, None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"email_delivery_mode": "invalid"},
        {"smtp_use_ssl": True, "smtp_use_starttls": True},
        {"smtp_username": "user", "smtp_password": None},
    ],
)
def test_email_configuration_is_validated_in_every_environment(overrides):
    with pytest.raises(ValueError):
        Settings(**overrides)


def test_smtp_delivery_uses_tls_authentication_and_stable_message_id(monkeypatch):
    sent = []

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            sent.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self):
            sent.append(("starttls",))

        def login(self, username, password):
            sent.append(("login", username, password))

        def send_message(self, message):
            sent.append(("message", message))

    monkeypatch.setattr(email_notifications.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(email_notifications.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_notifications.settings, "smtp_port", 587)
    monkeypatch.setattr(email_notifications.settings, "smtp_use_ssl", False)
    monkeypatch.setattr(email_notifications.settings, "smtp_use_starttls", True)
    monkeypatch.setattr(email_notifications.settings, "smtp_username", "mailer")
    monkeypatch.setattr(email_notifications.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_notifications.settings, "email_from_email", "lms@example.com")

    email_notifications._send_smtp(
        {
            "notification_id": "notice-1",
            "recipient_name": "Learner",
            "recipient_email": "learner@example.com",
            "subject": "Course assigned",
            "body_text": "Example body",
        }
    )

    message = next(item[1] for item in sent if item[0] == "message")
    assert ("starttls",) in sent
    assert ("login", "mailer", "secret") in sent
    assert message["Message-ID"] == "<notice-1@example.com>"


def test_claim_recovers_notifications_left_sending_after_worker_crash(monkeypatch):
    executed = {}

    class Result:
        def fetchall(self):
            return []

    class Connection:
        def execute(self, query, params):
            executed["query"] = query
            executed["params"] = params
            return Result()

        def commit(self):
            executed["committed"] = True

    @contextmanager
    def fake_connection():
        yield Connection()

    now = datetime(2026, 9, 18, 12, 0, 0)
    monkeypatch.setattr(email_notifications, "_now", lambda: now)
    monkeypatch.setattr(email_notifications, "get_connection", fake_connection)
    monkeypatch.setattr(email_notifications.settings, "email_lock_timeout_seconds", 600)

    email_notifications._claim_pending_notifications(25)

    assert "status = 'sending' AND locked_at <= ?" in executed["query"]
    assert executed["params"][0] == (now - timedelta(seconds=600)).isoformat()
    assert executed["committed"] is True

