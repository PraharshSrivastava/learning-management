"""Creator-only reversible course availability, with retained learning history."""

from uuid import uuid4

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.repositories.database import advisory_lock, course_transaction, get_connection


def require_editable_course(course_id, expected_revision=None):
    with get_connection() as db:
        row = db.execute(
            "SELECT status, lifecycle_revision FROM courses WHERE course_id = ? FOR UPDATE",
            (course_id,),
        ).fetchone()
    if not row:
        raise NotFoundError("Course not found")
    if expected_revision is not None and row["lifecycle_revision"] != expected_revision:
        raise ConflictError("Course availability changed. Refresh before continuing.")
    if row["status"] == "archived":
        raise DomainValidationError("Restore the archived course before changing assignments.")
    return row


def record_action(course_id, actor, action):
    with get_connection() as db:
        row = db.execute(
            """UPDATE courses SET lifecycle_revision = lifecycle_revision + 1,
            updated_at = now()::text WHERE course_id = ? RETURNING lifecycle_revision""",
            (course_id,),
        ).fetchone()
        db.execute(
            """INSERT INTO course_lifecycle_audit(audit_id,course_id,actor,action,revision)
            VALUES (?, ?, ?, ?, ?)""",
            (str(uuid4()), course_id, actor, action, row["lifecycle_revision"]),
        )
    return row["lifecycle_revision"]


def change_lifecycle(course_id, trainer_id, action, expected_revision):
    # Match the generation/deletion lock order before taking the course row lock.
    with advisory_lock(f"course_generation:{course_id}"):
        with course_transaction(course_id):
            return _change_lifecycle(course_id, trainer_id, action, expected_revision)


def _change_lifecycle(course_id, trainer_id, action, expected_revision):
    from app.repositories.assignments import get_assignment_rule
    from app.repositories.courses import get_course
    from app.services.assignments import api_disable_course_assignment

    with get_connection() as db:
        course = db.execute(
            "SELECT * FROM courses WHERE course_id = ? AND trainer_id = ? FOR UPDATE",
            (course_id, trainer_id),
        ).fetchone()
        if not course:
            raise NotFoundError("Course not found")
        if course["lifecycle_revision"] != expected_revision:
            raise ConflictError("Course availability changed. Refresh before continuing.")
        generation = db.execute(
            "SELECT status FROM course_generation_status WHERE course_id = ?", (course_id,)
        ).fetchone()
        if generation and generation["status"] in ("pending", "running"):
            raise ConflictError(
                "Wait for course generation to finish before changing availability."
            )
        rule = get_assignment_rule(course_id)
        if action == "restore":
            if course["status"] != "archived":
                raise ConflictError("Only an archived course can be restored.")
            db.execute("UPDATE courses SET status = 'published' WHERE course_id = ?", (course_id,))
            # Restore deliberately leaves the rule disabled and observers suspended.
            from app.repositories.assignments import save_assignment_rule

            save_assignment_rule(course_id, rule, disable=True, disabled_by_trainer_id=trainer_id)
            from app.repositories.observers import suspend_course

            suspend_course(course_id, trainer_id)
            record_action(course_id, trainer_id, "restore")
        elif action in ("disable", "archive"):
            if course["status"] != "published" or not rule.get("published_at"):
                raise ConflictError("Only a published course can be disabled or archived.")
            if action == "disable" and not rule["is_active"]:
                raise ConflictError("Course assignments are already disabled.")
            api_disable_course_assignment(course_id, trainer_id)
            if action == "archive":
                db.execute(
                    "UPDATE courses SET status = 'archived' WHERE course_id = ?", (course_id,)
                )
                record_action(course_id, trainer_id, "archive")
        else:
            raise DomainValidationError("Choose Disable, Archive or Restore.")
    return get_course(course_id)
