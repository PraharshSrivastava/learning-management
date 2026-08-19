"""Course persistence queries backed by normalized LMS tables."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from app.repositories.database import advisory_xact_lock, get_connection
from app.schemas.course import CourseRecord

COURSE_METADATA_FIELDS = {
    "images",
    "thumbnail_prompt_hash",
}
MODULE_METADATA_FIELDS = {
    "start_line",
    "end_line",
    "images",
    "pass_mark",
    "quiz_generation_error",
}


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _json_dumps(value: Any) -> Jsonb:
    return Jsonb(value, dumps=lambda item: json.dumps(item, ensure_ascii=False))


def _module_to_record(course_id: str, index: int, module: dict) -> dict:
    module_number = int(module.get("module_number") or index)
    metadata = {key: module[key] for key in MODULE_METADATA_FIELDS if key in module}
    passthrough = {
        key: value
        for key, value in module.items()
        if key
        not in {
            "module_id",
            "course_id",
            "module_number",
            "title",
            "source_text",
            "num_questions",
            "notes",
            "slides",
            "planned_slides",
            "quiz",
            "video_path",
            *MODULE_METADATA_FIELDS,
        }
    }
    if passthrough:
        metadata["extra"] = passthrough
    return {
        "module_id": module.get("module_id") or f"{course_id}:module:{module_number}",
        "course_id": course_id,
        "module_number": module_number,
        "title": module.get("title", ""),
        "source_text": module.get("source_text", "") or "",
        "num_questions": int(module.get("num_questions") or 0),
        "notes": module.get("notes", "") or "",
        "slides_json": _json_dumps(module.get("slides") or []),
        "planned_slides_json": _json_dumps(module.get("planned_slides") or []),
        "quiz_json": _json_dumps(module.get("quiz", None)),
        "video_path": module.get("video_path"),
        "metadata_json": _json_dumps(metadata),
    }


def _row_to_course(connection, row) -> dict:
    course_id = row["course_id"]
    metadata = _json_loads(row["metadata_json"], {})
    course = {
        "course_id": course_id,
        "trainer_id": row["trainer_id"],
        "document_id": row["document_id"],
        "course_name": row["course_name"],
        "course_description": row["course_description"],
        "course_objective": row["course_objective"],
        "course_difficulty": row["course_difficulty"],
        "language": row["language"],
        "target_audience": row["target_audience"],
        "thumbnail_path": row["thumbnail_path"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "published_at": row["published_at"],
        "modules": [],
    }
    course.update({key: metadata[key] for key in COURSE_METADATA_FIELDS if key in metadata})
    modules = connection.execute(
        "SELECT * FROM course_modules WHERE course_id = ? ORDER BY module_number",
        (course_id,),
    ).fetchall()
    for module_row in modules:
        module_metadata = _json_loads(module_row["metadata_json"], {})
        module = {
            "module_id": module_row["module_id"],
            "course_id": course_id,
            "module_number": module_row["module_number"],
            "title": module_row["title"],
            "source_text": module_row["source_text"],
            "num_questions": module_row["num_questions"],
            "notes": module_row["notes"],
            "slides": _json_loads(module_row["slides_json"], []),
            "planned_slides": _json_loads(module_row["planned_slides_json"], []),
            "quiz": _json_loads(module_row["quiz_json"], None),
            "video_path": module_row["video_path"],
        }
        module.update({key: value for key, value in module_metadata.items() if key != "extra"})
        module.update(module_metadata.get("extra") or {})
        course["modules"].append(module)
    generation = connection.execute(
        "SELECT * FROM course_generation_status WHERE course_id = ?", (course_id,)
    ).fetchone()
    if generation:
        state_payload = _json_loads(generation["stages_json"], {})
        state_extra = state_payload.pop("__state", {})
        state = {
            "status": generation["status"],
            "current_checkpoint": generation["checkpoint"],
            "stages": state_payload,
            "error": generation["error"],
            "updated_at": generation["updated_at"],
        }
        state.update(state_extra)
        if generation["status"] == "failed":
            state.setdefault("failed_checkpoint", generation["checkpoint"])
        course["generation"] = state
    CourseRecord.model_validate(course)
    return course


def get_all_courses(status: str | None = None) -> list[dict]:
    with get_connection() as connection:
        rows = (
            connection.execute("SELECT * FROM courses WHERE status = ? ORDER BY created_at", (status,)).fetchall()
            if status
            else connection.execute("SELECT * FROM courses ORDER BY created_at").fetchall()
        )
        return [_row_to_course(connection, row) for row in rows]


def get_course(course_id: str, status: str | None = None) -> dict | None:
    with get_connection() as connection:
        row = (
            connection.execute(
                "SELECT * FROM courses WHERE course_id = ? AND status = ?",
                (course_id, status),
            ).fetchone()
            if status
            else connection.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()
        )
        return _row_to_course(connection, row) if row else None


def save_course(course: dict, status: str) -> None:
    course_id = str(course.get("course_id") or uuid.uuid4())
    course["course_id"] = course_id
    course["status"] = status
    CourseRecord.model_validate(course)
    trainer_id = course.get("trainer_id")
    if not trainer_id:
        raise ValueError("A trainer_id is required to save a course.")
    now = datetime.now().isoformat()
    created_at = course.get("created_at") if isinstance(course.get("created_at"), str) else now
    metadata = {key: course[key] for key in COURSE_METADATA_FIELDS if key in course}
    with get_connection() as connection:
        document_id = course.get("document_id")
        connection.execute(
            """
            INSERT INTO courses (
                course_id, trainer_id, document_id, course_name, course_description,
                course_objective, course_difficulty, language, target_audience,
                thumbnail_path, status, created_at, updated_at, published_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                trainer_id = excluded.trainer_id,
                document_id = excluded.document_id,
                course_name = excluded.course_name,
                course_description = excluded.course_description,
                course_objective = excluded.course_objective,
                course_difficulty = excluded.course_difficulty,
                language = excluded.language,
                target_audience = excluded.target_audience,
                thumbnail_path = excluded.thumbnail_path,
                status = excluded.status,
                updated_at = excluded.updated_at,
                published_at = excluded.published_at,
                metadata_json = excluded.metadata_json
            """,
            (
                course_id,
                trainer_id,
                document_id,
                course.get("course_name") or "",
                course.get("course_description", ""),
                course.get("course_objective", ""),
                course.get("course_difficulty", ""),
                course.get("language", ""),
                course.get("target_audience", ""),
                course.get("thumbnail_path"),
                status,
                created_at,
                now,
                course.get("published_at") or (now if status == "published" else None),
                _json_dumps(metadata),
            ),
        )
        module_records = [
            _module_to_record(course_id, index, module)
            for index, module in enumerate(course.get("modules") or [], start=1)
        ]
        incoming_module_ids = {record["module_id"] for record in module_records}
        existing_module_ids = {
            row["module_id"]
            for row in connection.execute(
                "SELECT module_id FROM course_modules WHERE course_id = ?",
                (course_id,),
            ).fetchall()
        }
        for removed_module_id in existing_module_ids - incoming_module_ids:
            connection.execute(
                "DELETE FROM course_modules WHERE module_id = ?",
                (removed_module_id,),
            )
        connection.execute(
            "UPDATE course_modules SET module_number = -module_number WHERE course_id = ?",
            (course_id,),
        )
        for record in module_records:
            connection.execute(
                """
                INSERT INTO course_modules (
                    module_id, course_id, module_number, title, source_text, num_questions,
                    notes, slides_json, quiz_json, video_path, planned_slides_json,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(module_id) DO UPDATE SET
                    course_id = excluded.course_id,
                    module_number = excluded.module_number,
                    title = excluded.title,
                    source_text = excluded.source_text,
                    num_questions = excluded.num_questions,
                    notes = excluded.notes,
                    slides_json = excluded.slides_json,
                    quiz_json = excluded.quiz_json,
                    video_path = excluded.video_path,
                    planned_slides_json = excluded.planned_slides_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record["module_id"],
                    course_id,
                    record["module_number"],
                    record["title"],
                    record["source_text"],
                    record["num_questions"],
                    record["notes"],
                    record["slides_json"],
                    record["quiz_json"],
                    record["video_path"],
                    record["planned_slides_json"],
                    record["metadata_json"],
                    now,
                    now,
                ),
            )
        state = course.get("generation")
        if isinstance(state, dict):
            state_status = state.get("status") or "pending"
            checkpoint = state.get("current_checkpoint") or state.get("failed_checkpoint")
            state_extra = {
                key: value
                for key, value in state.items()
                if key not in {"status", "current_checkpoint", "stages", "error", "updated_at"}
            }
            stages_payload = dict(state.get("stages") or {})
            if state_extra:
                stages_payload["__state"] = state_extra
            connection.execute(
                """
                INSERT INTO course_generation_status (
                    course_id, status, checkpoint, stages_json, error, attempt_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(course_id) DO UPDATE SET
                    status = excluded.status,
                    checkpoint = excluded.checkpoint,
                    stages_json = excluded.stages_json,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    course_id,
                    state_status,
                    checkpoint,
                    _json_dumps(stages_payload),
                    state.get("error"),
                    now,
                ),
            )
        connection.commit()


def save_all_courses(courses: list[dict], status: str) -> None:
    for course in courses:
        course.setdefault("course_id", str(uuid.uuid4()))
    for course in courses:
        save_course(course, status)


def patch_generated_course_fields(
    course_id: str,
    course: dict,
    *,
    course_fields: tuple[str, ...] = (),
    module_fields: tuple[str, ...] = (),
) -> None:
    """Persist a generation stage's declared output fields without rewriting the course."""
    now = datetime.now().isoformat()
    with get_connection() as connection:
        advisory_xact_lock(connection, f"course_generation:{course_id}")
        existing = connection.execute(
            "SELECT metadata_json FROM courses WHERE course_id = ?",
            (course_id,),
        ).fetchone()
        if not existing:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")

        course_updates: list[str] = []
        params: list[Any] = []
        metadata = _json_loads(existing["metadata_json"], {})
        metadata_changed = False
        for field in course_fields:
            if field == "thumbnail_path":
                course_updates.append("thumbnail_path = ?")
                params.append(course.get("thumbnail_path"))
            elif field in COURSE_METADATA_FIELDS:
                metadata_changed = True
                if field in course:
                    metadata[field] = course[field]
                else:
                    metadata.pop(field, None)
            else:
                raise ValueError(f"Unsupported generated course field: {field}")
        if metadata_changed:
            course_updates.append("metadata_json = ?")
            params.append(_json_dumps(metadata))
        if course_updates:
            course_updates.append("updated_at = ?")
            params.append(now)
            params.append(course_id)
            connection.execute(
                f"UPDATE courses SET {', '.join(course_updates)} WHERE course_id = ?",
                params,
            )

        if module_fields:
            incoming_modules = course.get("modules") or []
            for index, module in enumerate(incoming_modules, start=1):
                module_id = module.get("module_id")
                module_number = int(module.get("module_number") or index)
                if module_id:
                    row = connection.execute(
                        """
                        SELECT module_id, metadata_json
                        FROM course_modules
                        WHERE course_id = ? AND module_id = ?
                        """,
                        (course_id, module_id),
                    ).fetchone()
                else:
                    row = connection.execute(
                        """
                        SELECT module_id, metadata_json
                        FROM course_modules
                        WHERE course_id = ? AND module_number = ?
                        """,
                        (course_id, module_number),
                    ).fetchone()
                if not row:
                    continue

                module_updates: list[str] = []
                module_params: list[Any] = []
                module_metadata = _json_loads(row["metadata_json"], {})
                module_metadata_changed = False
                for field in module_fields:
                    if field == "notes":
                        module_updates.append("notes = ?")
                        module_params.append(module.get("notes", ""))
                    elif field == "slides":
                        module_updates.append("slides_json = ?")
                        module_params.append(_json_dumps(module.get("slides") or []))
                    elif field == "planned_slides":
                        module_updates.append("planned_slides_json = ?")
                        module_params.append(_json_dumps(module.get("planned_slides") or []))
                    elif field == "quiz":
                        module_updates.append("quiz_json = ?")
                        module_params.append(_json_dumps(module.get("quiz", None)))
                    elif field == "video_path":
                        module_updates.append("video_path = ?")
                        module_params.append(module.get("video_path"))
                    elif field in MODULE_METADATA_FIELDS:
                        module_metadata_changed = True
                        if field in module:
                            module_metadata[field] = module[field]
                        else:
                            module_metadata.pop(field, None)
                    else:
                        raise ValueError(f"Unsupported generated module field: {field}")
                if module_metadata_changed:
                    module_updates.append("metadata_json = ?")
                    module_params.append(_json_dumps(module_metadata))
                if module_updates:
                    module_updates.append("updated_at = ?")
                    module_params.append(now)
                    module_params.append(row["module_id"])
                    connection.execute(
                        f"UPDATE course_modules SET {', '.join(module_updates)} WHERE module_id = ?",
                        module_params,
                    )
        connection.commit()


def patch_generation_state(course_id: str, update: Any) -> dict:
    """Apply a generation-state-only mutation without loading modules."""
    now = datetime.now().isoformat()
    with get_connection() as connection:
        advisory_xact_lock(connection, f"course_generation:{course_id}")
        exists = connection.execute(
            "SELECT 1 FROM courses WHERE course_id = ?",
            (course_id,),
        ).fetchone()
        if not exists:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")
        row = connection.execute(
            """
            SELECT status, checkpoint, stages_json, error, updated_at
            FROM course_generation_status
            WHERE course_id = ?
            """,
            (course_id,),
        ).fetchone()
        if row:
            stages = _json_loads(row["stages_json"], {})
            extra = stages.pop("__state", {})
            state = {
                "status": row["status"],
                "current_checkpoint": row["checkpoint"],
                "stages": stages,
                "error": row["error"],
                "updated_at": row["updated_at"],
            }
            if isinstance(extra, dict):
                state.update(extra)
        else:
            state = {
                "status": "pending",
                "current_checkpoint": None,
                "stages": {},
                "error": None,
                "updated_at": now,
            }

        course = {"course_id": course_id, "generation": state}
        update(course)
        state = course.get("generation") or {}
        state_status = state.get("status") or "pending"
        checkpoint = state.get("current_checkpoint") or state.get("failed_checkpoint")
        state_extra = {
            key: value
            for key, value in state.items()
            if key not in {"status", "current_checkpoint", "stages", "error", "updated_at"}
        }
        stages_payload = dict(state.get("stages") or {})
        if state_extra:
            stages_payload["__state"] = state_extra
        connection.execute(
            """
            INSERT INTO course_generation_status (
                course_id, status, checkpoint, stages_json, error, attempt_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                status = excluded.status,
                checkpoint = excluded.checkpoint,
                stages_json = excluded.stages_json,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                course_id,
                state_status,
                checkpoint,
                _json_dumps(stages_payload),
                state.get("error"),
                now,
            ),
        )
        connection.commit()
        state["updated_at"] = now
        return course


def update_course_status(course_id: str, new_status: str) -> None:
    now = datetime.now().isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE courses
            SET status = ?,
                updated_at = ?,
                published_at = CASE
                    WHEN ? = 'published' AND published_at IS NULL THEN ?
                    ELSE published_at
                END
            WHERE course_id = ?
            """,
            (new_status, now, new_status, now, course_id),
        )
        connection.commit()


def delete_course(course_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
        connection.commit()


class CourseRepository:
    @staticmethod
    def _validated(course: dict) -> dict:
        CourseRecord.model_validate(course)
        return course

    def list(self, status: str | None = None) -> list[dict]:
        return [self._validated(course) for course in get_all_courses(status)]

    def list_for_trainer(self, trainer_id: str, status: str | None = None) -> list[dict]:
        return [course for course in self.list(status) if course.get("trainer_id") == trainer_id]

    def get_draft(self, course_id: str) -> dict | None:
        course = get_course(course_id)
        return self._validated(course) if course else None

    def get_draft_for_trainer(self, course_id: str, trainer_id: str) -> dict | None:
        course = self.get_draft(course_id)
        if not course or course.get("trainer_id") != trainer_id:
            return None
        return course

    def list_drafts(self) -> list[dict]:
        return self.list("draft")

    def list_drafts_for_trainer(self, trainer_id: str) -> list[dict]:
        return self.list_for_trainer(trainer_id, "draft")

    def save_draft(self, course: dict) -> None:
        self._validated(course)
        save_course(course, "draft")
