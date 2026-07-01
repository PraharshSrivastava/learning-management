import os
import json
import urllib.parse
import re
import time
import requests
from typing import List, Dict, Any
from pydantic import BaseModel

from pipelines.config import get_llm_client, safe_chat_completion, BASE_DIR, TTS_ENDPOINT, TTS_VOICE, VOICE_TRANSCRIPTS
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
    Builds the user prompt showing the raw text, the slide structure with layout details,
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
        layout = slide.get("layout_type", "bullets")
        layout_str = str(layout).lower().split(".")[-1]
        lines.append(f"    [SLIDE {si + 1}] Title: {slide.get('slide_title', '')}")
        lines.append(f"      Layout: {layout_str.upper()}")
        
        if layout_str == "concept" and slide.get("concept_data"):
            data = slide["concept_data"]
            lines.append(f"      Core Term: {data.get('core_term', '')}")
            lines.append(f"      Definition: {data.get('definition', '')}")
            takeaways = data.get("key_takeaways", [])
            for t in takeaways:
                lines.append(f"        - Takeaway: {t}")
        elif layout_str == "steps" and slide.get("steps_data"):
            data = slide["steps_data"]
            for step in data.get("steps", []):
                lines.append(f"      - Step {step.get('step_number')}: {step.get('title', '')} - {step.get('description', '')}")
        elif layout_str == "comparison" and slide.get("comparison_data"):
            data = slide["comparison_data"]
            lines.append(f"      Left Column: {data.get('left_column_title', '')}")
            for p in data.get("left_column_points", []):
                lines.append(f"        - {p}")
            lines.append(f"      Right Column: {data.get('right_column_title', '')}")
            for p in data.get("right_column_points", []):
                lines.append(f"        - {p}")
        elif layout_str == "grid" and slide.get("grid_data"):
            data = slide["grid_data"]
            for col in data.get("columns", []):
                lines.append(f"      - Column '{col.get('header', '')}': {col.get('content', '')}")
        else:
            # Fallback to standard bullets
            bullets = slide.get("bullets_data")
            if not bullets:
                bullets = slide.get("bullets", [])
            for b in bullets:
                b_text = b if isinstance(b, str) else b.get("text", "")
                if b_text:
                    lines.append(f"      - {b_text}")

    lines.append("")
    lines.append("Please output the ModuleScriptSchema JSON containing the spoken script for each slide in order.")
    return "\n".join(lines)


# -------------------------------------------------------
# Speech Synthesis (TTS) Helper
# -------------------------------------------------------

def synthesize_speech_for_slide(text: str, output_path: str, language: str = 'en') -> bool:
    """
    Synthesize text into a high-quality speech file.
    Calls the custom Qwen-TTS clone API endpoint.
    """
    text = text.strip()
    if not text:
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 1. Clean script text for TTS engine
    cleaned_text = re.sub(r'<[^>]+>', '', text)
    cleaned_text = cleaned_text.replace('\\', "'").replace('"', "'")
    cleaned_text = re.sub(r'\b[A-Z]{2,}\b', lambda match: ' '.join(match.group(0)), cleaned_text)
    cleaned_text = cleaned_text.replace("Ltd.", "Limited").replace("Rs ", "Rupees ")

    # 2. Try Qwen-TTS clone engine
    if TTS_ENDPOINT:
        voice = TTS_VOICE
        clone_url = f"{TTS_ENDPOINT.rstrip('/')}/clone"
        payload = {
            "voice_name": voice,
            "text": cleaned_text,
            "language": "English",
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 50
        }
        try:
            print(f"    [TTS] Sending Qwen-TTS clone request using voice '{voice}'...")
            response = requests.post(
                clone_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=600
            )
            
            if response.status_code == 200:
                with open(output_path, "wb") as f_out:
                    f_out.write(response.content)
                print(f"    [TTS][SUCCESS] Synthesized Qwen-TTS speech saved to: {output_path}")
                return True
            else:
                print(f"    [TTS][ERROR] Qwen-TTS endpoint returned error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"    [TTS][ERROR] Failed to connect to Qwen-TTS: {e}")

    return False


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
        client, model_name = get_llm_client("scripts")
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
        print(f"  [SCRIPT] LLM successfully returned {len(parsed.slides)} slide scripts.")

        # Match and merge back positionally
        for si, slide in enumerate(slides):
            if si >= len(parsed.slides):
                print(f"    [WARNING] No script slide at index {si}. Using fallback empty script.")
                slide["script"] = ""
                continue
            slide["script"] = parsed.slides[si].script.strip()

    except Exception as e:
        print(f"  [SCRIPT][ERROR] LLM script generation failed for module '{module.get('title')}': {e}")
        # Inject empty fallback script for all slides to prevent frontend errors
        for slide in slides:
            if "script" not in slide:
                slide["script"] = ""

    return module
