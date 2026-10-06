"""Resolve LMS capabilities without changing existing Hub authoring access."""

from fastapi import Request

from app.core.exceptions import AuthenticationError
from app.repositories import lms_access as grants
from app.repositories.employees import EmployeeRepository
from app.repositories.report_access import report_roles, report_scope_version
from app.schemas.lms_access import LmsAccessResponse, LmsCapabilities
from app.security.hub_launch import HubApp
from app.services.auth import current_employee_from_request, current_trainer_from_request

_employees = EmployeeRepository()


def _employee_for_trainer(trainer: dict) -> dict:
    # No email fallback: a recycled address must never inherit an admin grant.
    directory_uuid = trainer.get("directory_uuid")
    employee = (
        _employees.get_by_directory_uuid(directory_uuid)
        if directory_uuid
        else _employees.get(trainer["trainer_id"])
    )
    if (
        not employee
        or employee.get("status") != "active"
        or employee.get("directory_status", "active") != "active"
    ):
        raise AuthenticationError("Active canonical trainer employee was not found")
    if directory_uuid and employee.get("directory_uuid") != directory_uuid:
        raise AuthenticationError("Trainer employee identity does not match")
    return employee


def current_lms_access(
    request: Request, authorization: str | None, app: HubApp
) -> LmsAccessResponse:
    trainer = None
    if app == "trainer":
        trainer = current_trainer_from_request(request, authorization)
        employee = _employee_for_trainer(trainer)
    else:
        employee = current_employee_from_request(request, authorization)
    if employee.get("status") != "active" or employee.get("directory_status", "active") != "active":
        raise AuthenticationError("Employee is not active")
    stored, version = grants.access_snapshot(employee)
    # Existing authenticated Trainer-app entitlement remains the authoring gate.
    # A projection alone or an Employee-app session confers no Trainer capability.
    roles = ["admin_trainer" if "admin_trainer" in stored else "trainer"] if trainer else []
    report = report_roles(employee)
    roles.extend(sorted(report))
    views = ["all_courses", "my_courses"] if trainer else []
    if "hod" in report:
        views.append("my_departments")
    if "observer" in report:
        views.append("observed")
    if report:
        views.append("combined")
    capabilities = LmsCapabilities(
        can_learn=app == "employee",
        can_view_department_performance="hod" in report,
        can_view_observed_performance="observer" in report,
        can_author_courses=trainer is not None,
        can_view_all_performance=trainer is not None,
        can_view_other_trainers_courses=trainer is not None and "admin_trainer" in stored,
    )
    return LmsAccessResponse(
        employee_id=employee["employee_id"],
        trainer_id=trainer["trainer_id"] if trainer else None,
        name=employee.get("name") or "",
        app=app,
        roles=roles,
        permissions_version=version,
        report_scope_version=report_scope_version() if report else "",
        capabilities=capabilities,
        performance_views=views,
    )
