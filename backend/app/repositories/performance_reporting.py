"""Set-based reads for trainer performance reports."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.settings import settings
from app.repositories.database import get_connection


def _assignment_scope(
    trainer_id: str,
    *,
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> tuple[str, list[object]]:
    conditions = [
        "c.trainer_id = ?",
        "c.status = 'published'",
        "ca.status <> 'revoked'",
        "ar.published_at IS NOT NULL",
        "ar.is_active = TRUE",
    ]
    params: list[object] = [trainer_id]
    if course_id:
        conditions.append("ca.course_id = ?")
        params.append(course_id)
    if employee_id:
        conditions.append("ca.employee_id = ?")
        params.append(employee_id)
    if department:
        conditions.append("e.department = ?")
        params.append(department)
    if mailing_list:
        conditions.append(
            "EXISTS (SELECT 1 FROM employee_groups eg WHERE eg.employee_id = e.employee_id AND eg.group_cn = ?)"
        )
        params.append(mailing_list)
    if joined_less_than_days_ago is not None:
        conditions.append(
            "e.join_date IS NOT NULL AND e.join_date::date > CURRENT_DATE - ?::integer"
        )
        params.append(joined_less_than_days_ago)
    return " AND ".join(conditions), params


def _assignment_summary_query(where: str) -> str:
    # SQL structure is fixed here; all user-supplied values are bound parameters.
    return f"""
        SELECT ca.assignment_id, ca.course_id, ca.employee_id, ca.status,
               ca.assigned_at, ca.deadline, ca.started_at, ca.completed_at,
               ca.last_learner_activity_at,
               e.name AS employee_name, e.department, e.status AS employee_status,
               c.course_name,
               ARRAY(SELECT eg.group_cn FROM employee_groups eg WHERE eg.employee_id = e.employee_id AND eg.group_cn IS NOT NULL ORDER BY eg.group_cn) AS mailing_lists,
               COUNT(cm.module_id) AS total_modules,
               COUNT(cm.module_id) FILTER (
                   WHERE mp.video_watched = TRUE
                   AND (cm.num_questions = 0 OR mp.quiz_passed = TRUE)
               ) AS completed_modules,
               COALESCE(SUM(mp.attempt_count), 0) AS total_attempts,
               AVG(mp.quiz_score) FILTER (WHERE mp.attempt_count > 0) AS average_score,
               COUNT(mp.quiz_score) FILTER (WHERE mp.attempt_count > 0) AS scored_modules,
               COALESCE(ev.failed_attempts, 0) AS failed_attempts
        FROM course_assignments ca
        JOIN courses c ON c.course_id = ca.course_id
        JOIN employees e ON e.employee_id = ca.employee_id
        JOIN assignment_rules ar ON ar.course_id = ca.course_id
        LEFT JOIN course_modules cm ON cm.course_id = c.course_id
        LEFT JOIN module_progress mp ON mp.assignment_id = ca.assignment_id AND mp.module_id = cm.module_id
        LEFT JOIN (
            SELECT assignment_id, COUNT(*) FILTER (WHERE passed = FALSE) AS failed_attempts
            FROM learning_events WHERE event_type = 'quiz_attempt'
            GROUP BY assignment_id
        ) ev ON ev.assignment_id = ca.assignment_id
        WHERE {where}
        GROUP BY ca.assignment_id, e.employee_id, c.course_id, ev.failed_attempts
    """  # nosec B608


def list_assignment_summaries(
    trainer_id: str,
    *,
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> list[dict]:
    where, params = _assignment_scope(
        trainer_id,
        course_id=course_id,
        employee_id=employee_id,
        department=department,
        mailing_list=mailing_list,
        joined_less_than_days_ago=joined_less_than_days_ago,
    )
    with get_connection() as connection:
        return [
            dict(row)
            for row in connection.execute(_assignment_summary_query(where), params).fetchall()
        ]


def assignment_page(
    trainer_id: str,
    *,
    status: str | None,
    search: str | None,
    sort: str,
    descending: bool,
    page: int,
    page_size: int,
    now: datetime,
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> tuple[int, list[dict]]:
    """Filter, count, sort and limit in PostgreSQL; return only the requested page."""
    where, scope_params = _assignment_scope(
        trainer_id,
        course_id=course_id,
        employee_id=employee_id,
        department=department,
        mailing_list=mailing_list,
        joined_less_than_days_ago=joined_less_than_days_ago,
    )
    filters = []
    filter_params: list[object] = []
    status_column = {
        "due_soon": "due_soon",
        "inactive": "inactive",
        "repeated_failures": "repeated_failures",
    }.get(status or "")
    if status_column:
        filters.append(status_column)
    elif status and status != "assigned":
        filters.append("report_status = ?")
        filter_params.append(status)
    if search and search.strip():
        filters.append(
            "(strpos(lower(employee_name), lower(?)) > 0 "
            "OR strpos(lower(course_name), lower(?)) > 0 "
            "OR strpos(lower(employee_id), lower(?)) > 0)"
        )
        filter_params.extend([search.strip()] * 3)
    filtered_where = " AND ".join(filters) if filters else "TRUE"
    sort_column = {
        "employee": "lower(employee_name)",
        "course": "lower(course_name)",
        "deadline": "COALESCE(deadline, '9999')",
        "progress": "completion_percent",
        "score": "COALESCE(score_percent, -1)",
        "last_activity": "COALESCE(last_learner_activity_at, '')",
        "status": "report_status",
    }[sort]
    direction = "DESC" if descending else "ASC"
    query = f"""
        WITH clock AS (
            SELECT ?::timestamp AS current_time, ?::timestamp AS due_end,
                   ?::timestamp AS inactive_cutoff
        ), summary AS (
            {_assignment_summary_query(where)}
        ), decorated AS (
            SELECT summary.*,
                   CASE WHEN status = 'completed' THEN 'completed'
                        WHEN deadline::timestamp < clock.current_time THEN 'overdue'
                        WHEN status = 'started' OR started_at IS NOT NULL THEN 'started'
                        ELSE 'pending' END AS report_status,
                   status <> 'completed' AND deadline::timestamp > clock.current_time
                       AND deadline::timestamp <= clock.due_end AS due_soon,
                   status <> 'completed' AND (
                       last_learner_activity_at::timestamp < clock.inactive_cutoff
                       OR (last_learner_activity_at IS NULL AND started_at IS NULL
                           AND assigned_at::timestamp < clock.inactive_cutoff)
                   ) AS inactive,
                   status <> 'completed' AND failed_attempts >= ? AS repeated_failures,
                   CASE WHEN total_modules > 0
                        THEN ROUND(100.0 * completed_modules / total_modules)
                        ELSE 0 END AS completion_percent,
                   CASE WHEN average_score <= 1 THEN ROUND((average_score * 100)::numeric, 1)
                        ELSE ROUND(average_score::numeric, 1) END AS score_percent
            FROM summary CROSS JOIN clock
        ), filtered AS (
            SELECT * FROM decorated WHERE {filtered_where}
        )
        SELECT (SELECT COUNT(*) FROM filtered) AS report_total, page_rows.*
        FROM (SELECT 1) anchor
        LEFT JOIN LATERAL (
            SELECT * FROM filtered
            ORDER BY {sort_column} {direction}, assignment_id {direction}
            LIMIT ? OFFSET ?
        ) page_rows ON TRUE
    """  # nosec B608
    params = [
        now.isoformat(),
        (now + timedelta(days=settings.email_due_soon_days)).isoformat(),
        (now - timedelta(days=14)).isoformat(),
        *scope_params,
        2,
        *filter_params,
        page_size,
        (page - 1) * page_size,
    ]
    with get_connection() as connection:
        rows = [dict(row) for row in connection.execute(query, params).fetchall()]
    return int(rows[0]["report_total"]), [
        {key: value for key, value in row.items() if key != "report_total"}
        for row in rows
        if row["assignment_id"] is not None
    ]


def list_scope_options(trainer_id: str) -> dict:
    with get_connection() as connection:
        courses = connection.execute(
            """
            SELECT DISTINCT c.course_id, c.course_name
            FROM courses c JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE c.trainer_id = ? AND c.status = 'published'
              AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
            ORDER BY c.course_name
            """,
            (trainer_id,),
        ).fetchall()
        employees = connection.execute(
            """
            SELECT DISTINCT e.employee_id, e.name, e.department
            FROM employees e
            JOIN course_assignments ca ON ca.employee_id = e.employee_id
            JOIN courses c ON c.course_id = ca.course_id
            JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE c.trainer_id = ? AND c.status = 'published' AND ca.status <> 'revoked'
              AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
            ORDER BY e.name
            """,
            (trainer_id,),
        ).fetchall()
        groups = connection.execute(
            """
            SELECT DISTINCT eg.group_cn
            FROM employee_groups eg
            JOIN course_assignments ca ON ca.employee_id = eg.employee_id
            JOIN courses c ON c.course_id = ca.course_id
            JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE c.trainer_id = ? AND c.status = 'published' AND ca.status <> 'revoked'
              AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
              AND eg.group_cn IS NOT NULL
            ORDER BY eg.group_cn
            """,
            (trainer_id,),
        ).fetchall()
    return {
        "courses": [dict(row) for row in courses],
        "employees": [dict(row) for row in employees],
        "departments": sorted({row["department"] for row in employees if row["department"]}),
        "mailing_lists": [row["group_cn"] for row in groups],
    }


def get_assignment_detail(trainer_id: str, assignment_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT ca.*, e.name AS employee_name, e.department, e.status AS employee_status,
                   c.course_name
            FROM course_assignments ca
            JOIN courses c ON c.course_id = ca.course_id
            JOIN employees e ON e.employee_id = ca.employee_id
            JOIN assignment_rules ar ON ar.course_id = ca.course_id
            WHERE ca.assignment_id = ? AND c.trainer_id = ? AND c.status = 'published'
              AND ca.status <> 'revoked' AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
            """,
            (assignment_id, trainer_id),
        ).fetchone()
        if not row:
            return None
        modules = connection.execute(
            """
            SELECT cm.module_id, cm.module_number, cm.title, cm.num_questions,
                   COALESCE(mp.video_watched, FALSE) AS video_watched,
                   COALESCE(mp.quiz_passed, FALSE) AS quiz_passed,
                   mp.quiz_score AS latest_score,
                   COALESCE(mp.attempt_count, 0) AS attempt_count,
                   mp.last_attempt_at
            FROM course_modules cm
            LEFT JOIN module_progress mp ON mp.module_id = cm.module_id AND mp.assignment_id = ?
            WHERE cm.course_id = ? ORDER BY cm.module_number
            """,
            (assignment_id, row["course_id"]),
        ).fetchall()
        attempts = connection.execute(
            """
            SELECT module_id, occurred_at, score, passed
            FROM learning_events
            WHERE assignment_id = ? AND event_type = 'quiz_attempt'
            ORDER BY occurred_at DESC
            """,
            (assignment_id,),
        ).fetchall()
    return {
        "assignment": dict(row),
        "modules": [dict(item) for item in modules],
        "attempts": [dict(item) for item in attempts],
    }


def course_module_summary(
    trainer_id: str,
    course_id: str,
    *,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> list[dict]:
    conditions = [
        "c.course_id = ?",
        "c.trainer_id = ?",
        "c.status = 'published'",
        "ar.published_at IS NOT NULL",
        "ar.is_active = TRUE",
    ]
    params: list[object] = [course_id, trainer_id]
    if employee_id:
        conditions.append("e.employee_id = ?")
        params.append(employee_id)
    if department:
        conditions.append("e.department = ?")
        params.append(department)
    if mailing_list:
        conditions.append(
            "EXISTS (SELECT 1 FROM employee_groups eg WHERE eg.employee_id = e.employee_id AND eg.group_cn = ?)"
        )
        params.append(mailing_list)
    if joined_less_than_days_ago is not None:
        conditions.append(
            "e.join_date IS NOT NULL AND e.join_date::date > CURRENT_DATE - ?::integer"
        )
        params.append(joined_less_than_days_ago)
    where = " AND ".join(conditions)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT cm.module_id, cm.module_number, cm.title, cm.num_questions,
                   COUNT(ca.assignment_id) AS assigned,
                   COUNT(mp.assignment_id) FILTER (WHERE mp.video_watched = TRUE) AS watched,
                   COUNT(mp.assignment_id) FILTER (WHERE mp.quiz_passed = TRUE) AS passed,
                   COALESCE(SUM(mp.attempt_count), 0) AS attempts,
                   AVG(mp.quiz_score) FILTER (WHERE mp.attempt_count > 0) AS average_score
            FROM course_modules cm
            JOIN courses c ON c.course_id = cm.course_id
            JOIN assignment_rules ar ON ar.course_id = c.course_id
            JOIN course_assignments ca ON ca.course_id = c.course_id AND ca.status <> 'revoked'
            JOIN employees e ON e.employee_id = ca.employee_id
            LEFT JOIN module_progress mp ON mp.assignment_id = ca.assignment_id AND mp.module_id = cm.module_id
            WHERE {where}
            GROUP BY cm.module_id
            ORDER BY cm.module_number
            """,  # nosec B608
            params,
        ).fetchall()
    return [dict(row) for row in rows]
