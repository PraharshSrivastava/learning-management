"""Development authentication state and current-employee resolution."""

from __future__ import annotations

import secrets

from fastapi import Request

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.settings import settings
from app.repositories.employees import EmployeeRepository
from app.repositories.trainers import TrainerRepository
from app.schemas.employee import LocalEmployeeLoginRequest
from app.schemas.trainer import TrainerLocalLoginRequest
from app.security.hub_launch import HubApp, hub_launch_verifier

_employees = EmployeeRepository()
_trainers = TrainerRepository()
_local_employee_sessions: dict[str, str] = {}
_local_trainer_sessions: dict[str, str] = {}


def _require_local_auth_enabled() -> None:
    if not settings.hub_launch_dev_mode:
        raise AuthenticationError("Local login is disabled outside development mode")


def _real_synced_employee(employee: dict) -> bool:
    return (
        employee.get("status") == "active"
        and employee.get("source") == "hub"
    )


def authorization_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError("Missing authorization token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Invalid authorization token")
    return token


def employee_id_from_token(token: str) -> str:
    _require_local_auth_enabled()
    employee_id = _local_employee_sessions.get(token)
    if not employee_id:
        raise AuthenticationError("Invalid or expired session")
    return employee_id


def current_employee(authorization: str | None) -> dict:
    employee = _employees.get(employee_id_from_token(authorization_token(authorization)))
    if not employee or employee.get("status") != "active":
        raise AuthenticationError("Employee is not active")
    return employee


def _hub_session(request: Request | None, app: HubApp):
    if request is None:
        return None
    session_data = getattr(request.state, "hub_user", None)
    if isinstance(session_data, dict) and session_data.get("app") == app:
        return session_data
    session = hub_launch_verifier.session_from_request(request, app)
    if session is None:
        return None
    request.state.hub_user = session.as_response()
    return request.state.hub_user


def current_employee_from_request(
    request: Request | None,
    authorization: str | None = None,
) -> dict:
    session = _hub_session(request, "employee")
    if session is not None:
        employee = _employees.get_by_hub_user_id(int(session["sub"]))
        if not employee or employee.get("status") != "active":
            raise AuthenticationError("Employee is not active or not synced from Hub")
        from app.services.assignments import ensure_assignments_for_employee

        ensure_assignments_for_employee(employee["employee_id"])
        return employee
    return current_employee(authorization)


def trainer_id_from_token(token: str) -> str:
    _require_local_auth_enabled()
    trainer_id = _local_trainer_sessions.get(token)
    if not trainer_id:
        raise AuthenticationError("Invalid or expired trainer session")
    return trainer_id


def current_trainer(authorization: str | None) -> dict:
    trainer = _trainers.get(trainer_id_from_token(authorization_token(authorization)))
    if not trainer or trainer.get("status") != "active":
        raise AuthenticationError("Trainer is not active")
    return trainer


def current_trainer_from_request(
    request: Request | None,
    authorization: str | None = None,
) -> dict:
    session = _hub_session(request, "trainer")
    if session is not None:
        employee = _employees.get_by_hub_user_id(int(session["sub"]))
        if not employee or employee.get("status") != "active":
            raise AuthenticationError("Trainer employee is not active or not synced from Hub")
        trainer = _trainers.upsert_from_employee(employee)
        if not trainer or trainer.get("status") != "active":
            raise AuthenticationError("Trainer is not active")
        return trainer
    return current_trainer(authorization)


def local_employee_login(payload: LocalEmployeeLoginRequest):
    from app.services.assignments import ensure_assignments_for_employee

    _require_local_auth_enabled()
    employee = _employees.get(payload.employee_id)
    if not employee or not _real_synced_employee(employee):
        raise NotFoundError("Active synced employee not found")
    token = secrets.token_urlsafe(32)
    _local_employee_sessions[token] = employee["employee_id"]
    ensure_assignments_for_employee(employee["employee_id"])
    return {"token": token, "employee": employee}


def list_local_trainers() -> list[dict]:
    _require_local_auth_enabled()
    return [
        {
            "trainer_id": employee["employee_id"],
            "name": employee["name"],
            "status": employee["status"],
            "directory_uuid": employee.get("directory_uuid"),
            "email": employee.get("email"),
        }
        for employee in _employees.list()
        if _real_synced_employee(employee)
    ]


def local_trainer_login(payload: TrainerLocalLoginRequest):
    _require_local_auth_enabled()
    employee = _employees.get(payload.trainer_id)
    if not employee or not _real_synced_employee(employee):
        raise NotFoundError("Active synced trainer employee not found")
    trainer = _trainers.upsert_from_employee(employee)
    token = secrets.token_urlsafe(32)
    _local_trainer_sessions[token] = trainer["trainer_id"]
    return {"token": token, "trainer": trainer}


def get_current_employee(authorization: str | None):
    return current_employee(authorization)


def clear_local_sessions() -> None:
    """Reset in-memory local auth state for isolated tests."""
    _local_employee_sessions.clear()
    _local_trainer_sessions.clear()
