"""Approved LMS course-notification email templates."""

from __future__ import annotations

import html
import math
from datetime import UTC, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.core.settings import settings

FOOTER = "This is an automated LMS notification. Please do not reply to this email."
DIGEST_ROW_LIMIT = 25


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _local(value: str | None) -> datetime | None:
    parsed = _parse(value)
    if parsed is None:
        return None
    timezone = ZoneInfo(settings.email_notification_timezone)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC).astimezone(timezone)
    return parsed.astimezone(timezone)


def format_date(value: str | None) -> str:
    parsed = _local(value)
    return parsed.strftime("%d %b %Y") if parsed else "Not set"


def format_datetime(value: str | None) -> str:
    parsed = _local(value)
    return parsed.strftime("%d %b %Y, %I:%M %p") if parsed else "Not set"


def first_name(value: str | None, fallback: str) -> str:
    name = " ".join(str(value or "").strip().split())
    if not name:
        return fallback
    if "," in name:
        after_comma = name.split(",", 1)[1].strip()
        if after_comma:
            return after_comma.split()[0]
    return name.split()[0]


def _absolute_url(base: str | None, **query: str) -> str:
    resolved = (base or settings.lms_public_url or "").rstrip("/")
    if not resolved:
        return "Open the LMS from the Hub dashboard"
    return f"{resolved}/?{urlencode(query)}" if query else resolved


def course_link(context: dict) -> str:
    return settings.lms_hub_login_url or "Open the LMS from the Hub dashboard"


def hod_report_link(event_type: str) -> str:
    return ""


def trainer_report_link(event_type: str, course_id: str | None = None) -> str:
    return settings.lms_hub_login_url or "Open the LMS from the Hub dashboard"


def completion_timing(context: dict) -> tuple[str, str]:
    completed = _local(context.get("completed_at"))
    deadline = _local(context.get("deadline"))
    if not completed or not deadline:
        return "", "Completed"
    seconds = (deadline - completed).total_seconds()
    if seconds > 0:
        days = int(seconds // 86400)
        if days >= 1:
            unit = "day" if days == 1 else "days"
            status = f"Completed {days} {unit} before the deadline"
            return f"{days} {unit} before the deadline", status
        return "before the deadline", "Completed before the deadline"
    if seconds == 0:
        return "on time", "Completed on time"
    return "after the deadline", "Completed after the deadline"


def days_overdue(context: dict, now: datetime | None = None) -> str:
    deadline = _local(context.get("deadline"))
    if not deadline:
        return "Not available"
    current = now or datetime.now(ZoneInfo(settings.email_notification_timezone))
    if current.tzinfo is None:
        current = current.replace(tzinfo=deadline.tzinfo)
    seconds = max(0.0, (current - deadline).total_seconds())
    days = int(seconds // 86400)
    if days < 1:
        return "Less than 1 day"
    return f"{days} day" if days == 1 else f"{days} days"


def time_remaining(context: dict, now: datetime | None = None) -> str:
    deadline = _local(context.get("deadline"))
    if not deadline:
        return "Not available"
    current = now or datetime.now(ZoneInfo(settings.email_notification_timezone))
    if current.tzinfo is None:
        current = current.replace(tzinfo=deadline.tzinfo)
    seconds = (deadline - current).total_seconds()
    if seconds <= 0:
        return "Deadline passed"
    if seconds < 86400:
        hours = max(1, math.ceil(seconds / 3600))
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    days = math.ceil(seconds / 86400)
    return f"{days} day" if days == 1 else f"{days} days"


def overdue_notice(context: dict) -> tuple[int, int]:
    """(this overdue notice, total notices); the last notice is the escalation."""
    maximum = int(context.get("overdue_notice_max") or settings.email_overdue_max_notices)
    return int(context.get("overdue_notice") or 1), maximum


def is_overdue_escalation(context: dict) -> bool:
    notice, maximum = overdue_notice(context)
    return notice >= maximum


def overdue_reminder_status(context: dict) -> str:
    notice, maximum = overdue_notice(context)
    return "Escalated" if notice >= maximum else f"{notice} of {maximum - 1}"


def ordinal(value: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
    if value in words:
        return words[value]
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _details_text(values: list[tuple[str, object]]) -> list[str]:
    return [f"{label}: {value}" for label, value in values]


def _html_document(title: str, paragraphs: list[str], details: list[tuple[str, object]], link_label: str | None = None, link: str | None = None, table: str | None = None, guidance: str = "") -> str:
    font = "Segoe UI,Arial,sans-serif"
    paragraph_html = "".join(f"<p style='margin:0 0 16px'>{html.escape(value)}</p>" for value in paragraphs if value)
    details_html = "".join(
        f"<tr><th style='text-align:left;padding:8px 16px 8px 0;font-weight:600'>{html.escape(label)}</th>"
        f"<td style='padding:8px 0'>{html.escape(str(value))}</td></tr>"
        for label, value in details
    )
    link_html = ""
    if link_label and link and link.startswith(("http://", "https://")):
        href = html.escape(link, quote=True)
        label = html.escape(link_label)
        # Classic Outlook renders with Word, which ignores inline-block, margins and
        # border-radius; it gets a VML button and every other client the padded link.
        link_html = (
            "<table role='presentation' border='0' cellspacing='0' cellpadding='0'><tr><td style='height:24px;line-height:24px;font-size:1px'>&nbsp;</td></tr></table>"
            "<!--[if mso]>"
            f"<v:roundrect xmlns:v='urn:schemas-microsoft-com:vml' xmlns:w='urn:schemas-microsoft-com:office:word' href='{href}' "
            "style='height:44px;v-text-anchor:middle;width:150px' arcsize='10%' stroke='f' fillcolor='#173b8f'>"
            f"<w:anchorlock/><center style='color:#ffffff;font-family:{font};font-size:15px;font-weight:bold'>{label}</center>"
            "</v:roundrect><![endif]-->"
            "<!--[if !mso]><!-->"
            "<table role='presentation' border='0' cellspacing='0' cellpadding='0'><tr>"
            "<td align='center' bgcolor='#173b8f' style='background:#173b8f;border-radius:4px'>"
            f"<a href='{href}' target='_blank' style='display:inline-block;padding:12px 24px;font-family:{font};font-size:15px;line-height:20px;"
            f"font-weight:600;color:#ffffff;text-decoration:none;border-radius:4px'>{label}</a>"
            "</td></tr></table><!--<![endif]-->"
        )
    guidance_html = f"<p style='font-size:14px;color:#596579;margin:16px 0 0'>{html.escape(guidance)}</p>" if guidance else ""
    return (
        "<!doctype html><html lang='en' xmlns='http://www.w3.org/1999/xhtml' xmlns:v='urn:schemas-microsoft-com:vml' xmlns:o='urn:schemas-microsoft-com:office:office'>"
        "<head><meta charset='utf-8'><meta name='x-apple-disable-message-reformatting'>"
        "<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]--></head>"
        f"<body style='margin:0;background:#f3f5f7;font-family:{font};color:#172033;line-height:1.5'>"
        "<table role='presentation' width='100%' style='border-collapse:collapse'><tr><td align='center' style='padding:24px 12px'>"
        "<table role='presentation' width='100%' style='max-width:660px;border-collapse:collapse;background:#fff;border-top:5px solid #173b8f'>"
        "<tr><td style='padding:24px 28px;border-bottom:1px solid #e5e9ef'><strong style='font-size:20px;color:#173b8f'>PhillipCapital</strong><br>"
        "<span style='font-size:13px;color:#667085'>Learning Management System</span></td></tr>"
        f"<tr><td style='padding:28px;font-size:16px'><h2 style='font-size:22px;color:#173b8f;margin:0 0 22px'>{html.escape(title)}</h2>{paragraph_html}"
        f"<table role='presentation' style='font-size:14px;border-collapse:collapse'>{details_html}</table>"
        f"{table or ''}{link_html}{guidance_html}</td></tr>"
        f"<tr><td style='padding:18px 28px;border-top:1px solid #e5e9ef;color:#667085;font-size:12px'>{html.escape(FOOTER)}</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def render_individual(context: dict, event_type: str, role: str) -> tuple[str, str, str]:
    course = context.get("course_name") or "Course"
    employee = context.get("employee_name") or "Employee"
    employee_first = first_name(employee, "there")
    deadline = format_datetime(context.get("deadline"))
    assigned = format_date(context.get("assigned_at"))
    progress = int(context.get("completion_percent") or 0)
    trainer = context.get("trainer_name") or "Not assigned"
    link = course_link(context)

    if event_type == "assigned" and role == "employee":
        subject = f"Course assignment: {course}"
        paragraphs = [f"Dear {employee_first},", "You have been assigned a new course in the Learning Management System.", "Please complete the course by the stated deadline."]
        details = [("Course", course), ("Assigned on", assigned), ("Deadline", deadline), ("Trainer", trainer)]
        link_label = "Start course"
    elif event_type == "assigned" and role == "hod":
        subject = f"Course assigned to {employee}: {course}"
        paragraphs = [f"Dear {first_name(context.get('hod_name'), 'there')},", f"{course} has been assigned to {employee}, a member of your team.", "Please note the assignment details below."]
        details = [("Employee", employee), ("Course", course), ("Assigned on", assigned), ("Deadline", deadline), ("Trainer", trainer)]
        link = hod_report_link("assigned")
        link_label = None
    elif event_type == "assignment_reminder":
        subject = f"Reminder: Continue {course}"
        paragraphs = [f"Dear {employee_first},", f"This is a reminder that {course} is still pending.", "Please continue the course and complete it by the stated deadline."]
        details = [("Course", course), ("Current progress", f"{progress}%"), ("Deadline", deadline), ("Time remaining", time_remaining(context))]
        link_label = "Continue course"
    elif event_type == "due_soon":
        subject = f"Upcoming deadline: {course}"
        paragraphs = [f"Dear {employee_first},", f"The deadline for {course} is approaching.", "Please complete the remaining modules before the deadline."]
        details = [("Current progress", f"{progress}%"), ("Deadline", deadline), ("Time remaining", time_remaining(context))]
        link_label = "Continue course"
    elif event_type == "completed":
        timing_sentence, timing_status = completion_timing(context)
        subject = f"Congratulations on completing {course}"
        paragraphs = [f"Congratulations, {employee_first}!", f"You have successfully completed {course} {timing_sentence}.", "Thank you for the time and effort you invested in completing this course.\nYour learning record has been updated successfully."]
        details = [("Course", course), ("Completion date", format_datetime(context.get("completed_at"))), ("Deadline", deadline), ("Status", timing_status)]
        link_label = "View course"
    elif event_type == "overdue" and is_overdue_escalation(context):
        escalated_to = "your Head of Department" if context.get("overdue_escalated_to") == "hod" else "the course trainer"
        subject = f"Escalation notice: Overdue course {course}"
        paragraphs = [f"Dear {employee_first},", f"The deadline for {course} has passed, and the course remains incomplete despite previous reminders.", f"This matter has now been escalated to {escalated_to} for further action.", "This is the final automated reminder you will receive for this course. Please complete the remaining modules at the earliest."]
        details = [("Course", course), ("Deadline", deadline), ("Days overdue", days_overdue(context)), ("Current progress", f"{progress}%"), ("Status", f"Escalated to {escalated_to.removeprefix('your ').removeprefix('the ')}")]
        link_label = "Resume course"
    elif event_type == "overdue":
        hours = settings.email_overdue_repeat_days * 24
        escalated_to = "your Head of Department" if context.get("overdue_escalated_to", "hod") == "hod" else "the course trainer"
        reminders = overdue_notice(context)[1] - 1
        subject = f"Overdue course: {course}"
        paragraphs = [f"Dear {employee_first},", f"The deadline for {course} has passed, and the course is still incomplete.", "Please complete the remaining modules as soon as possible.", f"Reminders will be sent every {hours} hours. If the course remains incomplete after the {ordinal(reminders)} reminder, the matter will be escalated to {escalated_to}."]
        details = [("Course", course), ("Deadline", deadline), ("Days overdue", days_overdue(context)), ("Current progress", f"{progress}%"), ("Reminder", overdue_reminder_status(context))]
        link_label = "Resume course"
    else:
        raise ValueError(f"Unsupported individual email template: {event_type}/{role}")

    journey = context.get("journey_title")
    if journey and role == "employee":
        step = f"Step {context.get('journey_step')} of {context.get('journey_step_count')}"
        paragraphs.insert(2, f"This course is {step.lower()} in your learning journey {journey}.")
        details.insert(1, ("Learning journey", f"{journey} ({step})"))

    if role != "hod":
        link_label = "Open LMS"
    guidance = "Sign in to the LMS and open My Courses to access this course." if role != "hod" else ""
    text_lines = []
    for paragraph in paragraphs:
        text_lines.extend([paragraph, ""])
    text_lines.extend(_details_text(details))
    if link_label:
        text_lines.extend(["", f"{link_label}: {link}"])
    text_lines.extend(["", guidance, "", FOOTER])
    return subject, "\n".join(text_lines), _html_document(subject, paragraphs, details, link_label, link, guidance=guidance)


def render_journey_assigned(context: dict) -> tuple[str, str, str]:
    """The one email a learner gets when a Learning Journey opens for them."""
    journey = context.get("journey_title") or "Learning journey"
    employee_first = first_name(context.get("employee_name"), "there")
    count = int(context.get("required_course_count") or 0)
    courses = f"{count} course{'s' if count != 1 else ''}" if count else "a series of courses"
    subject = f"Learning journey assigned: {journey}"
    paragraphs = [f"Dear {employee_first},", f"You have been enrolled in the learning journey {journey}.", f"This journey consists of {courses}. Each course becomes available in the LMS as you progress through the journey."]
    if context.get("certificate_enabled"):
        paragraphs.append("On completing the journey, you will receive a certificate of completion by email.")
    details = [("Learning journey", journey), ("Courses", count or "See the LMS"), ("Target completion date", format_date(context.get("deadline")))]
    link = course_link(context)
    guidance = "Sign in to the LMS and open Learning Journeys to begin."
    text_lines = []
    for paragraph in paragraphs:
        text_lines.extend([paragraph, ""])
    text_lines.extend(_details_text(details))
    text_lines.extend(["", f"Open LMS: {link}", "", guidance, "", FOOTER])
    return subject, "\n".join(text_lines), _html_document(subject, paragraphs, details, "Open LMS", link, guidance=guidance)


def render_journey_completed(context: dict) -> tuple[str, str, str]:
    """The learner's journey completion email; the certificate PDF is attached on sending."""
    journey = context.get("journey_title") or "Learning journey"
    employee_first = first_name(context.get("employee_name"), "there")
    count = int(context.get("required_course_count") or 0)
    courses = f"all {count} required course{'s' if count != 1 else ''}" if count else "all the required courses"
    subject = f"Learning journey completed: {journey}"
    paragraphs = [f"Dear {employee_first},", f"Congratulations on successfully completing the learning journey {journey}.", f"You have completed {courses} in this journey. Your certificate of completion is attached to this email.", "Thank you for your commitment to your learning and development. Your learning record has been updated accordingly."]
    details = [("Learning journey", journey), ("Courses completed", count or "All"), ("Completion date", format_date(context.get("completed_at"))), ("Certificate number", context.get("certificate_number") or "")]
    link = course_link(context)
    guidance = "You can also download your certificate from Learning Journeys in the LMS."
    text_lines = []
    for paragraph in paragraphs:
        text_lines.extend([paragraph, ""])
    text_lines.extend(_details_text(details))
    text_lines.extend(["", f"Open LMS: {link}", "", guidance, "", FOOTER])
    return subject, "\n".join(text_lines), _html_document(subject, paragraphs, details, "Open LMS", link, guidance=guidance)


def _digest_table(rows: list[dict], event_type: str) -> tuple[str, str]:
    headers = ["Employee", "Course", "Deadline"]
    if event_type == "assigned":
        headers = ["Employee", "Course", "Assigned on", "Deadline"]
    elif event_type == "completed":
        headers = ["Employee", "Course", "Completion date", "Status"]
    else:
        headers.append("Progress")
        if event_type == "overdue":
            headers.extend(["Days overdue", "Reminders"])
    text_rows = [" | ".join(headers), " | ".join("---" for _ in headers)]
    html_rows = "<tr>" + "".join(f"<th style='text-align:left;padding:8px;border-bottom:1px solid #d0d5dd'>{html.escape(header)}</th>" for header in headers) + "</tr>"
    for row in rows:
        if event_type == "assigned":
            values = [row.get("employee_name") or "Employee", row.get("course_name") or "Course", format_date(row.get("assigned_at")), format_datetime(row.get("deadline"))]
        elif event_type == "completed":
            values = [row.get("employee_name") or "Employee", row.get("course_name") or "Course", format_date(row.get("completed_at")), completion_timing(row)[1]]
        else:
            values = [row.get("employee_name") or "Employee", row.get("course_name") or "Course", format_date(row.get("deadline")), f"{int(row.get('completion_percent') or 0)}%"]
            if event_type == "overdue":
                values.extend([days_overdue(row), overdue_reminder_status(row)])
        text_rows.append(" | ".join(str(value) for value in values))
        html_rows += "<tr>" + "".join(f"<td style='padding:8px;border-bottom:1px solid #eaecf0'>{html.escape(str(value))}</td>" for value in values) + "</tr>"
    return "\n".join(text_rows), f"<table style='border-collapse:collapse;width:100%;margin:16px 0;font-size:14px'>{html_rows}</table>"


def render_digest(event_type: str, role: str, rows: list[dict], summary: dict, recipient_name: str | None = None) -> tuple[str, str, str]:
    count = len({row.get("employee_id") or row.get("assignment_id") for row in rows})
    course_name = rows[0].get("course_name") if rows else "Course"
    if event_type == "assigned" and role == "hod":
        subject = f"Team course assignments: {count} employees"
        paragraphs = ["The following courses have been assigned to members of your team.", "Please note the assignment dates and deadlines below."]
    elif event_type == "due_soon" and role == "hod":
        subject = f"Courses due soon: {count} team members require attention"
        paragraphs = ["The following members of your team have courses approaching their deadlines.", "Please follow up with the employees where required."]
    elif event_type == "due_soon":
        subject = f"Courses due soon: {count} employees require attention"
        paragraphs = ["The following employees have assigned courses approaching their deadlines.", "Please review the employees listed below and follow up where required."]
    elif event_type == "completed" and role == "hod":
        subject = "Team learning completion summary"
        paragraphs = ["The following members of your team have completed their assigned courses.", "The employees’ learning records have been updated automatically."]
    elif event_type == "completed":
        subject = "Learner completion summary"
        paragraphs = ["The following employees have completed their assigned courses.", "The learners’ course records have been updated automatically."]
    elif event_type == "overdue" and role == "hod":
        escalated = [row for row in rows if is_overdue_escalation(row)]
        subject = f"Overdue learning summary: {count} employees require attention"
        paragraphs = [f"{count} members of your team have overdue learning assignments.", "Please follow up with the employees listed in this report."]
        if escalated:
            subject += f" ({len(escalated)} escalated)"
            marked = "1 employee marked Escalated has received a final reminder" if len(escalated) == 1 else f"{len(escalated)} employees marked Escalated have received their final reminders"
            paragraphs.insert(1, f"{marked}, and the matter has been escalated to you for follow-up. Escalated employees will not appear in future overdue summaries.")
    elif event_type == "overdue":
        escalated = [row for row in rows if is_overdue_escalation(row)]
        subject = f"Overdue course summary: {course_name}"
        paragraphs = [f"{count} of {summary.get('assigned_count', 0)} assigned employees have not completed {course_name} by the deadline.", "The following employees have not completed their assigned courses by the deadline.", "Please review the employees listed below and follow up where required."]
        if escalated:
            to_hod = all(row.get("overdue_escalated_to") == "hod" for row in escalated)
            escalated_to = " to their Head of Department" if to_hod else ""
            paragraphs.insert(2, f"Employees marked Escalated have received their final reminder, and the matter has been escalated{escalated_to}. They will not appear in future overdue summaries.")
    else:
        raise ValueError(f"Unsupported digest template: {event_type}/{role}")

    name = recipient_name or (rows[0].get("hod_name" if role == "hod" else "trainer_name") if rows else None)
    paragraphs.insert(0, f"Dear {first_name(name, 'colleague')},")
    details: list[tuple[str, object]] = []
    if role == "trainer" or event_type == "overdue":
        details = [("Assigned employees" if role == "trainer" else "Total active assignments", summary.get("assigned_count", 0)), ("Completed", summary.get("completed_count", 0))]
        if event_type == "due_soon":
            details.append(("Due soon", count))
        if event_type == "overdue":
            details.append(("Overdue", count))
        details.append(("Completion rate", f"{summary.get('completion_rate', 0)}%"))
        if event_type == "overdue":
            details.append(("Overdue rate", f"{summary.get('overdue_rate', 0)}%"))

    visible_rows = rows if role == "hod" else rows[:DIGEST_ROW_LIMIT]
    if role != "hod" and len(rows) > DIGEST_ROW_LIMIT:
        paragraphs.append(
            f"Showing the first {DIGEST_ROW_LIMIT} assignments. Open the LMS and select Performance to review all {len(rows)} assignments."
        )
    table_text, table_html = _digest_table(visible_rows, event_type)
    report_link = hod_report_link(event_type) if role == "hod" else trainer_report_link(event_type, rows[0].get("course_id") if event_type == "overdue" and rows else None)
    text_parts = []
    for paragraph in paragraphs:
        text_parts.extend([paragraph, ""])
    text_parts.extend(_details_text(details))
    text_parts.extend(["", table_text])
    guidance = ""
    if role != "hod":
        guidance = "Sign in to the trainer LMS and open Performance to review learner progress."
        text_parts.extend(["", f"Open LMS: {report_link}", "", guidance])
    text_parts.extend(["", FOOTER])
    return subject, "\n".join(text_parts), _html_document(subject, paragraphs, details, "Open LMS" if role != "hod" else None, report_link, table_html, guidance=guidance)


__all__ = [
    "completion_timing",
    "days_overdue",
    "render_digest",
    "render_individual",
    "render_journey_assigned",
    "render_journey_completed",
    "time_remaining",
]
