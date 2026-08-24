"""Extract course blueprints, metadata, modules, and source images from uploaded PDFs."""

import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Set

import fitz
import pdfplumber

from app.core.logging import generation_logger
from app.core.providers import IMAGE_DIR, UPLOAD_DIR, get_llm_endpoint, safe_chat_completion
from app.core.settings import settings
from app.core.storage import public_asset_url
from app.documents.conversion import convert_office_to_pdf
from app.documents.pptx import extract_pptx_metadata_with_llm, extract_text_from_pptx
from app.generation.prompts import MODULE_EXTRACTION_PROMPT
from app.generation.runtime import complete_generation, log_event, mark_stage, now_iso, retry
from app.repositories.courses import delete_course, get_all_courses, get_course, save_course
from app.repositories.documents import get_document_by_file_name
from app.schemas.generation.blueprint import BlueprintExtractionResult, ModuleListSchema

logger = generation_logger(__name__)


def extract_text_and_pages(pdf_path: str):
    """
    Extracts text page-by-page and returns (metadata, body_lines, body_line_pages).
    """
    logger.info("pdf_text_extraction_started path=%s", pdf_path)

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
                        ("course_name", "Course Name"),
                        ("course_description", "Course Description"),
                        ("course_objective", "Course Objective"),
                        ("course_difficulty", "Course Difficulty"),
                        ("language", "Language"),
                        ("target_audience", "Target Audience"),
                    ]
                    for row in rows:
                        if len(row) >= 2:
                            label_cell = (row[0] or "").strip()
                            val_cell = (row[1] or "").strip()

                            # Normalize cell text
                            norm_label_cell = re.sub(r"\s+", " ", label_cell).strip().lower()
                            for key, label in labels:
                                norm_label = label.lower()
                                if norm_label_cell == norm_label:
                                    val_cleaned = re.sub(r"\s+", " ", val_cell).strip()
                                    parsed_meta[key] = val_cleaned
                                    break

                    if "course_name" in parsed_meta:
                        metadata = parsed_meta
                        try:
                            # Crop page below the table to get the remaining text
                            cropped_page = page.crop(
                                (0, first_table.bbox[3], page.width, page.height)
                            )
                            remaining_text = cropped_page.extract_text() or ""
                            cleaned_remaining = clean_extracted_text(remaining_text)
                        except (AttributeError, IndexError, TypeError, ValueError) as exc:
                            logger.warning(
                                "pdf_table_crop_failed page=%s error=%s",
                                page_num,
                                exc,
                            )
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
                lines = [line.strip() for line in norm_text.split("\n")]
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
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Step 2: Remove "Page N" / "Page N of M" artefacts
    text = re.sub(r"(?i)\bpage\s+\d+(\s+of\s+\d+)?\b", "", text)

    # Step 3: Collapse in-line whitespace (spaces/tabs) to single space
    text = re.sub(r"[ \t]+", " ", text)

    # Step 4: Re-join soft-hyphenated words (word-\nword → wordword)
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Step 5: Strip each line of trailing/leading whitespace, but preserve
    #         blank lines so paragraph structure is retained
    lines = text.split("\n")
    cleaned_lines = [line.strip() for line in lines]
    text = "\n".join(cleaned_lines)

    # Step 6: Collapse 3+ consecutive newlines to exactly 2 (one blank line)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


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
    labels = [
        ("course_name", "Course Name"),
        ("course_description", "Course Description"),
        ("course_objective", "Course Objective"),
        ("course_difficulty", "Course Difficulty"),
        ("language", "Language"),
        ("target_audience", "Target Audience"),
    ]

    positions = []
    for key, label in labels:
        match = re.search(r"^\s*" + re.escape(label) + r"\b", text, re.MULTILINE | re.IGNORECASE)
        if match:
            positions.append(
                {
                    "key": key,
                    "label": label,
                    "start": match.start(),
                    "end": match.end(),
                }
            )

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
            remainder = text[pos["end"] :]
            blank_match = re.search(r"\n\s*\n", remainder)
            if blank_match:
                val_end = pos["end"] + blank_match.start()
            else:
                # No blank line found — read to end of next line only
                line_end = remainder.find("\n")
                val_end = pos["end"] + (line_end if line_end != -1 else len(remainder))

        raw_val = text[val_start:val_end]
        # Strip leading punctuation/whitespace artifacts and collapse internal newlines
        raw_val = re.sub(r"^[:\s\-]+", "", raw_val).strip()
        raw_val = re.sub(r"\s*\n\s*", " ", raw_val)  # join wrapped lines
        raw_val = re.sub(r"\s+", " ", raw_val).strip()
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


def normalise_to_sentence_lines(text: str) -> str:
    """
    Two rules only:
      1. Every \\n  → new line
      2. Every . ! ? inside a line → new line after it
    No buffers, no accumulation, no special-casing.
    """
    SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

    output_lines = []
    for raw_line in text.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            output_lines.append("")
            continue
        parts = SENTENCE_SPLIT.split(stripped)
        for part in parts:
            p = part.strip()
            if p:
                output_lines.append(p)

    return "\n".join(output_lines)


def number_lines(text: str) -> tuple[str, list]:
    """
    Split text into lines, prefix each with [LINE N], and return:
    - numbered_text: the full string sent to the LLM
    - lines: the original list of lines (for slicing by index later)
    Skip empty lines from numbering so the LLM only counts content lines;
    but preserve them in original_lines for faithful text reconstruction.
    """
    lines = text.split("\n")
    numbered_lines = [f"[LINE {i + 1}] {line}" for i, line in enumerate(lines)]
    numbered_text = "\n".join(numbered_lines)
    return numbered_text, lines


def extract_modules_with_llm(body_lines: List[str], course_id: str = "blueprint") -> List[dict]:
    """
    Number every line of the document body, send to LLM, and get back
    a structured list of modules with integer start_line numbers.
    """
    logger.info("Numbering document lines for LLM...")

    numbered_lines = [f"[LINE {i + 1}] {line}" for i, line in enumerate(body_lines)]
    numbered_text = "\n".join(numbered_lines)

    # Send the complete document. Provider preflight rejects oversized requests explicitly.
    content = numbered_text
    total_lines = len(body_lines)

    logger.info("document_body_normalized line_count=%s", total_lines)

    json_schema = ModuleListSchema.model_json_schema()

    def generate_once():
        base_url, model_name = get_llm_endpoint(purpose="modules")
        response = safe_chat_completion(
            base_url=base_url,
            model=model_name,
            messages=[
                {"role": "system", "content": str(MODULE_EXTRACTION_PROMPT)},
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
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "ModuleListSchema", "schema": json_schema},
            },
            temperature=0.1,
            default_max_tokens=4096,
            course_id=course_id,
            stage="blueprint",
            attempts=1,
        )

        raw_content = response.choices[0].message.content
        parsed = ModuleListSchema.model_validate_json(raw_content)
        logger.info("blueprint_llm_modules_returned module_count=%s", len(parsed.modules))

        modules = [m.model_dump() for m in parsed.modules]
        for m in modules:
            m["num_questions"] = 3
        _validate_start_lines(modules, total_lines)

        if not modules:
            raise ValueError("LLM returned no modules")
        return modules

    return retry(generate_once, course_id=course_id, stage="blueprint", attempts=3)


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
            logger.info(
                f"  [WARNING] Module {m.get('module_number')} has invalid start_line={sl}. "
                f"Correcting to {fixed}."
            )
            m["start_line"] = fixed
        prev = m["start_line"]

    # Always force module 1 to start at line 1
    if modules:
        modules[0]["start_line"] = 1


def _looks_like_caption_line(line: str) -> bool:
    return bool(
        re.match(r"^\s*(?:figure|fig|img|image|caption|chart)\s*\d*[\s:.\-]", line, re.IGNORECASE)
    )


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
        clean_title = re.sub(r"[^\w\s]", "", title)

        for offset in range(1, 6):
            check_idx = curr_start - 1 - offset
            if check_idx < 0:
                break

            line = original_lines[check_idx].strip()
            if not line:
                # Skip blank lines and continue looking backward
                continue
            if _looks_like_caption_line(line):
                # Captions are often extracted immediately before the next module heading.
                # Do not move a module start into a caption block.
                break

            is_bullet = line.startswith(
                ("●", "○", "■", "▪", "▫", "-", "*", "+", "•", "○", "■", "□", "▲", "▼", "◆", "◇")
            )
            has_letters = any(c.isalpha() for c in line)

            if is_bullet or not has_letters or len(line) >= 120:
                # Bullet lines or text-less lines are never headers; stop searching backward
                break

            is_header = False

            # 1. Matches step/module headings (e.g. "Step 13", "Module 5", "12. Bank", roman numerals)
            generic_header_patterns = [
                r"^\s*(?:step|module|chapter|part|section)\s*\d+\b",
                r"^\s*\d+[:.)-]?\s+[A-Z]",
                r"^\s*[IVXLCDM]+[:.)-]?\s+[A-Z]",
            ]
            if any(re.match(pat, line, re.IGNORECASE) for pat in generic_header_patterns):
                is_header = True
            elif re.match(rf"^\s*(?:module|chapter|part|section)?\s*{num}\b", line, re.IGNORECASE):
                is_header = True
            else:
                # 2. Fuzzy matches module title by word overlap
                STOP_WORDS = {
                    "and",
                    "or",
                    "for",
                    "to",
                    "the",
                    "a",
                    "of",
                    "in",
                    "at",
                    "on",
                    "with",
                    "about",
                    "its",
                    "it",
                    "this",
                    "these",
                    "that",
                    "from",
                    "by",
                    "an",
                    "as",
                    "into",
                    "is",
                    "are",
                }

                def get_sig_words(text: str) -> set[str]:
                    words = re.findall(r"[a-z0-9]+", text.lower())
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
                    clean_line = re.sub(r"[^\w\s]", "", line.lower())
                    if clean_title and (clean_title in clean_line or clean_line in clean_title):
                        is_header = True

            if is_header:
                new_start = max(modules[i - 1]["start_line"] + 1, curr_start - offset)
                logger.info(
                    f"  [ADJUST] Adjusted Module {num} start_line from {curr_start} backward to {new_start} to capture header: '{line}'"
                )
                m["start_line"] = new_start
                break


def slice_modules_by_line(original_lines: list, modules: List[dict]) -> List[dict]:
    """
    Use the integer start_line from each module to slice original_lines directly.
    Module N's source_text = lines[start_line-1 : next_start_line-1].
    No regex, no search, no ambiguity.
    """
    resolved = []
    total = len(original_lines)

    for i, module in enumerate(modules):
        start_idx = module["start_line"] - 1  # convert 1-based to 0-based
        if i + 1 < len(modules):
            end_idx = modules[i + 1]["start_line"] - 1
        else:
            end_idx = total

        # Safety clamp
        start_idx = max(0, min(start_idx, total))
        end_idx = max(start_idx, min(end_idx, total))

        text_slice = "\n".join(original_lines[start_idx:end_idx]).strip()
        module["source_text"] = text_slice

        char_count = len(text_slice)
        logger.info(
            f"  Module {module.get('module_number')} [{module.get('title')}]: "
            f"lines {start_idx + 1}–{end_idx}, {char_count} chars"
        )

        if char_count < 100:
            logger.info(
                f"    [WARNING] Module {module.get('module_number')} has very little text "
                f"({char_count} chars). Check LLM start_line assignment."
            )

        resolved.append(module)

    return resolved


def extract_images_from_pdf(pdf_path: str, course_id: str) -> List[Dict[str, Any]]:
    """
    Opens the PDF with PyMuPDF, extracts embedded images and their captions (the text block
    immediately below the image), saves the image files to assets, and returns the metadata.
    """
    logger.info("pdf_image_extraction_started path=%s", pdf_path)
    doc = fitz.open(pdf_path)
    extracted = []

    # Create directory for course images
    course_image_dir = os.path.join(IMAGE_DIR, course_id)
    os.makedirs(course_image_dir, exist_ok=True)

    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc[page_num]

        # Get image positions
        images_info = page.get_image_info(xrefs=True)
        # Get text blocks sorted by coordinate order
        blocks = page.get_text("blocks")

        for img_idx, img in enumerate(images_info):
            xref = img["xref"]
            bbox = img["bbox"]  # (x0, y0, x1, y1)
            iy1 = bbox[3]  # bottom of image

            # Find candidate captions (the closest text block below the image)
            best_caption_raw = None
            min_dist = float("inf")

            for b in blocks:
                text_content = b[4].strip()
                if not text_content:
                    continue

                tx0, ty0, tx1, ty1 = b[0], b[1], b[2], b[3]

                # Check vertical distance from bottom of image to top of text
                dist = abs(ty0 - iy1)

                # Check if it starts with a caption prefix
                is_caption_format = bool(
                    re.match(
                        r"^\s*(figure|fig|img|image|caption|chart)\b", text_content, re.IGNORECASE
                    )
                )

                # Text block must be below or slightly overlapping the bottom of the image, OR be a caption format ending below the image
                if ty0 > iy1 - 20 or (is_caption_format and ty1 > iy1 - 20):
                    # Check horizontal alignment/overlap
                    ix0, ix1 = bbox[0], bbox[2]
                    overlap = max(0, min(ix1, tx1) - max(ix0, tx0))

                    # If they overlap horizontally or the text starts close to the image's x0
                    if overlap > 0 or (abs(tx0 - ix0) < 50):
                        effective_dist = 0 if is_caption_format else dist
                        if effective_dist < min_dist:
                            min_dist = effective_dist
                            # Split by paragraph double newlines and join lines in space-separated form
                            paragraphs = [
                                p for p in re.split(r"\n\s*\n", text_content) if p.strip()
                            ]
                            best_caption_raw = (
                                " ".join(paragraphs[0].split()) if paragraphs else text_content
                            )

            # Fallback: search top of next page if image is near bottom of the page
            if (
                not best_caption_raw
                and (page.rect.height - iy1 < 150)
                and (page_num + 1 < total_pages)
            ):
                next_page = doc[page_num + 1]
                next_blocks = next_page.get_text("blocks")
                min_next_page_ty0 = float("inf")

                for b in next_blocks:
                    text_content = b[4].strip()
                    if not text_content:
                        continue

                    tx0, ty0, tx1, ty1 = b[0], b[1], b[2], b[3]

                    if ty0 < 150:
                        ix0, ix1 = bbox[0], bbox[2]
                        overlap = max(0, min(ix1, tx1) - max(ix0, tx0))

                        if overlap > 0 or (abs(tx0 - ix0) < 50):
                            if ty0 < min_next_page_ty0:
                                min_next_page_ty0 = ty0
                                paragraphs = re.split(r"\n\s*\n", text_content)
                                best_caption_raw = " ".join(paragraphs[0].split())
                                logger.info(
                                    f'    [NEXT PAGE CAPTION] Found wrapped caption at top of page {page_num + 2}: "{best_caption_raw}"'
                                )

            if not best_caption_raw:
                best_caption_raw = f"Image on page {page_num + 1}"
                caption_content = best_caption_raw
            else:
                # Parse prefix (e.g. Figure 9: Cosine Similarity -> content="Cosine Similarity")
                prefix_pattern = re.compile(
                    r"^\s*(figure|fig|img|image|caption|chart)\s*\d*[:.-]?\s*(.*)", re.IGNORECASE
                )
                match = prefix_pattern.match(best_caption_raw)
                if match:
                    caption_content = match.group(2).strip()
                else:
                    caption_content = best_caption_raw

            # Extract and save the image
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                img_filename = f"page_{page_num + 1}_img_{img_idx + 1}_{xref}.{image_ext}"
                img_filepath = os.path.join(course_image_dir, img_filename)

                with open(img_filepath, "wb") as f:
                    f.write(image_bytes)

                # Relative path to backend (BASE_DIR) directory
                relative_path = public_asset_url("images", course_id, img_filename)

                extracted.append(
                    {
                        "image_id": f"img_{xref}",
                        "caption": caption_content,
                        "raw_caption": best_caption_raw,
                        "file_path": relative_path,
                        "page": page_num + 1,
                        "bbox": bbox,
                    }
                )
                logger.info(
                    f'  Extracted image {xref} on page {page_num + 1} with caption: "{caption_content}"'
                )
            except (RuntimeError, OSError, ValueError, TypeError) as e:
                logger.warning(
                    "image_extraction_failed xref=%s page=%s error=%s",
                    xref,
                    page_num + 1,
                    e,
                )

    return extracted


def parse_caption_prefix(text: str):
    """
    Parses a caption string to extract the prefix type, figure number, and the caption body.
    Example:
      "Figure 9: ChatGPT" -> ("figure", "9", "ChatGPT")
      "Fig 1.2 - Diagram" -> ("fig", "1.2", "Diagram")
      "ChatGPT" -> (None, None, "ChatGPT")
    """
    pattern = re.compile(
        r"^\s*(figure|fig|img|image|caption|chart)\s*(\d+(?:[\.-]\d+)*)?\s*[:.\-]?\s*(.*)",
        re.IGNORECASE,
    )
    match = pattern.match(text)
    if match:
        prefix_type = match.group(1).lower()
        num = match.group(2)
        body = match.group(3).strip()
        return prefix_type, num, body
    return None, None, text.strip()


def find_matching_line(
    caption: str,
    original_lines: List[str],
    line_pages: List[int] = None,
    image_page: int = None,
    raw_caption: str = None,
) -> int:
    """
    Finds the 1-based line index in original_lines that matches the caption.
    If line_pages and image_page are provided, restricts the search to target pages.
    """
    match_target = raw_caption if raw_caption else caption
    target_prefix, target_num, target_body = parse_caption_prefix(match_target)
    clean_target_body = re.sub(r"[^a-zA-Z0-9]", "", target_body.lower())
    if not clean_target_body:
        return -1

    # 1. Exact clean match with prefix alignment
    for idx, line in enumerate(original_lines):
        if line_pages and image_page and line_pages[idx] not in (image_page, image_page + 1):
            continue

        cand_prefix, cand_num, cand_body = parse_caption_prefix(line)
        clean_cand_body = re.sub(r"[^a-zA-Z0-9]", "", cand_body.lower())

        if target_prefix is not None:
            if cand_prefix is None:
                continue
            if target_num is not None and cand_num is not None and target_num != cand_num:
                continue
            if clean_target_body == clean_cand_body:
                return idx + 1
        else:
            if cand_prefix is not None:
                continue
            if clean_target_body == clean_cand_body:
                return idx + 1

    # 2. Fallback to substring matching with prefix alignment
    for idx, line in enumerate(original_lines):
        if line_pages and image_page and line_pages[idx] not in (image_page, image_page + 1):
            continue

        cand_prefix, cand_num, cand_body = parse_caption_prefix(line)
        clean_cand_body = re.sub(r"[^a-zA-Z0-9]", "", cand_body.lower())

        if target_prefix is not None:
            if cand_prefix is None:
                continue
            if target_num is not None and cand_num is not None and target_num != cand_num:
                continue
            if len(clean_cand_body) > 3 and clean_cand_body in clean_target_body:
                return idx + 1
            if len(clean_target_body) > 3 and clean_target_body in clean_cand_body:
                return idx + 1
        else:
            if cand_prefix is not None:
                continue
            if len(clean_cand_body) > 3 and clean_cand_body in clean_target_body:
                return idx + 1
            if len(clean_target_body) > 3 and clean_target_body in clean_cand_body:
                return idx + 1

    return -1


def get_caption_lines(
    caption: str, start_line_num: int, original_lines: List[str], raw_caption: str = None
) -> Set[int]:
    """
    Given an image caption (or raw caption) and the 1-based start line number where it matches,
    reconstructs multi-line captions by consuming consecutive lines in original_lines
    until the full cleaned caption is covered.
    Returns a set of 1-based line numbers containing the caption.
    """
    match_target = raw_caption if raw_caption else caption
    clean_cap = re.sub(r"[^a-zA-Z0-9]", "", match_target.lower())
    if not clean_cap or start_line_num < 1 or start_line_num > len(original_lines):
        return set()

    caption_line_indices = set()
    current_idx = start_line_num - 1
    accumulated_cleaned = ""

    # We loop and accumulate cleaned text from consecutive lines
    while current_idx < len(original_lines) and len(accumulated_cleaned) < len(clean_cap):
        line = original_lines[current_idx]
        clean_line = re.sub(r"[^a-zA-Z0-9]", "", line.lower())
        if clean_line:
            # If adding this line matches or is a prefix/substring of the remaining clean_cap
            remaining_cap = clean_cap[len(accumulated_cleaned) :]
            if clean_line in remaining_cap or remaining_cap in clean_line:
                accumulated_cleaned += clean_line
                caption_line_indices.add(current_idx + 1)
            else:
                # If it doesn't match/fit, stop (we hit non-caption content)
                break
        else:
            # If the line is empty (whitespace/formatting), still include it as part of the caption lines
            caption_line_indices.add(current_idx + 1)
        current_idx += 1

    return caption_line_indices


def assign_images_to_modules(
    images: List[Dict[str, Any]],
    original_lines: List[str],
    modules: List[Dict[str, Any]],
    total_pages: int = 1,
    line_pages: List[int] = None,
) -> List[Dict[str, Any]]:
    """
    Assigns each image to the module containing its corresponding line.
    If matching fails, falls back to a page-ratio estimation.
    """
    total_lines = len(original_lines)
    num_modules = len(modules)

    # Initialize/compute end_lines and image lists for each module
    for idx, module in enumerate(modules):
        if idx + 1 < num_modules:
            end_line = modules[idx + 1]["start_line"] - 1
        else:
            end_line = total_lines
        module["end_line"] = end_line
        if "images" not in module:
            module["images"] = []

    for img in images:
        line_num = find_matching_line(
            img["caption"],
            original_lines,
            line_pages=line_pages,
            image_page=img.get("page"),
            raw_caption=img.get("raw_caption"),
        )
        assigned = False

        if line_num != -1:
            for module in modules:
                if module["start_line"] <= line_num <= module["end_line"]:
                    # Avoid duplicates
                    if not any(
                        existing["image_id"] == img["image_id"] for existing in module["images"]
                    ):
                        module["images"].append(img)
                    assigned = True
                    logger.info(
                        f"  Assigned image {img['image_id']} to Module '{module['title']}' (matched to line {line_num})"
                    )
                    break

        # Fallback: estimate module by page number distribution
        if not assigned and num_modules > 0:
            page = img.get("page", 1)
            estimated_idx = min(
                num_modules - 1, int(((page - 1) / max(1, total_pages)) * num_modules)
            )
            module = modules[estimated_idx]
            if not any(existing["image_id"] == img["image_id"] for existing in module["images"]):
                module["images"].append(img)
            logger.info(
                f"  [FALLBACK] Assigned image {img['image_id']} to Module '{module['title']}' based on page {page}/{total_pages}"
            )

    # Clean up temporary 'end_line' fields to keep schema clean
    for module in modules:
        module.pop("end_line", None)

    return modules


def run_blueprint_extraction(pdf_path: str, course_id: str = "temp_course") -> dict:
    metadata, original_lines, original_line_pages = extract_text_and_pages(pdf_path)

    if not metadata:
        raise ValueError(
            "Document format not supported. The PDF must contain a metadata table with fields: "
            "Course Name, Course Description, Course Objective, Course Difficulty, Language, Target Audience."
        )

    logger.info(
        "blueprint_metadata_extracted keys=%s target_audience=%s",
        list(metadata.keys()),
        metadata.get("target_audience"),
    )

    modules = []
    images = []
    if original_lines:
        raw_modules = extract_modules_with_llm(original_lines, course_id=course_id)
        adjust_start_lines_for_headers(raw_modules, original_lines)
        modules = slice_modules_by_line(original_lines, raw_modules)
        good = sum(1 for m in modules if len(m.get("source_text", "")) >= 100)
        logger.info("module_text_slicing_completed matched=%s total=%s", good, len(modules))

        # Extract and assign images to modules
        import fitz

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
            logger.info("PDF contains images. Proceeding with image extraction.")
            images = extract_images_from_pdf(pdf_path, course_id)
            modules = assign_images_to_modules(
                images, original_lines, modules, total_pages, original_line_pages
            )
        else:
            logger.info("PDF does not contain images. Skipping image extraction.")
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
                        raw_caption=img.get("raw_caption"),
                    )
                    if line_num != -1:
                        lines_set = get_caption_lines(
                            img["caption"],
                            line_num,
                            original_lines,
                            raw_caption=img.get("raw_caption"),
                        )
                        caption_lines_to_remove.update(lines_set)

            for module in modules:
                lines = module.get("source_text", "").split("\n")
                filtered_lines = []
                for rel_idx, line in enumerate(lines):
                    global_line_num = module["start_line"] + rel_idx
                    if global_line_num in caption_lines_to_remove:
                        logger.info(
                            f"  Removing caption line from Module '{module.get('title')}' text: '{line}'"
                        )
                    else:
                        filtered_lines.append(line)
                module["source_text"] = "\n".join(filtered_lines)

    return BlueprintExtractionResult(
        course_name=metadata.get("course_name", ""),
        course_description=metadata.get("course_description", ""),
        course_objective=metadata.get("course_objective", ""),
        course_difficulty=metadata.get("course_difficulty", ""),
        language=metadata.get("language", ""),
        target_audience=metadata.get("target_audience", ""),
        modules=modules,
        images=images,
    ).model_dump()


def run_pptx_blueprint_extraction(pptx_path: str, course_id: str = "temp_course") -> dict:
    """Generate a blueprint from native PPTX text while intentionally ignoring images."""
    original_lines = extract_text_from_pptx(pptx_path)
    if not original_lines:
        raise ValueError("No text could be extracted from the PPTX.")

    metadata = extract_pptx_metadata_with_llm(original_lines, course_id=course_id)
    raw_modules = extract_modules_with_llm(original_lines, course_id=course_id)
    adjust_start_lines_for_headers(raw_modules, original_lines)
    modules = slice_modules_by_line(original_lines, raw_modules)
    good = sum(1 for module in modules if len(module.get("source_text", "")) >= 100)
    logger.info("pptx_module_text_slicing_completed matched=%s total=%s", good, len(modules))

    return BlueprintExtractionResult(
        course_name=metadata.get("course_name", ""),
        course_description=metadata.get("course_description", ""),
        course_objective=metadata.get("course_objective", ""),
        course_difficulty=metadata.get("course_difficulty", ""),
        language=metadata.get("language", ""),
        target_audience=metadata.get("target_audience", ""),
        modules=modules,
        images=[],
    ).model_dump()


def generate_course_outline(filename, course_id: str | None = None, trainer_id: str | None = None):
    logger.info("blueprint_generation_started file_name=%s", filename)
    document_path = os.path.join(UPLOAD_DIR, filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".pptx", ".docx"}:
        raise ValueError("Only PDF, PPTX, and DOCX files are supported.")
    if not os.path.exists(document_path):
        raise FileNotFoundError(f"Document file not found at {document_path}")

    document = get_document_by_file_name(filename, trainer_id)
    if document is None and trainer_id is None:
        document = get_document_by_file_name(filename)
    if document is None:
        raise FileNotFoundError("Uploaded document record not found")
    trainer_id = trainer_id or document["trainer_id"]

    blueprint_start = time.perf_counter()
    courses = get_all_courses("draft")

    course_id = course_id or f"course_{uuid.uuid4()}"
    existing_index = next(
        (i for i, course in enumerate(courses) if course.get("course_id") == course_id), None
    )
    created_checkpoint = existing_index is None
    checkpoint_course = (
        courses[existing_index]
        if existing_index is not None
        else {
            "course_id": course_id,
            "course_name": f"Blueprint generation: {filename}",
            "course_description": "",
            "course_objective": "",
            "course_difficulty": "",
            "language": "",
            "target_audience": "",
            "document_id": document["document_id"],
            "trainer_id": trainer_id,
            "created_at": now_iso(),
            "images": [],
            "modules": [],
        }
    )
    mark_stage(checkpoint_course, "blueprint", "running")
    save_course(checkpoint_course, "draft")
    log_event(course_id, "blueprint", "start", document_id=document["document_id"])

    try:
        if suffix == ".pptx":
            outline = run_pptx_blueprint_extraction(document_path, course_id=course_id)
        elif suffix == ".docx":
            converted_pdf = Path(settings.derived_document_dir) / f"{document['document_id']}.pdf"
            outline = run_blueprint_extraction(
                str(convert_office_to_pdf(Path(document_path), converted_pdf)),
                course_id=course_id,
            )
        else:
            outline = run_blueprint_extraction(document_path, course_id=course_id)
    except Exception as exc:
        if created_checkpoint:
            delete_course(course_id)
        else:
            failed_course = get_course(course_id, "draft")
            if failed_course is not None:
                mark_stage(failed_course, "blueprint", "failed", error=str(exc))
                save_course(failed_course, "draft")
        log_event(course_id, "blueprint", "failed", reason=str(exc))
        raise

    # Ensure the course name is unique
    base_name = outline.get("course_name", "Untitled Course")
    course_name = base_name
    counter = 1
    while any(
        c.get("course_id") != course_id and c.get("course_name") == course_name for c in courses
    ):
        course_name = f"{base_name} ({counter})"
        counter += 1

    outline["course_name"] = course_name
    outline["document_id"] = document["document_id"]
    outline["course_id"] = course_id
    outline["trainer_id"] = trainer_id
    outline["created_at"] = now_iso()
    mark_stage(outline, "blueprint", "completed")
    complete_generation(outline, time.perf_counter() - blueprint_start)

    save_course(outline, "draft")

    logger.info("blueprint_generation_completed file_name=%s course_id=%s", filename, course_id)
    return outline
