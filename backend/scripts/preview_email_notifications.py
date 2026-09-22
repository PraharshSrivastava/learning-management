"""Generate a browser gallery from the production email templates.

Run from the repository root:

    backend/.venv/Scripts/python.exe backend/scripts/preview_email_notifications.py
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.settings import settings  # noqa: E402
from app.services.email_templates import render_digest, render_individual  # noqa: E402


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _context(
    *,
    employee_id: str,
    employee_name: str,
    course_id: str,
    course_name: str,
    assigned_at: datetime,
    deadline: datetime,
    completion_percent: int,
    completed_at: datetime | None = None,
) -> dict:
    return {
        "assignment_id": f"preview-{employee_id}-{course_id}",
        "employee_id": employee_id,
        "employee_name": employee_name,
        "course_id": course_id,
        "course_name": course_name,
        "trainer_name": "Kiran Shah",
        "hod_name": "Rohit Khanna",
        "assigned_at": _iso(assigned_at),
        "deadline": _iso(deadline),
        "completed_at": _iso(completed_at) if completed_at else None,
        "completion_percent": completion_percent,
    }


def _sample_data() -> dict[str, dict]:
    now = datetime.now(UTC)
    common = {
        "employee_id": "EMP-1042",
        "employee_name": "Ananya Mehta",
        "course_id": "COURSE-AML-01",
        "course_name": "AML Training – India",
        "assigned_at": now - timedelta(days=5),
    }
    assigned = _context(**common, deadline=now + timedelta(days=25), completion_percent=0)
    reminder = _context(**common, deadline=now + timedelta(days=20), completion_percent=35)
    due_soon = _context(**common, deadline=now + timedelta(days=2, hours=4), completion_percent=60)
    completed = _context(
        **common,
        deadline=now + timedelta(days=2),
        completed_at=now,
        completion_percent=100,
    )
    overdue = _context(**common, deadline=now - timedelta(days=2, hours=3), completion_percent=60)
    return {
        "assigned": assigned,
        "reminder": reminder,
        "due_soon": due_soon,
        "completed": completed,
        "overdue": overdue,
    }


def _digest_rows(base: dict, event_type: str) -> list[dict]:
    people = [
        ("EMP-1042", "Ananya Mehta", 60),
        ("EMP-1077", "Vikram Shah", 25),
        ("EMP-1108", "Sneha Iyer", 80),
    ]
    rows = []
    for index, (employee_id, employee_name, progress) in enumerate(people):
        row = dict(base)
        row.update(
            employee_id=employee_id,
            employee_name=employee_name,
            assignment_id=f"preview-{event_type}-{employee_id}",
            completion_percent=100 if event_type == "completed" else progress,
        )
        if event_type == "completed":
            completed_at = datetime.now(UTC) - timedelta(hours=index * 8)
            row["completed_at"] = _iso(completed_at)
            row["deadline"] = _iso(completed_at + timedelta(days=index + 1))
        elif event_type == "overdue":
            row["deadline"] = _iso(datetime.now(UTC) - timedelta(days=index + 1, hours=2))
        else:
            row["deadline"] = _iso(datetime.now(UTC) + timedelta(days=index + 1, hours=2))
        rows.append(row)
    return rows


def _write_preview(output_dir: Path, slug: str, label: str, rendered: tuple[str, str, str]) -> dict:
    subject, text_body, html_body = rendered
    html_path = output_dir / f"{slug}.html"
    text_path = output_dir / f"{slug}.txt"
    html_path.write_text(html_body, encoding="utf-8")
    text_path.write_text(f"Subject: {subject}\n\n{text_body}\n", encoding="utf-8")
    return {
        "slug": slug,
        "label": label,
        "subject": subject,
        "html": html_path.name,
        "text": text_path.name,
    }


def _gallery(previews: list[dict]) -> str:
    cards = []
    for preview in previews:
        cards.append(
            "<section class='card'>"
            f"<div class='heading'><div><span class='kind'>{html.escape(preview['label'])}</span>"
            f"<h2>{html.escape(preview['subject'])}</h2></div>"
            f"<a href='{html.escape(preview['text'])}'>Plain text</a></div>"
            f"<iframe title='{html.escape(preview['label'], quote=True)}' src='{html.escape(preview['html'])}'></iframe>"
            "</section>"
        )
    return (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LMS email notification previews</title>
<style>
body{margin:0;background:#f4f7fb;color:#172033;font-family:Arial,sans-serif}.top{padding:32px max(24px,5vw);background:#173b8f;color:white}.top h1{margin:0 0 8px}.top p{margin:0;opacity:.85}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:24px;padding:28px max(24px,5vw)}.card{background:white;border:1px solid #dfe5ef;border-radius:12px;box-shadow:0 4px 18px #173b8f12;overflow:hidden}.heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:18px 20px;border-bottom:1px solid #e7ebf1}.heading h2{font-size:17px;margin:6px 0 0}.heading a{white-space:nowrap;color:#173b8f}.kind{font-size:12px;text-transform:uppercase;color:#667085;font-weight:700;letter-spacing:.04em}iframe{display:block;width:100%;height:560px;border:0;background:white}@media(max-width:600px){.grid{grid-template-columns:1fr;padding:14px}.heading{display:block}.heading a{display:inline-block;margin-top:10px}}
</style></head><body><header class="top"><h1>LMS notification email previews</h1><p>Generated from the production renderer. No email was sent.</p></header><main class="grid">"""
        + "".join(cards)
        + "</main></body></html>"
    )


def generate(output_dir: Path) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    settings.lms_employee_public_url = "http://localhost:6970"
    settings.lms_trainer_public_url = "http://localhost:6969"
    settings.email_notification_timezone = "Asia/Kolkata"

    samples = _sample_data()
    summary = {
        "assigned_count": 50,
        "completed_count": 20,
        "completion_rate": 40,
        "overdue_rate": 50,
    }
    specs = [
        (
            "01-assigned-employee",
            "Assigned · Employee",
            render_individual(samples["assigned"], "assigned", "employee"),
        ),
        (
            "02-assigned-hod",
            "Assigned · HOD",
            render_individual(samples["assigned"], "assigned", "hod"),
        ),
        (
            "03-five-day-reminder",
            "5-day reminder · Employee",
            render_individual(samples["reminder"], "assignment_reminder", "employee"),
        ),
        (
            "04-due-soon-employee",
            "Due soon · Employee",
            render_individual(samples["due_soon"], "due_soon", "employee"),
        ),
        (
            "05-completed-employee",
            "Completed · Employee",
            render_individual(samples["completed"], "completed", "employee"),
        ),
        (
            "06-overdue-employee",
            "Overdue · Employee",
            render_individual(samples["overdue"], "overdue", "employee"),
        ),
    ]
    for event_type, source in (
        ("due_soon", samples["due_soon"]),
        ("completed", samples["completed"]),
        ("overdue", samples["overdue"]),
    ):
        rows = _digest_rows(source, event_type)
        for role in ("hod", "trainer"):
            number = len(specs) + 1
            specs.append(
                (
                    f"{number:02d}-{event_type.replace('_', '-')}-{role}-digest",
                    f"{event_type.replace('_', ' ').title()} digest · {role.upper()}",
                    render_digest(event_type, role, rows, summary),
                )
            )

    previews = [
        _write_preview(output_dir, slug, label, rendered) for slug, label, rendered in specs
    ]
    (output_dir / "manifest.json").write_text(
        json.dumps(previews, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "index.html").write_text(_gallery(previews), encoding="utf-8")
    return previews


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("tmp/email-previews"))
    args = parser.parse_args()
    previews = generate(args.output.resolve())
    print(f"Generated {len(previews)} email previews at {args.output.resolve() / 'index.html'}")


if __name__ == "__main__":
    main()
