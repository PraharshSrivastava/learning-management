"""Coordinate generation state, retries, recovery, orchestration, and publishing."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from filelock import FileLock

from app.core.settings import settings
from app.core.storage import resolve_public_asset_path
from app.repositories.courses import (
    CourseRepository,
    delete_published_course,
    get_all_courses,
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
    course = CourseRepository().get_draft(course_id)
    if course is None:
        raise ValueError(f"Course '{course_id}' not found in courses database.")
    return course

def _merge_generated_course(latest: dict, incoming: dict) -> dict:
    merged = {**latest, **incoming}

    latest_state = latest.get("generation")
    if isinstance(latest_state, dict):
        # Worker output must never overwrite coordinator-owned checkpoint state.
        merged["generation"] = latest_state

    latest_modules = latest.get("modules", [])
    incoming_modules = incoming.get("modules", [])
    if isinstance(latest_modules, list) and isinstance(incoming_modules, list):
        modules = []
        max_len = max(len(latest_modules), len(incoming_modules))
        for index in range(max_len):
            latest_module = latest_modules[index] if index < len(latest_modules) else {}
            incoming_module = incoming_modules[index] if index < len(incoming_modules) else {}
            if isinstance(latest_module, dict) and isinstance(incoming_module, dict):
                modules.append({**latest_module, **incoming_module})
            else:
                modules.append(incoming_module or latest_module)
        merged["modules"] = modules

    return merged

def save_generated_course(course_id: str, course: dict) -> None:
    if course.get("id") != course_id:
        raise ValueError("Cannot save generated content for a different course")
    repository = CourseRepository()
    with FileLock(f"{database_path()}.{course_id}.generation.lock", timeout=60):
        latest = repository.get_draft(course_id)
        repository.save_draft(
            _merge_generated_course(latest, course) if latest else course
        )


def update_generation_state(course_id: str, update: Callable[[dict], None]) -> dict:
    """Apply one coordinator-owned checkpoint transition to the latest course state."""
    repository = CourseRepository()
    with FileLock(f"{database_path()}.{course_id}.generation.lock", timeout=60):
        course = repository.get_draft(course_id)
        if course is None:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")
        update(course)
        repository.save_draft(course)
        return course

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

def is_course_generation_complete(course: dict) -> bool:
    from app.generation.thumbnails import course_thumbnail_signature

    modules = course.get("modules", [])
    if not modules:
        return False

    thumbnail_path = course.get("thumbnail") or course.get("thumbnail_url")
    if not thumbnail_path:
        return False
    if course.get("thumbnail_prompt_hash") != course_thumbnail_signature(course):
        return False

    for module in modules:
        slides = module.get("slides", []) or []
        if not slides or not str(module.get("notes") or "").strip():
            return False
        for slide in slides:
            audio_path = str(slide.get("audio_path") or "").strip()
            if (
                not str(slide.get("script") or "").strip()
                or not audio_path
                or not resolve_public_asset_path(audio_path, settings).is_file()
                or resolve_public_asset_path(audio_path, settings).stat().st_size == 0
            ):
                return False
        video_path = str(module.get("video_path") or "").strip()
        if (
            not video_path
            or not resolve_public_asset_path(video_path, settings).is_file()
            or resolve_public_asset_path(video_path, settings).stat().st_size == 0
        ):
            return False
        try:
            num_questions = int(module.get("num_questions", 0))
        except (TypeError, ValueError):
            num_questions = 0
        if num_questions <= 0:
            continue
        quiz = module.get("quiz")
        if not quiz or not isinstance(quiz, dict) or not quiz.get("questions"):
            return False

    return True

def sync_clean_database(course_id: str | None = None):
    """Synchronize published courses while serializing concurrent publish operations."""
    with FileLock(f"{database_path()}.publish.lock", timeout=30):
        return _sync_clean_database(course_id)

def _sync_clean_database(target_course_id: str | None = None):
    """
    Convert already-complete draft courses into the employee-facing published shape.

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

    clean_courses = []
    dirty_draft_course_ids = set()
    skipped_courses = []

    for course in draft_courses:
        course_id = course.get("id", str(uuid.uuid4()))
        if "id" not in course:
            course["id"] = course_id
            dirty_draft_course_ids.add(course_id)

        if not is_course_generation_complete(course):
            skipped_courses.append(course_id)
            continue

        clean_modules = []
        for m in course.get("modules", []):
            clean_quiz = []
            draft_quiz = m.get("quiz", {})
            draft_questions = (
                draft_quiz.get("questions", []) if isinstance(draft_quiz, dict) else []
            )

            for q in draft_questions:
                # Retrieve or generate a persistent UUID for each question
                q_id = q.get("question_id")
                if not q_id:
                    q_id = str(uuid.uuid4())
                    q["question_id"] = q_id
                    dirty_draft_course_ids.add(course_id)

                # Options in draft: [{"key": "A", "text": "Opt A"}, ...]
                # Options in clean: ["Opt A", "Opt B", "Opt C", "Opt D"]
                draft_opts = q.get("options", [])
                # Ensure options are sorted by key (A, B, C, D)
                sorted_opts = sorted(
                    draft_opts, key=lambda o: str(o.get("key", "")).strip().upper()
                )
                clean_opts = [o.get("text", "") for o in sorted_opts]

                clean_quiz.append(
                    {
                        "question_id": q_id,
                        "question": q.get("question_text", ""),
                        "options": clean_opts,
                        "correct": q.get("correct_option", "A"),
                        "explanation": q.get("explanation", ""),
                    }
                )

            clean_modules.append(
                {
                    "module_number": m.get("module_number", 1),
                    "title": m.get("title", ""),
                    "notes": m.get("notes", "") or "",
                    "video_url": m.get("video_path", "") or "",
                    "quiz": clean_quiz,
                    "pass_mark": 0.67,
                }
            )

        thumbnail_path = course.get("thumbnail") or course.get("thumbnail_url")

        clean_courses.append(
            {
                "id": f"published:{course_id}",
                "course_id": course_id,
                "title": course.get("course_name", ""),
                "course_description": course.get("course_description", ""),
                "created_at": course.get("created_at", 0),
                "modules": clean_modules,
                "images": course.get("images", []),
                "thumbnail": thumbnail_path or "",
                "thumbnail_url": thumbnail_path or "",
                "thumbnail_prompt_hash": course.get("thumbnail_prompt_hash", "")
                if thumbnail_path
                else "",
            }
        )

    logger.info(
        f"[EXPORTER] Prepared {len(clean_courses)} published course(s) "
        f"from {len(draft_courses)} draft course(s); skipped incomplete={len(skipped_courses)}"
    )
    if skipped_courses:
        preview = ", ".join(skipped_courses[:5])
        suffix = "..." if len(skipped_courses) > 5 else ""
        logger.info("publish_sync_skipped_incomplete course_ids=%s", f"{preview}{suffix}")

    # Preserve only draft rows whose IDs changed; do not overwrite other jobs.
    if dirty_draft_course_ids:
        write_start = time.perf_counter()
        for course in draft_courses:
            if course["id"] in dirty_draft_course_ids:
                save_course(course, "draft")
        logger.info(
            "publish_draft_metadata_saved count=%s elapsed_seconds=%.1f",
            len(dirty_draft_course_ids),
            time.perf_counter() - write_start,
        )

    # Write the clean employee-facing courses to SQLite published rows.
    write_start = time.perf_counter()
    if target_course_id:
        if not clean_courses:
            raise PipelineStageError(
                "publish",
                f"Course '{target_course_id}' is not complete enough to publish.",
            )
        delete_published_course(target_course_id)
        save_course(clean_courses[0], "published")
    else:
        save_all_courses(clean_courses, "published")
    logger.info(
        "publish_rows_synchronized count=%s db=%s elapsed_seconds=%.1f",
        len(clean_courses),
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
        repository = CourseRepository()
        for course in repository.list_drafts():
            state = generation_state(course)
            if state.get("status") != "running":
                continue
            checkpoint = state.get("current_checkpoint") or "pipeline"
            if checkpoint == "wave_1":
                failed_stages = [
                    stage
                    for stage, entry in state.get("stages", {}).items()
                    if isinstance(entry, dict) and entry.get("status") == "running"
                ]
                state.update(
                    {
                        "status": "failed",
                        "current_checkpoint": "wave_1",
                        "failed_checkpoint": "wave_1",
                        "failed_stages": failed_stages,
                        "error": "Generation interrupted because the backend process restarted. Continue Wave 1.",
                    }
                )
            else:
                mark_stage(
                    course,
                    checkpoint,
                    "failed",
                    error="Generation interrupted because the backend process restarted. Continue from this checkpoint.",
                )
            log_event(course.get("id", "unknown"), checkpoint, "interrupted_by_restart")
            repository.save_draft(course)
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
        course = repository.get_draft(course_id)
        if course is None:
            raise ValueError(f"Course ID '{course_id}' not found in courses database.")
        return course

    def clear_wave_stage_output(stage: str) -> None:
        course = load_course()
        for module in course.get("modules", []):
            if stage == "quiz":
                module.pop("quiz", None)
                module.pop("quiz_generation_error", None)
            elif stage == "notes":
                module.pop("notes", None)
            elif stage == "slides":
                for field in ("planned_slides", "slides", "video_path"):
                    module.pop(field, None)
        if stage == "thumbnail":
            for field in ("thumbnail", "thumbnail_url", "thumbnail_prompt_hash"):
                course.pop(field, None)
        save_generated_course(course_id, course)

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
        snapshot["thumbnail"] = thumbnail_path
        snapshot["thumbnail_url"] = thumbnail_path
        snapshot["thumbnail_prompt_hash"] = course_thumbnail_signature(snapshot)
        save_generated_course(course_id, snapshot)

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
        wave_stages = (
            tuple(stage for stage in state.get("failed_stages", []) if stage in wave_stage_order)
            if state.get("failed_checkpoint") == "wave_1"
            else ()
        )
        for stage in wave_stages:
            clear_wave_stage_output(stage)

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

    def run_stage(stage: str, operation, attempts: int = 1):
        state = generation_state(load_course())
        if state.get("stages", {}).get(stage, {}).get("status") == "completed":
            logger.info("Generation | %s already completed", stage)
            return None
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

    run_stage("html", lambda: compile_slides_for_course(course_id), attempts=3)
    run_stage("scripts", lambda: generate_scripts_for_course(course_id))
    run_stage("tts", lambda: generate_tts_for_course(course_id))
    run_stage("video", lambda: generate_videos_for_course(course_id), attempts=3)

    def validate_and_publish() -> None:
        if not is_course_generation_complete(load_course()):
            raise PipelineStageError(
                "publish",
                "Course validation failed: required quiz, slides, scripts, notes, audio, video, or thumbnail output is missing.",
            )
        sync_clean_database(course_id)

    run_stage("publish", validate_and_publish, attempts=3)
    course = load_course()
    complete_generation(course, time.perf_counter() - pipeline_start)
    repository.save_draft(course)
    logger.info("Generation | Course completed | %.1fs", time.perf_counter() - pipeline_start)
    return course
