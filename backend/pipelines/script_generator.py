import json
import requests
from typing import List
from pydantic import BaseModel

from pipelines.config import get_llm_client, safe_chat_completion
from pipelines.prompts import SCRIPT_GENERATION_PROMPT


# -------------------------------------------------------
# Pydantic Response Schema
# Positional lists — order matches input exactly
# -------------------------------------------------------

class SlideScriptSchema(BaseModel):
    script: str


class ModuleScriptSchema(BaseModel):
    slides: List[SlideScriptSchema]


# -------------------------------------------------------
# Prompt Builder
# -------------------------------------------------------

def _build_script_prompt(module_text: str, module: dict, previous_script: str = None) -> str:
    """
    Builds the user prompt showing the raw text, the slide structure,
    and the optional previous module script for transition continuity.
    """
    lines = []

    if previous_script:
        lines.append("=== NARRATION SCRIPT FROM PREVIOUS MODULE (FOR CONTINUITY) ===")
        lines.append(previous_script)
        lines.append("==============================================================")
        lines.append("")

    lines.append(f"=== MODULE TITLE: {module.get('title', '')} ===")
    lines.append("")
    lines.append("=== RAW MODULE TEXT CONTENT (FOR REFERENCE DETAILS) ===")
    lines.append(module_text)
    lines.append("=======================================================")
    lines.append("")
    lines.append("=== CURRENT MODULE OUTLINE (SLIDES) ===")

    slides = module.get("slides", [])
    for si, slide in enumerate(slides):
        lines.append(f"    [SLIDE {si + 1}] Title: {slide.get('slide_title', '')}")
        for bi, bullet in enumerate(slide.get("bullets", [])):
            lines.append(f"      - {bullet.get('text', '')}")

    lines.append("")
    lines.append("Please output the ModuleScriptSchema JSON containing the spoken script for each slide in order.")
    return "\n".join(lines)


# -------------------------------------------------------
# Core Function — generate script for one module
# -------------------------------------------------------

def generate_scripts_for_module(
    module_text: str,
    module: dict,
    previous_script: str = None
) -> dict:
    """
    Call the LLM to generate slide narration scripts for a single module.
    Returns the updated module dict with "script" added to each slide.
    """
    slides = module.get("slides", [])
    if not slides:
        print(f"  [SCRIPT] No slides found for module '{module.get('title')}' — skipping script generation.")
        return module

    total_slides = len(slides)
    print(f"  [SCRIPT] Starting script generation: '{module.get('title')}', {total_slides} slides.")

    json_schema = ModuleScriptSchema.model_json_schema()
    user_message = _build_script_prompt(module_text, module, previous_script)

    try:
        client, model_name = get_llm_client()
        response = safe_chat_completion(
            client=client,
            model=model_name,
            messages=[
                {"role": "system", "content": SCRIPT_GENERATION_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ModuleScriptSchema",
                    "schema": json_schema,
                },
            },
            temperature=0.2,
            default_max_tokens=2048,
        )
        raw_content = response.choices[0].message.content

        parsed = ModuleScriptSchema.model_validate_json(raw_content)
        print(f"  [SCRIPT] LLM successfully returned {len(parsed.slides)} slides.")

        # Match and merge back positionally
        for si, slide in enumerate(slides):
            if si >= len(parsed.slides):
                print(f"    [WARNING] No script slide at index {si}. Using fallback empty script.")
                slide["script"] = ""
                continue
            slide["script"] = parsed.slides[si].script.strip()

    except Exception as e:
        print(f"  [SCRIPT][ERROR] LLM script generation failed for module '{module.get('title')}': {e}")
        # Inject empty fallback script for all slides to prevent front-end or save errors
        for slide in slides:
            if "script" not in slide:
                slide["script"] = ""

    return module
