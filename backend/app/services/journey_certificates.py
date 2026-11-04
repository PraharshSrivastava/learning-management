"""Learning Journey completion certificates: a branded, verifiable PDF.

Laid out like the certificates learners know from online platforms such as Coursera and Udemy:
the learner's name in large type, the journey and its courses, the completion date, and the
issuing Learning & Development team with its stamp. There is no personal signatory; the footer
says the certificate is computer-generated and that it records internal learning.

A certificate is stored when the journey is completed (learner name, journey title, courses and
date as they were then), and every download or check reads that record. Renaming the journey or
changing its courses later never changes a certificate already issued.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.core.exceptions import NotFoundError
from app.core.settings import settings
from app.repositories.employees import EmployeeRepository
from app.repositories.journeys import JourneyRepository

_journeys = JourneyRepository()
_employees = EmployeeRepository()

LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "brand" / "phillipcapital-new-brand-logo.png"
BRAND_BLUE = HexColor("#00317A")
ACCENT_GOLD = HexColor("#B8892B")
INK = HexColor("#172033")
MUTED = HexColor("#5F6878")
RULE = HexColor("#D0DBF4")

ISSUING_TEAM = "Learning & Development"
# The course list sits between the journey title and the date / issuer row; below this it would
# run into the stamp, so a list that cannot fit moves to a second page.
_FOOTER_BASE = 108
_LIST_BOTTOM = _FOOTER_BASE + 62
_COURSE_SIZES = (10, 9.5, 9, 8.5)


def certificate_number(journey_assignment_id: str) -> str:
    """A stable, unguessable number for one learner's completion of one journey."""
    digest = hashlib.sha256(f"lms-journey-certificate:{journey_assignment_id}".encode()).hexdigest().upper()
    return f"PCIL-LJ-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"


def clean_course_name(name: str) -> str:
    """Drop a trailing internal tag such as '(Varsity)' or '(SB, C1)' that means nothing to a reader."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", name).strip() or name


def _completion_date(value: str | None) -> str:
    try:
        parsed = datetime.fromisoformat(value or "")
    except ValueError:
        return ""
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def _fit_font(text: str, font: str, start: float, minimum: float, width: float) -> float:
    size = start
    while size > minimum and stringWidth(text, font, size) > width:
        size -= 1
    return size


def _centered(pdf: canvas.Canvas, text: str, y: float, font: str, size: float, color) -> None:
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    pdf.drawCentredString(pdf._pagesize[0] / 2, y, text)


def _spaced(text: str) -> str:
    return " ".join(text.upper())


def _frame_and_header(pdf: canvas.Canvas, number: str) -> None:
    """Brand-blue border with a fine gold rule inside; logo left, certificate number right."""
    page_width, page_height = pdf._pagesize
    pdf.setStrokeColor(BRAND_BLUE)
    pdf.setLineWidth(6)
    pdf.rect(18, 18, page_width - 36, page_height - 36)
    pdf.setStrokeColor(ACCENT_GOLD)
    pdf.setLineWidth(0.8)
    pdf.rect(30, 30, page_width - 60, page_height - 60)
    if LOGO_PATH.is_file():
        logo = ImageReader(str(LOGO_PATH))
        logo_width = 150
        image_width, image_height = logo.getSize()
        logo_height = logo_width * image_height / image_width
        pdf.drawImage(logo, 56, page_height - 56 - logo_height, width=logo_width, height=logo_height, mask="auto")
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(page_width - 56, page_height - 60, "CERTIFICATE NO.")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(INK)
    pdf.drawRightString(page_width - 56, page_height - 74, number)


def _footer_notes(pdf: canvas.Canvas) -> None:
    issuer = settings.certificate_issuer_name
    _centered(
        pdf,
        f"This is a computer-generated certificate issued by {issuer} through PhillipAcademy.",
        58,
        "Helvetica",
        7.5,
        MUTED,
    )
    _centered(
        pdf,
        "This certificate recognises completion of an internal learning journey and is not a regulatory certification.",
        46,
        "Helvetica",
        7.5,
        MUTED,
    )


def _arc_text(pdf: canvas.Canvas, text: str, radius: float, top: bool, size: float = 6.2) -> None:
    """Letters set around a circle, reading left to right across its top or its bottom."""
    pdf.setFont("Helvetica-Bold", size)
    widths = [stringWidth(char, "Helvetica-Bold", size) for char in text]
    span = sum(widths) / radius
    angle = math.pi / 2 + span / 2 if top else -math.pi / 2 - span / 2
    for char, width in zip(text, widths):
        step = width / radius
        middle = angle - step / 2 if top else angle + step / 2
        pdf.saveState()
        pdf.translate(radius * math.cos(middle), radius * math.sin(middle))
        pdf.rotate(math.degrees(middle) - 90 if top else math.degrees(middle) + 90)
        pdf.drawCentredString(0, 0, char)
        pdf.restoreState()
        angle = angle - step if top else angle + step


def _stamp(pdf: canvas.Canvas, x: float, y: float, radius: float = 46) -> None:
    """A hollow, tilted ink stamp pressed over the issuer block; the text under it stays readable."""
    pdf.saveState()
    pdf.translate(x, y)
    pdf.rotate(-14)
    pdf.setStrokeColor(BRAND_BLUE)
    pdf.setFillColor(BRAND_BLUE)
    pdf.setStrokeAlpha(0.7)
    pdf.setFillAlpha(0.7)
    pdf.setLineWidth(2.2)
    pdf.circle(0, 0, radius)
    pdf.setLineWidth(0.8)
    pdf.circle(0, 0, radius - 4)
    pdf.circle(0, 0, radius - 17)
    _arc_text(pdf, "PHILLIPCAPITAL INDIA", radius - 12.5, top=True)
    _arc_text(pdf, "LEARNING & DEVELOPMENT", radius - 8, top=False)
    for side in (-1, 1):
        pdf.circle(side * (radius - 10.5), 0, 1.1, stroke=0, fill=1)
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawCentredString(0, 6, "LEARNING")
    pdf.drawCentredString(0, -2, "JOURNEY")
    pdf.setLineWidth(0.6)
    pdf.line(-16, -6, 16, -6)
    pdf.setFont("Helvetica-Bold", 5.6)
    pdf.drawCentredString(0, -13, "COMPLETED")
    pdf.restoreState()


def _course_columns(
    courses: list[str], width: float, size: float, count: int
) -> tuple[list[list[str]], float, float]:
    """Numbered courses over `count` columns for the course record page; a wrapped course name
    stays together in one column."""
    column_width = (width - 28 * (count - 1)) / count
    entries = []
    for number, name in enumerate(courses, 1):
        wrapped = simpleSplit(f"{number}.  {name}", "Helvetica", size, column_width)
        entries.append([wrapped[0]] + ["    " + text for text in wrapped[1:]])
    target = sum(len(entry) for entry in entries) / count
    columns: list[list[str]] = [[]]
    for entry in entries:
        if columns[-1] and len(columns[-1]) + len(entry) / 2 > target and len(columns) < count:
            columns.append([])
        columns[-1] += entry
    return columns, column_width, max(len(column) for column in columns) * size * 1.5


def _course_record_page(pdf: canvas.Canvas, learner_name: str, journey_title: str, courses: list[str], number: str) -> None:
    page_width, page_height = pdf._pagesize
    _frame_and_header(pdf, number)
    _centered(pdf, _spaced("Course Record"), page_height - 130, "Helvetica-Bold", 13, BRAND_BLUE)
    pdf.setStrokeColor(ACCENT_GOLD)
    pdf.setLineWidth(1.2)
    pdf.line(page_width / 2 - 40, page_height - 140, page_width / 2 + 40, page_height - 140)
    heading = f"{learner_name}  ·  {journey_title}"
    _centered(pdf, heading, page_height - 162, "Helvetica-Bold", _fit_font(heading, "Helvetica-Bold", 11, 8, page_width - 160), INK)
    _centered(pdf, f"{len(courses)} courses completed", page_height - 178, "Helvetica", 9, MUTED)
    # The largest type that fits, in as few (wide) columns as possible.
    width = page_width - 160
    layouts = ((size, count) for size in (9.5, 9, 8.5, 8, 7.5, 7) for count in (1, 2, 3))
    for size, count in layouts:
        columns, column_width, height = _course_columns(courses, width, size, count)
        if page_height - 205 - height >= 80:
            break
    used = len(columns) * column_width + (len(columns) - 1) * 28
    left = (page_width - used) / 2
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", size)
    for index, column in enumerate(columns):
        y = page_height - 205
        for text in column:
            pdf.drawString(left + index * (column_width + 28), y, text)
            y -= size * 1.5
    _footer_notes(pdf)
    pdf.showPage()


def render_certificate_pdf(
    *,
    learner_name: str,
    journey_title: str,
    course_names: list[str],
    completed_at: str | None,
    number: str,
) -> bytes:
    """Draw the A4 landscape certificate (plus a course record page if needed) and return the PDF bytes."""
    buffer = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    issuer = settings.certificate_issuer_name
    pdf.setTitle(f"Certificate of Completion: {journey_title}")
    pdf.setAuthor(issuer)
    pdf.setSubject(f"{learner_name} completed {journey_title}")
    _frame_and_header(pdf, number)

    content_width = page_width - 160
    _centered(pdf, _spaced("Certificate of Completion"), page_height - 150, "Helvetica-Bold", 15, BRAND_BLUE)
    pdf.setStrokeColor(ACCENT_GOLD)
    pdf.setLineWidth(1.2)
    pdf.line(page_width / 2 - 40, page_height - 162, page_width / 2 + 40, page_height - 162)

    _centered(pdf, "This is to certify that", page_height - 196, "Helvetica", 13, MUTED)
    name_size = _fit_font(learner_name, "Times-Bold", 38, 22, content_width)
    _centered(pdf, learner_name, page_height - 240, "Times-Bold", name_size, INK)
    pdf.setStrokeColor(RULE)
    pdf.setLineWidth(0.8)
    pdf.line(page_width / 2 - 190, page_height - 252, page_width / 2 + 190, page_height - 252)

    _centered(pdf, "has successfully completed the learning journey", page_height - 282, "Helvetica", 13, MUTED)
    y = page_height - 316
    for line in simpleSplit(journey_title, "Helvetica-Bold", 22, content_width)[:2]:
        _centered(pdf, line, y, "Helvetica-Bold", 22, BRAND_BLUE)
        y -= 28

    # Courses: one centred paragraph, shrunk to fit; a list too long for that goes to page 2.
    courses = [clean_course_name(name) for name in course_names]
    overflow = False
    if courses:
        label = f"{len(courses)} course{'s' if len(courses) != 1 else ''}"
        text = f"{label}: " + " · ".join(courses)
        overflow = True
        for size in _COURSE_SIZES:
            lines = simpleSplit(text, "Helvetica", size, content_width - 60)
            if y - 2 - (len(lines) - 1) * size * 1.4 - size >= _LIST_BOTTOM:
                overflow = False
                for line in lines:
                    _centered(pdf, line, y - 2, "Helvetica", size, MUTED)
                    y -= size * 1.4
                break
        if overflow:
            _centered(pdf, f"{label} · full list on page 2", y - 2, "Helvetica", 10, MUTED)

    # Footer: completion date on the left, the issuing team on the right with the stamp over it.
    base = _FOOTER_BASE
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.6)
    pdf.line(90, base + 22, 290, base + 22)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(INK)
    pdf.drawCentredString(190, base + 30, _completion_date(completed_at))
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString(190, base + 8, "Date of completion")

    right_center = page_width - 190
    pdf.line(right_center - 100, base + 22, right_center + 100, base + 22)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(INK)
    pdf.drawCentredString(right_center, base + 30, ISSUING_TEAM)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString(right_center, base + 8, "Issued by")
    pdf.drawCentredString(right_center, base - 6, issuer)
    _stamp(pdf, right_center + 62, base + 10)

    _footer_notes(pdf)
    pdf.showPage()
    if overflow:
        _course_record_page(pdf, learner_name, journey_title, courses, number)
    pdf.save()
    return buffer.getvalue()


def issue_certificate(assignment: dict, journey: dict) -> dict | None:
    """Store the certificate for a completed journey as it reads now; an issued one never changes."""
    if not journey["certificate_enabled"] or not assignment.get("completed_at"):
        return None
    stored = _journeys.certificate_for_assignment(assignment["journey_assignment_id"])
    if stored is not None:
        return stored
    employee = _employees.get(assignment["employee_id"]) or {}
    return _journeys.issue_certificate(
        {
            "certificate_number": certificate_number(assignment["journey_assignment_id"]),
            "journey_assignment_id": assignment["journey_assignment_id"],
            "journey_id": assignment["journey_id"],
            "employee_id": assignment["employee_id"],
            "learner_name": employee.get("name") or assignment["employee_id"],
            "journey_title": journey["title"],
            "course_names": [step["course_name"] for step in journey["steps"] if step["is_required"]],
            "completed_at": assignment["completed_at"],
        }
    )


def _certificate_for(assignment: dict, journey: dict) -> tuple[str, bytes]:
    certificate = issue_certificate(assignment, journey)
    if certificate is None:
        raise NotFoundError("A certificate is available once every required course is passed.")
    number = certificate["certificate_number"]
    pdf = render_certificate_pdf(
        learner_name=certificate["learner_name"],
        journey_title=certificate["journey_title"],
        course_names=list(certificate["course_names"] or []),
        completed_at=certificate["completed_at"],
        number=number,
    )
    return f"{number}.pdf", pdf


def learner_certificate(employee_id: str, journey_id: str) -> tuple[str, bytes]:
    """The signed-in learner's own certificate for a journey they completed."""
    assignment = _journeys.assignments_for_employee(employee_id).get(journey_id)
    journey = _journeys.get(journey_id)
    if assignment is None or journey is None:
        raise NotFoundError("Certificate not found")
    return _certificate_for(assignment, journey)


def _issue_unstored(number: str) -> dict | None:
    """A journey completed before certificates were stored: issue its certificate on first check."""
    for assignment in _journeys.completed_assignments():
        if certificate_number(assignment["journey_assignment_id"]) == number:
            journey = _journeys.get(assignment["journey_id"])
            return issue_certificate(assignment, journey) if journey else None
    return None


def verify_certificate(number: str) -> dict:
    """Who a certificate number belongs to, for any trainer checking a certificate."""
    wanted = number.strip().upper()
    certificate = _journeys.get_certificate(wanted) or _issue_unstored(wanted)
    journey = _journeys.get(certificate["journey_id"]) if certificate else None
    if certificate is None or journey is None or not journey["certificate_enabled"]:
        return {"valid": False, "certificate_number": wanted}
    employee = _employees.get(certificate["employee_id"]) or {}
    return {
        "valid": True,
        "certificate_number": wanted,
        "learner_name": certificate["learner_name"],
        "department": employee.get("department") or "",
        "journey_title": certificate["journey_title"],
        "completed_at": certificate["completed_at"],
        "issued_at": certificate["issued_at"],
    }
