"""Course authoring business rules, independent of HTTP routing."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.langfuse_tracing import trace_scope
from app.modules.courses.artifacts import delete_course_artifacts
from app.modules.courses.quiz_schemas import ManualQuizRequest
from app.modules.courses.repository import CourseRepository
from app.modules.courses.schemas import CourseUpdateRequest
from app.modules.generation.generation_queue import generation_queue
from app.modules.generation.pipeline.blueprint import generate_course_outline
from app.modules.generation.pipeline.quiz import ModuleQuiz
from app.modules.generation.pipeline.runtime import now_iso
from app.modules.generation.pipeline.video_engine import (
    course_uses_video_engine,
    toggle_enabled,
    video_engine_available,
)
from app.modules.learning.notifications import schedule_employee_broadcast

logger = logging.getLogger(__name__)


class CourseService:
    def __init__(self, repository: CourseRepository | None = None):
        self.repository = repository or CourseRepository()

    def list_courses(self, trainer_id: str | None = None) -> list[dict]:
        if trainer_id:
            return self.repository.list_for_trainer(trainer_id)
        return self.repository.list()

    def list_course_summaries(self, trainer_id: str) -> list[dict]:
        return self.repository.list_summaries_for_trainer(trainer_id)

    def get_course(self, course_id: str, trainer_id: str) -> dict:
        course = self.repository.get_draft_for_trainer(course_id, trainer_id)
        if course is None:
            raise NotFoundError("Course not found")
        return course

    def generate_outline(self, filename: str, trainer_id: str) -> dict:
        with trace_scope(
            "lms.blueprint",
            session_id=str(uuid4()),
            user_id=trainer_id,
            metadata={"operation": "blueprint"},
            tags=["course-generation", "blueprint"],
        ):
            with generation_queue.run(
                course_id=f"blueprint:{trainer_id}:{filename}",
                operation="blueprint",
            ):
                course = generate_course_outline(filename, trainer_id=trainer_id)
        course["trainer_id"] = trainer_id
        self.repository.save_draft(course)
        return course

    def update_course(
        self, course_id: str, payload: CourseUpdateRequest, trainer_id: str | None = None
    ) -> dict:
        course = (
            self.repository.get_draft_for_trainer(course_id, trainer_id)
            if trainer_id
            else self.repository.get_draft(course_id)
        )
        if course is None:
            raise NotFoundError("Course not found")

        if course.get("status") == "archived":
            raise ConflictError("Restore the archived course before editing its content.")
        updated_fields = payload.model_dump(exclude_unset=True)
        blueprint_changed = False
        for field in (
            "course_name",
            "course_description",
            "course_objective",
            "course_difficulty",
            "language",
            "target_audience",
        ):
            if field in updated_fields:
                blueprint_changed = blueprint_changed or course.get(field) != updated_fields[field]
                course[field] = updated_fields[field]

        if "modules" in updated_fields:
            blueprint_changed = True
            course["modules"] = self._merge_modules(
                course.get("modules", []), updated_fields["modules"]
            )

        engine_changed = False
        if updated_fields.get("video_engine") is not None:
            engine_changed = self._apply_video_engine(course, bool(updated_fields["video_engine"]))
            # Videos from the other engine no longer match the course, so it is generated
            # again from its blueprint, as after a blueprint edit.
            # A checkpoint left by the other engine is cleared too, so Continue cannot
            # resume a run that was planned for a different pipeline.
            if engine_changed and (
                self._has_generated_content(course) or self._has_generation_progress(course)
            ):
                blueprint_changed = True

        if blueprint_changed:
            self._invalidate_generated_content(course)
        try:
            # Releasing the worker refuses the save while a generation job runs, which
            # also stops an engine switch in the middle of a run.
            self.repository.save_draft(
                course, release_generation_worker=blueprint_changed or engine_changed
            )
        except ConflictError as exc:
            if engine_changed and str(exc).startswith("Course generation is already running"):
                raise ConflictError(
                    "Wait for the current generation to finish before switching engines."
                ) from exc
            raise
        return course

    @staticmethod
    def _apply_video_engine(course: dict, requested: bool) -> bool:
        """Store the trainer's engine choice; True when it changes the course's engine."""
        if not toggle_enabled():
            raise ConflictError("Video Engine selection is not enabled.")
        if requested == course_uses_video_engine(course):
            # Record an explicit choice for an older course, without changing its engine.
            course["video_engine"] = requested
            return False
        if requested and not video_engine_available():
            raise DomainValidationError("Video Engine isn't available on this server.")
        course["video_engine"] = requested
        return True

    @staticmethod
    def _has_generation_progress(course: dict) -> bool:
        """True when generation went past the blueprint (any later stage or checkpoint)."""
        state = course.get("generation") or {}
        if state.get("failed_checkpoint") not in (None, "blueprint"):
            return True
        if state.get("current_checkpoint") not in (None, "blueprint"):
            return True
        return any(stage != "blueprint" for stage in (state.get("stages") or {}))

    @staticmethod
    def _has_generated_content(course: dict) -> bool:
        if course.get("thumbnail_path"):
            return True
        return any(
            module.get(field)
            for module in course.get("modules", [])
            for field in ("quiz", "notes", "slides", "planned_slides", "video_path", "video_service")
        )

    def update_module_quiz(
        self,
        course_id: str,
        module_number: int,
        payload: ManualQuizRequest,
        trainer_id: str | None = None,
    ) -> dict:
        parsed = ModuleQuiz.model_validate(
            {"questions": [item.model_dump() for item in payload.questions]}
        )
        for index, question in enumerate(parsed.questions, start=1):
            option_keys = {option.key.strip().upper() for option in question.options}
            if option_keys != {"A", "B", "C", "D"}:
                raise ValueError(f"Question {index} must include options A, B, C, and D.")
            if question.correct_option.strip().upper() not in option_keys:
                raise ValueError(f"Question {index} has an invalid correct option.")

        course = (
            self.repository.get_draft_for_trainer(course_id, trainer_id)
            if trainer_id
            else self.repository.get_draft(course_id)
        )
        if course is None:
            raise NotFoundError("Course not found")
        if course.get("status") == "archived":
            raise ConflictError("Restore the archived course before editing its content.")
        module = next(
            (
                item
                for item in course.get("modules", [])
                if int(item.get("module_number", 0)) == module_number
            ),
            None,
        )
        if module is None:
            raise NotFoundError("Module not found")
        module["quiz"] = parsed.model_dump()
        module["num_questions"] = len(parsed.questions)
        module.pop("quiz_generation_error", None)
        self.repository.save_draft(course)
        return course

    def delete_course(self, course_id: str, trainer_id: str, expected_revision: int | None = None) -> None:
        result = (self.repository.delete_for_trainer(course_id, trainer_id) if expected_revision is None else self.repository.delete_for_trainer(course_id, trainer_id, expected_revision))
        if result is None:
            raise NotFoundError("Course not found")
        if not result.get("deleted"):
            raise ConflictError("Course cannot be deleted while generation is pending or running")

        cleanup_failures = delete_course_artifacts(
            course_id,
            thumbnail_path=result.get("thumbnail_path"),
        )
        if cleanup_failures:
            logger.warning(
                "course_deleted_with_artifact_cleanup_failures course_id=%s paths=%s",
                course_id,
                cleanup_failures,
            )
        for employee_id in result.get("affected_employee_ids", []):
            schedule_employee_broadcast(employee_id)
        logger.info(
            "course_deleted course_id=%s trainer_id=%s affected_employees=%s",
            course_id,
            trainer_id,
            len(result.get("affected_employee_ids", [])),
        )

    @staticmethod
    def _merge_modules(existing_modules: list[dict], incoming_modules: list[object]) -> list[dict]:
        def start_line_key(value: object) -> str | None:
            return str(value).strip() if value is not None and value != "" else None

        by_start_line = {
            start_line_key(item.get("start_line")): item
            for item in existing_modules
            if start_line_key(item.get("start_line"))
        }
        by_title = {
            item.get("title", "").strip(): item for item in existing_modules if item.get("title")
        }
        merged = []
        for index, item in enumerate(incoming_modules, start=1):
            if isinstance(item, str):
                values = {
                    "title": item,
                    "source_text": "",
                    "start_line": None,
                    "num_questions": 3,
                }
            elif isinstance(item, dict):
                values = dict(item)
            else:
                values = item.model_dump()
            title = str(values.get("title") or "").strip()
            match = by_start_line.get(start_line_key(values.get("start_line"))) or by_title.get(
                title
            )
            module = dict(match) if match else {}
            module.update({"module_number": index, **values})
            module.pop("end_line", None)
            merged.append(module)
        return merged

    @staticmethod
    def _invalidate_generated_content(course: dict) -> None:
        for module in course.get("modules", []):
            for field in (
                "quiz",
                "quiz_generation_error",
                "planned_slides",
                "slides",
                "notes",
                "video_path",
                "video_service",
            ):
                module.pop(field, None)
        for field in ("thumbnail_path", "thumbnail_prompt_hash"):
            course.pop(field, None)
        blueprint_stage = course.setdefault("generation", {}).get("stages", {}).get("blueprint")
        course["generation"] = {
            "status": "pending",
            "current_checkpoint": None,
            "failed_stages": [],
            "stages": {"blueprint": blueprint_stage} if blueprint_stage else {},
            "updated_at": now_iso(),
        }
