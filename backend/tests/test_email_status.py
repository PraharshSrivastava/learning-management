"""The Email status report must never claim more than the system recorded."""

import itertools
import smtplib
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AuthorizationError
from app.schemas.reporting_scope import EmployeePerformanceScope
from app.services import email_notifications, email_status
from app.services.email_status import LABELS, derive_email_state

NOW = datetime(2026, 11, 11, 10, 42)


@pytest.fixture(autouse=True)
def limits(monkeypatch):
    monkeypatch.setattr(email_status.settings, "email_max_attempts", 5)
    monkeypatch.setattr(email_status.settings, "email_lock_timeout_seconds", 600)
    monkeypatch.setattr(email_status.settings, "email_notification_timezone", "Asia/Kolkata")


def facts(**overrides):
    base = {
        "notification_id": "n-1",
        "email_status": "pending",
        "claim_attempts": 0,
        "real_attempts": 0,
        "last_result": None,
        "smtp_code": None,
        "smtp_response": None,
        "has_unfinished": False,
        "locked_at": None,
        "next_attempt_at": "2026-11-11T10:47:00",
        "cancel_reason": None,
        "skip_reason": None,
    }
    base.update(overrides)
    return base


def state(**overrides):
    return derive_email_state(facts(**overrides), now=NOW)["state"]


FRESH_LOCK = (NOW - timedelta(seconds=30)).isoformat()
EXPIRED_LOCK = (NOW - timedelta(seconds=601)).isoformat()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"email_status": "sent", "last_result": "accepted"}, "accepted"),
        ({"email_status": "sent", "last_result": "started"}, "accepted"),
        ({"email_status": "sent", "last_result": "logged_only"}, "logged_only"),
        ({"email_status": "sent", "last_result": None}, "sent_untracked"),
        ({"email_status": "sent", "last_result": "rejected"}, "unrecognised"),
        ({"email_status": "pending"}, "queued"),
        ({"email_status": "pending", "claim_attempts": 2, "last_result": "rejected"}, "retrying"),
        ({"email_status": "failed", "claim_attempts": 2, "last_result": "rejected"}, "retrying"),
        ({"email_status": "failed", "claim_attempts": 5, "last_result": "rejected"}, "gave_up"),
        ({"email_status": "pending", "claim_attempts": 5, "last_result": "rejected"}, "gave_up"),
        ({"email_status": "pending", "claim_attempts": 1, "has_unfinished": True}, "unknown"),
        ({"email_status": "sending", "claim_attempts": 1, "locked_at": FRESH_LOCK}, "in_batch"),
        (
            {
                "email_status": "sending",
                "claim_attempts": 1,
                "locked_at": FRESH_LOCK,
                "has_unfinished": True,
            },
            "in_batch",
        ),
        (
            {
                "email_status": "sending",
                "claim_attempts": 1,
                "locked_at": EXPIRED_LOCK,
                "has_unfinished": True,
            },
            "unknown",
        ),
        ({"email_status": "sending", "claim_attempts": 1, "locked_at": EXPIRED_LOCK}, "queued"),
        ({"email_status": "sending", "claim_attempts": 5, "locked_at": EXPIRED_LOCK}, "gave_up"),
        ({"email_status": "cancelled", "cancel_reason": "assignment_withdrawn"}, "cancelled"),
        ({"email_status": "cancelled"}, "cancelled"),
        ({"notification_id": None, "skip_reason": "missing_email"}, "skipped"),
        ({"notification_id": None}, "no_record"),
        ({"email_status": "something_new"}, "unrecognised"),
    ],
)
def test_each_recorded_situation_has_exactly_one_state(overrides, expected):
    assert state(**overrides) == expected


def test_every_combination_of_facts_is_handled():
    combos = itertools.product(
        (None, "n-1"),
        ("pending", "sending", "sent", "failed", "cancelled", "bogus", None),
        (0, 1, 5, 9),
        (None, "started", "accepted", "logged_only", "rejected", "error", "abandoned"),
        (False, True),
        (None, FRESH_LOCK, EXPIRED_LOCK, "not-a-date"),
        (None, "assignment_withdrawn", "made_up"),
        (None, "missing_email", "made_up"),
    )
    for notification, status, claims, last, unfinished, lock, cancel, skip in combos:
        result = derive_email_state(
            facts(
                notification_id=notification,
                email_status=status,
                claim_attempts=claims,
                real_attempts=claims,
                last_result=last,
                has_unfinished=unfinished,
                locked_at=lock,
                cancel_reason=cancel,
                skip_reason=skip,
            ),
            now=NOW,
        )
        assert result["state"] in LABELS
        assert result["label"] == LABELS[result["state"]]
        assert result["detail"]


def test_raising_the_attempt_limit_turns_gave_up_back_into_will_retry(monkeypatch):
    row = {"email_status": "failed", "claim_attempts": 5, "last_result": "rejected"}
    assert state(**row) == "gave_up"
    monkeypatch.setattr(email_status.settings, "email_max_attempts", 8)
    assert state(**row) == "retrying"


def test_accepted_label_never_implies_delivery():
    assert LABELS["accepted"] == "Sent to mail server"


def test_retry_time_is_a_lower_bound_in_report_time():
    detail = derive_email_state(
        facts(
            claim_attempts=1,
            last_result="rejected",
            smtp_code=421,
            next_attempt_at="2026-11-11T05:17:00+00:00",
        ),
        now=NOW,
    )["detail"]
    assert detail == (
        "The mail server was busy or temporarily unavailable (code 421). "
        "Will retry, not before 11 Nov 2026, 10:47 AM IST."
    )


@pytest.mark.parametrize(
    ("code", "response", "expected"),
    [
        (550, "5.1.1 User unknown", "The mail server says this mailbox doesn't exist."),
        (550, "5.7.1 Rejected by policy", "The mail server rejected this email (code 550)."),
        (535, "bad credentials", "The mail server rejected the sender's login (code 535)."),
        (451, "try later", "The mail server was busy or temporarily unavailable (code 451)."),
    ],
)
def test_failure_text_says_only_what_the_reply_said(code, response, expected):
    assert (
        email_status.plain_failure(
            {"smtp_code": code, "smtp_response": response, "last_result": "rejected"}
        )
        == expected
    )


def test_timestamps_are_shown_in_report_time():
    assert email_status.display_time("2026-11-11T05:12:00+00:00") == "11 Nov 2026, 10:42 AM IST"


def test_naive_timestamps_follow_the_server_clock():
    naive = datetime(2026, 11, 11, 5, 12)
    expected = naive.astimezone(timezone.utc).astimezone(
        email_status.ZoneInfo("Asia/Kolkata")
    )
    assert email_status.to_report_time(naive.isoformat()) == expected


def test_masking_hides_the_mailbox():
    assert email_status.mask_email("ananya.mehta@example.com") == "an***@example.com"


def test_course_activity_uses_the_employees_report_rule():
    assert email_status.activity_for({"status": "completed"})["state"] == "completed"
    assert email_status.activity_for({"status": "pending", "completed_modules": 1})["state"] == (
        "in_progress"
    )
    assert email_status.activity_for({"status": "overdue", "started_at": "x"})["state"] == (
        "in_progress"
    )
    assert email_status.activity_for({"status": "overdue"})["state"] == "not_started"


def test_employee_scopes_are_refused():
    scope = EmployeePerformanceScope("e-1", "hub:1", "combined")
    with pytest.raises(AuthorizationError):
        email_status.course_report(scope, {"trainer_id": "t-1"}, course_id="c-1")


def test_email_routes_exist_only_in_the_trainer_api():
    from app.main import app

    paths = list(app.openapi()["paths"])
    assert "/api/trainer/performance/emails" in paths
    assert not [path for path in paths if "employee/performance/emails" in path]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"5.1.1 unknown")}),
            ("rejected", 550, "5.1.1 unknown"),
        ),
        (smtplib.SMTPDataError(554, b"policy"), ("rejected", 554, "policy")),
        (TimeoutError("timed out"), ("error", None, "timed out")),
    ],
)
def test_attempts_capture_the_servers_reply(error, expected):
    assert email_notifications._smtp_failure(error) == expected
