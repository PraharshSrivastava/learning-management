"""Course authoring business rules, independent of HTTP routing."""

from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.generation.blueprint import generate_course_outline
from app.generation.quiz import ModuleQuiz
from app.generation.runtime import now_iso
from app.repositories.courses import CourseRepository
from app.schemas.course import CourseUpdateRequest
from app.schemas.quiz import ManualQuizRequest
from app.services.generation_queue import generation_queue


class CourseService:
    def __init__(self, repository: CourseRepository | None = None):
        self.repository = repository or CourseRepository()

    def list_courses(self, trainer_id: str | None = None) -> list[dict]:
        if trainer_id:
            return self.repository.list_for_trainer(trainer_id)
        return self.repository.list()

    def generate_outline(self, filename: str, trainer_id: str) -> dict:
        with generation_queue.run(course_id=f"blueprint:{trainer_id}:{filename}", operation="blueprint"):
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

        if blueprint_changed:
            self._invalidate_generated_content(course)
        self.repository.save_draft(course)
        return course

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
