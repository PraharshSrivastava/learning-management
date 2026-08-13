"""Hub launch token verification tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.core.settings import Settings
from app.security.hub_launch import HubLaunchVerifier


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _token(secret: str, payload: dict) -> str:
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_b64}.{_b64url(signature)}"


def _verifier(secret: str = "test-secret") -> HubLaunchVerifier:
    return HubLaunchVerifier(
        Settings(
            hub_launch_secret=secret,
            hub_trainer_app_key="lms-trainer",
            hub_employee_app_key="lms-employee",
        )
    )


def test_accepts_valid_token_for_expected_app() -> None:
    token = _token(
        "test-secret",
        {
            "app_key": "lms-trainer",
            "app_id": 10,
            "sub": 42,
            "email": "trainer@phillipcapital.in",
            "exp": int(time.time()) + 60,
        },
    )

    session = _verifier().verify(token, "trainer")

    assert session is not None
    assert session.email == "trainer@phillipcapital.in"
    assert session.app == "trainer"


def test_rejects_token_for_wrong_app() -> None:
    token = _token(
        "test-secret",
        {
            "app_key": "lms-employee",
            "sub": 42,
            "email": "employee@phillipcapital.in",
            "exp": int(time.time()) + 60,
        },
    )

    assert _verifier().verify(token, "trainer") is None


def test_rejects_expired_token() -> None:
    token = _token(
        "test-secret",
        {
            "app_key": "lms-trainer",
            "sub": 42,
            "email": "trainer@phillipcapital.in",
            "exp": int(time.time()) - 1,
        },
    )

    assert _verifier().verify(token, "trainer") is None


def test_development_environment_bypasses_hub_session_requirement() -> None:
    verifier = HubLaunchVerifier(
        Settings(
            app_env="development",
            hub_trainer_app_key="lms-trainer",
            hub_employee_app_key="lms-employee",
        )
    )

    assert verifier.dev_bypass_enabled is True
