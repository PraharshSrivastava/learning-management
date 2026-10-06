"""Persisted grants are bound to stable directory identities, not email/name."""

from uuid import uuid4

from app.core.exceptions import DomainValidationError, NotFoundError
from app.repositories.database import advisory_xact_lock, get_connection


def identity_key(employee: dict) -> str:
    if employee.get("directory_uuid"):
        return "directory:" + str(employee["directory_uuid"])
    if employee.get("hub_user_id") is not None:
        return "hub:" + str(employee["hub_user_id"])
    raise DomainValidationError("A stable directory UUID or Hub user ID is required")


def access_snapshot(employee: dict) -> tuple[set[str], int]:
    key = identity_key(employee)
    with get_connection() as connection:
        row = connection.execute(
            """SELECT
            COALESCE((SELECT ARRAY_AGG(role ORDER BY role) FROM lms_authoring_roles
                WHERE employee_id = ? AND identity_key = ? AND active = TRUE), ARRAY[]::text[]) AS roles,
            COALESCE((SELECT permissions_version FROM lms_access_versions WHERE employee_id = ?), 0) AS permissions_version
            """,
            (employee["employee_id"], key, employee["employee_id"]),
        ).fetchone()
    return set(row["roles"]), int(row["permissions_version"])


def set_admin_grant(
    employee_id: str, *, active: bool, expected_identity: str, operator: str, reason: str
) -> dict:
    if not operator.strip() or not reason.strip() or not expected_identity.strip():
        raise DomainValidationError("Verified identity, operator and reason are required")
    with get_connection() as connection:
        advisory_xact_lock(connection, "lms-authoring-grant:" + employee_id)
        employee = connection.execute(
            "SELECT * FROM employees WHERE employee_id = ? FOR UPDATE", (employee_id,)
        ).fetchone()
        if not employee:
            raise NotFoundError("Employee not found")
        key = identity_key(employee)
        if key != expected_identity:
            raise DomainValidationError(
                "Employee stable identity does not match the requested identity"
            )
        if active and (
            employee["status"] != "active"
            or employee.get("directory_status", "active") != "active"
            or employee.get("source") != "hub"
        ):
            raise DomainValidationError(
                "Only an active synced Hub employee may receive Admin Trainer access"
            )
        previous = connection.execute(
            "SELECT * FROM lms_authoring_roles WHERE employee_id = ? AND role = 'admin_trainer'",
            (employee_id,),
        ).fetchone()
        # Revocation is permitted for disabled identities; regrant never transfers an old identity's privilege silently.
        old_active = bool(previous and previous["active"] and previous["identity_key"] == key)
        previous_active = bool(previous and previous["active"])
        if (active and old_active) or (not active and not previous_active):
            row = connection.execute(
                "SELECT permissions_version FROM lms_access_versions WHERE employee_id = ?",
                (employee_id,),
            ).fetchone()
            return {
                "changed": False,
                "permissions_version": int(row["permissions_version"]) if row else 0,
            }
        connection.execute(
            """INSERT INTO lms_authoring_roles(employee_id, role, identity_key, active, granted_by, revoked_at)
            VALUES (?, 'admin_trainer', ?, ?, ?, CASE WHEN ? THEN NULL ELSE CURRENT_TIMESTAMP END)
            ON CONFLICT(employee_id, role) DO UPDATE SET identity_key = excluded.identity_key,
                active = excluded.active, granted_by = excluded.granted_by,
                granted_at = CASE WHEN excluded.active THEN CURRENT_TIMESTAMP ELSE lms_authoring_roles.granted_at END,
                revoked_at = excluded.revoked_at""",
            (employee_id, key, active, operator, active),
        )
        version = connection.execute(
            """INSERT INTO lms_access_versions(employee_id, permissions_version) VALUES (?, 1)
            ON CONFLICT(employee_id) DO UPDATE SET permissions_version = lms_access_versions.permissions_version + 1
            RETURNING permissions_version""",
            (employee_id,),
        ).fetchone()["permissions_version"]
        connection.execute(
            """INSERT INTO lms_access_audit(audit_id, employee_id, identity_key, role, action, previous_active, next_active, operator, reason, permissions_version)
            VALUES (?, ?, ?, 'admin_trainer', ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid4()),
                employee_id,
                key,
                "grant" if active else "revoke",
                previous_active,
                active,
                operator,
                reason,
                version,
            ),
        )
        connection.commit()
    return {"changed": True, "permissions_version": int(version)}
