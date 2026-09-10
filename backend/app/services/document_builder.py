"""Document-builder orchestration with scratch-compatible behavior."""

from __future__ import annotations

import json
from io import BytesIO

from app.core.providers import get_llm_endpoint, safe_chat_completion
from app.document_builder.pdf_builder import (
    REQUIRED_METADATA_FIELDS,
    render_pdf,
    safe_filename,
)
from app.document_builder.prompts import (
    BOOLEAN_SETTING_SNIPPETS,
    DETAIL_LEVEL_SNIPPETS,
    SYSTEM_PROMPT,
    WRITING_FOCUS_SNIPPETS,
)
from app.services.uploads import UploadService


def _builder_skill_snippets(settings: dict) -> list[str]:
    detail_level = str(settings.get("detailLevel") or "standard").lower()
    writing_focus = str(settings.get("writingFocus") or "balanced").lower()
    tone = str(settings.get("tone") or "Clear and professional").strip()
    module_count = settings.get("moduleCount") or 4
    snippets = [
        f"Module-count skill: Create exactly {module_count} numbered modules unless the latest trainer message explicitly overrides the count.",
        f"Tone skill: Write in this style: {tone}. Keep the language natural and useful for workplace training.",
        DETAIL_LEVEL_SNIPPETS.get(detail_level, DETAIL_LEVEL_SNIPPETS["standard"]),
        WRITING_FOCUS_SNIPPETS.get(writing_focus, WRITING_FOCUS_SNIPPETS["balanced"]),
    ]
    for key, choices in BOOLEAN_SETTING_SNIPPETS.items():
        snippets.append(choices[bool(settings.get(key))])
    return snippets


def _build_user_prompt(payload: dict) -> str:
    settings = payload.get("builderSettings") or {}
    instructions = payload.get("instructions") or []
    current_draft = str(payload.get("currentDraft") or "").strip()
    trainer_message = str(payload.get("message") or "").strip()
    return f"""Trainer message:
{trainer_message}

All chat instructions so far:
{chr(10).join("- " + str(item) for item in instructions) if instructions else "- None"}

Current draft, if any:
{current_draft or "(none)"}

Builder setting skills:
{chr(10).join("- " + snippet for snippet in _builder_skill_snippets(settings))}

Rules:
- Return a full revised document, not a patch.
- Preserve useful current draft content unless the latest trainer message asks to change it.
- Output document must start with Module 1.
- No standalone non-module content is allowed.
- Ignore LMS metadata fields. They are saved separately in the UI and are not part of this request.
"""


def _module_only(document: str) -> str:
    text = str(document or "").strip()
    if not text:
        return ""
    if text.startswith("{") and '"document"' in text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                text = str(parsed.get("document") or "").strip()
        except json.JSONDecodeError:
            marker = '"document"'
            marker_index = text.find(marker)
            if marker_index >= 0:
                after_marker = text[marker_index + len(marker) :]
                colon_index = after_marker.find(":")
                if colon_index >= 0:
                    text = after_marker[colon_index + 1 :].strip().strip('"')
    lines = text.splitlines()
    first_module = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip().lower().startswith("module 1:")
        ),
        0,
    )
    cleaned = "\n".join(lines[first_module:]).strip()
    for marker in ('",\n"reply"', '\n"reply":', '\nmetadataSuggestions', '\n"metadataSuggestions"'):
        marker_index = cleaned.find(marker)
        if marker_index >= 0:
            cleaned = cleaned[:marker_index].strip().rstrip('",')
    return cleaned.replace("\\n", "\n").replace('\\"', '"').strip()


def _parse_llm_payload(content: str) -> dict:
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "document" in parsed:
            parsed["document"] = _module_only(parsed.get("document", ""))
            parsed.setdefault("reply", "I updated the module-only draft.")
            parsed.setdefault("metadataSuggestions", {})
            return parsed
    except json.JSONDecodeError:
        pass
    return {
        "document": _module_only(raw),
        "reply": "I updated the module-only draft.",
        "metadataSuggestions": {},
    }


def _completion_content(response: object) -> str:
    try:
        choices = getattr(response, "choices")
        if choices:
            content = getattr(choices[0].message, "content", "")
            return str(content or "")
    except (AttributeError, IndexError, TypeError):
        pass
    return str(response or "")


def validate_pdf_payload(payload: dict) -> tuple[dict, str, list[dict]]:
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict): raise ValueError("Metadata must be an object.")
    missing = [label for key, label in REQUIRED_METADATA_FIELDS if not str(metadata.get(key) or "").strip()]
    if missing: raise ValueError("Missing required metadata fields: " + ", ".join(missing))
    document = _module_only(str(payload.get("document") or ""))
    if not document: raise ValueError("Document draft is empty.")
    if not document.lstrip().lower().startswith("module 1:"): raise ValueError("Document draft must start with Module 1.")
    blocks = payload.get("documentBlocks")
    if not isinstance(blocks, list): blocks = [{"type": "text", "text": document}]
    cleaned = []
    for block in blocks:
        if not isinstance(block, dict): continue
        if str(block.get("type") or "").strip().lower() == "image":
            src = str(block.get("src") or "").strip()
            if src: cleaned.append({"type": "image", "src": src, "width": max(25, min(100, int(block.get("width") or 60))), "align": str(block.get("align") or "left").lower(), "caption": str(block.get("caption") or "").strip()})
        else:
            text = str(block.get("text") or "").strip()
            if text: cleaned.append({"type": "text", "text": text})
    if not cleaned: cleaned = [{"type": "text", "text": document}]
    first = cleaned[0]
    if first.get("type") != "text" or not str(first.get("text") or "").lstrip().lower().startswith("module 1:"):
        raise ValueError("The first draft block must be text that starts with Module 1.")
    return metadata, document, cleaned


class DocumentBuilderService:
    def __init__(self, uploads: UploadService): self.uploads = uploads

    def build(self, payload: dict) -> dict:
        base_url, model = get_llm_endpoint(purpose="modules")
        response = safe_chat_completion(base_url, model, [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": _build_user_prompt(payload)}], temperature=.25, default_max_tokens=7000, stage="document_builder")
        content = _completion_content(response)
        if not content.strip():
            raise ValueError("LLM returned an empty document builder response.")
        result = _parse_llm_payload(content)
        result["model"] = model
        return result

    def render(self, payload: dict) -> tuple[bytes, str]:
        metadata, document, blocks = validate_pdf_payload(payload)
        return render_pdf(metadata, document, blocks), f"{safe_filename(str(metadata.get('courseName') or 'document'))}-source.pdf"

    def save(self, payload: dict, trainer_id: str) -> dict:
        pdf, filename = self.render(payload)
        uploaded = self.uploads.save_document(filename, BytesIO(pdf), trainer_id)
        saved = next(item for item in self.uploads.list_documents(trainer_id) if item.file_name == uploaded.file_name)
        return {"file": saved.model_dump(), "message": "Document saved successfully"}
