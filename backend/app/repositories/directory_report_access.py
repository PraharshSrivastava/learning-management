"""Trusted directory adapter; no HTTP/manual HOD writer and no heuristics.

The verified upstream contract must call this after validation. The current
employee feed does not provide that contract, so production wiring is gated.
"""

from uuid import uuid4

from psycopg.types.json import Jsonb

from app.core.exceptions import DomainValidationError
from app.repositories.database import advisory_xact_lock, get_connection
from app.repositories.lms_access import identity_key


def reconcile_verified_departments(records, *, source_key, full_snapshot=False):
    if not source_key or not isinstance(records, list):
        raise DomainValidationError("A verified directory source and department records are required")
    with get_connection() as db:
        advisory_xact_lock(db, "lms-directory-department-access")
        before = [dict(r) for r in db.execute("SELECT hod_employee_id, identity_key, department_id, active FROM hod_department_access ORDER BY hod_employee_id, department_id").fetchall()]
        seen = set()
        affected = set()
        for record in records:
            external_key, name = record.get("external_key"), record.get("name")
            if not external_key or not name or external_key in seen:
                raise DomainValidationError("Department external keys and exact names must be unambiguous")
            seen.add(external_key)
            old = db.execute("SELECT * FROM lms_departments WHERE external_key = ?", (external_key,)).fetchone()
            label = db.execute("SELECT * FROM lms_departments WHERE name = ?", (name,)).fetchone()
            if label and (label["source"] != "directory-label" and (not old or label["department_id"] != old["department_id"])):
                raise DomainValidationError("Department names are ambiguous in this deployment")
            department_id = old["department_id"] if old else label["department_id"] if label else str(uuid4())
            db.execute("""INSERT INTO lms_departments(department_id, external_key, name, source, active)
                VALUES (?, ?, ?, 'directory', ?) ON CONFLICT(department_id) DO UPDATE SET
                external_key = excluded.external_key, name = excluded.name, source = 'directory', active = excluded.active""",
                (department_id, external_key, name, record.get("active", True)))
            if "hod_directory_uuids" not in record and record.get("active", True):
                continue  # Omitted associations are preserved on partial events.
            rows = db.execute("UPDATE hod_department_access SET active = FALSE, synced_at=CURRENT_TIMESTAMP WHERE department_id = ? RETURNING hod_employee_id", (department_id,)).fetchall()
            affected.update(row["hod_employee_id"] for row in rows)
            if not record.get("active", True):
                continue
            for directory_uuid in set(record["hod_directory_uuids"]):
                employee = db.execute("SELECT * FROM employees WHERE directory_uuid = ?", (directory_uuid,)).fetchone()
                if not employee or employee["status"] != "active" or employee["directory_status"] != "active" or employee["source"] != "hub":
                    raise DomainValidationError("Directory HOD association does not resolve to one active synced identity")
                affected.add(employee["employee_id"])
                db.execute("""INSERT INTO hod_department_access(hod_employee_id,identity_key,department_id,source,source_key)
                    VALUES (?, ?, ?, 'directory', ?) ON CONFLICT(hod_employee_id,department_id) DO UPDATE SET
                    identity_key=excluded.identity_key, active=TRUE, source_key=excluded.source_key, synced_at=CURRENT_TIMESTAMP""",
                    (employee["employee_id"], identity_key(employee), department_id, source_key))
        if full_snapshot:
            omitted = db.execute("UPDATE lms_departments SET active=FALSE WHERE source='directory' AND NOT(external_key = ANY(?::text[])) RETURNING department_id", (list(seen),)).fetchall()
            for row in omitted:
                revoked = db.execute("UPDATE hod_department_access SET active=FALSE WHERE department_id=? RETURNING hod_employee_id", (row["department_id"],)).fetchall()
                affected.update(item["hod_employee_id"] for item in revoked)
        after = [dict(r) for r in db.execute("SELECT hod_employee_id, identity_key, department_id, active FROM hod_department_access ORDER BY hod_employee_id, department_id").fetchall()]
        if before != after:
            for employee_id in affected:
                db.execute("""INSERT INTO lms_access_versions(employee_id,permissions_version) VALUES (?,1)
                    ON CONFLICT(employee_id) DO UPDATE SET permissions_version=lms_access_versions.permissions_version+1""", (employee_id,))
            db.execute("INSERT INTO lms_report_access_audit(audit_id,actor,action,before_json,after_json) VALUES (?, ?, 'directory-reconcile', ?, ?)",
                (str(uuid4()), 'directory:' + source_key, Jsonb(before), Jsonb(after)))
        db.commit()
