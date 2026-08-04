"""Generate and validate module quizzes."""

import copy
import time
from typing import Any, Dict

from pydantic import ValidationError

from app.core.exceptions import ProviderError
from app.core.logging import generation_logger
from app.core.providers import get_llm_endpoint, safe_chat_completion
from app.generation.parallel import default_llm_workers, run_parallel_stage_items
from app.generation.prompts import QUIZ_GENERATION_PROMPT
from app.generation.runtime import (
    PipelineStageError,
    load_course_for_generation,
    log_event,
    save_generated_course,
)
from app.schemas.generation.quiz import ModuleQuiz

QUIZ_GENERATION_ATTEMPTS = 3


def _module_has_valid_quiz(module: dict, num_q: int) -> bool:
    existing_questions = (
        module.get("quiz", {}).get("questions", []) if isinstance(module.get("quiz"), dict) else []
    )
    if len(existing_questions) != num_q:
        return False
    return all(
        isinstance(question, dict)
        and {
            str(option.get("key", "")).strip().upper()
            for option in question.get("options", [])
        }
        == {"A", "B", "C", "D"}
        and str(question.get("correct_option", "")).strip().upper() in {"A", "B", "C", "D"}
        for question in existing_questions
    )


def _generate_quiz_for_module(
    *,
    course_id: str,
    module: dict,
    index: int,
    difficulty: str,
    base_url: str,
    model_name: str,
    json_schema: dict,
    attempts: int,
) -> tuple[int, dict]:
    module = copy.deepcopy(module)
    started = time.perf_counter()
    try:
        num_q = int(module.get("num_questions", 0))
    except (ValueError, TypeError):
        num_q = 0

    module_number = module.get("module_number", index + 1)
    module_title = module.get("title", f"Module {index + 1}")
    module_text = module.get("text", "")
    log_event(course_id, "quiz", "module_started", module=module_number)

    if num_q <= 0:
        logger.info(
            "module_quiz_generation_skipped module_title=%s question_count=%s",
            module_title,
            num_q,
        )
        module.pop("quiz", None)
        return index, module

    if not module_text.strip():
        message = f"Module '{module_title}' has no source text; quiz generation cannot continue."
        logger.error("quiz_generation_validation_failed message=%s", message)
        module["quiz_generation_error"] = message
        raise RuntimeError(message)

    if _module_has_valid_quiz(module, num_q):
        logger.info(
            f"  [QUIZ] Module '{module_title}' already has a valid quiz; skipping checkpoint resume work."
        )
        return index, module

    logger.info(
        f"  Generating quiz for Module '{module_title}' ({num_q} questions, difficulty={difficulty})..."
    )

    user_message = (
        f"Generate a quiz with exactly {num_q} multiple choice questions.\n\n"
        f"Difficulty Level: {difficulty}\n"
        f'Module Title: "{module_title}"\n\n'
        f"MODULE CONTENT:\n"
        f"{module_text}\n"
    )

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            if attempt > 1:
                logger.info(
                    "module_quiz_generation_retry module_title=%s attempt=%s/%s",
                    module_title,
                    attempt,
                    attempts,
                )

            response = safe_chat_completion(
                base_url=base_url,
                model=model_name,
                messages=[
                    {"role": "system", "content": str(QUIZ_GENERATION_PROMPT)},
                    {"role": "user", "content": user_message},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ModuleQuiz",
                        "schema": json_schema,
                    },
                },
                temperature=0.2,
                default_max_tokens=4096,
                course_id=course_id,
                stage="quiz",
                module_number=module_number,
                attempts=1,
            )

            parsed = ModuleQuiz.model_validate_json(response.choices[0].message.content)
            if len(parsed.questions) != num_q:
                raise ValueError(f"Expected {num_q} questions, received {len(parsed.questions)}")
            for question in parsed.questions:
                keys = {option.key.strip().upper() for option in question.options}
                if keys != {"A", "B", "C", "D"} or question.correct_option.strip().upper() not in keys:
                    raise ValueError("Quiz question has invalid A-D options or correct answer")

            module["quiz"] = parsed.model_dump()
            module.pop("quiz_generation_error", None)
            logger.info("module_quiz_generation_completed question_count=%s", len(parsed.questions))
            log_event(
                course_id,
                "quiz",
                "module_completed",
                module=module_number,
                elapsed=f"{time.perf_counter() - started:.1f}s",
            )
            return index, module

        except (
            PipelineStageError,
            ProviderError,
            ValidationError,
            ValueError,
            KeyError,
            IndexError,
        ) as e:
            last_error = e
            logger.warning(
                "module_quiz_generation_attempt_failed module_title=%s attempt=%s/%s error=%s",
                module_title,
                attempt,
                attempts,
                e,
            )

    logger.info(
        "module_quiz_generation_failed module_title=%s attempts=%s",
        module_title,
        attempts,
    )
    module["quiz_generation_error"] = str(last_error) if last_error else "Unknown quiz generation error"
    raise RuntimeError(
        f"Quiz generation failed for module '{module_title}': {module['quiz_generation_error']}"
    )


def generate_quiz_for_course(
    course_id: str, *, attempts_per_module: int = QUIZ_GENERATION_ATTEMPTS
) -> Dict[str, Any]:
    """
    Generates quizzes for each module in a course if `num_questions` is > 0.
    Persists the updated course and returns its validated record.
    """
    logger.info("course_quiz_generation_started course_id=%s", course_id)

    course = load_course_for_generation(course_id)
    modules = course.get("modules", [])
    difficulty = course.get("course_difficulty", "Easy").strip()

    if not modules:
        raise ValueError("This course has no modules. Save a blueprint first.")

    base_url, model_name = get_llm_endpoint("quiz")
    json_schema = ModuleQuiz.model_json_schema()

    results = run_parallel_stage_items(
        course_id=course_id,
        stage="quiz",
        items=list(enumerate(modules)),
        worker_count=default_llm_workers(len(modules)),
        item_label=lambda item: {"module": item[1].get("module_number", item[0] + 1)},
        operation=lambda item: _generate_quiz_for_module(
            course_id=course_id,
            module=item[1],
            index=item[0],
            difficulty=difficulty,
            base_url=base_url,
            model_name=model_name,
            json_schema=json_schema,
            attempts=attempts_per_module,
        ),
    )
    for index, module in results:
        modules[index] = module

    course["modules"] = modules
    save_generated_course(course_id, course)

    logger.info(
        "course_quiz_generation_completed course_id=%s course_name=%s",
        course_id,
        course.get("course_name"),
    )
    return course


logger = generation_logger(__name__)
