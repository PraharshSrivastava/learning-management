"""Additive course lifecycle and history-preserving access migration."""

VERSION = "20261009_course_lifecycle_v1"


def apply_course_lifecycle_migration(cursor):
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(current_schema() || ?))", (":course_lifecycle_v1",)
    )
    cursor.execute(
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS lifecycle_revision BIGINT NOT NULL DEFAULT 0"
    )
    cursor.execute(
        "ALTER TABLE assignment_rules ADD COLUMN IF NOT EXISTS applied_include_filters_json JSONB"
    )
    cursor.execute(
        "ALTER TABLE assignment_rules ADD COLUMN IF NOT EXISTS applied_exclude_filters_json JSONB"
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS course_lifecycle_audit (
        audit_id TEXT PRIMARY KEY, course_id TEXT NOT NULL, actor TEXT NOT NULL,
        action TEXT NOT NULL, revision BIGINT NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS lms_schema_migrations (
        version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("SELECT version FROM lms_schema_migrations WHERE version = ?", (VERSION,))
    if cursor.fetchone():
        return
    # Existing published rules become their initial applied snapshot.
    cursor.execute("""UPDATE assignment_rules SET
        applied_include_filters_json = include_filters_json || jsonb_build_object('include_inactive', include_inactive),
        applied_exclude_filters_json = exclude_filters_json WHERE published_at IS NOT NULL""")
    # Revocation withdraws access; reconstruct only evidence-backed learning state.
    cursor.execute("""UPDATE course_assignments ca SET
        revoked_at = COALESCE(revoked_at, updated_at),
        status = CASE WHEN completed_at IS NOT NULL THEN 'completed'
            WHEN started_at IS NOT NULL OR EXISTS(SELECT 1 FROM module_progress mp
                WHERE mp.assignment_id = ca.assignment_id AND
                (mp.video_watched OR mp.quiz_passed OR mp.attempt_count > 0)) THEN 'started'
            ELSE 'pending' END WHERE status = 'revoked'""")
    cursor.execute("INSERT INTO lms_schema_migrations(version) VALUES (?)", (VERSION,))
