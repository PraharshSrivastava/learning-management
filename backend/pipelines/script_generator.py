import os
import json
import re
import subprocess
import requests
import imageio_ffmpeg
from typing import List
from pydantic import BaseModel, Field, create_model

from pipelines.config import get_llm_endpoint, safe_chat_completion, BASE_DIR, TTS_ENDPOINT, TTS_VOICE, TTS_TEMPERATURE, TTS_SPEED
from pipelines.prompts import SCRIPT_GENERATION_PROMPT
from pipelines.pipeline_runtime import retry


class SlideScriptSchema(BaseModel):
    script: str


class ModuleScriptSchema(BaseModel):
    slides: List[SlideScriptSchema]


def _batch_script_schema(slide_count: int):
    """Return a response schema that requires exactly one script per batch slide."""
    return create_model(
        f"BatchScriptSchema{slide_count}",
        slides=(List[SlideScriptSchema], Field(min_length=slide_count, max_length=slide_count)),
    )


def _build_script_prompt(
    module_text: str,
    module: dict,
    previous_script: str = None,
    course_context: dict = None,
    slide_number_offset: int = 0,
    batch_number: int = 1,
    total_batches: int = 1,
) -> str:
    """Build a narration prompt for one ordered batch of a module's slides."""
    lines = []

    if previous_script:
        lines.extend([
            "=== PRIOR NARRATION (FOR CONTINUITY) ===",
            previous_script,
            "==============================================================",
            "",
        ])

    if course_context:
        lines.extend([
            "=== COURSE AND MODULE CONTEXT ===",
            f"Course Name: {course_context.get('course_name', '')}",
            f"Module Number: {course_context.get('module_number', '')} of {course_context.get('total_modules', '')}",
            f"Current Module Title: {course_context.get('module_title', module.get('title', ''))}",
            f"Is First Module: {course_context.get('is_first_module', False)}",
            f"Is Final Module: {course_context.get('is_last_module', False)}",
            "Use this context to write the module cover narration and the final slide wrap-up.",
            "=================================",
            "",
        ])

    lines.extend([
        f"=== MODULE TITLE: {module.get('title', '')} ===",
        "",
        "=== SUPPORTING SOURCE TEXT ===",
        "Use this to enrich the slide narration. Do not narrate it directly or follow it ahead of the slide order.",
        module_text,
        "==============================",
        "",
        "=== SLIDE-BY-SLIDE PRESENTATION PLAN ===",
        "Follow this slide order exactly. Each script must sound like the presenter is discussing the slide while it is visible.",
    ])

    if total_batches > 1:
        first_slide = slide_number_offset + 1
        last_slide = slide_number_offset + len(module.get("slides", []))
        lines.extend([
            "",
            "=== BATCH INSTRUCTIONS ===",
            f"This is batch {batch_number} of {total_batches} for this module.",
            f"Generate only slides {first_slide} through {last_slide}.",
            f"Return exactly {len(module.get('slides', []))} scripts: one per listed slide, in that order.",
            "Never return scripts for any other slide in this module.",
            "Do not add a module wrap-up unless this is the final batch.",
            "==========================",
        ])

    for index, slide in enumerate(module.get("slides", []), start=slide_number_offset + 1):
        layout = str(slide.get("layout_type", "bullets")).lower().split(".")[-1]
        if slide.get("is_cover_slide") or layout == "cover":
            lines.extend([
                f"    [SLIDE {index}] MODULE COVER",
                f"      Course: {slide.get('course_name') or (course_context or {}).get('course_name', '')}",
                f"      Module Title: {slide.get('slide_title') or slide.get('title') or module.get('title', '')}",
                "      Purpose: Introduce this module before content begins. Do not teach detailed content on this cover slide.",
            ])
        else:
            lines.extend([
                f"    [SLIDE {index}] CONTENT SLIDE",
                json.dumps(slide, indent=6, ensure_ascii=True),
            ])

    lines.append("")
    if total_batches > 1:
        lines.append(
            f"Output JSON with exactly {len(module.get('slides', []))} items in `slides`, matching only this batch."
        )
    else:
        lines.append("Please output the ModuleScriptSchema JSON containing the spoken script for each slide in order.")
    return "\n".join(lines)


def _apply_tts_speed(output_path: str) -> bool:
    if abs(TTS_SPEED - 1.0) < 0.001:
        return True
    if TTS_SPEED <= 0:
        print(f"    [TTS][WARNING] Invalid TTS_SPEED={TTS_SPEED}; keeping original audio.")
        return True

    temp_path = f"{output_path}.speed.wav"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", output_path,
        "-filter:a", f"atempo={TTS_SPEED}", temp_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, errors="ignore")
    if result.returncode != 0:
        print(f"    [TTS][WARNING] Could not apply TTS_SPEED={TTS_SPEED}: {result.stderr}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
    os.replace(temp_path, output_path)
    print(f"    [TTS] Applied playback speed factor {TTS_SPEED}.")
    return True


def synthesize_speech_for_slide(text: str, output_path: str, language: str = "English") -> bool:
    text = text.strip()
    if not text:
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cleaned_text = re.sub(r"<[^>]+>", "", text)
    cleaned_text = cleaned_text.replace("\\", "'").replace('"', "'")
    cleaned_text = re.sub(r"\b[A-Z]{2,}\b", lambda match: " ".join(match.group(0)), cleaned_text)
    cleaned_text = cleaned_text.replace("Ltd.", "Limited").replace("Rs ", "Rupees ")

    if not TTS_ENDPOINT:
        return False

    # Sana is an uploaded clone registered directly on the RunPod TTS service.
    voice = TTS_VOICE
    tts_url = f"{TTS_ENDPOINT.rstrip('/')}/clone"
    payload = {
        "voice_name": voice,
        "text": cleaned_text,
        "language": language,
        "temperature": TTS_TEMPERATURE,
        "top_p": 0.95,
        "top_k": 50,
    }
    headers = {"Content-Type": "application/json"}

    try:
        print(f"    [TTS] Sending TTS request using voice '{voice}'...")
        response = requests.post(tts_url, json=payload, headers=headers, timeout=600)
        if response.status_code != 200:
            print(f"    [TTS][ERROR] TTS endpoint returned error {response.status_code}: {response.text}")
            return False
        with open(output_path, "wb") as audio_file:
            audio_file.write(response.content)
        _apply_tts_speed(output_path)
        print(f"    [TTS][SUCCESS] Synthesized Qwen-TTS speech saved to: {output_path}")
        return True
    except Exception as exc:
        print(f"    [TTS][ERROR] Failed to connect to TTS endpoint: {exc}")
        return False


def generate_scripts_for_module(
    module_text: str,
    module: dict,
    previous_script: str = None,
    course_context: dict = None,
) -> dict:
    """Generate narration in batches of up to five slides, preserving continuity."""
    slides = module.get("slides", [])
    if not slides:
        raise ValueError(f"No slides found for module '{module.get('title')}'; narration script generation cannot continue.")

    print(f"  [SCRIPT] Starting script generation: '{module.get('title')}', {len(slides)} slides.")
    batch_size = 5
    slide_batches = [slides[index:index + batch_size] for index in range(0, len(slides), batch_size)]
    generated_scripts: List[SlideScriptSchema] = []
    previous_batch_narration = previous_script

    for batch_index, batch_slides in enumerate(slide_batches):
        batch_number = batch_index + 1
        batch_module = dict(module)
        batch_module["slides"] = batch_slides
        batch_schema = _batch_script_schema(len(batch_slides))
        batch_context = dict(course_context or {})
        if len(slide_batches) > 1:
            batch_context["is_first_module"] = bool(batch_context.get("is_first_module")) and batch_index == 0
            batch_context["is_last_module"] = bool(batch_context.get("is_last_module")) and batch_index == len(slide_batches) - 1

        print(f"  [SCRIPT] Generating batch {batch_number}/{len(slide_batches)} ({len(batch_slides)} slides).")

        def generate_once():
            base_url, model_name = get_llm_endpoint("scripts")
            response = safe_chat_completion(
                base_url=base_url,
                model=model_name,
                messages=[
                    {"role": "system", "content": SCRIPT_GENERATION_PROMPT},
                    {"role": "user", "content": _build_script_prompt(
                        module_text,
                        batch_module,
                        previous_batch_narration,
                        batch_context,
                        slide_number_offset=batch_index * batch_size,
                        batch_number=batch_number,
                        total_batches=len(slide_batches),
                    )},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ModuleScriptSchema",
                        "schema": batch_schema.model_json_schema(),
                    },
                },
                temperature=0.2,
                # Five slide scripts fit comfortably beside this model's
                # source-text prompt within its 8,128-token context window.
                default_max_tokens=3072,
                course_id=str((course_context or {}).get("course_id") or "unknown"),
                stage="scripts",
                module_number=(course_context or {}).get("module_number"),
                attempts=1,
            )
            parsed = batch_schema.model_validate_json(response.choices[0].message.content)
            if len(parsed.slides) != len(batch_slides):
                raise ValueError(
                    f"Expected {len(batch_slides)} slide scripts in batch {batch_number}, "
                    f"received {len(parsed.slides)}"
                )
            if any(not item.script.strip() for item in parsed.slides):
                raise ValueError(f"LLM returned an empty slide script in batch {batch_number}")
            return parsed

        try:
            parsed = retry(
                generate_once,
                course_id=str((course_context or {}).get("course_id") or "unknown"),
                stage="scripts",
                attempts=3,
                module_number=(course_context or {}).get("module_number"),
            )
        except Exception as exc:
            print(f"  [SCRIPT][ERROR] Batch {batch_number} failed for module '{module.get('title')}': {exc}")
            raise

        generated_scripts.extend(parsed.slides)
        previous_batch_narration = "\n\n".join(
            f"[SLIDE {batch_index * batch_size + offset + 1}] {item.script.strip()}"
            for offset, item in enumerate(parsed.slides)
        )

    if len(generated_scripts) != len(slides):
        raise ValueError(f"Expected {len(slides)} slide scripts, received {len(generated_scripts)}")

    print(f"  [SCRIPT] LLM successfully returned {len(generated_scripts)} slide scripts.")
    for index, slide in enumerate(slides):
        slide["script"] = generated_scripts[index].script.strip()
    return module
