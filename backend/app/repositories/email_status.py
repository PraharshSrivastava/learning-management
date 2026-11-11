"""Reads for the Email status report: one consistent snapshot of a course's assignment emails."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.settings import settings
from app.repositories.database import get_connection
from app.repositories.performance_reporting import _assignment_scope, _decorated_assignments
from app.schemas.reporting_scope import TrainerReportScope

ATTEMPT_FACTS = """
    SELECT COUNT(*) FILTER (
               WHERE a.result <> 'abandoned'
               AND (n.resent_at IS NULL OR a.started_at >= n.resent_at)
           ) AS real_attempts,
           (ARRAY_AGG(a.result ORDER BY a.started_at DESC))[1] AS last_result,
           (ARRAY_AGG(a.smtp_code ORDER BY a.started_at DESC))[1] AS smtp_code,
           (ARRAY_AGG(a.smtp_response ORDER BY a.started_at DESC))[1] AS smtp_response,
           COALESCE(BOOL_OR(a.result = 'started'), FALSE) AS has_unfinished
    FROM email_delivery_attempts a
    WHERE a.notification_id = n.notification_id
"""


def course_snapshot(
    scope: TrainerReportScope,
    *,
    course_id: str,
    now: datetime,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> dict:
    """Assignment rows, course and worker status, all read in a single transaction."""
    where, scope_params = _assignment_scope(
        scope,
        course_id=course_id,
        department=department,
        mailing_list=mailing_list,
        joined_less_than_days_ago=joined_less_than_days_ago,
    )
    query = f"""
        {_decorated_assignments(where)}
        SELECT d.assignment_id, d.employee_id, d.employee_name, d.department, d.status,
               d.started_at, d.completed_at, d.revoked_at, d.completed_modules,
               d.completion_percent,
               ca.notification_lifecycle AS assignment_lifecycle,
               emp.email AS employee_email,
               n.notification_id, n.status AS email_status, n.attempts AS claim_attempts,
               n.next_attempt_at, n.locked_at, n.sent_at, n.updated_at AS email_updated_at,
               n.last_error, n.cancel_reason, n.recipient_email,
               n.notification_lifecycle AS email_lifecycle,
               skip.reason AS skip_reason, skip.created_at AS skip_at,
               facts.real_attempts, facts.last_result, facts.smtp_code, facts.smtp_response,
               facts.has_unfinished
        FROM decorated d
        JOIN course_assignments ca ON ca.assignment_id = d.assignment_id
        JOIN employees emp ON emp.employee_id = d.employee_id
        LEFT JOIN LATERAL (
            SELECT * FROM email_notifications en
            WHERE en.assignment_id = d.assignment_id
              AND en.event_type = 'assigned' AND en.recipient_role = 'employee'
            ORDER BY en.created_at DESC LIMIT 1
        ) n ON TRUE
        LEFT JOIN LATERAL (
            SELECT s.reason, s.created_at FROM email_notification_skips s
            WHERE s.assignment_id = d.assignment_id
              AND s.event_type = 'assigned' AND s.recipient_role = 'employee'
            ORDER BY s.notification_lifecycle DESC LIMIT 1
        ) skip ON TRUE
        LEFT JOIN LATERAL ({ATTEMPT_FACTS}) facts ON TRUE
    """  # nosec B608
    params = [
        now.isoformat(),
        (now + timedelta(days=settings.email_due_soon_days)).isoformat(),
        (now - timedelta(days=14)).isoformat(),
        *scope_params,
        2,
    ]
    with get_connection() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        rows = [dict(row) for row in connection.execute(query, params).fetchall()]
        course = connection.execute(
            "SELECT course_name, trainer_id FROM courses WHERE course_id = ?", (course_id,)
        ).fetchone()
        worker = connection.execute("SELECT * FROM email_worker_status WHERE id = 1").fetchone()
    return {
        "rows": rows,
        "course": dict(course) if course else None,
        "worker": dict(worker) if worker else None,
    }


def lock_notification_facts(connection, notification_id: str) -> dict | None:
    """Lock one assignment email and read what is recorded about it, for a resend."""
    row = connection.execute(
        f"""
        SELECT n.notification_id, n.assignment_id, n.event_type, n.recipient_role,
               n.status AS email_status, n.attempts AS claim_attempts, n.next_attempt_at,
               n.locked_at, n.last_error, n.cancel_reason, ca.course_id,
               facts.real_attempts, facts.last_result, facts.smtp_code, facts.smtp_response,
               facts.has_unfinished
        FROM email_notifications n
        JOIN course_assignments ca ON ca.assignment_id = n.assignment_id
        LEFT JOIN LATERAL ({ATTEMPT_FACTS}) facts ON TRUE
        WHERE n.notification_id = ?
        FOR UPDATE OF n
        """,  # nosec B608
        (notification_id,),
    ).fetchone()
    return dict(row) if row else None


def reset_for_resend(
    connection,
    notification_id: str,
    *,
    expected_status: str,
    recipient_email: str,
    recipient_name: str | None,
    lifecycle: int,
    trainer_id: str,
    now: str,
) -> bool:
    """Put one email back in the queue. False if its status changed in the meantime."""
    connection.execute(
        """
        UPDATE email_delivery_attempts
        SET result = 'abandoned', finished_at = ?
        WHERE notification_id = ? AND result = 'started'
        """,
        (now, notification_id),
    )
    row = connection.execute(
        """
        UPDATE email_notifications
        SET status = 'pending', attempts = 0, next_attempt_at = ?, locked_at = NULL,
            last_error = NULL, cancel_reason = NULL, recipient_email = ?, recipient_name = ?,
            notification_lifecycle = ?, resent_by = ?, resent_at = ?, updated_at = ?
        WHERE notification_id = ? AND status = ?
        RETURNING notification_id
        """,
        (
            now,
            recipient_email,
            recipient_name,
            lifecycle,
            trainer_id,
            now,
            now,
            notification_id,
            expected_status,
        ),
    ).fetchone()
    return row is not None
