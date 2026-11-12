"""PDF renderer copied from the scratch document builder."""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from xml.sax.saxutils import escape


REQUIRED_METADATA_FIELDS = [
    ("courseName", "Course Name"),
    ("courseDescription", "Course Description"),
    ("courseObjective", "Course Objective"),
    ("courseDifficulty", "Course Difficulty"),
    ("language", "Language"),
    ("targetAudience", "Target Audience"),
    ("courseType", "Course Type"),
]


def safe_filename(value: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in value)
    safe = "-".join(part for part in safe.split("-") if part)
    return (safe or "document")[:60]


def _paragraph_lines(document: str) -> list[str]:
    lines = []
    for raw_line in document.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _image_bytes_from_data_url(src: str) -> bytes:
    if src.startswith("data:image/") and "," in src:
        src = src.split(",", 1)[1]
    try:
        return base64.b64decode(src, validate=True)
    except binascii.Error as exc:
        raise ValueError("Image data is not valid base64.") from exc


def render_pdf(metadata: dict, document: str, blocks: list[dict]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=.75*inch, leftMargin=.75*inch,
                            topMargin=1.15*inch, bottomMargin=.75*inch,
                            title=str(metadata.get("courseName") or "Training Document"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("ScratchBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=12, leading=15, spaceAfter=10)
    label = ParagraphStyle("ScratchLabel", parent=styles["BodyText"], fontName="Times-Bold", fontSize=18, leading=22, spaceAfter=0)
    value = ParagraphStyle("ScratchValue", parent=styles["BodyText"], fontName="Times-Roman", fontSize=18, leading=22, spaceAfter=0)
    module = ParagraphStyle("ScratchModuleHeading", parent=body, fontName="Helvetica", fontSize=12, leading=15, spaceBefore=0, spaceAfter=10)
    bullet = ParagraphStyle("ScratchBullet", parent=body, leftIndent=16, firstLineIndent=-9)
    caption_style = ParagraphStyle("ScratchCaption", parent=body, fontName="Helvetica-Oblique", fontSize=10, leading=12, spaceAfter=10)
    rows = [[Paragraph(escape(name), label), Paragraph(escape(str(metadata.get(key) or "")), value)] for key, name in REQUIRED_METADATA_FIELDS]
    story = [Table(rows, colWidths=[3.25*inch, 3.25*inch], repeatRows=0, style=TableStyle([
        ("GRID", (0,0), (-1,-1), 1, "black"), ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ])), PageBreak(), Spacer(1, .95*inch)]
    text_blocks_seen = False
    for block in blocks:
        if block.get("type") == "image":
            raw = _image_bytes_from_data_url(str(block.get("src") or ""))
            reader = ImageReader(BytesIO(raw)); image_width, image_height = reader.getSize()
            target_width = doc.width * (int(block.get("width") or 60) / 100)
            target_height = target_width * (image_height / image_width)
            if target_height > 4.8*inch:
                target_height = 4.8*inch; target_width = target_height * (image_width / image_height)
            image = Image(BytesIO(raw), width=target_width, height=target_height)
            align = str(block.get("align") or "left").upper()
            image.hAlign = align if align in {"LEFT", "CENTER", "RIGHT"} else "LEFT"
            flowables = [image]
            caption = str(block.get("caption") or "").strip()
            if caption: flowables.append(Paragraph(escape(caption), caption_style))
            story.extend([KeepTogether(flowables), Spacer(1, 8)])
            continue
        text_blocks_seen = True
        for line in _paragraph_lines(str(block.get("text") or "")):
            escaped = escape(line)
            if line.lower().startswith("module ") and ":" in line: story.append(Paragraph(escaped, module))
            elif line.startswith(("- ", "* ")): story.append(Paragraph(escape(line[2:].strip()), bullet, bulletText="-"))
            else: story.append(Paragraph(escaped, body))
    if not text_blocks_seen:
        for line in _paragraph_lines(document):
            escaped = escape(line)
            if line.lower().startswith("module ") and ":" in line: story.append(Paragraph(escaped, module))
            elif line.startswith(("- ", "* ")): story.append(Paragraph(escape(line[2:].strip()), bullet, bulletText="-"))
            else: story.append(Paragraph(escaped, body))
            if line == "": story.append(Spacer(1, 6))
    doc.build(story)
    return buffer.getvalue()
