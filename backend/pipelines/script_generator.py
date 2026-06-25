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
    Attempts to call custom F5-TTS API endpoint on a remote GPU.
    If F5-TTS fails or is offline, falls back to Google's translate_tts endpoint.
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

    # 2. Try advanced F5-TTS engine
    if TTS_ENDPOINT:
        voice = TTS_VOICE
        ref_audio_path = os.path.join(BASE_DIR, "assets", "voices", f"{voice}.wav")
        ref_text = VOICE_TRANSCRIPTS.get(voice, VOICE_TRANSCRIPTS.get("ref_shreya", ""))
        
        # Speed coefficient mapping
        speed = "1.0"
        if "ref_shreya" in voice:
            speed = "0.98"
        elif "ref_srk" in voice:
            speed = "0.88"
        elif "ref_nitin" in voice:
            speed = "0.9"

        if os.path.exists(ref_audio_path) and ref_text:
            print(f"    [TTS] Sending F5-TTS request using voice profile '{voice}' (speed={speed})...")
            data = {
                "gen_text": cleaned_text,
                "ref_text": ref_text,
                "speed": speed
            }
            try:
                with open(ref_audio_path, "rb") as f_ref:
                    files = {
                        "ref_audio": (os.path.basename(ref_audio_path), f_ref, "audio/wav")
                    }
                    response = requests.post(TTS_ENDPOINT, data=data, files=files, timeout=60)
                
                if response.status_code == 200:
                    with open(output_path, "wb") as f_out:
                        f_out.write(response.content)
                    print(f"    [TTS][SUCCESS] Synthesized F5-TTS speech saved to: {output_path}")
                    return True
                else:
                    print(f"    [TTS][WARNING] F5-TTS endpoint returned error {response.status_code}: {response.text}")
            except Exception as e:
                print(f"    [TTS][WARNING] Failed to connect to F5-TTS: {e}")
        else:
            print(f"    [TTS][WARNING] Reference audio or transcript missing for F5-TTS voice '{voice}'")

    # 3. Fallback to Google Translate TTS
    print("    [TTS][FALLBACK] Falling back to robotic Google Translate TTS...")
    sentences = re.split(r'(?<=[.?,;!])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 < 200:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            
            if len(sentence) >= 200:
                words = sentence.split(" ")
                word_chunk = ""
                for word in words:
                    if len(word_chunk) + len(word) + 1 < 200:
                        if word_chunk:
                            word_chunk += " " + word
                        else:
                            word_chunk = word
                    else:
                        chunks.append(word_chunk)
                        word_chunk = word
                if word_chunk:
                    chunks.append(word_chunk)
                current_chunk = ""
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    try:
        with open(output_path, 'wb') as out_f:
            for idx, chunk in enumerate(chunks):
                chunk = chunk.strip()
                if not chunk:
                    continue
                
                if idx > 0:
                    time.sleep(0.3)

                encoded = urllib.parse.quote(chunk)
                url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl={language}&client=tw-ob&q={encoded}"
                
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                out_f.write(response.content)
        return True
    except Exception as e:
        print(f"    [TTS][ERROR] Google Translate fallback failed: {e}")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
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
