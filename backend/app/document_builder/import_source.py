"""Immutable owned source import, without course creation or source rewriting."""

from __future__ import annotations

import hashlib
import re
import shutil
from io import BytesIO
from uuid import uuid4

from app.core.exceptions import NotFoundError
from app.core.settings import settings
from app.repositories.documents import get_document
from app.schemas.document_workflow import (
    DraftModule,
    ExtractedSource,
    ImageBlock,
    SourceReference,
    SourceSpan,
    TableBlock,
    TextBlock,
)


class SourceImporter:
    def __init__(self, repository):
        self.repository = repository

    def load(self, draft_id, owner, request):
        draft = self.repository.get(draft_id, owner)
        if draft.revision != request.expectedRevision:
            from app.core.exceptions import ConflictError

            raise ConflictError("Save changed; reload before importing")
        if draft.content.modules and not request.referenceOnly:
            raise ValueError("Import into an empty draft to avoid overwriting existing work")
        source_id = uuid4().hex
        folder = settings.derived_document_dir / "builder" / draft_id / source_id
        folder.mkdir(parents=True, exist_ok=True)
        issues, blocks, spans, metadata = [], [], [], {}
        resources = []
        if request.documentId:
            document = get_document(request.documentId)
            if not document or document["trainer_id"] != owner:
                raise NotFoundError("Source document not found")
            source_path = (settings.upload_dir / document["file_path"]).resolve()
            if source_path.parent != settings.upload_dir.resolve() or not source_path.is_file():
                raise NotFoundError("Source file not found")
            if source_path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Source exceeds the 20 MB limit")
            snapshot = folder / ("original" + source_path.suffix.lower())
            with snapshot.open("xb") as destination, source_path.open("rb") as source:
                shutil.copyfileobj(source, destination)
            digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            name = document["file_name"].split("__", 1)[-1]
        else:
            snapshot = folder / "original.txt"
            snapshot.write_text(request.text, encoding="utf-8")
            digest = hashlib.sha256(request.text.encode()).hexdigest()
            name = "Pasted content"

        def text(value, location, kind="paragraph"):
            if not value.strip():
                return
            lines = value.splitlines()
            if len(lines) > 1 and re.match(r"^Module\s+\d+\s*:", lines[0], re.I):
                text(lines[0], location, "heading")
                text("\n".join(lines[1:]), location)
                return
            # Preserve wording; chunk only at boundaries for schema/context limits.
            for start in range(0, len(value), 18000):
                part = value[start : start + 18000]
                span = SourceSpan(id=uuid4().hex, text=part, location=location)
                spans.append(span)
                blocks.append(
                    (
                        TextBlock(
                            id=uuid4().hex,
                            type=kind,
                            text=part,
                            sourceReferences=[SourceReference(sourceId=source_id, spanId=span.id)],
                        ),
                        span.id,
                    )
                )

        def image(data, location):
            from PIL import Image

            try:
                with Image.open(BytesIO(data)) as value:
                    if value.width * value.height > 25000000:
                        raise ValueError("Image is too large")
                    asset_id = uuid4().hex
                    path = folder / (asset_id + ".png")
                    value.convert("RGB").save(path, "PNG")
                resources.append(
                    {
                        "id": asset_id,
                        "kind": "asset",
                        "body": {
                            "path": str(path),
                            "mime": "image/png",
                            "caption": location,
                        },
                    }
                )
                blocks.append(
                    (ImageBlock(id=uuid4().hex, assetId=asset_id, caption=location), None)
                )
            except (OSError, ValueError, Image.DecompressionBombError):
                issues.append(f"Unsupported image at {location}; review the original source")

        suffix = snapshot.suffix
        if suffix == ".txt":
            for number, paragraph in enumerate(re.split(r"\n\s*\n", request.text), 1):
                text(paragraph, f"Pasted paragraph {number}")
        elif suffix == ".pdf":
            import fitz

            with fitz.open(snapshot) as pdf:
                for number, page in enumerate(pdf, 1):
                    if not page.get_text().strip():
                        issues.append(f"Page {number} has no readable text; OCR is not available")
                    for block in page.get_text("dict")["blocks"]:
                        if block["type"] == 0:
                            value = "\n".join(
                                "".join(span["text"] for span in line["spans"])
                                for line in block["lines"]
                            )
                            text(value, f"Page {number}")
                        elif block["type"] == 1:
                            image(block["image"], f"Image on page {number}")
            issues.append(
                "PDF layout and tables are converted to reading-order blocks; review against the original"
            )
        elif suffix == ".docx":
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            from app.documents.docx import _table_metadata

            document = Document(snapshot)
            for number, element in enumerate(document.element.body, 1):
                location = f"Word block {number}"
                if element.tag.endswith("}p"):
                    paragraph = Paragraph(element, document)
                    text(
                        paragraph.text,
                        location,
                        "heading" if paragraph.style.name.startswith("Heading") else "paragraph",
                    )
                    for node in element.iter():
                        if node.tag.endswith("}blip"):
                            rid = node.get(
                                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                            )
                            if rid and rid in document.part.related_parts:
                                image(document.part.related_parts[rid].blob, location)
                elif element.tag.endswith("}tbl"):
                    table = Table(element, document)
                    found = _table_metadata(table)
                    if found:
                        metadata.update(found)
                        continue
                    rows = [[cell.text for cell in row.cells] for row in table.rows]
                    if rows and len(rows) <= 100 and max(map(len, rows)) <= 20:
                        span = SourceSpan(
                            id=uuid4().hex,
                            text="\n".join(" | ".join(row) for row in rows),
                            location=location,
                        )
                        spans.append(span)
                        blocks.append(
                            (
                                TableBlock(
                                    id=uuid4().hex,
                                    rows=rows,
                                    sourceReferences=[
                                        SourceReference(sourceId=source_id, spanId=span.id)
                                    ],
                                ),
                                span.id,
                            )
                        )
                    else:
                        text("\n".join(" | ".join(row) for row in rows), location)
                        issues.append(f"Large table at {location} converted to text")
            issues.append(
                "Word styling is normalized; embedded images and supported tables are retained"
            )
        elif suffix == ".pptx":
            from pptx import Presentation

            presentation = Presentation(snapshot)
            for number, slide in enumerate(presentation.slides, 1):
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        text(
                            shape.text,
                            f"Slide {number}",
                            "heading" if shape == slide.shapes.title else "paragraph",
                        )
                    elif shape.has_table:
                        text(
                            "\n".join(
                                " | ".join(cell.text for cell in row.cells)
                                for row in shape.table.rows
                            ),
                            f"Slide {number} table",
                        )
                    elif shape.shape_type == 13:
                        image(shape.image.blob, f"Image on slide {number}")
            issues.append("PowerPoint animations and layouts are normalized into document blocks")
        else:
            raise ValueError("Unsupported source format")
        if not spans:
            raise ValueError(
                "No readable text was extracted. Provide a text document or pasted content."
            )
        if len(spans) > 20000 or sum(len(span.text) for span in spans) > 1000000:
            raise ValueError("Extracted source is too large; split the source document")
        source = ExtractedSource(
            id=source_id,
            documentId=request.documentId,
            contentHash=digest,
            spans=spans,
            issues=issues,
        )
        resources.append(
            {
                "id": source_id,
                "kind": "source",
                "body": {
                    **source.model_dump(),
                    "path": str(snapshot),
                    "name": name,
                },
            }
        )
        if request.referenceOnly:
            return self.repository.import_content(
                draft_id, owner, request.expectedRevision, draft.content, resources
            )
        modules = []
        current = None
        for block, span_id in blocks:
            heading = (
                re.match(r"^Module\s+\d+\s*:\s*(.+)$", block.text.strip(), re.I)
                if isinstance(block, TextBlock)
                else None
            )
            if current is None or heading or (block.type == "heading" and current.blocks):
                current = DraftModule(
                    id=uuid4().hex,
                    title=(
                        heading.group(1)
                        if heading
                        else block.text[:200]
                        if block.type == "heading"
                        else name[:200]
                    ),
                    status="ready",
                )
                modules.append(current)
            # Retain source headings as content so no text disappears on import.
            if span_id:
                current.sourceReferences.append(SourceReference(sourceId=source_id, spanId=span_id))
            # Explicit module headings move into the module title; keep their
            # source reference, without stale numbering duplicated in the body.
            if not heading:
                current.blocks.append(block)
        content = draft.content.model_copy(deep=True)
        content.entryMode = "existing"
        content.modules = modules
        if not content.metadata.courseName:
            content.metadata.courseName = name.rsplit(".", 1)[0][:240]
        mapping = {
            "course_name": "courseName",
            "course_description": "courseDescription",
            "course_objective": "courseObjective",
            "course_difficulty": "courseDifficulty",
            "target_audience": "targetAudience",
            "language": "language",
        }
        for key, field in mapping.items():
            if metadata.get(key):
                setattr(content.metadata, field, metadata[key])
        return self.repository.import_content(
            draft_id, owner, request.expectedRevision, content, resources
        )
