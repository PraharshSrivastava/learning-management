"""Effective report roles and a safe department registry for observation selectors."""

from uuid import uuid4

from app.repositories.database import get_connection
from app.repositories.lms_access import identity_key


def department_options():
    # Existing feed supplies exact department labels. Preserve registry IDs; never
    # infer renames or leadership. A rename needs the verified directory adapter.
    with get_connection() as db:
        rows = db.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department <> '' ORDER BY department").fetchall()
        for row in rows:
            db.execute("""INSERT INTO lms_departments(department_id, external_key, name, source)
                VALUES (?, ?, ?, 'directory-label') ON CONFLICT(name) DO NOTHING""",
                (str(uuid4()), "label:" + row["department"], row["department"]))
        result = db.execute("""SELECT department_id, name FROM lms_departments d
            WHERE active AND EXISTS (SELECT 1 FROM employees e WHERE e.department = d.name)
            ORDER BY name""").fetchall()
        db.commit()
    return [dict(row) for row in result]


def report_roles(employee):
    with get_connection() as db:
        row = db.execute("""SELECT
            EXISTS(SELECT 1 FROM hod_department_access h JOIN lms_departments d USING(department_id)
                WHERE h.hod_employee_id = ? AND h.identity_key = ? AND h.active AND d.active
                    AND d.source = 'directory') AS hod,
            EXISTS(SELECT 1 FROM course_observer_grants g JOIN courses c USING(course_id)
                JOIN assignment_rules ar USING(course_id)
                WHERE g.observer_employee_id = ? AND g.identity_key = ? AND g.active
                AND c.status = 'published' AND ar.is_active AND ar.published_at IS NOT NULL
                AND (EXISTS(SELECT 1 FROM course_observer_employees s
                    WHERE s.course_id = g.course_id AND s.observer_employee_id = g.observer_employee_id AND s.phase = 'active')
                OR EXISTS(SELECT 1 FROM course_observer_departments s
                    WHERE s.course_id = g.course_id AND s.observer_employee_id = g.observer_employee_id AND s.phase = 'active'))) AS observer
            """, (employee["employee_id"], identity_key(employee), employee["employee_id"], identity_key(employee))).fetchone()
    return {key for key in ("hod", "observer") if row[key]}


def report_scope_version():
    # Include canonical membership and department mapping, not learner progress.
    # Changes clear report caches even when the viewer's grants are unchanged.
    with get_connection() as db:
        row = db.execute("""SELECT md5(
            COALESCE((SELECT string_agg(employee_id || ':' || COALESCE(directory_uuid, '') || ':' || COALESCE(department, '') || ':' || status || ':' || directory_status, '|' ORDER BY employee_id) FROM employees), '')
            || COALESCE((SELECT string_agg(hod_employee_id || ':' || identity_key || ':' || department_id || ':' || active::text, '|' ORDER BY hod_employee_id, department_id) FROM hod_department_access), '')
            || COALESCE((SELECT string_agg(department_id || ':' || name || ':' || source || ':' || active::text, '|' ORDER BY department_id) FROM lms_departments), '')
        ) AS version""").fetchone()
    return row["version"]
