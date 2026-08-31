"""Course assignment email outbox, scheduler, and SMTP delivery."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable

from app.core.settings import settings
from app.repositories.database import get_connection

logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None

COURSE_EVENTS = {"assigned", "reactivated", "due_soon", "completed", "overdue"}
ACTIVE_STATUSES = {"pending", "started", "overdue"}


def _now() -> datetime:
    return datetime.now()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _format_datetime(value: str | None) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return "not set"
    return parsed.strftime("%d %b %Y, %I:%M %p")


def _assignment_context(connection, assignment_id: str) -> dict | None:
    row = connection.execute(
        """
        SELECT
            ca.assignment_id,
            ca.course_id,
            ca.employee_id,
            ca.status AS assignment_status,
            ca.assigned_at,
            ca.deadline,
            ca.completed_at,
            ca.revoked_at,
            ca.notification_lifecycle,
            c.course_name,
            c.trainer_id,
            e.name AS employee_name,
            e.email AS employee_email,
            e.manager_employee_id,
            hod.name AS hod_name,
            hod.email AS hod_email,
            t.name AS trainer_name,
            t.email AS trainer_email
        FROM course_assignments ca
        JOIN courses c ON c.course_id = ca.course_id
        JOIN employees e ON e.employee_id = ca.employee_id
        LEFT JOIN employees hod ON hod.employee_id = e.manager_employee_id
        LEFT JOIN trainers t ON t.trainer_id = c.trainer_id
        WHERE ca.assignment_id = ?
        """,
        (assignment_id,),
    ).fetchone()
    return dict(row) if row else None


def _recipient_rows(context: dict) -> list[dict]:
    recipients = [
        {
            "role": "employee",
            "email": context.get("employee_email"),
            "name": context.get("employee_name"),
        },
        {
            "role": "hod",
            "email": context.get("hod_email"),
            "name": context.get("hod_name"),
        },
        {
            "role": "trainer",
            "email": context.get("trainer_email"),
            "name": context.get("trainer_name"),
        },
    ]
    resolved = []
    for recipient in recipients:
        email = str(recipient.get("email") or "").strip()
        if not email or "@" not in email:
            logger.info(
                "course_email_recipient_skipped assignment_id=%s role=%s reason=missing_email",
                context.get("assignment_id"),
                recipient["role"],
            )
            continue
        recipient["email"] = email
        resolved.append(recipient)
    return resolved


def _event_title(event_type: str) -> str:
    return {
        "assigned": "Course assigned",
        "reactivated": "Course reassigned",
        "due_soon": "Course due soon",
        "completed": "Course completed",
        "overdue": "Course overdue",
    }[event_type]


def _message_for(context: dict, event_type: str, role: str) -> tuple[str, str]:
    course_name = context.get("course_name") or "Course"
    employee_name = context.get("employee_name") or context.get("employee_id") or "Employee"
    deadline = _format_datetime(context.get("deadline"))
    completed_at = _format_datetime(context.get("completed_at"))
    subject = f"{_event_title(event_type)}: {course_name}"

    if event_type == "completed":
        action_line = f"{employee_name} completed {course_name} on {completed_at}."
    elif event_type == "overdue":
        action_line = f"{course_name} is overdue for {employee_name}. The deadline was {deadline}."
    elif event_type == "due_soon":
        action_line = f"{course_name} is due soon for {employee_name}. The deadline is {deadline}."
    elif event_type == "reactivated":
        action_line = f"{course_name} has been reassigned to {employee_name}. The deadline is {deadline}."
    else:
        action_line = f"{course_name} has been assigned to {employee_name}. The deadline is {deadline}."

    greeting = "Hello,"
    if role == "employee":
        greeting = f"Hello {employee_name},"
    elif role == "hod":
        greeting = f"Hello {context.get('hod_name') or 'HOD'},"
    elif role == "trainer":
        greeting = f"Hello {context.get('trainer_name') or 'Trainer'},"

    lines = [
        greeting,
        "",
        action_line,
        "",
        f"Employee: {employee_name}",
        f"Course: {course_name}",
        f"Deadline: {deadline}",
    ]
    if settings.lms_public_url:
        lines.extend(["", f"Open LMS: {settings.lms_public_url}"])
    lines.extend(["", "This is an automated LMS notification."])
    return subject, "\n".join(lines)


def _event_is_current(context: dict, event_type: str, lifecycle: int) -> bool:
    if int(context.get("notification_lifecycle") or 1) != lifecycle:
        return False
    status = context.get("assignment_status")
    if event_type == "completed":
        return status == "completed" and bool(context.get("completed_at"))
    if event_type in {"assigned", "reactivated", "due_soon"}:
        return status in {"pending", "started"}
    if event_type == "overdue":
        return status == "overdue"
    return False


def enqueue_assignment_notifications(assignment_id: str | None, event_type: str) -> int:
    """Queue event emails for learner, HOD/superior, and trainer."""
    if not assignment_id or event_type not in COURSE_EVENTS or settings.email_delivery_mode == "disabled":
        return 0
    now = _now().isoformat()
    created = 0
    with get_connection() as connection:
        context = _assignment_context(connection, assignment_id)
        if not context:
            return 0
        lifecycle = int(context.get("notification_lifecycle") or 1)
        if not _event_is_current(context, event_type, lifecycle):
            return 0
        for recipient in _recipient_rows(context):
            subject, body_text = _message_for(context, event_type, recipient["role"])
            row = connection.execute(
                """
                INSERT INTO email_notifications (
                    notification_id, assignment_id, notification_lifecycle, event_type,
                    recipient_role, recipient_email, recipient_name, subject, body_text,
                    status, next_attempt_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                ON CONFLICT (assignment_id, notification_lifecycle, event_type, recipient_role)
                DO NOTHING
                RETURNING notification_id
                """,
                (
                    str(uuid.uuid4()),
                    assignment_id,
                    lifecycle,
                    event_type,
                    recipient["role"],
                    recipient["email"],
                    recipient.get("name"),
                    subject,
                    body_text,
                    now,
                    now,
                    now,
                ),
            ).fetchone()
            if row:
                created += 1
        connection.commit()
    return created


def cancel_assignment_notifications(
    assignment_id: str | None,
    event_types: Iterable[str] = ("due_soon", "overdue"),
) -> int:
    if not assignment_id:
        return 0
    event_types = tuple(event for event in event_types if event in COURSE_EVENTS)
    if not event_types:
        return 0
    placeholders = ", ".join("?" for _ in event_types)
    now = _now().isoformat()
    with get_connection() as connection:
        row = connection.execute(
            f"""
            UPDATE email_notifications
            SET status = 'cancelled', updated_at = ?
            WHERE assignment_id = ?
              AND event_type IN ({placeholders})
              AND status IN ('pending', 'failed')
            RETURNING notification_id
            """,  # nosec B608
            (now, assignment_id, *event_types),
        ).fetchall()
        connection.commit()
    return len(row)


def enqueue_due_soon_notifications(as_of: datetime | None = None) -> int:
    if settings.email_delivery_mode == "disabled":
        return 0
    now = as_of or _now()
    threshold = now + timedelta(days=settings.email_due_soon_days)
    queued = 0
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT ca.assignment_id
            FROM course_assignments ca
            JOIN courses c ON c.course_id = ca.course_id
            JOIN assignment_rules ar ON ar.course_id = ca.course_id
            WHERE ca.status IN ('pending', 'started')
              AND c.status = 'published'
              AND ar.is_active = TRUE
              AND ca.deadline > ?
              AND ca.deadline <= ?
            """,
            (now.isoformat(), threshold.isoformat()),
        ).fetchall()
    for row in rows:
        queued += enqueue_assignment_notifications(row["assignment_id"], "due_soon")
    return queued


def enqueue_overdue_notifications(as_of: datetime | None = None) -> int:
    if settings.email_delivery_mode == "disabled":
        return 0
    now = as_of or _now()
    queued = 0
    with get_connection() as connection:
        rows = connection.execute(
            """
            UPDATE course_assignments ca
            SET status = 'overdue',
                updated_at = ?
            FROM courses c, assignment_rules ar
            WHERE c.course_id = ca.course_id
              AND ar.course_id = ca.course_id
              AND ca.status IN ('pending', 'started')
              AND c.status = 'published'
              AND ar.is_active = TRUE
              AND ca.deadline < ?
            RETURNING ca.assignment_id
            """,
            (now.isoformat(), now.isoformat()),
        ).fetchall()
        existing = connection.execute(
            """
            SELECT ca.assignment_id
            FROM course_assignments ca
            JOIN courses c ON c.course_id = ca.course_id
            JOIN assignment_rules ar ON ar.course_id = ca.course_id
            WHERE ca.status = 'overdue'
              AND c.status = 'published'
              AND ar.is_active = TRUE
              AND ca.deadline < ?
            """,
            (now.isoformat(),),
        ).fetchall()
        connection.commit()
    for row in [*rows, *existing]:
        queued += enqueue_assignment_notifications(row["assignment_id"], "overdue")
    return queued


def _send_smtp(notification: dict) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    from_email = settings.email_from_email or settings.smtp_username
    if not from_email:
        raise RuntimeError("EMAIL_FROM_EMAIL is not configured")

    message = EmailMessage()
    message["From"] = formataddr((settings.email_from_name, from_email))
    message["To"] = formataddr((notification.get("recipient_name") or "", notification["recipient_email"]))
    message["Subject"] = notification["subject"]
    message.set_content(notification["body_text"])

    if settings.smtp_use_ssl:
        client_factory = smtplib.SMTP_SSL
    else:
        client_factory = smtplib.SMTP
    with client_factory(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
        if settings.smtp_use_starttls and not settings.smtp_use_ssl:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def _send_notification(notification: dict) -> None:
    if settings.email_delivery_mode == "log":
        logger.info(
            "course_email_log notification_id=%s event=%s role=%s to=%s subject=%s",
            notification["notification_id"],
            notification["event_type"],
            notification["recipient_role"],
            notification["recipient_email"],
            notification["subject"],
        )
        return
    if settings.email_delivery_mode == "smtp":
        _send_smtp(notification)
        return
    raise RuntimeError(f"Unsupported EMAIL_DELIVERY_MODE: {settings.email_delivery_mode}")


def _claim_pending_notifications(limit: int) -> list[dict]:
    now = _now().isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            """
            WITH picked AS (
                SELECT notification_id
                FROM email_notifications
                WHERE status IN ('pending', 'failed')
                  AND next_attempt_at <= ?
                  AND attempts < ?
                ORDER BY next_attempt_at, created_at
                LIMIT ?
                FOR UPDATE SKIP LOCKED
            )
            UPDATE email_notifications en
            SET status = 'sending',
                attempts = en.attempts + 1,
                locked_at = ?,
                updated_at = ?
            FROM picked
            WHERE en.notification_id = picked.notification_id
            RETURNING en.*
            """,
            (now, settings.email_max_attempts, limit, now, now),
        ).fetchall()
        connection.commit()
    return [dict(row) for row in rows]


def _mark_sent(notification_id: str) -> None:
    now = _now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE email_notifications
            SET status = 'sent',
                sent_at = ?,
                last_error = NULL,
                locked_at = NULL,
                updated_at = ?
            WHERE notification_id = ?
            """,
            (now, now, notification_id),
        )
        connection.commit()


def _mark_failed(notification: dict, error: Exception) -> None:
    now_dt = _now()
    attempts = int(notification.get("attempts") or 0)
    final_status = "failed" if attempts >= settings.email_max_attempts else "pending"
    next_attempt = now_dt + timedelta(seconds=settings.email_retry_delay_seconds)
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE email_notifications
            SET status = ?,
                next_attempt_at = ?,
                locked_at = NULL,
                last_error = ?,
                updated_at = ?
            WHERE notification_id = ?
            """,
            (
                final_status,
                next_attempt.isoformat(),
                str(error)[:1000],
                now_dt.isoformat(),
                notification["notification_id"],
            ),
        )
        connection.commit()


def _cancel_stale(notification_id: str) -> None:
    now = _now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE email_notifications
            SET status = 'cancelled',
                locked_at = NULL,
                updated_at = ?
            WHERE notification_id = ?
            """,
            (now, notification_id),
        )
        connection.commit()


def process_pending_notifications(limit: int | None = None) -> int:
    if settings.email_delivery_mode == "disabled":
        return 0
    processed = 0
    for notification in _claim_pending_notifications(limit or settings.email_worker_batch_size):
        with get_connection() as connection:
            context = _assignment_context(connection, notification["assignment_id"])
        if not context or not _event_is_current(
            context,
            notification["event_type"],
            int(notification["notification_lifecycle"]),
        ):
            logger.info(
                "course_email_cancelled_stale notification_id=%s event=%s role=%s to=%s",
                notification["notification_id"],
                notification["event_type"],
                notification["recipient_role"],
                notification["recipient_email"],
            )
            _cancel_stale(notification["notification_id"])
            continue
        try:
            _send_notification(notification)
        except Exception as exc:
            logger.warning(
                "course_email_send_failed notification_id=%s event=%s role=%s to=%s error=%s",
                notification["notification_id"],
                notification["event_type"],
                notification["recipient_role"],
                notification["recipient_email"],
                exc,
            )
            _mark_failed(notification, exc)
            continue
        _mark_sent(notification["notification_id"])
        logger.info(
            "course_email_sent notification_id=%s event=%s role=%s to=%s",
            notification["notification_id"],
            notification["event_type"],
            notification["recipient_role"],
            notification["recipient_email"],
        )
        processed += 1
    return processed


def run_notification_cycle() -> dict[str, int]:
    due_soon = enqueue_due_soon_notifications()
    overdue = enqueue_overdue_notifications()
    sent = process_pending_notifications()
    return {"due_soon": due_soon, "overdue": overdue, "sent": sent}


async def _run_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_notification_cycle)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("course_email_notification_cycle_failed")
        await asyncio.sleep(settings.email_scheduler_interval_seconds)


def start_email_notification_scheduler() -> None:
    global _task
    if (
        not settings.email_scheduler_enabled
        or settings.email_delivery_mode == "disabled"
        or _task is not None
    ):
        return
    _task = asyncio.create_task(_run_loop(), name="email-notification-scheduler")


async def stop_email_notification_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
