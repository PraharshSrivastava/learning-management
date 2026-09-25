import ssl
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app.core.settings import Settings
from app.repositories.progress import _notification_transition
from app.services import email_notifications
from app.services.email_templates import completion_timing, render_digest, render_individual


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


def test_email_test_mode_requires_allowlist_and_subject_prefix():
    with pytest.raises(ValueError, match="EMAIL_RECIPIENT_ALLOWLIST"):
        Settings(email_test_mode=True)

    settings = Settings(
        email_test_mode=True,
        email_subject_prefix="[LMS UAT TEST]",
        email_recipient_allowlist="learner@example.com, MANAGER@example.com",
    )

    assert settings.email_recipient_allowlist == (
        "learner@example.com",
        "manager@example.com",
    )


def test_test_mode_accelerates_notification_windows(monkeypatch):
    assigned_at = datetime(2026, 9, 1, 10, 0, 0)
    monkeypatch.setattr(email_notifications.settings, "email_test_mode", True)
    monkeypatch.setattr(
        email_notifications.settings,
        "email_test_assignment_reminder_minutes",
        5,
    )
    monkeypatch.setattr(email_notifications.settings, "email_test_due_soon_window_minutes", 7)
    monkeypatch.setattr(email_notifications.settings, "email_test_overdue_repeat_minutes", 5)
    context = {
        "assignment_status": "pending",
        "notification_lifecycle": 1,
        "assigned_at": assigned_at.isoformat(),
        "deadline": (assigned_at + timedelta(minutes=20)).isoformat(),
        "course_status": "published",
        "assignment_rule_active": True,
    }

    monkeypatch.setattr(
        email_notifications,
        "_now",
        lambda: assigned_at + timedelta(minutes=5),
    )
    assert email_notifications._event_is_current(context, "assignment_reminder", 1)

    monkeypatch.setattr(
        email_notifications,
        "_now",
        lambda: assigned_at + timedelta(minutes=13),
    )
    assert email_notifications._event_is_current(context, "due_soon", 1)

    deadline = assigned_at + timedelta(minutes=20)
    assert (
        email_notifications._overdue_occurrence_key(
            deadline,
            deadline + timedelta(minutes=4, seconds=59),
        )
        == "period-1"
    )
    assert (
        email_notifications._overdue_occurrence_key(
            deadline,
            deadline + timedelta(minutes=5),
        )
        == "period-2"
    )


def test_test_digest_is_scheduled_after_short_delay(monkeypatch):
    now = datetime(2026, 9, 20, 10, 0, 0)
    monkeypatch.setattr(email_notifications.settings, "email_test_mode", True)
    monkeypatch.setattr(email_notifications.settings, "email_test_digest_delay_minutes", 1)

    assert email_notifications._digest_send_at(now, 24) == now + timedelta(minutes=1)


def test_allowlist_filters_recipients_and_prefixes_subject(monkeypatch):
    monkeypatch.setattr(
        email_notifications.settings,
        "email_recipient_allowlist",
        ("learner@example.com",),
    )
    monkeypatch.setattr(
        email_notifications.settings,
        "email_subject_prefix",
        "[LMS UAT TEST]",
    )
    context = {
        "assignment_id": "assignment-1",
        "course_id": "course-1",
        "course_name": "AML Essentials",
        "employee_email": "learner@example.com",
        "employee_name": "Learner",
        "hod_email": "manager@example.com",
        "hod_name": "Manager",
        "assigned_at": "2026-09-01T09:00:00",
        "deadline": "2026-09-08T09:00:00",
    }

    assert [item["role"] for item in email_notifications._recipient_rows(context, "assigned")] == [
        "employee"
    ]
    subject, _, _ = email_notifications._message_for(context, "assigned", "employee")
    assert subject == "[LMS UAT TEST] New course assigned: AML Essentials"
    assert email_notifications._email_subject(subject) == subject


def test_digest_recipient_uses_employee_manager_as_hod():
    context = {
        "assignment_id": "assignment-1",
        "employee_email": "learner@example.com",
        "employee_name": "Learner",
        "hod_email": "manager@example.com",
        "hod_name": "Manager",
        "hod_employee_id": "manager-1",
        "trainer_email": "trainer@example.com",
        "trainer_name": "Trainer",
    }

    recipient = email_notifications._digest_recipient(context, "hod", "completed")

    assert recipient is not None
    assert recipient["role"] == "hod"
    assert recipient["email"] == "manager@example.com"


def test_event_is_stale_when_assignment_lifecycle_changes():
    context = {
        "assignment_status": "pending",
        "notification_lifecycle": 3,
        "completed_at": None,
    }

    assert not email_notifications._event_is_current(context, "assigned", 2)
    assert email_notifications._event_is_current(context, "assigned", 3)


def test_recipient_matrix_matches_course_notification_policy():
    context = {
        "assignment_id": "assignment-1",
        "employee_email": "learner@example.com",
        "hod_email": "manager@example.com",
        "trainer_email": "trainer@example.com",
    }

    assert [item["role"] for item in email_notifications._recipient_rows(context, "assigned")] == [
        "employee",
        "hod",
    ]
    assert [
        item["role"] for item in email_notifications._recipient_rows(context, "assignment_reminder")
    ] == ["employee"]
    for event_type in ("due_soon", "completed", "overdue"):
        assert [
            item["role"] for item in email_notifications._recipient_rows(context, event_type)
        ] == ["employee"]
        assert email_notifications.DIGEST_RECIPIENT_ROLES[event_type] == {"hod", "trainer"}


def test_approved_assignment_template_contains_details_and_no_reply_footer(monkeypatch):
    monkeypatch.setattr(
        email_notifications.settings,
        "lms_employee_public_url",
        "https://employee.example.com",
    )
    context = {
        "course_id": "course-1",
        "course_name": "AML Essentials",
        "employee_name": "Ananya Mehta",
        "assigned_at": "2026-09-01T09:00:00",
        "deadline": "2026-09-08T09:00:00",
        "trainer_name": "Kiran Shah",
    }

    subject, body_text, body_html = render_individual(context, "assigned", "employee")

    assert subject == "New course assigned: AML Essentials"
    assert "Hello Ananya," in body_text
    assert "Assigned on: 01 Sep 2026" in body_text
    assert "Please do not reply to this email." in body_text
    assert "course_id=course-1" in body_html


def test_completion_timing_uses_full_twenty_four_hour_periods():
    assert (
        completion_timing(
            {
                "completed_at": "2026-09-08T08:00:00",
                "deadline": "2026-09-10T09:00:00",
            }
        )[1]
        == "Completed 2 days before the deadline"
    )
    assert (
        completion_timing(
            {
                "completed_at": "2026-09-10T08:30:00",
                "deadline": "2026-09-10T09:00:00",
            }
        )[1]
        == "Completed before the deadline"
    )
    assert (
        completion_timing(
            {
                "completed_at": "2026-09-10T09:01:00",
                "deadline": "2026-09-10T09:00:00",
            }
        )[1]
        == "Completed after the deadline"
    )


def test_hod_overdue_digest_has_one_summary_and_all_employee_rows(monkeypatch):
    monkeypatch.setattr(
        email_notifications.settings,
        "lms_employee_public_url",
        "https://employee.example.com",
    )
    rows = [
        {
            "assignment_id": "a-1",
            "employee_id": "e-1",
            "employee_name": "Ananya Mehta",
            "course_name": "AML Essentials",
            "deadline": "2026-09-10T09:00:00",
            "completion_percent": 60,
        },
        {
            "assignment_id": "a-2",
            "employee_id": "e-2",
            "employee_name": "Rohit Khanna",
            "course_name": "AML Essentials",
            "deadline": "2026-09-10T09:00:00",
            "completion_percent": 20,
        },
    ]

    subject, body_text, body_html = render_digest(
        "overdue",
        "hod",
        rows,
        {
            "assigned_count": 4,
            "completed_count": 2,
            "completion_rate": 50,
            "overdue_rate": 50,
        },
    )

    assert subject == "Overdue learning summary: 2 employees require attention"
    assert body_text.count("Ananya Mehta") == 1
    assert body_text.count("Rohit Khanna") == 1
    assert "Completion rate: 50%" in body_text
    assert "<table" in body_html


def test_email_html_escapes_directory_and_course_values():
    _, _, body_html = render_individual(
        {
            "course_id": "course-1",
            "course_name": "AML <script>alert(1)</script>",
            "employee_name": "Ananya & Team",
            "deadline": "2026-09-10T09:00:00",
        },
        "due_soon",
        "employee",
    )

    assert "<script>" not in body_html
    assert "&lt;script&gt;" in body_html
    assert "Ananya &amp; Team" not in body_html  # Greeting deliberately uses the first name only.


def test_digest_send_time_respects_overdue_interval(monkeypatch):
    monkeypatch.setattr(email_notifications.settings, "email_digest_send_time", "09:00")
    monkeypatch.setattr(
        email_notifications.settings,
        "email_notification_timezone",
        "Asia/Kolkata",
    )
    now = datetime(2026, 9, 20, 10, 0, 0)

    assert email_notifications._digest_send_at(now, 24) == datetime(2026, 9, 21, 3, 30, 0)
    assert email_notifications._digest_send_at(
        now,
        48,
        "2026-09-20T09:00:00",
    ) == datetime(2026, 9, 22, 9, 0, 0)


def test_assignment_reminder_becomes_current_after_five_days(monkeypatch):
    assigned_at = datetime(2026, 9, 1, 10, 0, 0)
    context = {
        "assignment_status": "pending",
        "notification_lifecycle": 1,
        "assigned_at": assigned_at.isoformat(),
        "deadline": (assigned_at + timedelta(days=10)).isoformat(),
        "course_status": "published",
        "assignment_rule_active": True,
    }
    monkeypatch.setattr(email_notifications.settings, "email_assignment_reminder_days", 5)

    monkeypatch.setattr(
        email_notifications,
        "_now",
        lambda: assigned_at + timedelta(days=5) - timedelta(seconds=1),
    )
    assert not email_notifications._event_is_current(context, "assignment_reminder", 1)

    monkeypatch.setattr(
        email_notifications,
        "_now",
        lambda: assigned_at + timedelta(days=5),
    )
    assert email_notifications._event_is_current(context, "assignment_reminder", 1)

    context["assignment_status"] = "completed"
    assert not email_notifications._event_is_current(context, "assignment_reminder", 1)


def test_employee_completing_on_day_two_never_gets_day_five_reminder(monkeypatch):
    assigned_at = datetime(2026, 9, 1, 10, 0, 0)
    completed_at = assigned_at + timedelta(days=2)
    day_five = assigned_at + timedelta(days=5)
    monkeypatch.setattr(email_notifications.settings, "email_assignment_reminder_days", 5)
    monkeypatch.setattr(email_notifications, "_now", lambda: day_five)
    context = {
        "assignment_status": "completed",
        "notification_lifecycle": 2,
        "assigned_at": assigned_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "deadline": (assigned_at + timedelta(days=10)).isoformat(),
        "course_status": "published",
        "assignment_rule_active": True,
    }

    assert not email_notifications._event_is_current(context, "assignment_reminder", 2)


def test_due_soon_email_replaces_day_five_reminder_when_windows_overlap(monkeypatch):
    assigned_at = datetime(2026, 9, 1, 10, 0, 0)
    day_five = assigned_at + timedelta(days=5)
    monkeypatch.setattr(email_notifications.settings, "email_assignment_reminder_days", 5)
    monkeypatch.setattr(email_notifications.settings, "email_due_soon_days", 2)
    monkeypatch.setattr(email_notifications, "_now", lambda: day_five)
    context = {
        "assignment_status": "pending",
        "notification_lifecycle": 1,
        "assigned_at": assigned_at.isoformat(),
        "deadline": (assigned_at + timedelta(days=7)).isoformat(),
        "course_status": "published",
        "assignment_rule_active": True,
    }

    assert not email_notifications._event_is_current(context, "assignment_reminder", 1)
    assert email_notifications._event_is_current(context, "due_soon", 1)


@pytest.mark.parametrize(
    ("status", "course_status", "rule_active"),
    [
        ("revoked", "published", True),
        ("pending", "draft", True),
        ("pending", "published", False),
    ],
)
def test_day_five_reminder_requires_an_active_assignment(
    monkeypatch,
    status,
    course_status,
    rule_active,
):
    assigned_at = datetime(2026, 9, 1, 10, 0, 0)
    monkeypatch.setattr(email_notifications.settings, "email_assignment_reminder_days", 5)
    monkeypatch.setattr(email_notifications, "_now", lambda: assigned_at + timedelta(days=5))
    context = {
        "assignment_status": status,
        "notification_lifecycle": 1,
        "assigned_at": assigned_at.isoformat(),
        "deadline": (assigned_at + timedelta(days=10)).isoformat(),
        "course_status": course_status,
        "assignment_rule_active": rule_active,
    }

    assert not email_notifications._event_is_current(context, "assignment_reminder", 1)


def test_reactivation_changes_lifecycle_without_sending_reassigned_email():
    existing = {
        "status": "revoked",
        "deadline": "2026-09-20T12:00:00",
        "notification_lifecycle": 4,
    }
    reactivated = {
        "status": "pending",
        "deadline": "2026-09-25T12:00:00",
    }

    assert _notification_transition(existing, reactivated) == (5, None)


def test_overdue_occurrence_changes_every_two_days(monkeypatch):
    deadline = datetime(2026, 9, 10, 9, 0, 0)
    monkeypatch.setattr(email_notifications.settings, "email_overdue_repeat_days", 2)

    assert (
        email_notifications._overdue_occurrence_key(
            deadline,
            deadline + timedelta(minutes=1),
        )
        == "period-1"
    )
    assert (
        email_notifications._overdue_occurrence_key(
            deadline,
            deadline + timedelta(days=1, hours=23),
        )
        == "period-1"
    )
    assert (
        email_notifications._overdue_occurrence_key(
            deadline,
            deadline + timedelta(days=2),
        )
        == "period-2"
    )
    assert (
        email_notifications._overdue_occurrence_key(
            deadline,
            deadline + timedelta(days=4),
        )
        == "period-3"
    )


def test_only_current_overdue_occurrence_can_be_sent(monkeypatch):
    deadline = datetime(2026, 9, 10, 9, 0, 0)
    now = deadline + timedelta(days=2, minutes=1)
    monkeypatch.setattr(email_notifications.settings, "email_overdue_repeat_days", 2)
    monkeypatch.setattr(email_notifications, "_now", lambda: now)
    context = {
        "assignment_status": "overdue",
        "notification_lifecycle": 2,
        "deadline": deadline.isoformat(),
        "course_status": "published",
        "assignment_rule_active": True,
    }

    assert not email_notifications._event_is_current(context, "overdue", 2, "period-1")
    assert email_notifications._event_is_current(context, "overdue", 2, "period-2")


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
        {"email_digest_send_time": "25:00"},
        {"email_notification_timezone": "Not/AZone"},
    ],
)
def test_email_configuration_is_validated_in_every_environment(overrides):
    with pytest.raises(ValueError):
        Settings(**overrides)


def test_smtp_mode_rejects_plaintext_even_without_authentication():
    with pytest.raises(ValueError, match="requires SMTP_USE_STARTTLS or SMTP_USE_SSL"):
        Settings(
            email_delivery_mode="smtp",
            smtp_host="smtp.example.com",
            email_from_email="lms@example.com",
            smtp_use_starttls=False,
            smtp_use_ssl=False,
        )


def test_smtp_delivery_uses_tls_authentication_and_stable_message_id(monkeypatch):
    sent = []

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            sent.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            sent.append(("starttls", context))

        def ehlo(self):
            sent.append(("ehlo",))

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
            "body_html": "<p>Example body</p>",
        }
    )

    message = next(item[1] for item in sent if item[0] == "message")
    tls_context = next(item[1] for item in sent if item[0] == "starttls")
    assert tls_context.verify_mode == ssl.CERT_REQUIRED
    assert tls_context.check_hostname
    assert sent.index(("ehlo",)) < sent.index(("login", "mailer", "secret"))
    assert ("login", "mailer", "secret") in sent
    assert message["Message-ID"] == "<notice-1@example.com>"
    assert message.is_multipart()
    assert message.get_body(preferencelist=("html",)).get_content_type() == "text/html"


def test_smtp_ssl_verifies_certificate_before_authentication(monkeypatch):
    sent = []

    class FakeSmtpSsl:
        def __init__(self, host, port, timeout, *, context):
            sent.append(("connect", host, port, timeout))
            assert context.verify_mode == ssl.CERT_REQUIRED
            assert context.check_hostname

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self, username, password):
            sent.append(("login", username, password))

        def send_message(self, message):
            sent.append(("message", message))

    monkeypatch.setattr(email_notifications.smtplib, "SMTP_SSL", FakeSmtpSsl)
    monkeypatch.setattr(email_notifications.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_notifications.settings, "smtp_port", 465)
    monkeypatch.setattr(email_notifications.settings, "smtp_use_ssl", True)
    monkeypatch.setattr(email_notifications.settings, "smtp_use_starttls", False)
    monkeypatch.setattr(email_notifications.settings, "smtp_username", "mailer")
    monkeypatch.setattr(email_notifications.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_notifications.settings, "email_from_email", "lms@example.com")

    email_notifications._send_smtp(
        {
            "notification_id": "notice-ssl",
            "recipient_name": "Learner",
            "recipient_email": "learner@example.com",
            "subject": "Course assigned",
            "body_text": "Example body",
        }
    )

    assert sent[0][0] == "connect"
    assert sent[1] == ("login", "mailer", "secret")
    assert sent[2][0] == "message"


def test_smtp_does_not_authenticate_when_starttls_fails(monkeypatch):
    class FailingSmtp:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            raise ssl.SSLCertVerificationError("certificate verify failed")

        def login(self, username, password):
            pytest.fail("Credentials must not be sent after TLS verification fails")

        def send_message(self, message):
            pytest.fail("Email must not be sent after TLS verification fails")

    monkeypatch.setattr(email_notifications.smtplib, "SMTP", FailingSmtp)
    monkeypatch.setattr(email_notifications.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_notifications.settings, "smtp_port", 587)
    monkeypatch.setattr(email_notifications.settings, "smtp_use_ssl", False)
    monkeypatch.setattr(email_notifications.settings, "smtp_use_starttls", True)
    monkeypatch.setattr(email_notifications.settings, "smtp_username", "mailer")
    monkeypatch.setattr(email_notifications.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_notifications.settings, "email_from_email", "lms@example.com")

    with pytest.raises(ssl.SSLCertVerificationError):
        email_notifications._send_smtp(
            {
                "notification_id": "notice-bad-cert",
                "recipient_name": "Learner",
                "recipient_email": "learner@example.com",
                "subject": "Course assigned",
                "body_text": "Example body",
            }
        )


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
