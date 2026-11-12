"""Response contracts for the Email status report."""

from __future__ import annotations

from app.core.schemas import ApiSchema


class EmailStatusTile(ApiSchema):
    key: str
    label: str
    count: int


class EmailStatusBanner(ApiSchema):
    kind: str
    message: str


class EmailStatusRow(ApiSchema):
    assignment_id: str
    notification_id: str | None = None
    employee_id: str
    employee_name: str
    email: str | None = None
    department: str | None = None
    state: str
    label: str
    detail: str
    note: str | None = None
    attempts: int | None = None
    max_attempts: int
    updated_at: str | None = None
    activity_state: str
    activity_label: str
    activity_percent: int
    can_resend: bool
    resend_needs_confirmation: bool
    technical_detail: str | None = None


class EmailStatusReport(ApiSchema):
    generated_at: str
    course_id: str
    course_name: str | None = None
    can_resend: bool
    total: int
    accepted_count: int
    failed_count: int
    not_started_count: int
    tiles: list[EmailStatusTile]
    banners: list[EmailStatusBanner]
    last_send_round: str | None = None
    matched: int
    page: int
    page_size: int
    rows: list[EmailStatusRow]


class EmailResendResult(ApiSchema):
    resent: int
    skipped: int
