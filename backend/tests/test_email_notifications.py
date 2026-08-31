from app.core.settings import Settings
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

    recipients = email_notifications._recipient_rows(context)

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

