"""Generate learner-facing module notes as a first-class pipeline stage."""

from pydantic import BaseModel

from pipelines.config import get_llm_endpoint, safe_chat_completion
from pipelines.pipeline_runtime import retry


class ModuleSummarySchema(BaseModel):
    notes: list[str]


def generate_summary_for_module(module: dict, course_id: str = "unknown") -> str:
    """Return a short, factual set of learner notes for one module."""
    source = module.get("text", "").strip()
    if not source:
        raise ValueError(f"Module '{module.get('title', '')}' has no source text; notes generation cannot continue.")
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

    try:
        return retry(
            generate_once, course_id=course_id, stage="notes", attempts=3,
            module_number=module.get("module_number"),
        )
    except Exception as exc:
        print(f"  [SUMMARY][WARNING] Could not generate notes for '{module.get('title', '')}': {exc}")
        raise
