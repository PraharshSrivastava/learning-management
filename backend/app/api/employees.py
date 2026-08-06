"""Employee directory endpoints."""

from fastapi import APIRouter, Header

from app.schemas.employee import EmployeeResponse
from app.services.auth import get_current_employee
from app.services.employees import list_employees

router = APIRouter(prefix="/api", tags=["employees"])


@router.get("/employees", response_model=list[EmployeeResponse])
def employees():
    return list_employees()


@router.get("/me", response_model=EmployeeResponse)
def me(authorization: str | None = Header(default=None)):
    return get_current_employee(authorization)
