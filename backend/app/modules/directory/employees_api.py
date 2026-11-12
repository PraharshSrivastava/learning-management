"""Employee directory endpoints."""

from fastapi import APIRouter, Header, Request

from app.modules.auth.service import current_employee_from_request
from app.modules.directory.employee_schemas import EmployeeResponse
from app.modules.directory.employees import list_employees

router = APIRouter(prefix="/api", tags=["employees"])


@router.get("/employees", response_model=list[EmployeeResponse])
def employees():
    return list_employees()


@router.get("/me", response_model=EmployeeResponse)
def me(request: Request, authorization: str | None = Header(default=None)):
    return current_employee_from_request(request, authorization)
