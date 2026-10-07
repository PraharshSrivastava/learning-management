"""Revisioned Observer selectors with immediate restriction and explicit apply."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from app.repositories.database import atomic_course, get_connection
from app.repositories.lms_access import identity_key


def _config(db, course_id):
    row = db.execute("SELECT revision FROM course_observer_configs WHERE course_id = ?", (course_id,)).fetchone()
    observers = []
    for grant in db.execute("SELECT * FROM course_observer_grants WHERE course_id = ? ORDER BY observer_employee_id", (course_id,)).fetchall():
        item = {"observer_employee_id": grant["observer_employee_id"], "is_active": grant["active"]}
        for phase in ("active", "pending"):
            item[phase] = {
                "employee_ids": [r["employee_id"] for r in db.execute("SELECT employee_id FROM course_observer_employees WHERE course_id = ? AND observer_employee_id = ? AND phase = ? ORDER BY employee_id", (course_id, grant["observer_employee_id"], phase)).fetchall()],
                "department_ids": [r["department_id"] for r in db.execute("SELECT department_id FROM course_observer_departments WHERE course_id = ? AND observer_employee_id = ? AND phase = ? ORDER BY department_id", (course_id, grant["observer_employee_id"], phase)).fetchall()],
            }
        if item["is_active"] or item["pending"]["employee_ids"] or item["pending"]["department_ids"]:
            observers.append(item)
    return {"course_id": course_id, "revision": row["revision"] if row else 0, "observers": observers}


def get_config(course_id):
    with get_connection() as db:
        return _config(db, course_id)


def _lock(db, course_id, trainer_id, revision):
    course = db.execute("SELECT trainer_id, status FROM courses WHERE course_id = ? FOR UPDATE", (course_id,)).fetchone()
    if not course:
        raise NotFoundError("Course not found")
    if course["trainer_id"] != trainer_id:
        raise AuthorizationError("Only the course creator can manage observers")
    db.execute("INSERT INTO course_observer_configs(course_id) VALUES (?) ON CONFLICT DO NOTHING", (course_id,))
    current = db.execute("SELECT revision FROM course_observer_configs WHERE course_id = ? FOR UPDATE", (course_id,)).fetchone()["revision"]
    if current != revision:
        raise ConflictError("Observer configuration has changed. Refresh before saving or applying.")
    return course


def _employee(db, employee_id):
    row = db.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
    if not row or row["status"] != "active" or row.get("directory_status", "active") != "active" or row.get("source") != "hub":
        raise DomainValidationError("Choose an active synced employee")
    identity_key(row)
    return row


def _finish(db, course_id, trainer_id, before, affected, action):
    db.execute("UPDATE course_observer_configs SET revision = revision + 1 WHERE course_id = ?", (course_id,))
    for employee_id in affected:
        db.execute("""INSERT INTO lms_access_versions(employee_id, permissions_version) VALUES (?, 1)
            ON CONFLICT(employee_id) DO UPDATE SET permissions_version = lms_access_versions.permissions_version + 1""", (employee_id,))
    after = _config(db, course_id)
    db.execute("INSERT INTO lms_report_access_audit(audit_id, course_id, actor, action, revision, before_json, after_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), course_id, trainer_id, action, after["revision"], Jsonb(before), Jsonb(after)))
    db.commit()
    return after


@atomic_course
def save_config(course_id, trainer_id, payload):
    with get_connection() as db:
        _lock(db, course_id, trainer_id, payload.revision)
        before = _config(db, course_id)
        existing = db.execute("SELECT observer_employee_id FROM course_observer_grants WHERE course_id = ?", (course_id,)).fetchall()
        affected = {r["observer_employee_id"] for r in existing}
        incoming = {s.observer_employee_id for s in payload.observers}
        from app.services.assignment_conflicts import validate_separation
        validate_separation(course_id, proposed_observers=incoming, db=db)
        for employee_id in affected - incoming:
            db.execute("DELETE FROM course_observer_employees WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id))
            db.execute("DELETE FROM course_observer_departments WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id))
            db.execute("UPDATE course_observer_grants SET active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id))
        for selection in payload.observers:
            observer = _employee(db, selection.observer_employee_id)
            employee_id = observer["employee_id"]
            affected.add(employee_id)
            key = identity_key(observer)
            old = db.execute("SELECT identity_key FROM course_observer_grants WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id)).fetchone()
            if old and old["identity_key"] != key:
                for table in ("course_observer_employees", "course_observer_departments"):
                    db.execute(f"DELETE FROM {table} WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id))
            db.execute("""INSERT INTO course_observer_grants(course_id, observer_employee_id, identity_key, granted_by_trainer_id)
                VALUES (?, ?, ?, ?) ON CONFLICT(course_id, observer_employee_id) DO UPDATE SET
                identity_key = excluded.identity_key, granted_by_trainer_id = excluded.granted_by_trainer_id, updated_at = CURRENT_TIMESTAMP""",
                (course_id, employee_id, key, trainer_id))
            for table in ("course_observer_employees", "course_observer_departments"):
                db.execute(f"DELETE FROM {table} WHERE course_id = ? AND observer_employee_id = ? AND phase = 'pending'", (course_id, employee_id))
            for target_id in set(selection.employee_ids):
                target = _employee(db, target_id)
                db.execute("INSERT INTO course_observer_employees VALUES (?, ?, 'pending', ?, ?)", (course_id, employee_id, target_id, identity_key(target)))
            for department_id in set(selection.department_ids):
                if not db.execute("SELECT department_id FROM lms_departments WHERE department_id = ? AND active", (department_id,)).fetchone():
                    raise DomainValidationError("Choose a current directory department")
                db.execute("INSERT INTO course_observer_departments VALUES (?, ?, 'pending', ?)", (course_id, employee_id, department_id))
            # A save may only shrink the live set. Additions stay pending until apply.
            for table, column in (("course_observer_employees", "employee_id"), ("course_observer_departments", "department_id")):
                db.execute(f"""DELETE FROM {table} a WHERE a.course_id = ? AND a.observer_employee_id = ? AND a.phase = 'active'
                    AND NOT EXISTS(SELECT 1 FROM {table} p WHERE p.course_id = a.course_id AND p.observer_employee_id = a.observer_employee_id
                        AND p.phase = 'pending' AND p.{column} = a.{column})""", (course_id, employee_id))
        return _finish(db, course_id, trainer_id, before, affected, "save")


@atomic_course
def apply_config(course_id, trainer_id, revision):
    with get_connection() as db:
        course = _lock(db, course_id, trainer_id, revision)
        rule = db.execute("SELECT is_active, published_at FROM assignment_rules WHERE course_id = ?", (course_id,)).fetchone()
        if course["status"] != "published" or not rule or not rule["is_active"] or not rule["published_at"]:
            raise DomainValidationError("Publish and assign the course before applying observers")
        from app.services.assignment_conflicts import validate_separation
        validate_separation(course_id, db=db)
        before = _config(db, course_id)
        affected = set()
        for item in before["observers"]:
            employee_id = item["observer_employee_id"]
            observer = _employee(db, employee_id)
            grant = db.execute("SELECT identity_key FROM course_observer_grants WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id)).fetchone()
            if grant["identity_key"] != identity_key(observer):
                raise DomainValidationError("Observer identity changed; save the configuration again")
            affected.add(employee_id)
            for target in db.execute("SELECT employee_id, identity_key FROM course_observer_employees WHERE course_id = ? AND observer_employee_id = ? AND phase = 'pending'", (course_id, employee_id)).fetchall():
                if identity_key(_employee(db, target["employee_id"])) != target["identity_key"]:
                    raise DomainValidationError("An observed employee identity changed; save the configuration again")
            if db.execute("""SELECT 1 FROM course_observer_departments s JOIN lms_departments d USING(department_id)
                WHERE s.course_id = ? AND s.observer_employee_id = ? AND s.phase = 'pending' AND NOT d.active""", (course_id, employee_id)).fetchone():
                raise DomainValidationError("An observed department is no longer active")
            for table, columns in (("course_observer_employees", "employee_id, identity_key"), ("course_observer_departments", "department_id")):
                db.execute(f"DELETE FROM {table} WHERE course_id = ? AND observer_employee_id = ? AND phase = 'active'", (course_id, employee_id))
                db.execute(f"INSERT INTO {table} SELECT course_id, observer_employee_id, 'active', {columns} FROM {table} WHERE course_id = ? AND observer_employee_id = ? AND phase = 'pending'", (course_id, employee_id))
            db.execute("UPDATE course_observer_grants SET active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE course_id = ? AND observer_employee_id = ?", (course_id, employee_id))
        return _finish(db, course_id, trainer_id, before, affected, "apply")


@atomic_course
def suspend_course(course_id, trainer_id=None):
    with get_connection() as db:
        owner = db.execute("SELECT trainer_id FROM courses WHERE course_id = ? FOR UPDATE", (course_id,)).fetchone()
        if not owner:
            raise NotFoundError("Course not found")
        before = _config(db, course_id)
        actor = trainer_id or owner["trainer_id"]
        _lock(db, course_id, actor, before["revision"])
        affected = db.execute("UPDATE course_observer_grants SET active = FALSE WHERE course_id = ? AND active RETURNING observer_employee_id", (course_id,)).fetchall()
        if not affected:
            return before
        return _finish(db, course_id, actor, before, {r["observer_employee_id"] for r in affected}, "suspend")
