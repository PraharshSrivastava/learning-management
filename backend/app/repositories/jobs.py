"""Persistence for generation worker lifecycle state."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from app.repositories.database import get_connection
from app.schemas.generation import GenerationJobResponse


class GenerationJobRepository:
    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def _ensure_course(connection, course_id: str) -> None:
        if connection.execute("SELECT 1 FROM courses WHERE course_id = ?", (course_id,)).fetchone():
            return
        now = GenerationJobRepository._now()
        connection.execute(
            """
            INSERT INTO courses (
                course_id, trainer_id, course_name, status, created_at, updated_at
            ) VALUES (?, 'trainer_0001', '', 'draft', ?, ?)
            """,
            (course_id, now, now),
        )

    @staticmethod
    def _load_state_payload(value: str | None) -> tuple[dict, dict]:
        payload = json.loads(value or "{}")
        if not isinstance(payload, dict):
            payload = {}
        extra = payload.pop("__state", {})
        if not isinstance(extra, dict):
            extra = {}
        return payload, extra

    @staticmethod
    def _dump_state_payload(stages: dict, extra: dict) -> str:
        payload = dict(stages)
        if extra:
            payload["__state"] = extra
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def _failed_payload(
        cls,
        *,
        stages_json: str | None,
        checkpoint: str | None,
        reason: str,
    ) -> tuple[str, str]:
        stages, extra = cls._load_state_payload(stages_json)
        now = cls._now()
        checkpoint = checkpoint or extra.get("current_checkpoint") or extra.get("failed_checkpoint")
        checkpoint = str(checkpoint or "pipeline")

        if checkpoint == "wave_1":
            failed_stages = [
                stage
                for stage, entry in stages.items()
                if isinstance(entry, dict) and entry.get("status") == "running"
            ]
            for stage in failed_stages:
                entry = stages.setdefault(stage, {})
                entry.update(
                    {
                        "status": "failed",
                        "error": reason,
                        "updated_at": now,
                        "completed_at": now,
                    }
                )
            extra.update(
                {
                    "current_checkpoint": "wave_1",
                    "failed_checkpoint": "wave_1",
                    "failed_stages": failed_stages,
                    "error": reason,
                    "failed_at": now,
                }
            )
            return "wave_1", cls._dump_state_payload(stages, extra)

        entry = stages.setdefault(checkpoint, {})
        if isinstance(entry, dict):
            entry.update(
                {
                    "status": "failed",
                    "error": reason,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
        extra.update(
            {
                "current_checkpoint": None,
                "failed_checkpoint": checkpoint,
                "failed_stages": [],
                "error": reason,
                "failed_at": now,
            }
        )
        return checkpoint, cls._dump_state_payload(stages, extra)

    @classmethod
    def _has_running_nested_stage(cls, stages_json: str | None) -> bool:
        stages, _extra = cls._load_state_payload(stages_json)
        return any(
            isinstance(entry, dict) and entry.get("status") == "running"
            for entry in stages.values()
        )

    def create(self, job: GenerationJobResponse) -> None:
        now = self._now()
        try:
            with get_connection() as connection:
                self._ensure_course(connection, job.course_id)
                active = connection.execute(
                    """
                    SELECT worker_id FROM course_generation_state
                    WHERE course_id = ? AND status IN ('pending', 'running') AND worker_id IS NOT NULL
                    """,
                    (job.course_id,),
                ).fetchone()
                if active:
                    raise ValueError("Generation is already running for this course")
                connection.execute(
                    """
                    INSERT INTO course_generation_state (
                        course_id, status, checkpoint, stages_json, error, worker_id,
                        attempt_count, updated_at
                    ) VALUES (?, ?, NULL, '{}', ?, ?, 1, ?)
                    ON CONFLICT(course_id) DO UPDATE SET
                        status = excluded.status,
                        error = excluded.error,
                        worker_id = excluded.worker_id,
                        attempt_count = course_generation_state.attempt_count + 1,
                        updated_at = excluded.updated_at
                    """,
                    (job.course_id, job.status, job.error, job.id, now),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Generation is already running for this course") from exc

    def save(self, job: GenerationJobResponse) -> None:
        if job.status == "failed":
            self.fail_worker(job.id, job.error or "Generation worker failed.")
            return
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE course_generation_state
                SET status = ?, error = ?, worker_id = ?, updated_at = ?
                WHERE worker_id = ?
                """,
                (job.status, job.error, job.id, self._now(), job.id),
            )
            connection.commit()

    def get(self, job_id: str) -> GenerationJobResponse | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT course_id, status, error, worker_id, updated_at, stages_json
                FROM course_generation_state
                WHERE worker_id = ?
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        stages = json.loads(row["stages_json"] or "{}")
        return GenerationJobResponse.model_validate(
            {
                "id": row["worker_id"],
                "course_id": row["course_id"],
                "status": row["status"],
                "created_at": stages.get("job_created_at") or row["updated_at"],
                "started_at": stages.get("job_started_at"),
                "completed_at": stages.get("job_completed_at")
                if row["status"] in {"completed", "failed"}
                else None,
                "error": row["error"],
            }
        )

    def fail_interrupted(self, reason: str) -> int:
        """Fail interrupted generation attempts and their nested checkpoint metadata."""
        updated = 0
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT course_id, status, checkpoint, stages_json
                FROM course_generation_state
                WHERE status IN ('pending', 'running', 'failed')
                """
            ).fetchall()
            for row in rows:
                if row["status"] == "failed" and not self._has_running_nested_stage(
                    row["stages_json"]
                ):
                    continue
                checkpoint, stages_json = self._failed_payload(
                    stages_json=row["stages_json"],
                    checkpoint=row["checkpoint"],
                    reason=reason,
                )
                connection.execute(
                    """
                    UPDATE course_generation_state
                    SET status = 'failed',
                        checkpoint = ?,
                        stages_json = ?,
                        error = ?,
                        worker_id = NULL,
                        locked_until = NULL,
                        updated_at = ?
                    WHERE course_id = ?
                    """,
                    (checkpoint, stages_json, reason, self._now(), row["course_id"]),
                )
                updated += 1
            connection.commit()
            return updated

    def fail_worker(self, worker_id: str, reason: str) -> int:
        """Fail one worker attempt and keep the JSON generation metadata in sync."""
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT course_id, checkpoint, stages_json
                FROM course_generation_state
                WHERE worker_id = ?
                """,
                (worker_id,),
            ).fetchone()
            if not row:
                return 0
            checkpoint, stages_json = self._failed_payload(
                stages_json=row["stages_json"],
                checkpoint=row["checkpoint"],
                reason=reason,
            )
            connection.execute(
                """
                UPDATE course_generation_state
                SET status = 'failed',
                    checkpoint = ?,
                    stages_json = ?,
                    error = ?,
                    worker_id = ?,
                    locked_until = NULL,
                    updated_at = ?
                WHERE worker_id = ?
                """,
                (checkpoint, stages_json, reason, worker_id, self._now(), worker_id),
            )
            connection.commit()
            return 1
