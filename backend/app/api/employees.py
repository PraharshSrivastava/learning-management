"""Employee directory endpoints."""

from fastapi import APIRouter, Header, Request

from app.schemas.employee import EmployeeResponse
from app.services.auth import current_employee_from_request
from app.services.employees import list_employees

router = APIRouter(prefix="/api", tags=["employees"])


@router.get("/employees", response_model=list[EmployeeResponse])
def employees():
    return list_employees()


@router.get("/me", response_model=EmployeeResponse)
def me(request: Request, authorization: str | None = Header(default=None)):
    return current_employee_from_request(request, authorization)
