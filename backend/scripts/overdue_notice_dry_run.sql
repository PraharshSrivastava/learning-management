-- Read-only preview of what the overdue email cap will do, before email is enabled.
-- Lists every currently overdue assignment, how many overdue notices it has already
-- been issued in its current deadline cycle (same counting as the application), and
-- what happens next. Assumes EMAIL_OVERDUE_MAX_NOTICES=5; change the 5s below if not.
--
--   psql "$DATABASE_URL" -f backend/scripts/overdue_notice_dry_run.sql

WITH issued AS (
    SELECT assignment_id, notification_lifecycle, occurrence_key
    FROM email_notifications
    WHERE event_type = 'overdue' AND status <> 'cancelled' AND assignment_id IS NOT NULL
    UNION
    SELECT eni.assignment_id, eni.notification_lifecycle, eni.occurrence_key
    FROM email_notification_items eni
    JOIN email_notifications en ON en.notification_id = eni.notification_id
    WHERE en.event_type = 'overdue' AND en.status <> 'cancelled'
),
issued_counts AS (
    SELECT assignment_id, notification_lifecycle, COUNT(*) AS notices_issued
    FROM issued
    GROUP BY assignment_id, notification_lifecycle
),
employee_sent AS (
    SELECT assignment_id, COUNT(*) AS employee_emails_sent_all_time
    FROM email_notifications
    WHERE event_type = 'overdue' AND recipient_role = 'employee' AND status = 'sent'
    GROUP BY assignment_id
)
SELECT
    e.name AS employee,
    e.email AS employee_email,
    c.course_name AS course,
    ca.deadline,
    COALESCE(ic.notices_issued, 0) AS notices_issued_this_deadline,
    COALESCE(es.employee_emails_sent_all_time, 0) AS employee_emails_sent_all_time,
    CASE
        WHEN COALESCE(ic.notices_issued, 0) >= 5 THEN 'No more overdue emails'
        WHEN COALESCE(ic.notices_issued, 0) = 4 THEN 'Next: escalation notice (final email)'
        ELSE 'Next: reminder ' || (COALESCE(ic.notices_issued, 0) + 1) || ' of 4'
    END AS next_overdue_email
FROM course_assignments ca
JOIN courses c ON c.course_id = ca.course_id
JOIN assignment_rules ar ON ar.course_id = ca.course_id
JOIN employees e ON e.employee_id = ca.employee_id
LEFT JOIN issued_counts ic
  ON ic.assignment_id = ca.assignment_id
 AND ic.notification_lifecycle = ca.notification_lifecycle
LEFT JOIN employee_sent es ON es.assignment_id = ca.assignment_id
WHERE ca.revoked_at IS NULL
  AND c.status = 'published'
  AND ar.is_active = TRUE
  AND ca.status IN ('pending', 'started', 'overdue')
  AND ca.deadline < to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS')
ORDER BY notices_issued_this_deadline DESC, employee, course;
