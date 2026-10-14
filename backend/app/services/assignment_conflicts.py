"""Course-local employee/Observer role separation, evaluated under the course lock."""

from app.core.exceptions import ConflictError
from app.repositories.assignments import employee_matches_assignment_rule, get_assignment_rule
from app.repositories.database import get_connection
from app.repositories.employees import list_employees


class EmployeeObserverConflict(ConflictError):
    code = "employee_observer_conflict"


def observer_ids(course_id, db=None):
    def read(connection):
        return {
            r["observer_employee_id"]
            for r in connection.execute(
                """
            SELECT g.observer_employee_id FROM course_observer_grants g
            JOIN employees e ON e.employee_id = g.observer_employee_id
            WHERE g.course_id = ? AND g.identity_key = CASE
              WHEN NULLIF(e.directory_uuid, '') IS NOT NULL THEN 'directory:' || e.directory_uuid
              ELSE 'hub:' || e.hub_user_id::text END
            AND (g.active OR
              EXISTS(SELECT 1 FROM course_observer_employees s WHERE s.course_id=g.course_id AND s.observer_employee_id=g.observer_employee_id AND s.phase='pending') OR
              EXISTS(SELECT 1 FROM course_observer_departments s WHERE s.course_id=g.course_id AND s.observer_employee_id=g.observer_employee_id AND s.phase='pending'))
            """,
                (course_id,),
            ).fetchall()
        }

    if db is not None:
        return read(db)
    with get_connection() as connection:
        return read(connection)


def validate_separation(course_id, rule=None, proposed_observers=None, db=None):
    if db is None:
        with get_connection() as connection:
            return validate_separation(course_id, rule, proposed_observers, connection)
    ids = observer_ids(course_id, db) if proposed_observers is None else set(proposed_observers)
    if not ids:
        return
    rule = rule if rule is not None else get_assignment_rule(course_id)
    employees = list_employees(include_inactive=True)
    matched = {e["employee_id"] for e in employees if employee_matches_assignment_rule(e, rule)}
    assigned = {
        r["employee_id"]
        for r in db.execute(
            "SELECT employee_id FROM course_assignments WHERE course_id = ? AND status <> 'revoked' AND revoked_at IS NULL",
            (course_id,),
        ).fetchall()
    }
    conflicts = sorted(ids & (matched | assigned))
    if conflicts:
        names = {e["employee_id"]: e["name"] for e in employees}
        label = ", ".join(names.get(i, i) for i in conflicts[:10])
        suffix = f" and {len(conflicts) - 10} others" if len(conflicts) > 10 else ""
        raise EmployeeObserverConflict(
            f"{label}{suffix} is selected as both an employee and an Observer for this course. Remove the conflicting Observer selection or resolve the existing assignment before continuing."
        )
