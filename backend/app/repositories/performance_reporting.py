"""Set-based reads for trainer performance reports."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.settings import settings
from app.repositories.database import get_connection
from app.schemas.reporting_scope import TrainerReportScope, owner_filter


def _assignment_scope(
    trainer_id: TrainerReportScope,
    *,
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> tuple[str, list[object]]:
    owner_sql, owner_params = owner_filter(trainer_id)
    conditions = [
        "c.status = 'published'",
        "ca.status <> 'revoked'",
        "ar.published_at IS NOT NULL",
        "ar.is_active = TRUE",
    ]
    params: list[object] = list(owner_params)
    if owner_sql:
        conditions.insert(0, "c.trainer_id = ?")
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
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (WHERE passed = FALSE) AS failed_attempts
            FROM learning_events
            WHERE assignment_id = ca.assignment_id AND event_type = 'quiz_attempt'
        ) ev ON TRUE
        LEFT JOIN course_modules cm ON cm.course_id = c.course_id
        LEFT JOIN module_progress mp ON mp.assignment_id = ca.assignment_id AND mp.module_id = cm.module_id
        WHERE {where}
        GROUP BY ca.assignment_id, e.employee_id, c.course_id, ev.failed_attempts
    """  # nosec B608


def list_assignment_summaries(
    trainer_id: TrainerReportScope,
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


def _decorated_assignments(where: str) -> str:
    """Shared assignment flags and scores for assignment and employee reports."""
    return f"""
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
        )
    """  # nosec B608


def assignment_page(
    trainer_id: TrainerReportScope,
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
        {_decorated_assignments(where)}, filtered AS (
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


def employee_page(
    trainer_id: TrainerReportScope,
    *,
    search: str | None,
    attention: str | None,
    sort: str,
    descending: bool,
    page: int,
    page_size: int,
    now: datetime,
    **scope: object,
) -> tuple[dict, list[dict]]:
    """Aggregate full scoped course totals in SQL, returning only one employee page."""
    where, scope_params = _assignment_scope(trainer_id, **scope)
    filters = []
    filter_params: list[object] = []
    if search and search.strip():
        filters.append(
            "(strpos(lower(employee_name), lower(?)) > 0 "
            "OR strpos(lower(employee_id), lower(?)) > 0)"
        )
        filter_params.extend([search.strip()] * 2)
    if attention == "needs_attention":
        filters.append("needs_attention")
    elif attention == "overdue":
        filters.append("overdue > 0")
    elif attention == "completed":
        filters.append("completed = assigned")
    filtered_where = " AND ".join(filters) if filters else "TRUE"
    sort_column = {
        "employee": "lower(employee_name)",
        "assigned": "assigned",
        "completion": "completion_rate",
        "overdue": "overdue",
        "score": "COALESCE(average_score, -1)",
    }[sort]
    direction = "DESC" if descending else "ASC"
    query = f"""
        {_decorated_assignments(where)}, employees AS (
            SELECT employee_id, MAX(employee_name) AS employee_name,
                   MAX(employee_status) AS employee_status, MAX(department) AS department,
                   COUNT(*) AS assigned,
                   COUNT(*) FILTER (WHERE report_status = 'completed') AS completed,
                   COUNT(*) FILTER (WHERE report_status <> 'completed'
                       AND (started_at IS NOT NULL OR completed_modules > 0 OR status = 'started'))
                       AS in_progress,
                   COUNT(*) FILTER (WHERE report_status <> 'completed'
                       AND started_at IS NULL AND completed_modules = 0 AND status <> 'started')
                       AS not_started,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE report_status = 'completed') / COUNT(*), 1)
                       AS completion_rate,
                   COUNT(*) FILTER (WHERE report_status = 'overdue') AS overdue,
                   COUNT(*) FILTER (WHERE due_soon) AS due_soon,
                   COUNT(*) FILTER (WHERE inactive) AS inactive,
                   COUNT(*) FILTER (WHERE repeated_failures) AS repeated_failures,
                   ROUND(SUM(score_percent * scored_modules) /
                       NULLIF(SUM(scored_modules) FILTER (WHERE score_percent IS NOT NULL), 0), 1)
                       AS average_score,
                   COALESCE(SUM(scored_modules) FILTER (WHERE score_percent IS NOT NULL), 0)
                       AS scored_modules,
                   (ARRAY_AGG(last_learner_activity_at
                       ORDER BY last_learner_activity_at::timestamp DESC NULLS LAST))[1]
                       AS last_learner_activity_at,
                   BOOL_OR(COALESCE(report_status = 'overdue' OR due_soon OR inactive
                       OR repeated_failures, FALSE)) AS needs_attention
            FROM decorated GROUP BY employee_id
        ), filtered AS (
            SELECT * FROM employees WHERE {filtered_where}
        ), totals AS (
            SELECT COUNT(*) AS summary_employees,
                   COALESCE(SUM(assigned), 0) AS summary_assigned,
                   COALESCE(SUM(completed), 0) AS summary_completed,
                   COALESCE(SUM(overdue), 0) AS summary_overdue
            FROM filtered
        )
        SELECT totals.*, page_rows.*
        FROM totals LEFT JOIN LATERAL (
            SELECT * FROM filtered
            ORDER BY {sort_column} {direction}, employee_id {direction}
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
    summary = {
        key: int(rows[0][f"summary_{key}"])
        for key in ("employees", "assigned", "completed", "overdue")
    }
    employees = [
        {key: value for key, value in row.items() if not key.startswith("summary_")}
        for row in rows
        if row["employee_id"] is not None
    ]
    for row in employees:
        row["completion_rate"] = float(row["completion_rate"])
        if row["average_score"] is not None:
            row["average_score"] = float(row["average_score"])
    return summary, employees


def list_scope_options(trainer_id: TrainerReportScope) -> dict:
    owner_sql, owner_params = owner_filter(trainer_id)
    with get_connection() as connection:
        courses = connection.execute(
            f"""
            SELECT DISTINCT c.course_id, c.course_name
            FROM courses c JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE {owner_sql}c.status = 'published'
              AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
            ORDER BY c.course_name
            """,
            owner_params,
        ).fetchall()
        departments = connection.execute(
            f"""
            SELECT DISTINCT e.department
            FROM employees e
            JOIN course_assignments ca ON ca.employee_id = e.employee_id
            JOIN courses c ON c.course_id = ca.course_id
            JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE {owner_sql}c.status = 'published' AND ca.status <> 'revoked'
              AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
              AND e.department IS NOT NULL AND e.department <> ''
            ORDER BY e.department
            """,
            owner_params,
        ).fetchall()
        groups = connection.execute(
            f"""
            SELECT DISTINCT eg.group_cn
            FROM employee_groups eg
            JOIN course_assignments ca ON ca.employee_id = eg.employee_id
            JOIN courses c ON c.course_id = ca.course_id
            JOIN assignment_rules ar ON ar.course_id = c.course_id
            WHERE {owner_sql}c.status = 'published' AND ca.status <> 'revoked'
              AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
              AND eg.group_cn IS NOT NULL
            ORDER BY eg.group_cn
            """,
            owner_params,
        ).fetchall()
    return {
        "courses": [dict(row) for row in courses],
        "departments": [row["department"] for row in departments],
        "mailing_lists": [row["group_cn"] for row in groups],
    }


def get_assignment_detail(trainer_id: TrainerReportScope, assignment_id: str) -> dict | None:
    owner_sql, owner_params = owner_filter(trainer_id)
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT ca.*, e.name AS employee_name, e.department, e.status AS employee_status,
                   c.course_name
            FROM course_assignments ca
            JOIN courses c ON c.course_id = ca.course_id
            JOIN employees e ON e.employee_id = ca.employee_id
            JOIN assignment_rules ar ON ar.course_id = ca.course_id
            WHERE ca.assignment_id = ? AND {owner_sql}c.status = 'published'
              AND ca.status <> 'revoked' AND ar.published_at IS NOT NULL AND ar.is_active = TRUE
            """,
            (assignment_id, *owner_params),
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
    trainer_id: TrainerReportScope,
    course_id: str,
    *,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> list[dict]:
    owner_sql, owner_params = owner_filter(trainer_id)
    conditions = [
        "c.course_id = ?",
        "c.status = 'published'",
        "ar.published_at IS NOT NULL",
        "ar.is_active = TRUE",
    ]
    params: list[object] = [course_id, *owner_params]
    if owner_sql:
        conditions.insert(1, "c.trainer_id = ?")
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
