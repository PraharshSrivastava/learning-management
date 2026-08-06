"""Development authentication state and current-employee resolution."""

from __future__ import annotations

import secrets

from app.core.exceptions import AuthenticationError, NotFoundError
from app.repositories.employees import EmployeeRepository
from app.repositories.trainers import TrainerRepository
from app.schemas.employee import DemoLoginRequest
from app.schemas.trainer import TrainerDemoLoginRequest

_employees = EmployeeRepository()
_trainers = TrainerRepository()
_demo_sessions: dict[str, str] = {}
_trainer_demo_sessions: dict[str, str] = {}


def authorization_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError("Missing authorization token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Invalid authorization token")
    return token


def employee_id_from_token(token: str) -> str:
    employee_id = _demo_sessions.get(token)
    if not employee_id:
        raise AuthenticationError("Invalid or expired session")
    return employee_id


def current_employee(authorization: str | None) -> dict:
    employee = _employees.get(employee_id_from_token(authorization_token(authorization)))
    if not employee or employee.get("status") != "active":
        raise AuthenticationError("Employee is not active")
    return employee


def trainer_id_from_token(token: str) -> str:
    trainer_id = _trainer_demo_sessions.get(token)
    if not trainer_id:
        raise AuthenticationError("Invalid or expired trainer session")
    return trainer_id


def current_trainer(authorization: str | None) -> dict:
    trainer = _trainers.get(trainer_id_from_token(authorization_token(authorization)))
    if not trainer or trainer.get("status") != "active":
        raise AuthenticationError("Trainer is not active")
    return trainer


def demo_login(payload: DemoLoginRequest):
    from app.services.assignments import ensure_assignments_for_employee

    employee = _employees.get(payload.employee_id)
    if not employee or employee.get("status") != "active":
        raise NotFoundError("Active employee not found")
    token = secrets.token_urlsafe(32)
    _demo_sessions[token] = employee["employee_id"]
    ensure_assignments_for_employee(employee["employee_id"])
    return {"token": token, "employee": employee}


def list_demo_trainers() -> list[dict]:
    return [trainer for trainer in _trainers.list() if trainer.get("status") == "active"]


def trainer_demo_login(payload: TrainerDemoLoginRequest):
    trainer = _trainers.get(payload.trainer_id)
    if not trainer or trainer.get("status") != "active":
        raise NotFoundError("Active trainer not found")
    token = secrets.token_urlsafe(32)
    _trainer_demo_sessions[token] = trainer["trainer_id"]
    return {"token": token, "trainer": trainer}


def get_current_employee(authorization: str | None):
    return current_employee(authorization)


def clear_demo_sessions() -> None:
    """Reset in-memory demo auth state for isolated tests."""
    _demo_sessions.clear()
    _trainer_demo_sessions.clear()
