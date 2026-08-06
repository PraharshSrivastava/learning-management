"""Coordinate generation state, retries, recovery, orchestration, and publishing."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from filelock import FileLock

from app.core.settings import settings
from app.core.storage import resolve_public_asset_path
from app.repositories.courses import (
    CourseRepository,
    get_all_courses,
    get_course,
    patch_generated_course_fields,
    patch_generation_state,
    save_all_courses,
    save_course,
)
from app.repositories.database import database_path
from app.schemas.generation import GenerationState

logger = logging.getLogger(__name__)

T = TypeVar("T")

PIPELINE_STAGES = (
    "blueprint",
    "quiz",
    "slides",
    "html",
    "scripts",
    "notes",
    "tts",
    "video",
    "thumbnail",
    "publish",
)

class PipelineStageError(RuntimeError):
    def __init__(
        self,
        stage: str,
        message: str,
        module_number: int | None = None,
        slide_number: int | None = None,
    ):
        super().__init__(message)
        self.stage = stage
        self.module_number = module_number
        self.slide_number = slide_number

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def log_event(course_id: str, stage: str, event: str, **details: Any) -> None:
    suffix = " ".join(f"{key}={value}" for key, value in details.items() if value is not None)
    logger.debug(
        "pipeline_event course_id=%s stage=%s event=%s%s",
        course_id,
        stage,
        event,
        f" {suffix}" if suffix else "",
    )

def retry(
    operation: Callable[[], T],
    *,
    course_id: str,
    stage: str,
    attempts: int,
    module_number: int | None = None,
    slide_number: int | None = None,
) -> T:
    """Run one external operation with clear, bounded retry logging."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        log_event(
            course_id,
            stage,
            "attempt_start",
            attempt=f"{attempt}/{attempts}",
            module=module_number,
            slide=slide_number,
        )
        try:
            result = operation()
            log_event(
                course_id,
                stage,
                "attempt_success",
                attempt=f"{attempt}/{attempts}",
                module=module_number,
                slide=slide_number,
                elapsed=f"{time.perf_counter() - started:.1f}s",
            )
            return result
        except Exception as exc:
            last_error = exc
            log_event(
                course_id,
                stage,
                "attempt_failed",
                attempt=f"{attempt}/{attempts}",
                module=module_number,
                slide=slide_number,
                elapsed=f"{time.perf_counter() - started:.1f}s",
                reason=str(exc)[:500],
            )
    raise PipelineStageError(
        stage, str(last_error or "Unknown generation error"), module_number, slide_number
    )

def generation_state(course: dict) -> dict:
    state = course.setdefault("generation", {})
    state.setdefault("status", "pending")
    state.setdefault("stages", {})
    state.setdefault("failed_stages", [])
    state.setdefault("started_at", now_iso())
    GenerationState.model_validate(state)
    return state

def mark_stage(
    course: dict,
    stage: str,
    status: str,
    *,
    error: str = "",
    module_number: int | None = None,
    slide_number: int | None = None,
    elapsed_seconds: float | None = None,
) -> None:
    state = generation_state(course)
    entry = state["stages"].setdefault(stage, {})
    entry.update({"status": status, "updated_at": now_iso()})
    if status == "running":
        entry["started_at"] = now_iso()
        entry.pop("error", None)
    if status in {"completed", "failed"}:
        entry["completed_at"] = now_iso()
    if elapsed_seconds is not None:
        entry["duration_seconds"] = round(elapsed_seconds, 2)
    if module_number is not None:
        entry["module_number"] = module_number
    if slide_number is not None:
        entry["slide_number"] = slide_number
    if error:
        entry["error"] = error

    if status == "failed":
        state.update(
            {
                "status": "failed",
                "current_checkpoint": None,
                "failed_checkpoint": stage,
                "error": error,
                "module_number": module_number,
                "slide_number": slide_number,
                "failed_at": now_iso(),
            }
        )
    elif status == "running":
        state.update({"status": "running", "current_checkpoint": stage})
        if state.get("failed_checkpoint") == stage:
            for key in ("failed_checkpoint", "error", "module_number", "slide_number", "failed_at"):
                state.pop(key, None)
    elif status == "completed":
        if state.get("current_checkpoint") == stage:
            state["current_checkpoint"] = None

def complete_generation(course: dict, elapsed_seconds: float) -> None:
    state = generation_state(course)
    previous_total = float(state.get("total_duration_seconds") or 0)
    state.update(
        {
            "status": "completed",
            "current_checkpoint": None,
            "failed_stages": [],
            "completed_at": now_iso(),
            "last_run_duration_seconds": round(elapsed_seconds, 2),
            "total_duration_seconds": round(previous_total + elapsed_seconds, 2),
        }
    )
    for key in ("failed_checkpoint", "error", "module_number", "slide_number"):
        state.pop(key, None)

def load_course_for_generation(course_id: str) -> dict:
    course = get_course(course_id)
    if course is None:
        raise ValueError(f"Course '{course_id}' not found in courses database.")
    return course

def save_generated_course(
    course_id: str,
    course: dict,
    *,
    course_fields: tuple[str, ...] = (),
    module_fields: tuple[str, ...] = (),
) -> None:
    """Persist only fields owned by one generation stage.

    Wave 1 stages run concurrently from independent snapshots. Restricting each
    write to its declared fields prevents a slower worker from restoring stale
    values over output already committed by another worker.
    """
    if course.get("course_id") != course_id:
        raise ValueError("Cannot save generated content for a different course")
    if not course_fields and not module_fields:
        raise ValueError("Generated course writes must declare owned fields")
    with FileLock(f"{database_path()}.{course_id}.generation.lock", timeout=60):
        patch_generated_course_fields(
            course_id,
            course,
            course_fields=course_fields,
            module_fields=module_fields,
        )


def update_generation_state(course_id: str, update: Callable[[dict], None]) -> dict:
    """Apply one coordinator-owned checkpoint transition to the latest course state."""
    with FileLock(f"{database_path()}.{course_id}.generation.lock", timeout=60):
        return patch_generation_state(course_id, update)

def ensure_module_cover_slide(
    course: dict, module: dict, module_number: int, total_modules: int
) -> None:
    slides = module.setdefault("slides", [])
    cover_title = module.get("title", f"Module {module_number}")
    cover_slide = {
        "slide_title": cover_title,
        "title": cover_title,
        "layout_type": "cover",
        "is_cover_slide": True,
        "course_name": course.get("course_name", ""),
        "module_number": module_number,
        "total_modules": total_modules,
        "bullets": [],
        "bullets_data": [],
        "image_ids": [],
    }

    if slides and (
        slides[0].get("is_cover_slide") or str(slides[0].get("layout_type", "")).lower() == "cover"
    ):
        existing_script = slides[0].get("script")
        existing_audio = slides[0].get("audio_path")
        slides[0].update(cover_slide)
        if existing_script:
            slides[0]["script"] = existing_script
        if existing_audio:
            slides[0]["audio_path"] = existing_audio
        return

    slides.insert(0, cover_slide)

def _asset_is_nonempty(path: object) -> bool:
    value = str(path or "").strip()
    if not value:
        return False
    resolved = resolve_public_asset_path(value, settings)
    return resolved.is_file() and resolved.stat().st_size > 0


def _thumbnail_output_complete(course: dict) -> bool:
    from app.generation.thumbnails import course_thumbnail_signature

    thumbnail_path = course.get("thumbnail_path")
    return bool(
        _asset_is_nonempty(thumbnail_path)
        and course.get("thumbnail_prompt_hash") == course_thumbnail_signature(course)
    )


def _slides_output_complete(course: dict) -> bool:
    modules = course.get("modules") or []
    return bool(modules) and all(module.get("slides") for module in modules)


def _notes_output_complete(course: dict) -> bool:
    modules = course.get("modules") or []
    return bool(modules) and all(str(module.get("notes") or "").strip() for module in modules)


def _quiz_output_complete(course: dict) -> bool:
    for module in course.get("modules") or []:
        try:
            num_questions = int(module.get("num_questions", 0))
        except (TypeError, ValueError):
            num_questions = 0
        if num_questions <= 0:
            continue
        quiz = module.get("quiz")
        if not isinstance(quiz, dict) or not quiz.get("questions"):
            return False
    return True


def _scripts_output_complete(course: dict) -> bool:
    return _slides_output_complete(course) and all(
        str(slide.get("script") or "").strip()
        for module in course.get("modules") or []
        for slide in module.get("slides") or []
    )


def _tts_output_complete(course: dict) -> bool:
    return _slides_output_complete(course) and all(
        _asset_is_nonempty(slide.get("audio_path"))
        for module in course.get("modules") or []
        for slide in module.get("slides") or []
    )


def _video_output_complete(course: dict) -> bool:
    modules = course.get("modules") or []
    return bool(modules) and all(_asset_is_nonempty(module.get("video_path")) for module in modules)


def _html_output_complete(course: dict) -> bool:
    course_id = str(course.get("course_id") or "")
    modules = course.get("modules") or []
    return bool(course_id and modules) and all(
        (settings.slide_dir / course_id / f"module_{index}.html").is_file()
        and (settings.slide_dir / course_id / f"module_{index}.html").stat().st_size > 0
        for index, _module in enumerate(modules, start=1)
    )


def missing_generation_outputs(course: dict) -> list[str]:
    checks = (
        ("thumbnail", _thumbnail_output_complete),
        ("quiz", _quiz_output_complete),
        ("notes", _notes_output_complete),
        ("slides", _slides_output_complete),
        ("html", _html_output_complete),
        ("scripts", _scripts_output_complete),
        ("tts", _tts_output_complete),
        ("video", _video_output_complete),
    )
    return [stage for stage, check in checks if not check(course)]


def is_course_generation_complete(course: dict) -> bool:
    if not course.get("modules"):
        return False
    if missing_generation_outputs(course):
        return False

    return True

def sync_clean_database(course_id: str | None = None):
    """Prepare complete courses while serializing lifecycle transitions."""
    with FileLock(f"{database_path()}.publish.lock", timeout=30):
        return _sync_clean_database(course_id)

def _sync_clean_database(target_course_id: str | None = None):
    """
    Move complete generated courses into the ready lifecycle state.

    This function intentionally does not run generation work. The full pipeline is
    responsible for creating quizzes, videos, and thumbnails before this exporter runs.
    """
    start = time.perf_counter()
    logger.info("publish_sync_started db=%s", database_path())

    if target_course_id:
        draft_course = CourseRepository().get_draft(target_course_id)
        draft_courses = [draft_course] if draft_course is not None else []
    else:
        draft_courses = get_all_courses("draft")

    ready_courses = []
    skipped_courses = []

    for course in draft_courses:
        course_id = course["course_id"]
        if not is_course_generation_complete(course):
            skipped_courses.append(course_id)
            continue
        ready_courses.append(course)

    logger.info(
        f"[EXPORTER] Prepared {len(ready_courses)} ready course(s) "
        f"from {len(draft_courses)} draft course(s); skipped incomplete={len(skipped_courses)}"
    )
    if skipped_courses:
        preview = ", ".join(skipped_courses[:5])
        suffix = "..." if len(skipped_courses) > 5 else ""
        logger.info("publish_sync_skipped_incomplete course_ids=%s", f"{preview}{suffix}")

    # Lifecycle changes must retain the canonical course and module payloads.
    write_start = time.perf_counter()
    if target_course_id:
        if not ready_courses:
            raise PipelineStageError(
                "publish",
                f"Course '{target_course_id}' is not complete enough to publish.",
            )
        save_course(ready_courses[0], "ready")
    else:
        save_all_courses(ready_courses, "ready")
    logger.info(
        "publish_rows_synchronized count=%s db=%s elapsed_seconds=%.1f",
        len(ready_courses),
        database_path(),
        time.perf_counter() - write_start,
    )
    logger.info(
        "publish_sync_completed elapsed_seconds=%.1f",
        time.perf_counter() - start,
    )

def recover_interrupted_generations() -> None:
    """Mark work left running by a process restart as recoverable failure."""
    try:
        from app.repositories.jobs import GenerationJobRepository

        GenerationJobRepository().fail_interrupted(
            "Generation interrupted because the backend process restarted. Continue from this checkpoint."
        )
    except Exception:
        logger.exception("Could not recover interrupted course generations")

def run_full_course_generation(course_id: str, *, restart_from_blueprint: bool) -> dict:
    """Run the course pipeline with a barrier and recovery queue for Wave 1."""
    from app.generation.html import compile_slides_for_course
    from app.generation.notes import generate_notes_for_course
    from app.generation.quiz import generate_quiz_for_course
    from app.generation.scripts import generate_scripts_for_course
    from app.generation.slides import generate_slides_for_course
    from app.generation.thumbnails import course_thumbnail_signature, generate_course_thumbnail
    from app.generation.tts import generate_tts_for_course
    from app.generation.video import generate_videos_for_course
    from app.services.courses import CourseService

    pipeline_start = time.perf_counter()
    repository = CourseRepository()
    wave_stage_order = ("thumbnail", "quiz", "notes", "slides")

    def load_course() -> dict:
        course = get_course(course_id)
        if course is None:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")
        return course

    def clear_wave_stage_output(stage: str) -> None:
        course = load_course()
        course_fields: tuple[str, ...] = ()
        module_fields: tuple[str, ...] = ()
        for module in course.get("modules", []):
            if stage == "quiz":
                module.pop("quiz", None)
                module.pop("quiz_generation_error", None)
                module_fields = ("quiz", "quiz_generation_error")
            elif stage == "notes":
                module.pop("notes", None)
                module_fields = ("notes",)
            elif stage == "slides":
                for field in ("planned_slides", "slides", "video_path"):
                    module.pop(field, None)
                module_fields = ("planned_slides", "slides", "video_path")
        if stage == "thumbnail":
            for field in ("thumbnail_path", "thumbnail_prompt_hash"):
                course.pop(field, None)
            course_fields = ("thumbnail_path", "thumbnail_prompt_hash")
        save_generated_course(
            course_id,
            course,
            course_fields=course_fields,
            module_fields=module_fields,
        )

    def update_wave_stage(stage: str, status: str, error: str = "") -> None:
        def update(course: dict) -> None:
            state = generation_state(course)
            entry = state["stages"].setdefault(stage, {})
            entry.update({"status": status, "updated_at": now_iso()})
            if error:
                entry["error"] = error
            else:
                entry.pop("error", None)

        update_generation_state(course_id, update)

    def reset_stage_checkpoints(stages: tuple[str, ...]) -> None:
        def update(course: dict) -> None:
            state = generation_state(course)
            for stage in stages:
                entry = state["stages"].setdefault(stage, {})
                entry["status"] = "pending"
                for field in ("error", "started_at", "completed_at", "duration_seconds"):
                    entry.pop(field, None)

        update_generation_state(course_id, update)

    def start_wave(stages: tuple[str, ...]) -> None:
        def update(course: dict) -> None:
            state = generation_state(course)
            state.update(
                {
                    "status": "running",
                    "current_checkpoint": "wave_1",
                    "failed_stages": [],
                }
            )
            for key in ("failed_checkpoint", "error", "module_number", "slide_number", "failed_at"):
                state.pop(key, None)
            for stage in stages:
                state["stages"][stage] = {"status": "running", "updated_at": now_iso()}

        update_generation_state(course_id, update)

    def fail_wave(stages: list[str], failures: dict[str, Exception]) -> None:
        def update(course: dict) -> None:
            state = generation_state(course)
            state.update(
                {
                    "status": "failed",
                    "current_checkpoint": "wave_1",
                    "failed_checkpoint": "wave_1",
                    "failed_stages": stages,
                    "error": "; ".join(f"{stage}: {failures[stage]}" for stage in stages),
                    "failed_at": now_iso(),
                }
            )

        update_generation_state(course_id, update)

    def create_thumbnail(*, attempts: int) -> None:
        snapshot = load_course()
        thumbnail_path = generate_course_thumbnail(snapshot, course_id, attempts=attempts)
        if not thumbnail_path:
            raise ValueError("Thumbnail generation returned no file")
        snapshot["thumbnail_path"] = thumbnail_path
        snapshot["thumbnail_prompt_hash"] = course_thumbnail_signature(snapshot)
        save_generated_course(
            course_id,
            snapshot,
            course_fields=("thumbnail_path", "thumbnail_prompt_hash"),
        )

    wave_operations = {
        "thumbnail": lambda: create_thumbnail(attempts=1),
        "quiz": lambda: generate_quiz_for_course(course_id, attempts_per_module=1),
        "notes": lambda: generate_notes_for_course(course_id, attempts_per_module=1),
        "slides": lambda: generate_slides_for_course(course_id),
    }

    if restart_from_blueprint:
        fresh_course = load_course()
        CourseService._invalidate_generated_content(fresh_course)
        repository.save_draft(fresh_course)
        wave_stages = wave_stage_order
    else:
        state = generation_state(load_course())
        if state.get("failed_checkpoint") == "wave_1":
            wave_stages = tuple(
                stage for stage in state.get("failed_stages", []) if stage in wave_stage_order
            )
        elif state.get("failed_checkpoint") == "publish":
            missing_outputs = set(missing_generation_outputs(load_course()))
            wave_stages = tuple(stage for stage in wave_stage_order if stage in missing_outputs)
        else:
            wave_stages = ()
        for stage in wave_stages:
            clear_wave_stage_output(stage)

    if "slides" in wave_stages:
        reset_stage_checkpoints(("html", "scripts", "tts", "video"))

    if wave_stages:
        logger.info(
            "Generation | Wave 1 started | %s",
            ", ".join(wave_stages),
        )
        start_wave(wave_stages)
        wave_started = time.perf_counter()
        failures: dict[str, Exception] = {}
        with ThreadPoolExecutor(max_workers=len(wave_stages), thread_name_prefix="wave-1") as executor:
            futures = {executor.submit(wave_operations[stage]): stage for stage in wave_stages}
            for future in as_completed(futures):
                stage = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    failures[stage] = exc
                    update_wave_stage(stage, "failed", str(exc))
                    logger.warning("Generation | Wave 1 %s queued for recovery | %s", stage, exc)
                else:
                    update_wave_stage(stage, "completed")
                    logger.info("Generation | Wave 1 %s completed", stage)

        if failures:
            logger.info("Generation | Wave 1 recovery started | %s item(s)", len(failures))
            for stage in tuple(failures):
                recovered = False
                for retry_number in (2, 3):
                    clear_wave_stage_output(stage)
                    update_wave_stage(stage, "running")
                    logger.info(
                        "Generation | Recovery started | %s | attempt %s/3",
                        stage,
                        retry_number,
                    )
                    try:
                        wave_operations[stage]()
                    except Exception as exc:
                        failures[stage] = exc
                        update_wave_stage(stage, "failed", str(exc))
                    else:
                        failures.pop(stage, None)
                        update_wave_stage(stage, "completed")
                        recovered = True
                        logger.info("Generation | Recovery %s completed", stage)
                        break
                if not recovered:
                    logger.error("Generation | Recovery %s exhausted", stage)

        if failures:
            failed_stages = [stage for stage in wave_stages if stage in failures]
            fail_wave(failed_stages, failures)
            raise PipelineStageError(
                "wave_1",
                "Wave 1 could not complete: "
                + "; ".join(f"{stage}: {failures[stage]}" for stage in failed_stages),
            )

        logger.info("Generation | Wave 1 completed | %.1fs", time.perf_counter() - wave_started)

    def run_stage(stage: str, operation, attempts: int = 1, output_is_valid=None):
        state = generation_state(load_course())
        if state.get("stages", {}).get(stage, {}).get("status") == "completed":
            if output_is_valid is None or output_is_valid(load_course()):
                logger.info("Generation | %s already completed", stage)
                return None
            logger.warning("Generation | %s marked completed but output is missing; rerunning", stage)
        started = time.perf_counter()
        update_generation_state(course_id, lambda course: mark_stage(course, stage, "running"))
        logger.info("Generation | %s started", stage)
        try:
            result = (
                retry(operation, course_id=course_id, stage=stage, attempts=attempts)
                if attempts > 1
                else operation()
            )
        except Exception as exc:
            failure = exc if isinstance(exc, PipelineStageError) else PipelineStageError(stage, str(exc))

            def fail_stage(course: dict) -> None:
                mark_stage(
                    course,
                    stage,
                    "failed",
                    error=str(failure),
                    module_number=failure.module_number,
                    slide_number=failure.slide_number,
                    elapsed_seconds=time.perf_counter() - started,
                )

            update_generation_state(course_id, fail_stage)
            logger.error("Generation | %s failed | %.1fs | %s", stage, time.perf_counter() - started, failure)
            raise failure

        update_generation_state(
            course_id,
            lambda course: mark_stage(
                course, stage, "completed", elapsed_seconds=time.perf_counter() - started
            ),
        )
        logger.info("Generation | %s completed | %.1fs", stage, time.perf_counter() - started)
        return result

    run_stage(
        "html",
        lambda: compile_slides_for_course(course_id),
        attempts=3,
        output_is_valid=_html_output_complete,
    )

    if not _scripts_output_complete(load_course()):
        stale_course = load_course()
        for module in stale_course.get("modules") or []:
            for slide in module.get("slides") or []:
                slide.pop("audio_path", None)
            module.pop("video_path", None)
        save_generated_course(
            course_id,
            stale_course,
            module_fields=("slides", "video_path"),
        )
        reset_stage_checkpoints(("tts", "video"))
    run_stage(
        "scripts",
        lambda: generate_scripts_for_course(course_id),
        output_is_valid=_scripts_output_complete,
    )

    if not _tts_output_complete(load_course()):
        stale_course = load_course()
        for module in stale_course.get("modules") or []:
            module.pop("video_path", None)
        save_generated_course(course_id, stale_course, module_fields=("video_path",))
        reset_stage_checkpoints(("video",))
    run_stage(
        "tts",
        lambda: generate_tts_for_course(course_id),
        output_is_valid=_tts_output_complete,
    )
    run_stage(
        "video",
        lambda: generate_videos_for_course(course_id),
        attempts=3,
        output_is_valid=_video_output_complete,
    )

    def validate_and_publish() -> None:
        course = load_course()
        missing_outputs = missing_generation_outputs(course)
        if missing_outputs:
            raise PipelineStageError(
                "publish",
                "Course validation failed; missing output: " + ", ".join(missing_outputs),
            )
        sync_clean_database(course_id)

    run_stage("publish", validate_and_publish, attempts=3)
    course = get_course(course_id)
    if course is None:
        raise ValueError(f"Course ID '{course_id}' not found after generation.")
    complete_generation(course, time.perf_counter() - pipeline_start)
    save_course(course, course.get("status", "draft"))
    logger.info("Generation | Course completed | %.1fs", time.perf_counter() - pipeline_start)
    return course
