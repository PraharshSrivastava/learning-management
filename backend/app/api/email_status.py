"""Trainer-only Email status endpoints.

Kept out of `analytics.py` on purpose: that module mirrors every Performance route into the
employee API, and these show email addresses and mail server details.
"""

import csv
import io

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response

from app.core.schemas import RequestSchema
from app.modules.access.report_access import current_report_scope
from app.modules.auth.service import current_trainer_from_request
from app.schemas.email_status import EmailResendResult, EmailStatusReport
from app.services import email_status as reports

router = APIRouter(prefix="/api/trainer/performance/emails", tags=["email-status"])

CSV_FIELDS = (
    "employee_name",
    "email",
    "department",
    "label",
    "detail",
    "note",
    "attempts",
    "updated_at",
    "activity_label",
)
CSV_HEADERS = (
    "Employee",
    "Email",
    "Department",
    "Email status",
    "Details",
    "Note",
    "Attempts",
    "Last update",
    "Course activity",
)


class ResendRequest(RequestSchema):
    confirm_unknown: bool = False


def _viewer(request: Request, authorization: str | None):
    scope = current_report_scope(request, authorization, app="trainer")
    return scope, current_trainer_from_request(request, authorization)


def _filters(department, mailing_list, joined_less_than_days_ago) -> dict:
    return {
        "department": department,
        "mailing_list": mailing_list,
        "joined_less_than_days_ago": joined_less_than_days_ago,
    }


@router.get("", response_model=EmailStatusReport)
def email_status_report(
    request: Request,
    course_id: str,
    authorization: str | None = Header(default=None),
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    tile: str | None = None,
    search: str | None = Query(default=None, max_length=120),
    not_started: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    scope, trainer = _viewer(request, authorization)
    return reports.course_report(
        scope,
        trainer,
        course_id=course_id,
        tile=tile,
        search=search,
        not_started=not_started,
        page=page,
        page_size=page_size,
        **_filters(department, mailing_list, joined_less_than_days_ago),
    )


@router.get("/export")
def email_status_export(
    request: Request,
    course_id: str,
    authorization: str | None = Header(default=None),
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    tile: str | None = None,
    search: str | None = Query(default=None, max_length=120),
    not_started: bool = False,
):
    scope, trainer = _viewer(request, authorization)
    rows = reports.csv_rows(
        scope,
        trainer,
        course_id=course_id,
        tile=tile,
        search=search,
        not_started=not_started,
        **_filters(department, mailing_list, joined_less_than_days_ago),
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                "'" + value
                if isinstance(value := row.get(key), str)
                and value.lstrip().startswith(("=", "+", "-", "@"))
                else value
                for key in CSV_FIELDS
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="email-status.csv"'},
    )


@router.post("/resend-failed", response_model=EmailResendResult)
def email_resend_failed(
    request: Request,
    course_id: str,
    authorization: str | None = Header(default=None),
):
    scope, trainer = _viewer(request, authorization)
    return reports.resend_failed(scope, trainer, course_id=course_id)


@router.post("/{notification_id}/resend", response_model=EmailResendResult)
def email_resend(
    notification_id: str,
    payload: ResendRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return reports.resend(notification_id, trainer, confirm_unknown=payload.confirm_unknown)
