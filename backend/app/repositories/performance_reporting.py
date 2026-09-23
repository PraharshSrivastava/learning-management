"""Set-based reads for trainer performance reports."""

from __future__ import annotations

from app.repositories.database import get_connection


def list_assignment_summaries(
    trainer_id: str,
    *,
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = None,
) -> list[dict]:
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
    where = " AND ".join(conditions)
    # SQL structure is fixed here; all user-supplied values are bound parameters.
    query = f"""
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
    with get_connection() as connection:
        return [dict(row) for row in connection.execute(query, params).fetchall()]


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
