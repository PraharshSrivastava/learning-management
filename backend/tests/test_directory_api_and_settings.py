import pytest
from pydantic import ValidationError

from app.api import directory as directory_api
from app.core.exceptions import AuthenticationError
from app.core.settings import Settings


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


def test_production_allows_directory_sync_to_be_disabled_without_directory_secrets():
    settings = _production_settings()

    assert settings.directory_sync_enabled is False


def test_production_requires_directory_config_when_scheduler_is_enabled():
    with pytest.raises(ValidationError) as exc_info:
        _production_settings(directory_sync_enabled=True)

    message = str(exc_info.value)
    assert "DIRECTORY_EXPORTS_BASE_URL" in message
    assert "DIRECTORY_EXPORTS_API_KEY" in message
    assert "DIRECTORY_SYNC_ADMIN_KEY" in message


def test_sync_status_requires_internal_key(monkeypatch):
    monkeypatch.setattr(directory_api.settings, "directory_sync_admin_key", "sync-secret")

    with pytest.raises(AuthenticationError):
        directory_api.sync_status(x_directory_sync_key="wrong")


def test_sync_status_returns_config_and_persisted_states(monkeypatch):
    monkeypatch.setattr(directory_api.settings, "directory_sync_admin_key", "sync-secret")
    monkeypatch.setattr(directory_api.settings, "directory_sync_enabled", True)
    monkeypatch.setattr(directory_api.settings, "directory_sync_interval_hours", 24)
    monkeypatch.setattr(directory_api.settings, "directory_sync_page_limit", 100)
    monkeypatch.setattr(directory_api.settings, "directory_exports_base_url", "http://hub")
    monkeypatch.setattr(directory_api.settings, "directory_exports_api_key", "api-key")
    monkeypatch.setattr(
        directory_api,
        "list_sync_states",
        lambda: [
            {
                "job_name": "employee_change_logs",
                "cursor": 123,
                "last_attempt_at": "2026-08-19T00:00:00",
                "last_success_at": "2026-08-19T00:00:00",
                "last_status": "success",
                "last_error": None,
                "stats_json": {"received": 2},
            }
        ],
    )

    response = directory_api.sync_status(x_directory_sync_key="sync-secret")

    assert response["enabled"] is True
    assert response["configured"] is True
    assert response["states"][0]["job_name"] == "employee_change_logs"
    assert response["states"][0]["cursor"] == 123
