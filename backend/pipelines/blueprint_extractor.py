import re
import requests
import pdfplumber
from typing import List
from pydantic import BaseModel

from pipelines.config import get_llm_endpoint, safe_chat_completion
from pipelines.prompts import MODULE_EXTRACTION_PROMPT


# -------------------------------------------------------
# Pydantic Schemas for LLM Response
# -------------------------------------------------------
class ModuleSchema(BaseModel):
    module_number: int
    title: str
    start_line: int          # INTEGER line number — no more text anchors
    num_questions: int = 3

class ModuleListSchema(BaseModel):
    modules: List[ModuleSchema]


# -------------------------------------------------------
# PDF Text Extraction
# -------------------------------------------------------
def extract_text_and_pages(pdf_path: str):
    """
    Extracts text page-by-page and returns (metadata, body_lines, body_line_pages).
    """
    print(f"Extracting text from PDF: {pdf_path}")
    import pdfplumber
    
    metadata = None
    body_lines = []
    body_line_pages = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            page_num = idx + 1
            text = page.extract_text()
            if not text:
                continue
            
            cleaned_text = clean_extracted_text(text)
            
            if page_num == 1:
                # Parse metadata from the first page
                # First try table extraction
                tables = page.find_tables()
                if tables:
                    parsed_meta = {}
                    first_table = tables[0]
                    rows = first_table.extract()
                    labels = [
                        ("course_name",        "Course Name"),
                        ("course_description", "Course Description"),
                        ("course_objective",   "Course Objective"),
                        ("course_difficulty",  "Course Difficulty"),
                        ("language",           "Language"),
                        ("target_audience",    "Target Audience"),
                        ("course_type",        "Course Type"),
                    ]
                    for row in rows:
                        if len(row) >= 2:
                            label_cell = (row[0] or "").strip()
                            val_cell = (row[1] or "").strip()
                            
                            # Normalize cell text
                            norm_label_cell = re.sub(r'\s+', ' ', label_cell).strip().lower()
                            for key, label in labels:
                                norm_label = label.lower()
                                if norm_label_cell == norm_label:
                                    val_cleaned = re.sub(r'\s+', ' ', val_cell).strip()
                                    parsed_meta[key] = val_cleaned
                                    break
                    
                    if "course_name" in parsed_meta:
                        metadata = parsed_meta
                        try:
                            # Crop page below the table to get the remaining text
                            cropped_page = page.crop((0, first_table.bbox[3], page.width, page.height))
                            remaining_text = cropped_page.extract_text() or ""
                            cleaned_remaining = clean_extracted_text(remaining_text)
                        except Exception as e:
                            print(f"      [WARNING] Cropping page below table failed: {e}. Falling back to empty remaining text.")
                            cleaned_remaining = ""
                        norm_text = normalise_to_sentence_lines(cleaned_remaining)
                    else:
                        # Table didn't look like our metadata table, fallback to programmatic parsing
                        metadata, remaining_text = extract_metadata_programmatically(cleaned_text)
                        if not metadata:
                            remaining_text = cleaned_text
                        norm_text = normalise_to_sentence_lines(remaining_text)
                else:
                    # No tables found, fallback to programmatic parsing
                    metadata, remaining_text = extract_metadata_programmatically(cleaned_text)
                    if not metadata:
                        remaining_text = cleaned_text
                    norm_text = normalise_to_sentence_lines(remaining_text)
            else:
                norm_text = normalise_to_sentence_lines(cleaned_text)
                
            if norm_text.strip():
                # Split by \n and clean page lines
                lines = [line.strip() for line in norm_text.split('\n')]
                cleaned_lines = []
                for line in lines:
                    if not line:
                        if cleaned_lines and cleaned_lines[-1] != "":
                            cleaned_lines.append("")
                    else:
                        cleaned_lines.append(line)
                
                # Strip leading/trailing blank lines of the page
                while cleaned_lines and cleaned_lines[0] == "":
                    cleaned_lines.pop(0)
                while cleaned_lines and cleaned_lines[-1] == "":
                    cleaned_lines.pop()
                    
                if cleaned_lines:
                    body_lines.extend(cleaned_lines)
                    body_line_pages.extend([page_num] * len(cleaned_lines))
                
    return metadata, body_lines, body_line_pages


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
def extract_modules_with_llm(body_lines: List[str]) -> List[dict]:
    """
    Number every line of the document body, send to LLM, and get back
    a structured list of modules with integer start_line numbers.
    """
    print("Numbering document lines for LLM...")

    numbered_lines = [f"[LINE {i + 1}] {line}" for i, line in enumerate(body_lines)]
    numbered_text = '\n'.join(numbered_lines)

    # Truncate to 50,000 chars
    content = numbered_text[:50000]
    total_lines = len(body_lines)

    print(f"  Document body: {total_lines} lines after normalisation.")

    json_schema = ModuleListSchema.model_json_schema()

    try:
        base_url, model_name = get_llm_endpoint()
        response = safe_chat_completion(
            base_url=base_url,
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
            default_max_tokens=1024
        )

        raw_content = response.choices[0].message.content
        parsed = ModuleListSchema.model_validate_json(raw_content)
        print(f"LLM returned {len(parsed.modules)} modules.")

        modules = [m.model_dump() for m in parsed.modules]
        for m in modules:
            m["num_questions"] = 3
        _validate_start_lines(modules, total_lines)

        return modules

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
# Adjust start lines programmatically to capture headers
# -------------------------------------------------------
def adjust_start_lines_for_headers(modules: List[dict], original_lines: List[str]):
    """
    Look backward from each module's start_line. If a preceding line (up to 5 lines back)
    matches the module's title (contains title, or starts with standard header formats),
    adjust the start_line backward to capture that header. Skip blank lines and bullet points.
    """
    for i in range(1, len(modules)):
        m = modules[i]
        curr_start = m["start_line"]
        title = m["title"].strip().lower()
        num = m["module_number"]
        
        # Clean title for fuzzy comparison
        clean_title = re.sub(r'[^\w\s]', '', title)
        
        for offset in range(1, 6):
            check_idx = curr_start - 1 - offset
            if check_idx < 0:
                break
                
            line = original_lines[check_idx].strip()
            if not line:
                # Skip blank lines and continue looking backward
                continue
                
            is_bullet = line.startswith((
                '●', '○', '■', '▪', '▫', '-', '*', '+', '•', 
                '○', '■', '□', '▲', '▼', '◆', '◇'
            ))
            has_letters = any(c.isalpha() for c in line)
            
            if is_bullet or not has_letters or len(line) >= 120:
                # Bullet lines or text-less lines are never headers; stop searching backward
                break
                
            is_header = False
            
            # 1. Matches step/module headings (e.g. "Step 13", "Module 5", "12. Bank", roman numerals)
            generic_header_patterns = [
                rf'^\s*(?:step|module|chapter|part|section)\s*\d+\b',
                rf'^\s*\d+[:.)-]?\s+[A-Z]',
                rf'^\s*[IVXLCDM]+[:.)-]?\s+[A-Z]'
            ]
            if any(re.match(pat, line, re.IGNORECASE) for pat in generic_header_patterns):
                is_header = True
            elif re.match(rf'^\s*(?:module|chapter|part|section)?\s*{num}\b', line, re.IGNORECASE):
                is_header = True
            else:
                # 2. Fuzzy matches module title by word overlap
                STOP_WORDS = {
                    "and", "or", "for", "to", "the", "a", "of", "in", "at", "on", "with", "about", 
                    "its", "it", "this", "these", "that", "from", "by", "an", "as", "into", "is", "are"
                }
                def get_sig_words(text: str) -> set[str]:
                    words = re.findall(r'[a-z0-9]+', text.lower())
                    return {w for w in words if w not in STOP_WORDS}
                
                words_title = get_sig_words(title)
                words_line = get_sig_words(line)
                
                if words_title and words_line:
                    intersection = words_title.intersection(words_line)
                    similarity = len(intersection) / min(len(words_title), len(words_line))
                    if similarity >= 0.5:
                        is_header = True
                        
                # 3. Substring matching fallback
                if not is_header:
                    clean_line = re.sub(r'[^\w\s]', '', line.lower())
                    if clean_title and (clean_title in clean_line or clean_line in clean_title):
                        is_header = True
                        
            if is_header:
                new_start = max(modules[i-1]["start_line"] + 1, curr_start - offset)
                print(f"  [ADJUST] Adjusted Module {num} start_line from {curr_start} backward to {new_start} to capture header: '{line}'")
                m["start_line"] = new_start
                break

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
    metadata, original_lines, original_line_pages = extract_text_and_pages(pdf_path)

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
    if original_lines:
        try:
            raw_modules = extract_modules_with_llm(original_lines)
            adjust_start_lines_for_headers(raw_modules, original_lines)
            modules = slice_modules_by_line(original_lines, raw_modules)
            good = sum(1 for m in modules if len(m.get('text', '')) >= 100)
            print(f"Successfully sliced text for {good} / {len(modules)} modules.")
            
            # Extract and assign images to modules
            import fitz
            from pipelines.image_extractor import (
                extract_images_from_pdf,
                assign_images_to_modules,
                find_matching_line,
                get_caption_lines
            )
            
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
                modules = assign_images_to_modules(images, original_lines, modules, total_pages, original_line_pages)
            else:
                print(f"PDF does not contain images. Skipping image extraction.")
                images = []
            
            # Remove image captions from module text while preserving image tags
            if images:
                caption_lines_to_remove = set()
                for img in images:
                    if img.get("caption"):
                        line_num = find_matching_line(
                            img["caption"], 
                            original_lines, 
                            line_pages=original_line_pages, 
                            image_page=img.get("page"),
                            raw_caption=img.get("raw_caption")
                        )
                        if line_num != -1:
                            lines_set = get_caption_lines(img["caption"], line_num, original_lines, raw_caption=img.get("raw_caption"))
                            caption_lines_to_remove.update(lines_set)
                
                for module in modules:
                    lines = module.get("text", "").split('\n')
                    filtered_lines = []
                    for rel_idx, line in enumerate(lines):
                        global_line_num = module["start_line"] + rel_idx
                        if global_line_num in caption_lines_to_remove:
                            print(f"  Removing caption line from Module '{module.get('title')}' text: '{line}'")
                        else:
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
