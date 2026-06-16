import re
import requests
import pdfplumber
from typing import List
from pydantic import BaseModel

from pipelines.config import get_llm_client
from pipelines.prompts import MODULE_EXTRACTION_PROMPT


# -------------------------------------------------------
# Pydantic Schemas for LLM Response
# -------------------------------------------------------
class ModuleSchema(BaseModel):
    module_number: int
    title: str
    start_line: int          # INTEGER line number — no more text anchors

class ModuleListSchema(BaseModel):
    modules: List[ModuleSchema]


# -------------------------------------------------------
# PDF Text Extraction
# -------------------------------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"Extracting text from PDF: {pdf_path}")
    text_content = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_content.append(text)
    raw_text = "\n".join(text_content)
    return clean_extracted_text(raw_text)


def clean_extracted_text(text: str) -> str:
    """
    Cleans raw PDF text:
    1. Normalise line endings.
    2. Remove embedded page numbers.
    3. Collapse repeated spaces/tabs within a line.
    4. Re-join words that were hyphenated across a line break (soft hyphens).
    5. Preserve intentional blank lines (paragraph / section dividers) by
       protecting double-newlines before any stripping.
    6. Strip trailing whitespace from each line.
    7. Collapse 3+ consecutive newlines back to 2.
    """
    if not text:
        return ""

    # Step 1: Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Step 2: Remove "Page N" / "Page N of M" artefacts
    text = re.sub(r'(?i)\bpage\s+\d+(\s+of\s+\d+)?\b', '', text)

    # Step 3: Collapse in-line whitespace (spaces/tabs) to single space
    text = re.sub(r'[ \t]+', ' ', text)

    # Step 4: Re-join soft-hyphenated words (word-\nword → wordword)
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # Step 5: Strip each line of trailing/leading whitespace, but preserve
    #         blank lines so paragraph structure is retained
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines]
    text = '\n'.join(cleaned_lines)

    # Step 6: Collapse 3+ consecutive newlines to exactly 2 (one blank line)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# -------------------------------------------------------
# Metadata Extraction — handles multi-line values & Course Type
# -------------------------------------------------------
def extract_metadata_programmatically(text: str):
    """
    Parse the fixed-format metadata table at the start of the document.

    The table uses the pattern:
        Label    value that may wrap onto the
                 next physical line(s)
        NextLabel  next value...

    Strategy:
    - Find the character position of every known label.
    - For each label, its value spans from the end of that label
      to the start of the next label (or to the end of the metadata block).
    - Join wrapped lines inside each value with a single space.
    - Everything after the last metadata label's value is body content.

    Returns (metadata_dict, remaining_body_text) or (None, text) if not found.
    """
    # FIX 1: Added "course_type" to the labels list and kept order matching
    # the standard template so position-based slicing works correctly.
    labels = [
        ("course_name",        "Course Name"),
        ("course_description", "Course Description"),
        ("course_objective",   "Course Objective"),
        ("course_difficulty",  "Course Difficulty"),
        ("language",           "Language"),
        ("target_audience",    "Target Audience"),
        ("course_type",        "Course Type"),
    ]

    positions = []
    for key, label in labels:
        match = re.search(
            r'^\s*' + re.escape(label) + r'\b',
            text,
            re.MULTILINE | re.IGNORECASE
        )
        if match:
            positions.append({
                "key":   key,
                "label": label,
                "start": match.start(),
                "end":   match.end(),
            })

    if not positions:
        return None, text

    positions.sort(key=lambda x: x["start"])
    metadata = {}

    for idx, pos in enumerate(positions):
        val_start = pos["end"]

        if idx + 1 < len(positions):
            # Value runs up to the start of the next label
            val_end = positions[idx + 1]["start"]
        else:
            # Last label: value runs to the end of the metadata block.
            # The metadata block ends at the first line that does NOT look
            # like a continuation of the value — specifically the first
            # non-empty line that starts a new paragraph (blank line before it).
            # Simple heuristic: read to the next blank line or 300 chars,
            # whichever comes first.
            remainder = text[pos["end"]:]
            blank_match = re.search(r'\n\s*\n', remainder)
            if blank_match:
                val_end = pos["end"] + blank_match.start()
            else:
                # No blank line found — read to end of next line only
                line_end = remainder.find('\n')
                val_end = pos["end"] + (line_end if line_end != -1 else len(remainder))

        raw_val = text[val_start:val_end]
        # Strip leading punctuation/whitespace artifacts and collapse internal newlines
        raw_val = re.sub(r'^[:\s\-]+', '', raw_val).strip()
        raw_val = re.sub(r'\s*\n\s*', ' ', raw_val)   # join wrapped lines
        raw_val = re.sub(r'\s+', ' ', raw_val).strip()
        metadata[pos["key"]] = raw_val

    # Remaining body text starts after the last metadata entry
    last_end = positions[-1]["end"]
    # Advance past the last label's value
    if positions[-1]["key"] in metadata:
        last_val = metadata[positions[-1]["key"]]
        # Find where that value ends in the original text
        advance = text[last_end:].find(last_val.split()[-1]) if last_val else 0
        if advance != -1:
            last_end = last_end + advance + len(last_val.split()[-1])

    remaining_text = text[last_end:].strip()

    # Guard: if remaining_text is empty or tiny, fall back to the simpler cut
    if len(remaining_text) < 50:
        last_known_end = max(pos["end"] for pos in positions)
        remaining_text = text[last_known_end:].strip()

    return metadata, remaining_text


# -------------------------------------------------------
# Logical-line Normalisation
# -------------------------------------------------------
def normalise_to_sentence_lines(text: str) -> str:
    """
    Two rules only:
      1. Every \\n  → new line
      2. Every . ! ? inside a line → new line after it
    No buffers, no accumulation, no special-casing.
    """
    SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

    output_lines = []
    for raw_line in text.split('\n'):
        stripped = raw_line.strip()
        if not stripped:
            output_lines.append('')
            continue
        parts = SENTENCE_SPLIT.split(stripped)
        for part in parts:
            p = part.strip()
            if p:
                output_lines.append(p)

    return '\n'.join(output_lines)



# -------------------------------------------------------
# Line Numbering — inject [LINE N] prefix before LLM call
# -------------------------------------------------------
def number_lines(text: str) -> tuple[str, list]:
    """
    Split text into lines, prefix each with [LINE N], and return:
    - numbered_text: the full string sent to the LLM
    - lines: the original list of lines (for slicing by index later)
    Skip empty lines from numbering so the LLM only counts content lines;
    but preserve them in original_lines for faithful text reconstruction.
    """
    lines = text.split('\n')
    numbered_lines = [f"[LINE {i + 1}] {line}" for i, line in enumerate(lines)]
    numbered_text = '\n'.join(numbered_lines)
    return numbered_text, lines


# -------------------------------------------------------
# LLM Module Extraction — now uses numbered lines
# -------------------------------------------------------
def extract_modules_with_llm(remaining_text: str) -> tuple[List[dict], list]:
    """
    Number every line of the document body, send to LLM, and get back
    a structured list of modules with integer start_line numbers.
    Returns (modules_list, original_lines).
    """
    print("Normalising and numbering document lines for LLM...")

    # FIX 2 & 3: Normalise prose to sentence-per-line before numbering
    normalised_text = normalise_to_sentence_lines(remaining_text)

    numbered_text, original_lines = number_lines(normalised_text)

    # Truncate to 50,000 chars
    content = numbered_text[:50000]
    total_lines = len(original_lines)

    print(f"  Document body: {total_lines} lines after normalisation.")

    json_schema = ModuleListSchema.model_json_schema()

    try:
        client, model_name = get_llm_client()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": MODULE_EXTRACTION_PROMPT
                },
                {
                    "role": "user",
                    "content": (
                        f"Your task is to segment the training document content below into modules.\n"
                        f"The document has {total_lines} lines total, each prefixed with [LINE N].\n\n"
                        f"CRITICAL REQUIREMENTS:\n"
                        f"1. You MUST generate between 3 and 6 modules (aim for 4-5), "
                        f"unless the text explicitly has more than 6 labeled chapters/modules.\n"
                        f"2. Every single line must be covered under some module — no gaps.\n"
                        f"3. For start_line, provide the INTEGER line number exactly as shown "
                        f"in the [LINE N] prefix. Do NOT guess — read the number from the prefix.\n"
                        f"4. The first module's start_line MUST be 1.\n"
                        f"5. start_line values must be strictly increasing.\n\n"
                        f"Here is the training document content:\n\n{content}"
                    )
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ModuleListSchema",
                    "schema": json_schema
                }
            },
            temperature=0.1,
            max_tokens=4096
        )

        raw_content = response.choices[0].message.content
        parsed = ModuleListSchema.model_validate_json(raw_content)
        print(f"LLM returned {len(parsed.modules)} modules.")

        modules = [m.model_dump() for m in parsed.modules]
        _validate_start_lines(modules, total_lines)

        return modules, original_lines

    except requests.exceptions.Timeout:
        raise RuntimeError("LLM request timed out after 600 seconds.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"LLM request failed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Failed to parse LLM module response: {str(e)}")


def _validate_start_lines(modules: List[dict], total_lines: int):
    """
    Ensure start_line values are strictly increasing and within [1, total_lines].
    Fixes any violations in-place with a warning.
    """
    prev = 0
    for i, m in enumerate(modules):
        sl = m.get("start_line", -1)
        if not isinstance(sl, int) or sl <= prev or sl > total_lines:
            fixed = prev + max(1, (total_lines - prev) // (len(modules) - i))
            print(f"  [WARNING] Module {m.get('module_number')} has invalid start_line={sl}. "
                  f"Correcting to {fixed}.")
            m["start_line"] = fixed
        prev = m["start_line"]

    # Always force module 1 to start at line 1
    if modules:
        modules[0]["start_line"] = 1


# -------------------------------------------------------
# Direct Line-Number Slicing — replaces regex anchor resolution
# -------------------------------------------------------
def slice_modules_by_line(original_lines: list, modules: List[dict]) -> List[dict]:
    """
    Use the integer start_line from each module to slice original_lines directly.
    Module N's text = lines[start_line-1 : next_start_line-1].
    No regex, no search, no ambiguity.
    """
    resolved = []
    total = len(original_lines)

    for i, module in enumerate(modules):
        start_idx = module["start_line"] - 1          # convert 1-based to 0-based
        if i + 1 < len(modules):
            end_idx = modules[i + 1]["start_line"] - 1
        else:
            end_idx = total

        # Safety clamp
        start_idx = max(0, min(start_idx, total))
        end_idx   = max(start_idx, min(end_idx, total))

        text_slice = '\n'.join(original_lines[start_idx:end_idx]).strip()
        module["text"] = text_slice

        char_count = len(text_slice)
        print(f"  Module {module.get('module_number')} [{module.get('title')}]: "
              f"lines {start_idx+1}–{end_idx}, {char_count} chars")

        if char_count < 100:
            print(f"    [WARNING] Module {module.get('module_number')} has very little text "
                  f"({char_count} chars). Check LLM start_line assignment.")

        resolved.append(module)

    return resolved


# -------------------------------------------------------
# Main Entry Point
# -------------------------------------------------------
def run_blueprint_extraction(pdf_path: str, course_id: str = "temp_course") -> dict:
    text = extract_text_from_pdf(pdf_path)

    if not text.strip():
        raise ValueError("The PDF document does not contain any readable text.")

    print("Extracting course metadata...")
    metadata, remaining_text = extract_metadata_programmatically(text)

    if not metadata:
        raise ValueError(
            "Document format not supported. The PDF must contain a metadata table with fields: "
            "Course Name, Course Description, Course Objective, Course Difficulty, Language, Target Audience."
        )

    print(f"Metadata extracted: {list(metadata.keys())}")
    print(f"  target_audience = {metadata.get('target_audience')}")
    print(f"  course_type     = {metadata.get('course_type')}")

    modules = []
    images = []
    if remaining_text.strip():
        try:
            raw_modules, original_lines = extract_modules_with_llm(remaining_text)
            modules = slice_modules_by_line(original_lines, raw_modules)
            good = sum(1 for m in modules if len(m.get('text', '')) >= 100)
            print(f"Successfully sliced text for {good} / {len(modules)} modules.")
            
            # Extract and assign images to modules
            import fitz
            from pipelines.image_extractor import extract_images_from_pdf, assign_images_to_modules
            
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # Count images in PDF first to see if it is a non-image PDF
            has_images = False
            for page in doc:
                if len(page.get_image_info(xrefs=True)) > 0:
                    has_images = True
                    break
            doc.close()
            
            if has_images:
                print(f"PDF contains images. Proceeding with image extraction.")
                images = extract_images_from_pdf(pdf_path, course_id)
                modules = assign_images_to_modules(images, original_lines, modules, total_pages)
            else:
                print(f"PDF does not contain images. Skipping image extraction.")
                images = []
            
            # Remove image captions from module text so they don't get treated as content lines
            for module in modules:
                mod_images = module.get("images", [])
                if mod_images:
                    clean_captions = {
                        re.sub(r'[^a-zA-Z0-9]', '', img['caption'].lower())
                        for img in mod_images
                        if img.get('caption')
                    }
                    lines = module.get("text", "").split('\n')
                    filtered_lines = []
                    for line in lines:
                        clean_line = re.sub(r'[^a-zA-Z0-9]', '', line.lower())
                        if clean_line:
                            is_caption = False
                            for clean_cap in clean_captions:
                                if clean_line == clean_cap:
                                    is_caption = True
                                    break
                            if is_caption:
                                print(f"  Removing caption line from Module '{module.get('title')}' text: '{line}'")
                                continue
                        filtered_lines.append(line)
                    module["text"] = '\n'.join(filtered_lines)
        except Exception as e:
            print(f"  [ERROR] Module extraction/image assignment failed: {e}")
            modules = []


    return {
        "course_name":        metadata.get("course_name", ""),
        "course_description": metadata.get("course_description", ""),
        "course_objective":   metadata.get("course_objective", ""),
        "course_difficulty":  metadata.get("course_difficulty", ""),
        "language":           metadata.get("language", ""),
        "target_audience":    metadata.get("target_audience", ""),
        "course_type":        metadata.get("course_type", ""),
        "modules":            modules,
        "images":             images,
    }
