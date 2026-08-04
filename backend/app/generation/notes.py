"""Generate and persist concise learner-facing module notes."""

import copy
import time

from app.core.logging import generation_logger
from app.core.providers import get_llm_endpoint, safe_chat_completion
from app.generation.parallel import default_llm_workers, run_parallel_stage_items
from app.generation.runtime import (
    load_course_for_generation,
    log_event,
    retry,
    save_generated_course,
)
from app.schemas.generation.notes import ModuleSummarySchema

logger = generation_logger(__name__)

def generate_summary_for_module(
    module: dict, course_id: str = "unknown", *, attempts: int = 3
) -> str:
    """Return a short, factual set of learner notes for one module."""
    source = module.get("text", "").strip()
    if not source:
        raise ValueError(
            f"Module '{module.get('title', '')}' has no source text; notes generation cannot continue."
        )

    def generate_once():
        base_url, model_name = get_llm_endpoint("scripts")
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Create concise learner notes for a training module. "
                        "Return 3 to 6 factual bullet points. Do not introduce "
                        "facts not present in the source."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Module: {module.get('title', '')}\n\nSource:\n{source}",
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ModuleSummarySchema",
                    "schema": ModuleSummarySchema.model_json_schema(),
                },
            },
            course_id=course_id,
            stage="notes",
            module_number=module.get("module_number"),
            attempts=1,
        )
        parsed = ModuleSummarySchema.model_validate_json(response.choices[0].message.content)
        notes = [note.strip() for note in parsed.notes if note.strip()]
        if not notes:
            raise ValueError("LLM returned empty learner notes")
        return "\n".join(f"- {note}" for note in notes)

    return retry(
        generate_once,
        course_id=course_id,
        stage="notes",
        attempts=attempts,
        module_number=module.get("module_number"),
    )

def generate_notes_for_course(course_id: str, *, attempts_per_module: int = 3) -> dict:
    course = load_course_for_generation(course_id)
    modules = course.get("modules", [])

    def generate_for_module(item: tuple[int, dict]) -> tuple[int, dict]:
        index, module = item
        module = copy.deepcopy(module)
        module_number = module.get("module_number", index + 1)
        started = time.perf_counter()
        log_event(course_id, "notes", "module_started", module=module_number)
        module["notes"] = generate_summary_for_module(
            module, course_id=course_id, attempts=attempts_per_module
        )
        log_event(
            course_id,
            "notes",
            "module_completed",
            module=module_number,
            elapsed=f"{time.perf_counter() - started:.1f}s",
        )
        return index, module

    results = run_parallel_stage_items(
        course_id=course_id,
        stage="notes",
        items=list(enumerate(modules)),
        worker_count=default_llm_workers(len(modules)),
        item_label=lambda item: {"module": item[1].get("module_number", item[0] + 1)},
        operation=generate_for_module,
    )
    for index, module in results:
        modules[index] = module
    course["modules"] = modules
    save_generated_course(course_id, course)
    return course
