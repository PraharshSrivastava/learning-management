"""Email status report: what the system recorded about each course assignment email.

`derive_email_state` is the only place that decides a label. Every label says exactly what was
recorded and no more: acceptance by the mail server does not prove the email reached an inbox.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from app.core.settings import is_single_mailbox, settings
from app.db.database import get_connection
from app.modules.access.course_authorization import is_admin_trainer
from app.modules.access.reporting_scope import TrainerPerformanceScope
from app.modules.courses import repository as courses
from app.repositories import email_status as repository
from app.services import email_notifications as outbox

LABELS = {
    "accepted": "Sent to mail server",
    "sent_untracked": "Recorded as sent",
    "logged_only": "Not emailed (log mode)",
    "queued": "Waiting in queue",
    "in_batch": "In current send batch",
    "retrying": "Failed, will retry",
    "gave_up": "Failed, gave up",
    "unknown": "Outcome unknown",
    "cancelled": "Cancelled",
    "skipped": "Not sent",
    "no_record": "No email record",
    "unrecognised": "Status unavailable",
}
# Problems first, so they are what a trainer sees.
SORT_ORDER = (
    "unrecognised",
    "gave_up",
    "unknown",
    "retrying",
    "skipped",
    "no_record",
    "in_batch",
    "queued",
    "cancelled",
    "logged_only",
    "accepted",
    "sent_untracked",
)
TILES = (
    ("accepted", "Sent to mail server", ("accepted",)),
    ("sent_untracked", "Recorded as sent", ("sent_untracked",)),
    ("logged_only", "Not emailed (log mode)", ("logged_only",)),
    ("queued", "Waiting in queue", ("queued",)),
    ("in_batch", "In current send batch", ("in_batch",)),
    ("retrying", "Failed, will retry", ("retrying",)),
    ("gave_up", "Failed, gave up", ("gave_up",)),
    ("unknown", "Outcome unknown", ("unknown",)),
    ("cancelled", "Cancelled", ("cancelled",)),
    ("not_sent", "Not sent or no record", ("skipped", "no_record")),
    ("unrecognised", "Status unavailable", ("unrecognised",)),
)
ALWAYS_SHOWN_TILES = {"accepted", "gave_up"}
SKIP_TEXT = {
    "missing_email": "No email address in the directory when assigned.",
    "not_allowlisted": "Not on the recipient allowlist when assigned.",
    "delivery_disabled": "Email delivery was off when assigned.",
    "journey_only": "Journey course: this course sends no course emails.",
}
CANCEL_TEXT = {
    "assignment_changed": "The assignment changed before sending.",
    "assignment_removed": "The assignment no longer exists.",
    "assignment_withdrawn": "The assignment was withdrawn before sending.",
    "already_completed": "The employee completed the course before sending.",
    "already_overdue": "The deadline passed before sending. Overdue emails apply instead.",
    "course_unavailable": "The course was no longer available when sending.",
    "journey_course": "Journey course: this course sends no course emails.",
    "not_allowlisted": "Not on the recipient allowlist when sending.",
    "not_applicable": "This email no longer applied when sending.",
    "moved_to_digest": "Replaced by a summary email.",
    "overdue_limit": "The overdue email limit was reached.",
}
ASSIGNMENT_CHANGED_NOTE = (
    "The assignment changed after this email (new deadline or reactivated). "
    "No new assignment email was sent."
)
RESENDABLE_STATES = {"gave_up", "unknown"}
PAGE_SIZE_LIMIT = 100


def _parse(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def to_report_time(value: object) -> datetime | None:
    """Stored times are the server's local clock unless they carry an offset."""
    parsed = _parse(value)
    if parsed is None:
        return None
    return parsed.astimezone(ZoneInfo(settings.email_notification_timezone))


def display_time(value: object) -> str | None:
    local = to_report_time(value)
    return local.strftime("%d %b %Y, %I:%M %p %Z") if local else None


def plain_failure(facts: dict) -> str:
    """Plain wording for the last failure. Never claims more than the reply said."""
    code = facts.get("smtp_code")
    response = str(facts.get("smtp_response") or "")
    if code:
        code = int(code)
        if "5.1.1" in response or "5.1.10" in response:
            return "The mail server says this mailbox doesn't exist."
        if code in (530, 534, 535, 538):
            return f"The mail server rejected the sender's login (code {code})."
        if 400 <= code < 500:
            return f"The mail server was busy or temporarily unavailable (code {code})."
        return f"The mail server rejected this email (code {code})."
    if facts.get("last_result") == "error":
        return "The email could not be handed to the mail server."
    return "The last attempt failed."


def derive_email_state(facts: dict, *, now: datetime) -> dict:
    """Decide the state, label and detail for one assignment email from recorded facts."""

    def result(state: str, detail: str) -> dict:
        return {"state": state, "label": LABELS[state], "detail": detail}

    if not facts.get("notification_id"):
        reason = facts.get("skip_reason")
        if reason:
            return result("skipped", SKIP_TEXT.get(reason, "Reason not recorded."))
        return result("no_record", "The system has no record of an email for this assignment.")

    status = facts.get("email_status")
    claims = int(facts.get("claim_attempts") or 0)
    real = int(facts.get("real_attempts") or 0)
    last_result = facts.get("last_result")
    unfinished = bool(facts.get("has_unfinished"))
    limit = settings.email_max_attempts
    unknown = result(
        "unknown", "Sending was interrupted. This email may or may not have gone out."
    )

    if status == "sent":
        if last_result in ("accepted", "started"):
            detail = (
                f"Accepted on attempt {real}."
                if real > 1
                else "The mail server accepted this email."
            )
            return result("accepted", detail)
        if last_result == "logged_only":
            return result("logged_only", "Written to the server log only. No email left the system.")
        if last_result is None:
            return result(
                "sent_untracked",
                "Sent before detailed tracking began. Delivery method not recorded.",
            )
        return result("unrecognised", "The recorded details for this email do not agree.")

    if status in ("pending", "failed"):
        if unfinished:
            return unknown
        if claims == 0:
            return result("queued", "Will go out in a coming send round.")
        if claims >= limit:
            return result("gave_up", plain_failure(facts))
        when = display_time(facts.get("next_attempt_at"))
        return result(
            "retrying",
            f"{plain_failure(facts)} Will retry, not before {when}."
            if when
            else f"{plain_failure(facts)} Will retry.",
        )

    if status == "sending":
        locked_at = _parse(facts.get("locked_at"))
        lock_age = timedelta(seconds=settings.email_lock_timeout_seconds)
        if locked_at is not None and locked_at > now - lock_age:
            return result("in_batch", "Picked up in the current send round.")
        if unfinished:
            return unknown
        if claims >= limit:
            return result("gave_up", "This email was never tried and will not be retried.")
        return result("queued", "Will go out in a coming send round.")

    if status == "cancelled":
        reason = facts.get("cancel_reason")
        if reason:
            return result("cancelled", CANCEL_TEXT.get(reason, "Reason not recorded."))
        return result("cancelled", "Reason not recorded (before detailed tracking).")

    return result("unrecognised", "This email has a status the report does not recognise.")


def activity_for(row: dict) -> dict:
    """Course activity, using the same started rule as the Employees report."""
    percent = int(row.get("completion_percent") or 0)
    if row.get("revoked_at") or row.get("status") == "revoked":
        return {"state": "withdrawn", "label": "Assignment withdrawn", "percent": percent}
    if row.get("status") == "completed":
        return {"state": "completed", "label": "Completed", "percent": 100}
    if (
        row.get("started_at") is not None
        or int(row.get("completed_modules") or 0) > 0
        or row.get("status") == "started"
    ):
        return {"state": "in_progress", "label": f"In progress, {percent}%", "percent": percent}
    return {"state": "not_started", "label": "Not started", "percent": 0}


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    return f"{local[:2]}***@{domain}"


def _can_manage(course: dict | None, trainer: dict) -> bool:
    return bool(course) and (course["trainer_id"] == trainer["trainer_id"] or is_admin_trainer(trainer))


def _delivery_banners(worker: dict | None, now: datetime) -> list[dict]:
    banners = []
    mode = settings.email_delivery_mode
    if mode == "disabled":
        return [
            {"kind": "disabled", "message": "Email delivery is off. Nothing here will be sent."}
        ]
    if mode == "log":
        banners.append(
            {"kind": "log", "message": "Log mode. Emails are written to the server log, not sent."}
        )
    if settings.email_test_mode:
        banners.append(
            {"kind": "test", "message": "Test mode. Only allow-listed addresses receive email."}
        )
    if not settings.email_scheduler_enabled:
        banners.append(
            {
                "kind": "worker",
                "message": "The email worker is switched off. Queued emails are not moving.",
            }
        )
        return banners
    finished = _parse(worker["last_cycle_finished_at"]) if worker else None
    limit = timedelta(seconds=settings.email_scheduler_interval_seconds * 3)
    if finished is None:
        banners.append(
            {
                "kind": "worker",
                "message": "The email worker has not recorded a run yet. Queued emails may not be moving.",
            }
        )
    elif not worker["last_cycle_ok"] or finished < now - limit:
        banners.append(
            {
                "kind": "worker",
                "message": f"The email worker last ran at {display_time(finished)}. "
                "Queued emails are not moving.",
            }
        )
    return banners


def _report_row(row: dict, *, now: datetime, can_manage: bool, is_admin: bool) -> dict:
    derived = derive_email_state(row, now=now)
    activity = activity_for(row)
    state = derived["state"]
    note = None
    if (
        state in ("accepted", "logged_only", "sent_untracked")
        and row.get("status") != "completed"
        and row.get("email_lifecycle") != row.get("assignment_lifecycle")
    ):
        note = ASSIGNMENT_CHANGED_NOTE
    email = row.get("recipient_email") or row.get("employee_email")
    updated = (
        row.get("sent_at") if row.get("email_status") == "sent" else row.get("email_updated_at")
    ) or row.get("skip_at")
    real = int(row.get("real_attempts") or 0)
    return {
        "assignment_id": row["assignment_id"],
        "notification_id": row.get("notification_id"),
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "email": email if can_manage else mask_email(email),
        "department": row.get("department"),
        "state": state,
        "label": derived["label"],
        "detail": derived["detail"],
        "note": note,
        "attempts": real or None,
        "max_attempts": settings.email_max_attempts,
        "updated_at": display_time(updated),
        "activity_state": activity["state"],
        "activity_label": activity["label"],
        "activity_percent": activity["percent"],
        "can_resend": can_manage and state in RESENDABLE_STATES,
        "resend_needs_confirmation": state == "unknown",
        "technical_detail": row.get("smtp_response") or row.get("last_error") if is_admin else None,
    }


def _sent_not_started(row: dict) -> bool:
    return row["state"] in ("accepted", "sent_untracked") and row["activity_state"] == "not_started"


def _build(scope, trainer: dict, course_id: str, filters: dict) -> dict:
    if not isinstance(scope, TrainerPerformanceScope):
        raise AuthorizationError("Email status is only available in the trainer app")
    now = outbox._now()
    snapshot = repository.course_snapshot(scope, course_id=course_id, now=now, **filters)
    can_manage = _can_manage(snapshot["course"], trainer)
    is_admin = is_admin_trainer(trainer)
    rows = [
        _report_row(row, now=now, can_manage=can_manage, is_admin=is_admin)
        for row in snapshot["rows"]
    ]
    rows.sort(key=lambda row: (SORT_ORDER.index(row["state"]), row["employee_name"].lower()))
    return {"rows": rows, "snapshot": snapshot, "now": now, "can_manage": can_manage}


def _select(rows: list[dict], *, tile: str | None, search: str | None, not_started: bool) -> list[dict]:
    states = next((item[2] for item in TILES if item[0] == tile), None)
    if tile and tile != "all" and states is None:
        raise DomainValidationError("Unknown email status filter")
    needle = (search or "").strip().lower()
    return [
        row
        for row in rows
        if (states is None or row["state"] in states)
        and (not not_started or _sent_not_started(row))
        # Only what this viewer can see is searchable, so masked addresses cannot be probed.
        and (
            not needle
            or needle in row["employee_name"].lower()
            or needle in (row["email"] or "").lower()
        )
    ]


def course_report(
    scope,
    trainer: dict,
    *,
    course_id: str,
    tile: str | None = None,
    search: str | None = None,
    not_started: bool = False,
    page: int = 1,
    page_size: int = 50,
    **filters,
) -> dict:
    built = _build(scope, trainer, course_id, filters)
    rows, snapshot, now = built["rows"], built["snapshot"], built["now"]
    counts = {state: 0 for state in LABELS}
    for row in rows:
        counts[row["state"]] += 1
    tiles = [{"key": "all", "label": "All employees", "count": len(rows)}]
    for key, label, states in TILES:
        count = sum(counts[state] for state in states)
        if count or key in ALWAYS_SHOWN_TILES:
            tiles.append({"key": key, "label": label, "count": count})
    selected = _select(rows, tile=tile, search=search, not_started=not_started)
    size = min(max(page_size, 1), PAGE_SIZE_LIMIT)
    worker = snapshot["worker"]
    course = snapshot["course"]
    return {
        "generated_at": display_time(now),
        "course_id": course_id,
        "course_name": course["course_name"] if course else None,
        "can_resend": built["can_manage"],
        "total": len(rows),
        "accepted_count": counts["accepted"],
        "failed_count": counts["gave_up"],
        "not_started_count": sum(1 for row in rows if _sent_not_started(row)),
        "tiles": tiles,
        "banners": _delivery_banners(worker, now),
        "last_send_round": display_time(worker["last_cycle_finished_at"]) if worker else None,
        "matched": len(selected),
        "page": page,
        "page_size": size,
        "rows": selected[(page - 1) * size : page * size],
    }


def csv_rows(
    scope,
    trainer: dict,
    *,
    course_id: str,
    tile: str | None = None,
    search: str | None = None,
    not_started: bool = False,
    **filters,
) -> list[dict]:
    built = _build(scope, trainer, course_id, filters)
    return _select(built["rows"], tile=tile, search=search, not_started=not_started)


def _resend_one(notification_id: str, trainer: dict, *, confirm_unknown: bool) -> str:
    """Put one email back in the queue, or raise why it can't be. Returns the course id."""
    if settings.email_delivery_mode == "disabled":
        raise ConflictError("Email delivery is off, so nothing can be resent.")
    with get_connection() as connection:
        facts = repository.lock_notification_facts(connection, notification_id)
        if not facts or facts["event_type"] != "assigned" or facts["recipient_role"] != "employee":
            raise NotFoundError("Email not found")
        owner = courses.get_course_owner(facts["course_id"])
        if owner != trainer["trainer_id"] and not is_admin_trainer(trainer):
            raise AuthorizationError("Only the course's owner or an Admin Trainer can resend emails")
        now = outbox._now()
        state = derive_email_state(facts, now=now)["state"]
        if state not in RESENDABLE_STATES:
            raise ConflictError("This email's status changed. Refresh and try again.")
        if state == "unknown" and not confirm_unknown:
            raise ConflictError("This email may already have gone out. Confirm to resend it.")
        context = outbox._assignment_context(connection, facts["assignment_id"])
        lifecycle = int(context.get("notification_lifecycle") or 1) if context else 1
        if not context or not outbox._event_is_current(context, "assigned", lifecycle):
            raise ConflictError("This assignment can no longer receive its assignment email.")
        email = str(context.get("employee_email") or "").strip()
        if not is_single_mailbox(email):
            raise ConflictError("This employee has no valid email address in the directory.")
        if not outbox._recipient_allowed(email):
            raise ConflictError("This employee is not on the recipient allowlist.")
        updated = repository.reset_for_resend(
            connection,
            notification_id,
            expected_status=facts["email_status"],
            recipient_email=email,
            recipient_name=context.get("employee_name"),
            lifecycle=lifecycle,
            trainer_id=trainer["trainer_id"],
            now=now.isoformat(),
        )
        if not updated:
            raise ConflictError("This email's status changed. Refresh and try again.")
        connection.commit()
    return facts["course_id"]


def resend(notification_id: str, trainer: dict, *, confirm_unknown: bool = False) -> dict:
    _resend_one(notification_id, trainer, confirm_unknown=confirm_unknown)
    return {"resent": 1, "skipped": 0}


def resend_failed(scope, trainer: dict, *, course_id: str) -> dict:
    """Resend every email that gave up. Outcome unknown is never included in bulk."""
    built = _build(scope, trainer, course_id, {})
    if not built["can_manage"]:
        raise AuthorizationError("Only the course's owner or an Admin Trainer can resend emails")
    resent = skipped = 0
    for row in built["rows"]:
        if row["state"] != "gave_up":
            continue
        try:
            _resend_one(row["notification_id"], trainer, confirm_unknown=False)
            resent += 1
        except ConflictError:
            skipped += 1
    return {"resent": resent, "skipped": skipped}
