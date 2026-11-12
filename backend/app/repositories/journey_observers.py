"""Revisioned journey Observer selectors, the same model as course Observers.

Save stores a pending selection and takes access away at once; additions reach the Observer
only when Apply runs on a published journey. Disabling a journey suspends its Observers.
"""

from uuid import uuid4

from psycopg.types.json import Jsonb

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.db.database import get_connection
from app.modules.access.repository import identity_key
from app.repositories.observers import _employee


def _config(db, journey_id):
    row = db.execute(
        "SELECT revision FROM learning_journey_observer_configs WHERE journey_id = ?", (journey_id,)
    ).fetchone()
    observers = []
    for grant in db.execute(
        # Named columns: an upgraded table has them in another order than a new one.
        """SELECT observer_employee_id, active FROM learning_journey_observers
        WHERE journey_id = ? ORDER BY observer_employee_id""",
        (journey_id,),
    ).fetchall():
        item = {"observer_employee_id": grant["observer_employee_id"], "is_active": grant["active"]}
        for phase in ("active", "pending"):
            item[phase] = {
                "employee_ids": [r["employee_id"] for r in db.execute(
                    """SELECT employee_id FROM learning_journey_observer_employees
                    WHERE journey_id = ? AND observer_employee_id = ? AND phase = ? ORDER BY employee_id""",
                    (journey_id, grant["observer_employee_id"], phase),
                ).fetchall()],
                "department_ids": [r["department_id"] for r in db.execute(
                    """SELECT department_id FROM learning_journey_observer_departments
                    WHERE journey_id = ? AND observer_employee_id = ? AND phase = ? ORDER BY department_id""",
                    (journey_id, grant["observer_employee_id"], phase),
                ).fetchall()],
            }
        if item["is_active"] or item["pending"]["employee_ids"] or item["pending"]["department_ids"]:
            observers.append(item)
    return {"journey_id": journey_id, "revision": row["revision"] if row else 0, "observers": observers}


def get_config(journey_id):
    with get_connection() as db:
        return _config(db, journey_id)


def _lock(db, journey_id, trainer_id, revision):
    journey = db.execute(
        "SELECT trainer_id, status FROM learning_journeys WHERE journey_id = ? FOR UPDATE", (journey_id,)
    ).fetchone()
    if not journey or journey["trainer_id"] != trainer_id:
        raise NotFoundError("Learning journey not found")
    db.execute(
        "INSERT INTO learning_journey_observer_configs(journey_id) VALUES (?) ON CONFLICT DO NOTHING",
        (journey_id,),
    )
    current = db.execute(
        "SELECT revision FROM learning_journey_observer_configs WHERE journey_id = ? FOR UPDATE",
        (journey_id,),
    ).fetchone()["revision"]
    if current != revision:
        raise ConflictError("Observer configuration has changed. Refresh before saving or applying.")
    return journey


def _finish(db, journey_id, trainer_id, before, affected, action):
    db.execute(
        "UPDATE learning_journey_observer_configs SET revision = revision + 1 WHERE journey_id = ?",
        (journey_id,),
    )
    for employee_id in affected:
        db.execute("""INSERT INTO lms_access_versions(employee_id, permissions_version) VALUES (?, 1)
            ON CONFLICT(employee_id) DO UPDATE SET permissions_version = lms_access_versions.permissions_version + 1""",
            (employee_id,))
    after = _config(db, journey_id)
    db.execute(
        """INSERT INTO lms_report_access_audit(audit_id, course_id, actor, action, revision, before_json, after_json)
        VALUES (?, NULL, ?, ?, ?, ?, ?)""",
        (str(uuid4()), trainer_id, "journey_observers_" + action, after["revision"], Jsonb(before), Jsonb(after)),
    )
    db.commit()
    return after


def save_config(journey_id, trainer_id, payload, check_separation):
    """check_separation(observer_ids) raises when an Observer is also a learner of the journey."""
    with get_connection() as db:
        _lock(db, journey_id, trainer_id, payload.revision)
        before = _config(db, journey_id)
        existing = db.execute(
            "SELECT observer_employee_id FROM learning_journey_observers WHERE journey_id = ?", (journey_id,)
        ).fetchall()
        affected = {r["observer_employee_id"] for r in existing}
        incoming = {s.observer_employee_id for s in payload.observers}
        check_separation(incoming)
        for employee_id in affected - incoming:
            for table in ("learning_journey_observer_employees", "learning_journey_observer_departments"):
                db.execute(f"DELETE FROM {table} WHERE journey_id = ? AND observer_employee_id = ?", (journey_id, employee_id))
            db.execute("""UPDATE learning_journey_observers SET active = FALSE, updated_at = now()::text
                WHERE journey_id = ? AND observer_employee_id = ?""", (journey_id, employee_id))
        for selection in payload.observers:
            observer = _employee(db, selection.observer_employee_id)
            employee_id = observer["employee_id"]
            affected.add(employee_id)
            key = identity_key(observer)
            old = db.execute(
                "SELECT identity_key FROM learning_journey_observers WHERE journey_id = ? AND observer_employee_id = ?",
                (journey_id, employee_id),
            ).fetchone()
            if old and old["identity_key"] != key:
                for table in ("learning_journey_observer_employees", "learning_journey_observer_departments"):
                    db.execute(f"DELETE FROM {table} WHERE journey_id = ? AND observer_employee_id = ?", (journey_id, employee_id))
            db.execute("""INSERT INTO learning_journey_observers(journey_id, observer_employee_id, identity_key, granted_by_trainer_id)
                VALUES (?, ?, ?, ?) ON CONFLICT(journey_id, observer_employee_id) DO UPDATE SET
                identity_key = excluded.identity_key, granted_by_trainer_id = excluded.granted_by_trainer_id,
                updated_at = now()::text""",
                (journey_id, employee_id, key, trainer_id))
            for table in ("learning_journey_observer_employees", "learning_journey_observer_departments"):
                db.execute(f"DELETE FROM {table} WHERE journey_id = ? AND observer_employee_id = ? AND phase = 'pending'",
                    (journey_id, employee_id))
            for target_id in set(selection.employee_ids):
                target = _employee(db, target_id)
                db.execute("""INSERT INTO learning_journey_observer_employees
                    (journey_id, observer_employee_id, phase, employee_id, identity_key) VALUES (?, ?, 'pending', ?, ?)""",
                    (journey_id, employee_id, target_id, identity_key(target)))
            for department_id in set(selection.department_ids):
                if not db.execute("SELECT department_id FROM lms_departments WHERE department_id = ? AND active", (department_id,)).fetchone():
                    raise DomainValidationError("Choose a current directory department")
                db.execute("""INSERT INTO learning_journey_observer_departments
                    (journey_id, observer_employee_id, phase, department_id) VALUES (?, ?, 'pending', ?)""",
                    (journey_id, employee_id, department_id))
            # A save may only shrink the live set. Additions stay pending until apply.
            for table, column in (("learning_journey_observer_employees", "employee_id"),
                                  ("learning_journey_observer_departments", "department_id")):
                db.execute(f"""DELETE FROM {table} a WHERE a.journey_id = ? AND a.observer_employee_id = ? AND a.phase = 'active'
                    AND NOT EXISTS(SELECT 1 FROM {table} p WHERE p.journey_id = a.journey_id
                        AND p.observer_employee_id = a.observer_employee_id
                        AND p.phase = 'pending' AND p.{column} = a.{column})""", (journey_id, employee_id))
        return _finish(db, journey_id, trainer_id, before, affected, "save")


def apply_config(journey_id, trainer_id, revision, check_separation):
    with get_connection() as db:
        journey = _lock(db, journey_id, trainer_id, revision)
        if journey["status"] != "published":
            raise DomainValidationError("Publish the journey before applying observers")
        before = _config(db, journey_id)
        check_separation({item["observer_employee_id"] for item in before["observers"]})
        affected = set()
        for item in before["observers"]:
            employee_id = item["observer_employee_id"]
            observer = _employee(db, employee_id)
            grant = db.execute(
                "SELECT identity_key FROM learning_journey_observers WHERE journey_id = ? AND observer_employee_id = ?",
                (journey_id, employee_id),
            ).fetchone()
            if grant["identity_key"] != identity_key(observer):
                raise DomainValidationError("Observer identity changed; save the configuration again")
            affected.add(employee_id)
            for target in db.execute("""SELECT employee_id, identity_key FROM learning_journey_observer_employees
                WHERE journey_id = ? AND observer_employee_id = ? AND phase = 'pending'""", (journey_id, employee_id)).fetchall():
                if identity_key(_employee(db, target["employee_id"])) != target["identity_key"]:
                    raise DomainValidationError("An observed employee identity changed; save the configuration again")
            if db.execute("""SELECT 1 FROM learning_journey_observer_departments s JOIN lms_departments d USING(department_id)
                WHERE s.journey_id = ? AND s.observer_employee_id = ? AND s.phase = 'pending' AND NOT d.active""",
                (journey_id, employee_id)).fetchone():
                raise DomainValidationError("An observed department is no longer active")
            for table, columns in (("learning_journey_observer_employees", "employee_id, identity_key"),
                                   ("learning_journey_observer_departments", "department_id")):
                db.execute(f"DELETE FROM {table} WHERE journey_id = ? AND observer_employee_id = ? AND phase = 'active'",
                    (journey_id, employee_id))
                db.execute(f"""INSERT INTO {table}(journey_id, observer_employee_id, phase, {columns})
                    SELECT journey_id, observer_employee_id, 'active', {columns} FROM {table}
                    WHERE journey_id = ? AND observer_employee_id = ? AND phase = 'pending'""", (journey_id, employee_id))
            db.execute("""UPDATE learning_journey_observers SET active = TRUE, updated_at = now()::text
                WHERE journey_id = ? AND observer_employee_id = ?""", (journey_id, employee_id))
        return _finish(db, journey_id, trainer_id, before, affected, "apply")


def suspend_journey(journey_id, trainer_id):
    """A disabled journey's Observers lose access until the creator applies them again."""
    with get_connection() as db:
        before = _config(db, journey_id)
        _lock(db, journey_id, trainer_id, before["revision"])
        affected = db.execute("""UPDATE learning_journey_observers SET active = FALSE, updated_at = now()::text
            WHERE journey_id = ? AND active RETURNING observer_employee_id""", (journey_id,)).fetchall()
        if not affected:
            return before
        return _finish(db, journey_id, trainer_id, before, {r["observer_employee_id"] for r in affected}, "suspend")
