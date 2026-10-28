"""Learning Journey completion certificates: a branded, verifiable PDF.

Laid out like the certificates learners know from online platforms such as Coursera and Udemy:
the learner's name in large type, what they completed, the date, the issuing company and its
signatory, and a unique certificate number that can be checked later. The signatory's name is
printed under a signature line; no handwritten signature is reproduced.
"""

from __future__ import annotations

import hashlib
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


def certificate_number(journey_assignment_id: str) -> str:
    """A stable, unguessable number for one learner's completion of one journey."""
    digest = hashlib.sha256(f"lms-journey-certificate:{journey_assignment_id}".encode()).hexdigest().upper()
    return f"PCIL-LJ-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"


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


def render_certificate_pdf(
    *,
    learner_name: str,
    journey_title: str,
    course_names: list[str],
    completed_at: str | None,
    number: str,
) -> bytes:
    """Draw the A4 landscape certificate and return the PDF bytes."""
    buffer = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    issuer = settings.certificate_issuer_name
    pdf.setTitle(f"Certificate of Completion: {journey_title}")
    pdf.setAuthor(issuer)
    pdf.setSubject(f"{learner_name} completed {journey_title}")

    # Frame: a brand-blue border with a fine gold rule inside it.
    pdf.setStrokeColor(BRAND_BLUE)
    pdf.setLineWidth(6)
    pdf.rect(18, 18, page_width - 36, page_height - 36)
    pdf.setStrokeColor(ACCENT_GOLD)
    pdf.setLineWidth(0.8)
    pdf.rect(30, 30, page_width - 60, page_height - 60)

    # Header: logo on the left, certificate number on the right.
    if LOGO_PATH.is_file():
        logo = ImageReader(str(LOGO_PATH))
        logo_width = 150
        image_width, image_height = logo.getSize()
        pdf.drawImage(
            logo,
            56,
            page_height - 56 - logo_width * image_height / image_width,
            width=logo_width,
            height=logo_width * image_height / image_width,
            mask="auto",
        )
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(page_width - 56, page_height - 60, "CERTIFICATE NO.")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(INK)
    pdf.drawRightString(page_width - 56, page_height - 74, number)

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
    title_lines = simpleSplit(journey_title, "Helvetica-Bold", 22, content_width)[:2]
    y = page_height - 316
    for line in title_lines:
        _centered(pdf, line, y, "Helvetica-Bold", 22, BRAND_BLUE)
        y -= 28

    if course_names:
        shown = course_names[:6]
        summary = " · ".join(shown)
        if len(course_names) > len(shown):
            summary += f" and {len(course_names) - len(shown)} more"
        label = f"{len(course_names)} course{'s' if len(course_names) != 1 else ''}: "
        lines = simpleSplit(label + summary, "Helvetica", 10, content_width - 60)[:2]
        for line in lines:
            _centered(pdf, line, y - 2, "Helvetica", 10, MUTED)
            y -= 14

    # Footer blocks: completion date on the left, signatory on the right.
    base = 108
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
    pdf.drawCentredString(right_center, base + 8, settings.certificate_signatory_name)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString(right_center, base - 6, settings.certificate_signatory_title)
    pdf.drawCentredString(right_center, base - 18, issuer)

    _centered(
        pdf,
        f"Issued by {issuer} through its Learning Management System. "
        f"This certificate can be verified with the Learning team using certificate number {number}.",
        48,
        "Helvetica",
        7.5,
        MUTED,
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _certificate_for(assignment: dict, journey: dict) -> tuple[str, bytes]:
    if not journey["certificate_enabled"] or not assignment.get("completed_at"):
        raise NotFoundError("A certificate is available once every required course is passed.")
    employee = _employees.get(assignment["employee_id"]) or {}
    number = certificate_number(assignment["journey_assignment_id"])
    pdf = render_certificate_pdf(
        learner_name=employee.get("name") or assignment["employee_id"],
        journey_title=journey["title"],
        course_names=[step["course_name"] for step in journey["steps"] if step["is_required"]],
        completed_at=assignment["completed_at"],
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


def verify_certificate(number: str) -> dict:
    """Who a certificate number belongs to, for any trainer checking a certificate."""
    wanted = number.strip().upper()
    for assignment in _journeys.completed_assignments():
        if certificate_number(assignment["journey_assignment_id"]) != wanted:
            continue
        journey = _journeys.get(assignment["journey_id"])
        if journey is None or not journey["certificate_enabled"]:
            break
        employee = _employees.get(assignment["employee_id"]) or {}
        return {
            "valid": True,
            "certificate_number": wanted,
            "learner_name": employee.get("name") or assignment["employee_id"],
            "department": employee.get("department") or "",
            "journey_title": journey["title"],
            "completed_at": assignment["completed_at"],
        }
    return {"valid": False, "certificate_number": wanted}
