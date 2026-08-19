"""Employee and authentication API contracts."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema, RequestSchema


class LocalEmployeeLoginRequest(RequestSchema):
    employee_id: str = Field(min_length=1)


class EmployeeResponse(ApiSchema):
    employee_id: str
    name: str = ""
    job_title: str = ""
    department: str | None = None
    mailing_lists: list[str] = Field(default_factory=list)
    join_date: str | None = None
    status: str = "active"
    directory_uuid: str | None = None
    hub_user_id: int | None = None
    email: str | None = None
    sam_account_name: str | None = None
    company: str | None = None
    manager_directory_uuid: str | None = None
    manager_employee_id: str | None = None
    directory_status: str = "active"
    source: str = "hub"
    directory_changed_at: str | None = None
    synced_at: str | None = None


class LoginResponse(ApiSchema):
    token: str
    employee: EmployeeResponse
