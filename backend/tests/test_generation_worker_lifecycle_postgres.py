"""Generation worker ownership across trainer blueprint edits."""

import os

import pytest
from test_assignment_workspace_postgres import workspace_db as workspace_db

from app.core.exceptions import ConflictError
from app.repositories import database
from app.repositories.jobs import GenerationJobRepository
from app.schemas.course import CourseUpdateRequest
from app.schemas.generation import GenerationJobResponse
from app.services.courses import CourseService

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated PostgreSQL opt-in"
)


def generation_row():
    with database.get_connection() as db:
        return db.execute(
            "SELECT status, worker_id FROM course_generation_status WHERE course_id='course'"
        ).fetchone()


def seed_generation(status: str, worker_id: str) -> None:
    with database.get_connection() as db:
        db.execute(
            """
            INSERT INTO course_generation_status(
                course_id, status, stages_json, worker_id, attempt_count
            ) VALUES ('course', ?, '{}', ?, 1)
            """,
            (status, worker_id),
        )
        db.commit()


def test_blueprint_edit_releases_completed_worker_for_next_job(workspace_db):
    seed_generation("completed", "old-worker")

    updated = CourseService().update_course(
        "course", CourseUpdateRequest(course_name="Updated course"), "creator"
    )

    row = generation_row()
    assert updated["course_name"] == "Updated course"
    assert row["status"] == "pending"
    assert row["worker_id"] is None

    GenerationJobRepository().create(
        GenerationJobResponse(
            id="new-worker",
            course_id="course",
            status="pending",
            created_at="2026-10-15T00:00:00+00:00",
        )
    )
    row = generation_row()
    assert row["status"] == "pending"
    assert row["worker_id"] == "new-worker"


def test_blueprint_edit_does_not_take_over_active_worker(workspace_db):
    seed_generation("running", "active-worker")

    with pytest.raises(ConflictError, match="already running"):
        CourseService().update_course(
            "course", CourseUpdateRequest(course_name="Unsafe edit"), "creator"
        )

    row = generation_row()
    assert row["status"] == "running"
    assert row["worker_id"] == "active-worker"
    with database.get_connection() as db:
        course = db.execute(
            "SELECT course_name FROM courses WHERE course_id='course'"
        ).fetchone()
    assert course["course_name"] == "Test course"
