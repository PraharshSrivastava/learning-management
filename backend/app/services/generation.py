"""Course-generation use cases independent of FastAPI routing."""

from __future__ import annotations

from app.core.exceptions import ConflictError
from app.core.settings import Settings
from app.generation.blueprint import generate_course_outline
from app.generation.runtime import generation_state, run_full_course_generation
from app.repositories.courses import CourseRepository
from app.repositories.documents import get_document
from app.repositories.jobs import GenerationJobRepository
from app.services.generation_queue import generation_queue
from app.services.jobs import GenerationJobManager


class GenerationService:
    def __init__(
        self,
        jobs: GenerationJobManager,
        config: Settings,
        courses: CourseRepository | None = None,
    ):
        self.jobs = jobs
        self.config = config
        self.courses = courses or CourseRepository()

    def draft(self, course_id: str, trainer_id: str | None = None) -> dict:
        course = (
            self.courses.get_draft_for_trainer(course_id, trainer_id)
            if trainer_id
            else self.courses.get_draft(course_id)
        )
        if course is None:
            raise FileNotFoundError("Course not found")
        return course

    def generate_quiz(self, course_id: str, trainer_id: str | None = None) -> dict:
        from app.generation.quiz import generate_quiz_for_course

        self.draft(course_id, trainer_id)
        with generation_queue.run(course_id=course_id, operation="quiz"):
            return generate_quiz_for_course(course_id)

    def generate_slides(self, course_id: str, trainer_id: str | None = None) -> dict:
        from app.generation.html import compile_slides_for_course
        from app.generation.slides import generate_slides_for_course

        self.draft(course_id, trainer_id)
        with generation_queue.run(course_id=course_id, operation="slides"):
            course = generate_slides_for_course(course_id)
            compile_slides_for_course(course_id)
            return course

    def generate_scripts(self, course_id: str, trainer_id: str | None = None) -> dict:
        from app.generation.html import compile_slides_for_course
        from app.generation.scripts import generate_scripts_for_course

        self.draft(course_id, trainer_id)
        with generation_queue.run(course_id=course_id, operation="scripts"):
            course = generate_scripts_for_course(course_id)
            compile_slides_for_course(course_id)
            return course

    def generate_video(self, course_id: str, module_number: int, trainer_id: str | None = None) -> dict:
        from app.generation.video import generate_video_for_module

        self.draft(course_id, trainer_id)
        with generation_queue.run(course_id=course_id, operation=f"video:{module_number}"):
            generate_video_for_module(course_id, module_number)
            return self.draft(course_id, trainer_id)

    def generate_full_course(self, course_id: str, trainer_id: str | None = None) -> dict:
        self.draft(course_id, trainer_id)
        with generation_queue.run(course_id=course_id, operation="full_course"):
            return run_full_course_generation(course_id, restart_from_blueprint=True)

    def start_full_course_job(self, course_id: str, trainer_id: str | None = None):
        self.draft(course_id, trainer_id)
        try:
            return self.jobs.submit_process(
                course_id,
                backend_dir=self.config.backend_dir,
                restart_from_blueprint=True,
            )
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc

    def get_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if job is None:
            raise FileNotFoundError("Generation job not found")
        return job

    def continue_generation(self, course_id: str, trainer_id: str | None = None) -> dict:
        course = self.draft(course_id, trainer_id)
        state = generation_state(course)
        checkpoint = state.get("failed_checkpoint") or state.get("current_checkpoint")
        if checkpoint == "blueprint":
            document = get_document(course.get("document_id", ""))
            if not document:
                raise ValueError("Blueprint checkpoint has no source document")
            with generation_queue.run(course_id=course_id, operation="continue:blueprint"):
                return generate_course_outline(
                    document["file_path"],
                    course_id=course_id,
                    trainer_id=course["trainer_id"],
                )
        if not checkpoint:
            raise ValueError("This course has no generation checkpoint to continue")
        with generation_queue.run(course_id=course_id, operation="continue"):
            return run_full_course_generation(course_id, restart_from_blueprint=False)


def build_generation_service(config: Settings) -> GenerationService:
    jobs = GenerationJobManager(
        config.generation_max_concurrency,
        repository=GenerationJobRepository(),
    )
    return GenerationService(jobs, config)
