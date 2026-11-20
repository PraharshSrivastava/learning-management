"""Read page geometry, text blocks and images from a PDF.

Built on pdfplumber (pdfminer.six for structure, pypdfium2 for rendering), which are
permissively licensed. Coordinates are in PDF points with the origin at the top-left
of the page, so a larger ``y`` is lower on the page.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Iterator

import pdfplumber
from pdfminer.layout import LTTextBox
from PIL import Image

# Rendering bounds for images that cannot be copied out of the file as they are.
_MIN_DPI = 72.0
_MAX_DPI = 300.0

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class PdfImage:
    """One image placed on a page."""

    xref: int | None  # PDF object number; the same number means the same image data
    bbox: BBox  # (x0, y0, x1, y1) where the image is drawn
    width: int  # pixel size of the stored image
    height: int
    _stream: Any = None


class PdfPage:
    def __init__(self, page: Any, number: int) -> None:
        self._page = page
        self.number = number
        self.width = float(page.width)
        self.height = float(page.height)

    def text(self) -> str:
        return self._page.extract_text() or ""

    def text_blocks(self) -> list[tuple[float, float, float, float, str]]:
        """Paragraph-like blocks as (x0, y0, x1, y1, text), top to bottom.

        Blocks come from pdfminer's layout analysis, which groups nearby lines into
        text boxes. Lines inside a block are joined with newlines.
        """
        blocks = []
        for item in self._page.layout:
            if not isinstance(item, LTTextBox):
                continue
            value = item.get_text().strip("\n")
            if not value.strip():
                continue
            x0, y0, x1, y1 = item.bbox  # pdfminer measures from the bottom-left
            blocks.append(
                (float(x0), self.height - float(y1), float(x1), self.height - float(y0), value)
            )
        blocks.sort(key=lambda block: (block[1], block[0]))
        return blocks

    def images(self) -> list[PdfImage]:
        """Images in the order they appear, top to bottom then left to right."""
        found = []
        for item in self._page.images:
            source = item.get("srcsize") or (0, 0)
            stream = item.get("stream")
            found.append(
                PdfImage(
                    xref=getattr(stream, "objid", None),
                    bbox=(
                        float(item["x0"]),
                        float(item["top"]),
                        float(item["x1"]),
                        float(item["bottom"]),
                    ),
                    width=int(source[0] or 0),
                    height=int(source[1] or 0),
                    _stream=stream,
                )
            )
        found.sort(key=lambda image: (round(image.bbox[1], 1), round(image.bbox[0], 1)))
        return found

    def image_bytes(self, image: PdfImage) -> tuple[bytes, str]:
        """The image as a file: the stored JPEG when it is a plain one, else a PNG render.

        Raises ValueError when the image has no visible area on the page.
        """
        stored = _plain_jpeg(image._stream)
        if stored is not None:
            return stored, "jpeg"

        x0, y0, x1, y1 = image.bbox
        box = (max(x0, 0.0), max(y0, 0.0), min(x1, self.width), min(y1, self.height))
        if box[2] - box[0] < 1 or box[3] - box[1] < 1:
            raise ValueError("Image has no visible area on the page")
        dpi = 72.0 * image.width / (x1 - x0) if image.width and x1 > x0 else 150.0
        dpi = min(max(dpi, _MIN_DPI), _MAX_DPI)
        rendered = self._page.crop(box, strict=False).to_image(resolution=dpi).original
        output = io.BytesIO()
        rendered.convert("RGB").save(output, format="PNG")
        return output.getvalue(), "png"


class PdfDocument:
    """``with PdfDocument(path) as pdf: for page in pdf: ...``"""

    def __init__(self, path: Any) -> None:
        # Layout parameters switch on pdfminer's text-box grouping for ``text_blocks``.
        self._pdf = pdfplumber.open(path, laparams={})

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._pdf.close()

    def __len__(self) -> int:
        return len(self._pdf.pages)

    def __iter__(self) -> Iterator[PdfPage]:
        for index, page in enumerate(self._pdf.pages):
            yield PdfPage(page, index + 1)

    def page(self, number: int) -> PdfPage:
        """A page by its 1-based number."""
        return PdfPage(self._pdf.pages[number - 1], number)


def pdf_has_images(path: Any) -> bool:
    with PdfDocument(path) as pdf:
        return any(page.images() for page in pdf)


def _plain_jpeg(stream: Any) -> bytes | None:
    """The stored bytes when the image is an ordinary RGB or grey JPEG with no mask."""
    if stream is None:
        return None
    try:
        filters = [str(getattr(name, "name", name)) for name, _ in stream.get_filters()]
        if filters not in (["DCTDecode"], ["DCT"]):
            return None
        if stream.attrs.get("SMask") is not None or stream.attrs.get("Mask") is not None:
            return None
        data = stream.get_rawdata()
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format != "JPEG" or probe.mode not in ("RGB", "L"):
                return None
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        return None
