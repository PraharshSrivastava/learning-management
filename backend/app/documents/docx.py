"""Native DOCX text, metadata, and image extraction for course blueprints."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from PIL import Image as PILImage

from app.core.logging import generation_logger
from app.core.providers import IMAGE_DIR
from app.core.storage import public_asset_url

logger = generation_logger(__name__)

REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SUPPORTED_IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
}


@dataclass
class DocxBlock:
    text: str = ""
    rows: list[str] = field(default_factory=list)
    image_rids: list[str] = field(default_factory=list)
    is_table: bool = False
    is_metadata_table: bool = False
    start_line: int | None = None
    end_line: int | None = None


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _sentence_lines(text: str) -> list[str]:
    sentence_split = re.compile(r"(?<=[.!?])\s+")
    lines: list[str] = []
    for raw_line in _clean_text(text).split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue
        lines.extend(part.strip() for part in sentence_split.split(stripped) if part.strip())
    return lines


def _looks_like_caption(text: str) -> bool:
    return bool(re.match(r"^\s*(?:figure|fig|img|image|caption|chart)\s*\d*[\s:.\-]", text, re.I))


def _image_rids(element: Any) -> list[str]:
    rids: list[str] = []
    for node in element.iter():
        if not str(node.tag).endswith("}blip"):
            continue
        rid = node.attrib.get(f"{{{REL_NS}}}embed") or node.attrib.get(f"{{{REL_NS}}}link")
        if rid and rid not in rids:
            rids.append(rid)
    return rids


def _iter_body_blocks(document: Any) -> Iterable[Any]:
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _table_rows(table: Any) -> list[str]:
    rows: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            value = re.sub(r"\s+", " ", cell.text or "").strip()
            if value and value not in cells:
                cells.append(value)
        if cells:
            rows.append(" | ".join(cells))
    return rows


def _table_metadata(table: Any) -> dict[str, str] | None:
    labels = {
        "course name": "course_name",
        "course description": "course_description",
        "course objective": "course_objective",
        "course difficulty": "course_difficulty",
        "language": "language",
        "target audience": "target_audience",
    }
    metadata: dict[str, str] = {}
    for row in table.rows:
        if len(row.cells) < 2:
            continue
        label = re.sub(r"\s+", " ", row.cells[0].text or "").strip().lower()
        value = re.sub(r"\s+", " ", row.cells[1].text or "").strip()
        key = labels.get(label)
        if key and value:
            metadata[key] = value
    return metadata if "course_name" in metadata else None


def _part_extension(content_type: str, fallback_index: int) -> str:
    if content_type in SUPPORTED_IMAGE_TYPES:
        return SUPPORTED_IMAGE_TYPES[content_type]
    subtype = content_type.rsplit("/", 1)[-1].lower()
    if subtype in {"png", "jpeg", "jpg", "gif", "bmp", "tiff"}:
        return "jpg" if subtype == "jpeg" else subtype
    return f"bin{fallback_index}"


def _nearest_caption(blocks: list[DocxBlock], block_index: int) -> tuple[str, int | None]:
    current = blocks[block_index].text.strip()
    if current and _looks_like_caption(current):
        return current, blocks[block_index].start_line

    for offset in range(1, 4):
        next_index = block_index + offset
        if next_index < len(blocks):
            text = blocks[next_index].text.strip()
            if text:
                if _looks_like_caption(text):
                    return text, blocks[next_index].start_line
                break

    for offset in range(1, 4):
        prev_index = block_index - offset
        if prev_index >= 0:
            text = blocks[prev_index].text.strip()
            if text:
                if _looks_like_caption(text):
                    return text, blocks[prev_index].start_line
                return text, blocks[prev_index].start_line

    return "Image from DOCX", blocks[block_index].start_line


def _caption_body(caption: str) -> str:
    match = re.match(
        r"^\s*(?:figure|fig|img|image|caption|chart)\s*\d*[:.\-]?\s*(.*)",
        caption,
        re.I,
    )
    if match and match.group(1).strip():
        return match.group(1).strip()
    return caption.strip()


def extract_docx_blueprint_source(docx_path: str, course_id: str) -> tuple[dict[str, str] | None, list[str], list[dict[str, Any]]]:
    """Extract course metadata, normalized body lines, and embedded images from a DOCX."""
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError(
            "DOCX support requires python-docx. Install backend requirements and restart."
        ) from exc

    logger.info("docx_extraction_started path=%s", docx_path)
    document = Document(docx_path)
    metadata: dict[str, str] | None = None
    blocks: list[DocxBlock] = []

    for block in _iter_body_blocks(document):
        if hasattr(block, "rows"):
            parsed_metadata = _table_metadata(block)
            table_block = DocxBlock(
                rows=_table_rows(block),
                is_table=True,
                is_metadata_table=parsed_metadata is not None,
                image_rids=_image_rids(block._element),
            )
            if parsed_metadata is not None and metadata is None:
                metadata = parsed_metadata
            blocks.append(table_block)
        else:
            blocks.append(
                DocxBlock(
                    text=_clean_text(block.text or ""),
                    image_rids=_image_rids(block._element),
                )
            )

    body_lines: list[str] = []
    for block in blocks:
        if block.is_metadata_table:
            continue
        new_lines = block.rows if block.is_table else _sentence_lines(block.text)
        if new_lines:
            block.start_line = len(body_lines) + 1
            body_lines.extend(new_lines)
            block.end_line = len(body_lines)

    image_dir = Path(IMAGE_DIR) / course_id
    image_dir.mkdir(parents=True, exist_ok=True)
    images: list[dict[str, Any]] = []
    seen_rids: set[str] = set()
    image_index = 0

    for block_index, block in enumerate(blocks):
        if block.is_metadata_table:
            continue
        for rid in block.image_rids:
            if rid in seen_rids:
                continue
            seen_rids.add(rid)
            part = document.part.related_parts.get(rid)
            content_type = getattr(part, "content_type", "")
            if part is None or not str(content_type).startswith("image/"):
                continue

            image_index += 1
            ext = _part_extension(str(content_type), image_index)
            filename = f"docx_img_{image_index}.{ext}"
            output_path = image_dir / filename
            output_path.write_bytes(part.blob)

            width = height = 0
            try:
                with PILImage.open(output_path) as opened:
                    width, height = opened.size
            except OSError:
                pass

            raw_caption, line = _nearest_caption(blocks, block_index)
            caption = _caption_body(raw_caption)
            aspect_ratio = width / height if width > 0 and height > 0 else None
            orientation = (
                "landscape" if aspect_ratio is not None and aspect_ratio >= 1.2
                else "portrait" if aspect_ratio is not None and aspect_ratio <= 0.83
                else "square"
            )

            images.append(
                {
                    "image_id": f"docx_img_{image_index}",
                    "caption": caption or f"Image {image_index}",
                    "raw_caption": raw_caption,
                    "file_path": public_asset_url("images", course_id, filename),
                    "page": 1,
                    "line": line,
                    "caption_line": line if _looks_like_caption(raw_caption) else None,
                    "bbox": None,
                    "width": width,
                    "height": height,
                    "aspect_ratio": aspect_ratio,
                    "orientation": orientation,
                }
            )

    logger.info(
        "docx_extraction_completed line_count=%s image_count=%s metadata=%s",
        len(body_lines),
        len(images),
        bool(metadata),
    )
    return metadata, body_lines, images
