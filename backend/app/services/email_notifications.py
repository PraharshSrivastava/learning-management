"""Course assignment email outbox, scheduler, and SMTP delivery."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable
from zoneinfo import ZoneInfo

from app.core.settings import settings
from app.repositories.database import advisory_lock, get_connection
from app.services.email_templates import render_digest, render_individual

logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None

COURSE_EVENTS = {
    "assigned",
    "assignment_reminder",
    "due_soon",
    "completed",
    "overdue",
}
EVENT_RECIPIENT_ROLES = {
    "assigned": {"employee", "hod"},
    "assignment_reminder": {"employee"},
    "due_soon": {"employee"},
    "completed": {"employee"},
    "overdue": {"employee"},
}
DIGEST_RECIPIENT_ROLES = {
    "due_soon": {"hod", "trainer"},
    "completed": {"hod", "trainer"},
    "overdue": {"hod", "trainer"},
}


def _now() -> datetime:
    return datetime.now()


def _assignment_reminder_delay() -> timedelta:
    if settings.email_test_mode:
        return timedelta(minutes=settings.email_test_assignment_reminder_minutes)
    return timedelta(days=settings.email_assignment_reminder_days)


def _due_soon_window() -> timedelta:
    if settings.email_test_mode:
        return timedelta(minutes=settings.email_test_due_soon_window_minutes)
    return timedelta(days=settings.email_due_soon_days)


def _overdue_repeat_interval() -> timedelta:
    if settings.email_test_mode:
        return timedelta(minutes=settings.email_test_overdue_repeat_minutes)
    return timedelta(days=settings.email_overdue_repeat_days)


def _recipient_allowed(email: str | None) -> bool:
    allowlist = {item.lower() for item in settings.email_recipient_allowlist}
    return not allowlist or str(email or "").strip().lower() in allowlist


def _email_subject(subject: str) -> str:
    prefix = settings.email_subject_prefix.strip()
    if not prefix or subject.startswith(prefix):
        return subject
    return f"{prefix} {subject}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _compatible_now(reference: datetime, now: datetime | None = None) -> datetime:
    current = now or _now()
    if reference.tzinfo and not current.tzinfo:
        return current.astimezone(reference.tzinfo)
    if not reference.tzinfo and current.tzinfo:
        return current.replace(tzinfo=None)
    return current


def _overdue_occurrence_key(deadline: datetime, now: datetime | None = None) -> str:
    current = _compatible_now(deadline, now)
    elapsed_seconds = max(0.0, (current - deadline).total_seconds())
    repeat_seconds = _overdue_repeat_interval().total_seconds()
    occurrence = int(elapsed_seconds // repeat_seconds) + 1
    return f"period-{occurrence}"


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
            c.status AS course_status,
            c.trainer_id,
            ar.is_active AS assignment_rule_active,
            e.name AS employee_name,
            e.email AS employee_email,
            e.manager_employee_id,
            hod.employee_id AS hod_employee_id,
            hod.name AS hod_name,
            hod.email AS hod_email,
            t.name AS trainer_name,
            t.email AS trainer_email
            ,(
                SELECT COUNT(*)
                FROM course_modules cm
                WHERE cm.course_id = ca.course_id
            ) AS total_modules
            ,(
                SELECT COUNT(*)
                FROM course_modules cm
                LEFT JOIN module_progress mp
                  ON mp.assignment_id = ca.assignment_id
                 AND mp.module_id = cm.module_id
                WHERE cm.course_id = ca.course_id
                  AND COALESCE(mp.video_watched, FALSE) = TRUE
                  AND (
                      cm.quiz_json = 'null'::jsonb
                      OR cm.quiz_json = '{}'::jsonb
                      OR cm.quiz_json = '[]'::jsonb
                      OR COALESCE(mp.quiz_passed, FALSE) = TRUE
                  )
            ) AS completed_modules
        FROM course_assignments ca
        JOIN courses c ON c.course_id = ca.course_id
        LEFT JOIN assignment_rules ar ON ar.course_id = ca.course_id
        JOIN employees e ON e.employee_id = ca.employee_id
        LEFT JOIN employees hod ON hod.employee_id = e.manager_employee_id
        LEFT JOIN trainers t ON t.trainer_id = c.trainer_id
        WHERE ca.assignment_id = ?
        """,
        (assignment_id,),
    ).fetchone()
    if not row:
        return None
    context = dict(row)
    total = int(context.get("total_modules") or 0)
    completed = int(context.get("completed_modules") or 0)
    context["completion_percent"] = round((completed / total) * 100) if total else 0
    return context


def _recipient_rows(context: dict, event_type: str) -> list[dict]:
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
        if recipient["role"] not in EVENT_RECIPIENT_ROLES[event_type]:
            continue
        email = str(recipient.get("email") or "").strip()
        if not email or "@" not in email:
            logger.info(
                "course_email_recipient_skipped assignment_id=%s role=%s reason=missing_email",
                context.get("assignment_id"),
                recipient["role"],
            )
            continue
        if not _recipient_allowed(email):
            logger.info(
                "course_email_recipient_skipped assignment_id=%s role=%s reason=not_allowlisted",
                context.get("assignment_id"),
                recipient["role"],
            )
            continue
        recipient["email"] = email
        resolved.append(recipient)
    return resolved


def _message_for(context: dict, event_type: str, role: str) -> tuple[str, str, str]:
    subject, body_text, body_html = render_individual(context, event_type, role)
    return _email_subject(subject), body_text, body_html


def _event_is_current(
    context: dict,
    event_type: str,
    lifecycle: int,
    occurrence_key: str = "once",
) -> bool:
    if int(context.get("notification_lifecycle") or 1) != lifecycle:
        return False
    status = context.get("assignment_status")
    if context.get("course_status") not in {None, "published"}:
        return False
    if context.get("assignment_rule_active") is False:
        return False
    if event_type == "completed":
        return status == "completed" and bool(context.get("completed_at"))
    if event_type == "assigned":
        return status in {"pending", "started"}
    deadline = _parse_datetime(context.get("deadline"))
    now = _now()
    if deadline:
        now = _compatible_now(deadline, now)
    if event_type == "assignment_reminder":
        assigned_at = _parse_datetime(context.get("assigned_at"))
        if not assigned_at:
            return False
        reminder_now = _compatible_now(assigned_at)
        reminder_at = assigned_at + _assignment_reminder_delay()
        return bool(
            status in {"pending", "started"}
            and reminder_now >= reminder_at
            and (not deadline or deadline > now + _due_soon_window())
        )
    if event_type == "due_soon":
        return bool(
            status in {"pending", "started"}
            and deadline
            and now < deadline <= now + _due_soon_window()
        )
    if event_type == "overdue":
        return bool(
            status == "overdue"
            and deadline
            and deadline < now
            and occurrence_key == _overdue_occurrence_key(deadline, now)
        )
    return False


def enqueue_assignment_notifications(
    assignment_id: str | None,
    event_type: str,
    *,
    occurrence_key: str | None = None,
    connection=None,
) -> int:
    """Queue event emails for learner, HOD/superior, and trainer."""
    if (
        not assignment_id
        or event_type not in COURSE_EVENTS
        or settings.email_delivery_mode == "disabled"
    ):
        return 0
    now = _now().isoformat()
    created = 0
    connection_context = nullcontext(connection) if connection is not None else get_connection()
    with connection_context as active_connection:
        context = _assignment_context(active_connection, assignment_id)
        if not context:
            return 0
        lifecycle = int(context.get("notification_lifecycle") or 1)
        if occurrence_key is None:
            deadline = _parse_datetime(context.get("deadline"))
            if event_type == "overdue" and deadline:
                occurrence_key = _overdue_occurrence_key(deadline)
            else:
                occurrence_key = "once"
        if not _event_is_current(context, event_type, lifecycle, occurrence_key):
            return 0
        for recipient in _recipient_rows(context, event_type):
            subject, body_text, body_html = _message_for(context, event_type, recipient["role"])
            row = active_connection.execute(
                """
                INSERT INTO email_notifications (
                    notification_id, assignment_id, notification_lifecycle, event_type,
                    occurrence_key,
                    recipient_role, recipient_email, recipient_name, subject, body_text, body_html,
                    status, next_attempt_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                ON CONFLICT (
                    assignment_id, notification_lifecycle, event_type,
                    occurrence_key, recipient_role
                )
                DO NOTHING
                RETURNING notification_id
                """,
                (
                    str(uuid.uuid4()),
                    assignment_id,
                    lifecycle,
                    event_type,
                    occurrence_key,
                    recipient["role"],
                    recipient["email"],
                    recipient.get("name"),
                    subject,
                    body_text,
                    body_html,
                    now,
                    now,
                    now,
                ),
            ).fetchone()
            if row:
                created += 1
        if event_type in DIGEST_RECIPIENT_ROLES:
            created += enqueue_digest_notifications(
                assignment_id,
                event_type,
                occurrence_key,
                connection=active_connection,
            )
        if connection is None:
            active_connection.commit()
    return created


def _digest_send_at(
    now: datetime, interval_hours: float, last_sent_at: str | None = None
) -> datetime:
    """Return the next configured local digest time, respecting the delivery interval."""
    try:
        hour, minute = (int(part) for part in settings.email_digest_send_time.split(":", 1))
    except (TypeError, ValueError):
        hour, minute = 9, 0
    timezone = ZoneInfo(settings.email_notification_timezone)
    local_now = (
        now.replace(tzinfo=UTC).astimezone(timezone)
        if now.tzinfo is None
        else now.astimezone(timezone)
    )
    if settings.email_test_mode:
        candidate = local_now + timedelta(minutes=settings.email_test_digest_delay_minutes)
    else:
        candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= local_now:
            candidate += timedelta(days=1)
    last_sent = _parse_datetime(last_sent_at)
    if last_sent is not None:
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=UTC)
        eligible = last_sent.astimezone(timezone) + timedelta(hours=interval_hours)
        if candidate < eligible:
            candidate = eligible
    return candidate.astimezone(UTC).replace(tzinfo=None)


def _digest_recipient(context: dict, role: str, event_type: str) -> dict | None:
    if role == "hod":
        scope_id = context.get("hod_employee_id")
        scope_type = "hod"
        email = context.get("hod_email")
        name = context.get("hod_name")
    else:
        trainer_id = context.get("trainer_id")
        scope_type = "trainer_course" if event_type == "overdue" else "trainer"
        scope_id = (
            f"{trainer_id}:{context.get('course_id')}"
            if scope_type == "trainer_course"
            else trainer_id
        )
        email = context.get("trainer_email")
        name = context.get("trainer_name")
    email = str(email or "").strip()
    if not scope_id or not email or "@" not in email or not _recipient_allowed(email):
        logger.info(
            "course_email_digest_recipient_skipped assignment_id=%s role=%s reason=missing_recipient",
            context.get("assignment_id"),
            role,
        )
        return None
    return {
        "role": role,
        "scope_type": scope_type,
        "scope_id": str(scope_id),
        "email": email,
        "name": name,
    }


def _enqueue_digest_item(
    connection,
    context: dict,
    event_type: str,
    role: str,
    occurrence_key: str,
) -> int:
    recipient = _digest_recipient(context, role, event_type)
    if recipient is None:
        return 0
    lifecycle = int(context.get("notification_lifecycle") or 1)
    prior = connection.execute(
        """
        SELECT 1
        FROM email_notification_items eni
        JOIN email_notifications en ON en.notification_id = eni.notification_id
        WHERE eni.assignment_id = ?
          AND eni.notification_lifecycle = ?
          AND eni.occurrence_key = ?
          AND en.event_type = ?
          AND en.recipient_role = ?
          AND en.digest_scope_type = ?
          AND en.digest_scope_id = ?
          AND en.status <> 'cancelled'
        LIMIT 1
        """,
        (
            context["assignment_id"],
            lifecycle,
            occurrence_key,
            event_type,
            role,
            recipient["scope_type"],
            recipient["scope_id"],
        ),
    ).fetchone()
    if prior:
        return 0

    now = _now()
    interval_hours = (
        _overdue_repeat_interval().total_seconds() / 3600
        if event_type == "overdue"
        else settings.email_completion_digest_interval_hours
        if event_type == "completed"
        else settings.email_due_soon_digest_interval_hours
    )
    last_sent = connection.execute(
        """
        SELECT MAX(sent_at) AS sent_at
        FROM email_notifications
        WHERE message_kind = 'digest'
          AND event_type = ?
          AND recipient_role = ?
          AND digest_scope_type = ?
          AND digest_scope_id = ?
          AND status = 'sent'
        """,
        (event_type, role, recipient["scope_type"], recipient["scope_id"]),
    ).fetchone()
    send_at = _digest_send_at(
        now,
        interval_hours,
        last_sent["sent_at"] if last_sent else None,
    )
    created_at = now.isoformat()
    row = None
    for _attempt in range(2):
        digest_key = ":".join(
            (
                event_type,
                role,
                recipient["scope_type"],
                recipient["scope_id"],
                send_at.isoformat(),
            )
        )
        row = connection.execute(
            """
            INSERT INTO email_notifications (
                notification_id, assignment_id, notification_lifecycle, event_type,
                occurrence_key, recipient_role, recipient_email, recipient_name,
                subject, body_text, body_html, message_kind, digest_key,
                digest_scope_type, digest_scope_id, status, next_attempt_at,
                created_at, updated_at
            ) VALUES (
                ?, NULL, 1, ?, ?, ?, ?, ?, '', '', NULL, 'digest', ?, ?, ?,
                'pending', ?, ?, ?
            )
            ON CONFLICT (digest_key) WHERE digest_key IS NOT NULL DO UPDATE
            SET recipient_email = excluded.recipient_email,
                recipient_name = excluded.recipient_name,
                updated_at = excluded.updated_at
            WHERE email_notifications.status IN ('pending', 'failed')
            RETURNING notification_id
            """,
            (
                str(uuid.uuid4()),
                event_type,
                send_at.date().isoformat(),
                role,
                recipient["email"],
                recipient.get("name"),
                digest_key,
                recipient["scope_type"],
                recipient["scope_id"],
                send_at.isoformat(),
                created_at,
                created_at,
            ),
        ).fetchone()
        if row:
            break
        send_at += timedelta(hours=interval_hours)
    if not row:
        return 0
    inserted = connection.execute(
        """
        INSERT INTO email_notification_items (
            notification_id, assignment_id, notification_lifecycle,
            occurrence_key, created_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        RETURNING assignment_id
        """,
        (row["notification_id"], context["assignment_id"], lifecycle, occurrence_key, created_at),
    ).fetchone()
    return 1 if inserted else 0


def enqueue_digest_notifications(
    assignment_id: str,
    event_type: str,
    occurrence_key: str = "once",
    *,
    connection=None,
) -> int:
    if event_type not in DIGEST_RECIPIENT_ROLES or settings.email_delivery_mode == "disabled":
        return 0
    connection_context = nullcontext(connection) if connection is not None else get_connection()
    created = 0
    with connection_context as active_connection:
        context = _assignment_context(active_connection, assignment_id)
        if not context or not _event_is_current(
            context,
            event_type,
            int(context.get("notification_lifecycle") or 1),
            occurrence_key,
        ):
            return 0
        for role in sorted(DIGEST_RECIPIENT_ROLES[event_type]):
            created += _enqueue_digest_item(
                active_connection,
                context,
                event_type,
                role,
                occurrence_key,
            )
        if connection is None:
            active_connection.commit()
    return created


def cancel_assignment_notifications(
    assignment_id: str | None,
    event_types: Iterable[str] = ("assignment_reminder", "due_soon", "overdue"),
    *,
    connection=None,
) -> int:
    if not assignment_id:
        return 0
    event_types = tuple(event for event in event_types if event in COURSE_EVENTS)
    if not event_types:
        return 0
    placeholders = ", ".join("?" for _ in event_types)
    now = _now().isoformat()
    connection_context = nullcontext(connection) if connection is not None else get_connection()
    with connection_context as active_connection:
        row = active_connection.execute(
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
        if connection is None:
            active_connection.commit()
    return len(row)


def migrate_pending_digest_notifications() -> int:
    """Convert pre-digest HOD/trainer outbox rows without resending history."""
    if settings.email_delivery_mode == "disabled":
        return 0
    migrated = 0
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT assignment_id, event_type, occurrence_key
            FROM email_notifications
            WHERE message_kind = 'individual'
              AND recipient_role IN ('hod', 'trainer')
              AND event_type IN ('due_soon', 'completed', 'overdue')
              AND status IN ('pending', 'failed')
              AND assignment_id IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            migrated += enqueue_digest_notifications(
                row["assignment_id"],
                row["event_type"],
                row["occurrence_key"] or "once",
                connection=connection,
            )
        connection.execute(
            """
            UPDATE email_notifications
            SET status = 'cancelled', updated_at = ?
            WHERE message_kind = 'individual'
              AND recipient_role IN ('hod', 'trainer')
              AND event_type IN ('due_soon', 'completed', 'overdue')
              AND status IN ('pending', 'failed')
            """,
            (_now().isoformat(),),
        )
        connection.commit()
    return migrated


def enqueue_assignment_reminders(as_of: datetime | None = None) -> int:
    if settings.email_delivery_mode == "disabled":
        return 0
    now = as_of or _now()
    assigned_before = now - _assignment_reminder_delay()
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
              AND ca.assigned_at <= ?
              AND ca.deadline > ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM email_notifications en
                  WHERE en.assignment_id = ca.assignment_id
                    AND en.event_type = 'assignment_reminder'
                    AND en.status = 'sent'
              )
            """,
            (
                assigned_before.isoformat(),
                (now + _due_soon_window()).isoformat(),
            ),
        ).fetchall()
    for row in rows:
        queued += enqueue_assignment_notifications(
            row["assignment_id"],
            "assignment_reminder",
        )
    return queued


def enqueue_due_soon_notifications(as_of: datetime | None = None) -> int:
    if settings.email_delivery_mode == "disabled":
        return 0
    now = as_of or _now()
    threshold = now + _due_soon_window()
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
            RETURNING ca.assignment_id, ca.deadline
            """,
            (now.isoformat(), now.isoformat()),
        ).fetchall()
        for row in rows:
            queued += enqueue_assignment_notifications(
                row["assignment_id"],
                "overdue",
                occurrence_key=_overdue_occurrence_key(
                    _parse_datetime(row["deadline"]) or now,
                    now,
                ),
                connection=connection,
            )
        connection.commit()

    # Reconciliation makes the scheduler self-healing if an older deployment
    # changed an assignment to overdue without creating its outbox rows.
    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT ca.assignment_id, ca.deadline
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
    for row in existing:
        deadline = _parse_datetime(row["deadline"])
        if deadline:
            queued += enqueue_assignment_notifications(
                row["assignment_id"],
                "overdue",
                occurrence_key=_overdue_occurrence_key(deadline, now),
            )
    return queued


def _send_smtp(notification: dict) -> None:
    if not _recipient_allowed(notification.get("recipient_email")):
        raise RuntimeError("Recipient is not included in EMAIL_RECIPIENT_ALLOWLIST")
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    from_email = settings.email_from_email or settings.smtp_username
    if not from_email:
        raise RuntimeError("EMAIL_FROM_EMAIL is not configured")

    message = EmailMessage()
    message["From"] = formataddr((settings.email_from_name, from_email))
    message["To"] = formataddr(
        (notification.get("recipient_name") or "", notification["recipient_email"])
    )
    message["Subject"] = notification["subject"]
    sender_domain = from_email.rsplit("@", 1)[-1]
    message["Message-ID"] = f"<{notification['notification_id']}@{sender_domain}>"
    message.set_content(notification["body_text"])
    if notification.get("body_html"):
        message.add_alternative(notification["body_html"], subtype="html")

    if settings.smtp_use_ssl:
        client_factory = smtplib.SMTP_SSL
    else:
        client_factory = smtplib.SMTP
    with client_factory(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as smtp:
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
    now_dt = _now()
    now = now_dt.isoformat()
    stale_before = (now_dt - timedelta(seconds=settings.email_lock_timeout_seconds)).isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            """
            WITH picked AS (
                SELECT notification_id
                FROM email_notifications
                WHERE (
                    status IN ('pending', 'failed')
                    OR (status = 'sending' AND locked_at <= ?)
                  )
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
            (stale_before, now, settings.email_max_attempts, limit, now, now),
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


def _digest_contexts(connection, notification: dict) -> list[dict]:
    items = connection.execute(
        """
        SELECT assignment_id, notification_lifecycle, occurrence_key
        FROM email_notification_items
        WHERE notification_id = ?
        ORDER BY created_at, assignment_id
        """,
        (notification["notification_id"],),
    ).fetchall()
    contexts = []
    for item in items:
        context = _assignment_context(connection, item["assignment_id"])
        if not context or not _event_is_current(
            context,
            notification["event_type"],
            int(item["notification_lifecycle"]),
            item["occurrence_key"],
        ):
            continue
        recipient = _digest_recipient(
            context,
            notification["recipient_role"],
            notification["event_type"],
        )
        if not recipient:
            continue
        if (
            recipient["email"].lower() != str(notification["recipient_email"]).lower()
            or recipient["scope_type"] != notification.get("digest_scope_type")
            or recipient["scope_id"] != notification.get("digest_scope_id")
        ):
            continue
        contexts.append(context)
    if notification["event_type"] == "overdue":
        contexts.sort(
            key=lambda item: (item.get("deadline") or "", item.get("employee_name") or "")
        )
    elif notification["event_type"] == "due_soon":
        contexts.sort(
            key=lambda item: (item.get("deadline") or "", item.get("employee_name") or "")
        )
    else:
        contexts.sort(
            key=lambda item: (item.get("completed_at") or "", item.get("employee_name") or "")
        )
    return contexts


def _digest_summary(connection, notification: dict) -> dict[str, int]:
    scope_type = notification.get("digest_scope_type")
    scope_id = notification.get("digest_scope_id")
    scope_sql = ""
    params: list[object] = []
    if scope_type == "hod":
        scope_sql = "AND e.manager_employee_id = ?"
        params.append(scope_id)
    elif scope_type == "trainer_course":
        trainer_id, _, course_id = str(scope_id or "").partition(":")
        scope_sql = "AND c.trainer_id = ? AND ca.course_id = ?"
        params.extend((trainer_id, course_id))
    else:
        scope_sql = "AND c.trainer_id = ?"
        params.append(scope_id)
    now = _now().isoformat()
    count_expression = (
        "COUNT(DISTINCT e.employee_id)"
        if notification.get("recipient_role") == "trainer"
        else "COUNT(*)"
    )
    completed_expression = (
        "COUNT(DISTINCT e.employee_id) FILTER (WHERE ca.status = 'completed')"
        if notification.get("recipient_role") == "trainer"
        else "COUNT(*) FILTER (WHERE ca.status = 'completed')"
    )
    overdue_expression = (
        "COUNT(DISTINCT e.employee_id) FILTER (WHERE ca.status = 'overdue' OR (ca.status IN ('pending', 'started') AND ca.deadline < ?))"
        if notification.get("recipient_role") == "trainer"
        else "COUNT(*) FILTER (WHERE ca.status = 'overdue' OR (ca.status IN ('pending', 'started') AND ca.deadline < ?))"
    )
    row = connection.execute(
        f"""
        SELECT
            {count_expression} AS assigned_count,
            {completed_expression} AS completed_count,
            {overdue_expression} AS overdue_count
        FROM course_assignments ca
        JOIN courses c ON c.course_id = ca.course_id
        JOIN assignment_rules ar ON ar.course_id = ca.course_id
        JOIN employees e ON e.employee_id = ca.employee_id
        WHERE ca.status <> 'revoked'
          AND c.status = 'published'
          AND ar.is_active = TRUE
          {scope_sql}
        """,  # nosec B608 -- scope_sql is selected only from constants above
        (now, *params),
    ).fetchone()
    assigned = int(row["assigned_count"] or 0) if row else 0
    completed = int(row["completed_count"] or 0) if row else 0
    overdue = int(row["overdue_count"] or 0) if row else 0
    return {
        "assigned_count": assigned,
        "completed_count": completed,
        "overdue_count": overdue,
        "completion_rate": round((completed / assigned) * 100) if assigned else 0,
        "overdue_rate": round((overdue / assigned) * 100) if assigned else 0,
    }


def process_pending_notifications(limit: int | None = None) -> int:
    if settings.email_delivery_mode == "disabled":
        return 0
    processed = 0
    for notification in _claim_pending_notifications(limit or settings.email_worker_batch_size):
        if not _recipient_allowed(notification.get("recipient_email")):
            logger.warning(
                "course_email_cancelled_not_allowlisted notification_id=%s role=%s to=%s",
                notification["notification_id"],
                notification["recipient_role"],
                notification["recipient_email"],
            )
            _cancel_stale(notification["notification_id"])
            continue
        notification["subject"] = _email_subject(notification["subject"])
        if notification.get("message_kind") == "digest":
            with get_connection() as connection:
                contexts = _digest_contexts(connection, notification)
                summary = _digest_summary(connection, notification)
            if not contexts:
                logger.info(
                    "course_email_digest_cancelled_empty notification_id=%s event=%s role=%s",
                    notification["notification_id"],
                    notification["event_type"],
                    notification["recipient_role"],
                )
                _cancel_stale(notification["notification_id"])
                continue
            subject, body_text, body_html = render_digest(
                notification["event_type"],
                notification["recipient_role"],
                contexts,
                summary,
            )
            notification.update(
                subject=_email_subject(subject),
                body_text=body_text,
                body_html=body_html,
            )
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
                "course_email_sent notification_id=%s event=%s role=%s to=%s items=%s",
                notification["notification_id"],
                notification["event_type"],
                notification["recipient_role"],
                notification["recipient_email"],
                len(contexts),
            )
            processed += 1
            continue
        with get_connection() as connection:
            context = _assignment_context(connection, notification["assignment_id"])
        if (
            notification["recipient_role"]
            not in EVENT_RECIPIENT_ROLES.get(notification["event_type"], set())
            or not context
            or not _event_is_current(
                context,
                notification["event_type"],
                int(notification["notification_lifecycle"]),
                notification.get("occurrence_key") or "once",
            )
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
    with advisory_lock("email-notification-cycle"):
        migrated = migrate_pending_digest_notifications()
        overdue = enqueue_overdue_notifications()
        assignment_reminder = enqueue_assignment_reminders()
        due_soon = enqueue_due_soon_notifications()
        sent = process_pending_notifications()
        return {
            "assignment_reminder": assignment_reminder,
            "due_soon": due_soon,
            "overdue": overdue,
            "migrated": migrated,
            "sent": sent,
        }


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
    if settings.email_test_mode:
        logger.warning(
            "course_email_test_mode_enabled reminder_minutes=%s due_soon_minutes=%s "
            "overdue_repeat_minutes=%s digest_delay_minutes=%s allowlisted_recipients=%s",
            settings.email_test_assignment_reminder_minutes,
            settings.email_test_due_soon_window_minutes,
            settings.email_test_overdue_repeat_minutes,
            settings.email_test_digest_delay_minutes,
            len(settings.email_recipient_allowlist),
        )
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
