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
    return _absolute_url(
        settings.lms_employee_public_url,
        view="course",
        course_id=str(context.get("course_id") or ""),
    )


def hod_report_link(event_type: str) -> str:
    return _absolute_url(settings.lms_employee_public_url, view="team-performance", status=event_type)


def trainer_report_link(event_type: str, course_id: str | None = None) -> str:
    query = {"view": "performance", "status": event_type}
    if course_id:
        query["course_id"] = course_id
    return _absolute_url(settings.lms_trainer_public_url, **query)


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


def _details_text(values: list[tuple[str, object]]) -> list[str]:
    return [f"{label}: {value}" for label, value in values]


def _html_document(title: str, paragraphs: list[str], details: list[tuple[str, object]], link_label: str | None = None, link: str | None = None, table: str | None = None) -> str:
    paragraph_html = "".join(f"<p>{html.escape(value)}</p>" for value in paragraphs if value)
    details_html = "".join(
        f"<tr><th style='text-align:left;padding:4px 12px 4px 0'>{html.escape(label)}</th>"
        f"<td style='padding:4px 0'>{html.escape(str(value))}</td></tr>"
        for label, value in details
    )
    link_html = ""
    if link_label and link and link.startswith(("http://", "https://")):
        link_html = f"<p><a href='{html.escape(link, quote=True)}'>{html.escape(link_label)}</a></p>"
    return (
        "<!doctype html><html><body style='font-family:Arial,sans-serif;color:#172033;line-height:1.5'>"
        f"<h2 style='color:#173b8f'>{html.escape(title)}</h2>{paragraph_html}"
        f"<table role='presentation' style='border-collapse:collapse'>{details_html}</table>"
        f"{table or ''}{link_html}<p style='color:#667085;font-size:12px'>{html.escape(FOOTER)}</p>"
        "</body></html>"
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
        subject = f"New course assigned: {course}"
        paragraphs = [f"Hello {employee_first},", "You have been assigned a new course in the Learning Management System.", "Please complete the course by the stated deadline."]
        details = [("Course", course), ("Assigned on", assigned), ("Deadline", deadline), ("Trainer", trainer)]
        link_label = "Start course"
    elif event_type == "assigned" and role == "hod":
        subject = f"Course assigned to {employee}: {course}"
        paragraphs = [f"Hello {first_name(context.get('hod_name'), 'there')},", f"{course} has been assigned to {employee}, a member of your team.", "You can monitor the employee’s progress from the LMS dashboard."]
        details = [("Employee", employee), ("Course", course), ("Assigned on", assigned), ("Deadline", deadline), ("Trainer", trainer)]
        link = hod_report_link("assigned")
        link_label = "View learning record"
    elif event_type == "assignment_reminder":
        subject = f"Reminder: Continue {course}"
        paragraphs = [f"Hello {employee_first},", f"This is a reminder that {course} is still pending.", "Please continue the course and complete it by the stated deadline."]
        details = [("Course", course), ("Current progress", f"{progress}%"), ("Deadline", deadline), ("Time remaining", time_remaining(context))]
        link_label = "Continue course"
    elif event_type == "due_soon":
        subject = f"Due soon: {course} must be completed by {format_date(context.get('deadline'))}"
        paragraphs = [f"Hello {employee_first},", f"The deadline for {course} is approaching.", "Please complete the remaining modules before the deadline."]
        details = [("Current progress", f"{progress}%"), ("Deadline", deadline), ("Time remaining", time_remaining(context))]
        link_label = "Continue course"
    elif event_type == "completed":
        timing_sentence, timing_status = completion_timing(context)
        subject = f"Congratulations on completing {course}"
        paragraphs = [f"Congratulations, {employee_first}!", f"You have successfully completed {course} {timing_sentence}.", "Thank you for the time and effort you invested in completing this course.\nYour learning record has been updated successfully."]
        details = [("Course", course), ("Completion date", format_datetime(context.get("completed_at"))), ("Deadline", deadline), ("Status", timing_status)]
        link_label = "View course"
    elif event_type == "overdue":
        subject = f"Action required: {course} is overdue"
        paragraphs = [f"{employee_first}, the deadline for {course} has passed, and the course is still incomplete.", "Please complete the remaining modules as soon as possible.", "You will continue receiving reminders every 48 hours until the course is completed."]
        details = [("Course", course), ("Deadline", deadline), ("Days overdue", days_overdue(context)), ("Current progress", f"{progress}%")]
        link_label = "Resume course"
    else:
        raise ValueError(f"Unsupported individual email template: {event_type}/{role}")

    text_lines = []
    for paragraph in paragraphs:
        text_lines.extend([paragraph, ""])
    text_lines.extend(_details_text(details))
    if link_label:
        text_lines.extend(["", f"{link_label}: {link}"])
    text_lines.extend(["", FOOTER])
    return subject, "\n".join(text_lines), _html_document(subject, paragraphs, details, link_label, link)


def _digest_table(rows: list[dict], event_type: str) -> tuple[str, str]:
    headers = ["Employee", "Course", "Deadline"]
    if event_type == "completed":
        headers = ["Employee", "Course", "Completion date", "Status"]
    else:
        headers.append("Progress")
        if event_type == "overdue":
            headers.append("Days overdue")
    text_rows = [" | ".join(headers), " | ".join("---" for _ in headers)]
    html_rows = "<tr>" + "".join(f"<th style='text-align:left;padding:8px;border-bottom:1px solid #d0d5dd'>{html.escape(header)}</th>" for header in headers) + "</tr>"
    for row in rows:
        if event_type == "completed":
            values = [row.get("employee_name") or "Employee", row.get("course_name") or "Course", format_date(row.get("completed_at")), completion_timing(row)[1]]
        else:
            values = [row.get("employee_name") or "Employee", row.get("course_name") or "Course", format_date(row.get("deadline")), f"{int(row.get('completion_percent') or 0)}%"]
            if event_type == "overdue":
                values.append(days_overdue(row))
        text_rows.append(" | ".join(str(value) for value in values))
        html_rows += "<tr>" + "".join(f"<td style='padding:8px;border-bottom:1px solid #eaecf0'>{html.escape(str(value))}</td>" for value in values) + "</tr>"
    return "\n".join(text_rows), f"<table style='border-collapse:collapse;width:100%;margin:16px 0'>{html_rows}</table>"


def render_digest(event_type: str, role: str, rows: list[dict], summary: dict) -> tuple[str, str, str]:
    count = len({row.get("employee_id") or row.get("assignment_id") for row in rows})
    course_name = rows[0].get("course_name") if rows else "Course"
    if event_type == "due_soon" and role == "hod":
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
        subject = f"Overdue learning summary: {count} employees require attention"
        paragraphs = [f"{count} members of your team have overdue learning assignments.", "Please follow up with the employees listed in this report."]
    elif event_type == "overdue":
        subject = f"Overdue course summary: {course_name}"
        paragraphs = [f"{count} of {summary.get('assigned_count', 0)} assigned employees have not completed {course_name} by the deadline.", "The following employees have not completed their assigned courses by the deadline.", "Please review the employees listed below and follow up where required."]
    else:
        raise ValueError(f"Unsupported digest template: {event_type}/{role}")

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

    visible_rows = rows[:DIGEST_ROW_LIMIT]
    if len(rows) > DIGEST_ROW_LIMIT:
        paragraphs.append(
            f"Showing the first {DIGEST_ROW_LIMIT} assignments. Use the complete report link to review all {len(rows)} assignments."
        )
    table_text, table_html = _digest_table(visible_rows, event_type)
    report_link = hod_report_link(event_type) if role == "hod" else trainer_report_link(event_type, rows[0].get("course_id") if event_type == "overdue" and rows else None)
    text_parts = []
    for paragraph in paragraphs:
        text_parts.extend([paragraph, ""])
    text_parts.extend(_details_text(details))
    text_parts.extend(["", table_text, "", f"View complete report: {report_link}", "", FOOTER])
    return subject, "\n".join(text_parts), _html_document(subject, paragraphs, details, "View complete report", report_link, table_html)


__all__ = [
    "completion_timing",
    "days_overdue",
    "render_digest",
    "render_individual",
    "time_remaining",
]
