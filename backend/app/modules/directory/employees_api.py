"""Employee directory endpoints."""

from fastapi import APIRouter, Header, Request

from app.modules.directory.employee_schemas import EmployeeResponse
from app.modules.directory.employees import list_employees
from app.services.auth import current_employee_from_request

router = APIRouter(prefix="/api", tags=["employees"])


@router.get("/employees", response_model=list[EmployeeResponse])
def employees():
    return list_employees()


@router.get("/me", response_model=EmployeeResponse)
def me(request: Request, authorization: str | None = Header(default=None)):
    return current_employee_from_request(request, authorization)
