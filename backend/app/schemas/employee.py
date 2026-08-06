"""Employee and authentication API contracts."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema, RequestSchema


class DemoLoginRequest(RequestSchema):
    employee_id: str = Field(min_length=1)


class EmployeeResponse(ApiSchema):
    employee_id: str
    name: str = ""
    job_title: str = ""
    department: str = ""
    join_date: str = ""
    status: str = "active"


class LoginResponse(ApiSchema):
    token: str
    employee: EmployeeResponse
