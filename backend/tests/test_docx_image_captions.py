from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document
from docx.shared import Inches
from PIL import Image

from app.documents.docx import extract_docx_blueprint_source

ALT = "A typical money laundering scheme: placement, layering and integration"


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.documents.docx.IMAGE_DIR", str(tmp_path / "images"))


def _png() -> BytesIO:
    buffer = BytesIO()
    Image.new("RGB", (900, 500), "gray").save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _docx(path, *, alt: str | None, caption: str | None = None) -> str:
    document = Document()
    document.add_paragraph("Scheduled offence: an offence listed in Part A or Part C of the Schedule.")
    picture = document.add_picture(_png(), width=Inches(5))
    if alt is not None:
        picture._inline.docPr.set("descr", alt)
    if caption:
        document.add_paragraph(caption)
    document.add_paragraph("Money laundering usually happens in three stages.")
    document.save(path)
    return str(path)


def _caption(path) -> str:
    _, _, images = extract_docx_blueprint_source(path, "course_1")
    assert len(images) == 1
    return images[0]["caption"]


def test_alt_text_is_used_instead_of_the_neighbouring_line(tmp_path) -> None:
    assert _caption(_docx(tmp_path / "a.docx", alt=ALT)) == ALT


def test_an_explicit_figure_caption_still_wins_over_alt_text(tmp_path) -> None:
    path = _docx(tmp_path / "b.docx", alt=ALT, caption="Figure 1: The three stages")
    assert _caption(path) == "The three stages"


@pytest.mark.parametrize("alt", [None, "", "Picture 1", "image3.png", "A diagram Description automatically generated"])
def test_missing_or_generic_alt_text_keeps_the_old_fallback(tmp_path, alt) -> None:
    assert _caption(_docx(tmp_path / "c.docx", alt=alt)).startswith("Scheduled offence")
