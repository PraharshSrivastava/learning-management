"""Retire the archived state without reopening learning or Observer access."""
from uuid import uuid4

VERSION = "20261012_enable_disable_v1"


def apply_availability_migration(cursor):
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(current_schema() || ?))", (":enable_disable_v1",))
    cursor.execute("SELECT version FROM lms_schema_migrations WHERE version = ?", (VERSION,))
    if cursor.fetchone():
        return
    cursor.execute("""SELECT c.course_id, c.lifecycle_revision, ar.published_at
        FROM courses c LEFT JOIN assignment_rules ar ON ar.course_id = c.course_id
        WHERE c.status = 'archived' ORDER BY c.course_id FOR UPDATE OF c""")
    courses = cursor.fetchall()
    if any(not c["published_at"] for c in courses):
        raise RuntimeError("Archived courses lack published assignment evidence; availability migration requires administrator review.")
    for course in courses:
        course_id = course["course_id"]
        cursor.execute("""UPDATE assignment_rules SET is_active = FALSE,
            disabled_at = COALESCE(disabled_at, now()::text), updated_at = now()::text
            WHERE course_id = ?""", (course_id,))
        cursor.execute("""UPDATE course_assignments SET revoked_at = COALESCE(revoked_at, now()::text),
            revoked_reason = COALESCE(revoked_reason, 'course_archived'),
            notification_lifecycle = notification_lifecycle + 1 WHERE course_id = ?""", (course_id,))
        cursor.execute("""UPDATE course_observer_grants SET active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE course_id = ? AND active RETURNING observer_employee_id""", (course_id,))
        affected = cursor.fetchall()
        if affected:
            cursor.execute("UPDATE course_observer_configs SET revision = revision + 1 WHERE course_id = ?", (course_id,))
            for grant in affected:
                cursor.execute("""INSERT INTO lms_access_versions(employee_id, permissions_version) VALUES (?, 1)
                    ON CONFLICT(employee_id) DO UPDATE SET permissions_version = lms_access_versions.permissions_version + 1""", (grant["observer_employee_id"],))
        cursor.execute("""UPDATE courses SET status = 'published', lifecycle_revision = lifecycle_revision + 1,
            updated_at = now()::text WHERE course_id = ?""", (course_id,))
        cursor.execute("""INSERT INTO course_lifecycle_audit(audit_id, course_id, actor, action, revision)
            VALUES (?, ?, 'system:migration', 'archived_to_disabled', ?)""",
            (str(uuid4()), course_id, course["lifecycle_revision"] + 1))
    cursor.execute("INSERT INTO lms_schema_migrations(version) VALUES (?)", (VERSION,))
