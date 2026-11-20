"""Build small PDFs and read their text in tests, without a PDF engine of our own."""

from io import BytesIO

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


class _Page:
    def __init__(self, canvas: Canvas, height: float) -> None:
        self._canvas = canvas
        self._height = height

    def insert_text(self, point, text: str, size: int = 11) -> None:
        """Draw text lines; ``point`` is the first baseline, measured from the top-left."""
        x, y = point
        for index, line in enumerate(text.split("\n")):
            self._canvas.setFont("Helvetica", size)
            self._canvas.drawString(x, self._height - y - index * size * 1.2, line)

    def insert_image(self, rect, stream: bytes) -> None:
        """Draw an image into ``rect`` = (x0, y0, x1, y1), measured from the top-left."""
        x0, y0, x1, y1 = rect
        self._canvas.drawImage(
            ImageReader(BytesIO(stream)), x0, self._height - y1, width=x1 - x0, height=y1 - y0
        )


class PdfWriter:
    """``with PdfWriter(path) as document: document.new_page().insert_text(...)``"""

    def __init__(self, path) -> None:
        self._canvas = Canvas(str(path))
        self._open = False

    def __enter__(self) -> "PdfWriter":
        return self

    def __exit__(self, exc_type, *_) -> None:
        if exc_type is None:
            if self._open:
                self._canvas.showPage()
            self._canvas.save()

    def new_page(self, width: float = 595, height: float = 842) -> _Page:
        if self._open:
            self._canvas.showPage()
        self._canvas.setPageSize((width, height))
        self._open = True
        return _Page(self._canvas, height)


def pdf_pages(data: bytes) -> list[str]:
    """The text of each page of a PDF held in memory."""
    return [
        "".join(item.get_text() for item in page if isinstance(item, LTTextContainer))
        for page in extract_pages(BytesIO(data))
    ]
