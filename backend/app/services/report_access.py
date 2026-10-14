"""Validate the requested contribution; SQL intersects it with each row."""

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.repositories.lms_access import identity_key
from app.repositories.report_access import report_roles
from app.schemas.reporting_scope import EmployeePerformanceScope, TrainerPerformanceScope
from app.services.auth import current_employee_from_request, current_trainer_from_request
from app.services.lms_access import _employee_for_trainer


def current_report_scope(request, authorization, *, app):
    course_status = request.query_params.get("course_status", "active")
    if course_status not in ("active", "disabled", "archived", "all"):
        raise AuthorizationError("Choose a valid course status filter")
    if course_status == "archived":
        course_status = "disabled"  # Old bookmarks retain authorized historical results.
    default = "all_courses" if app == "trainer" else "combined"
    view = request.query_params.get("view", default)
    if app == "trainer":
        trainer = current_trainer_from_request(request, authorization)
        if view in ("all_courses", "my_courses"):
            return TrainerPerformanceScope(trainer["trainer_id"], all_courses=view == "all_courses", course_status=course_status)
        employee = _employee_for_trainer(trainer)
    else:
        employee = current_employee_from_request(request, authorization)
    if employee["status"] != "active" or employee.get("directory_status", "active") != "active":
        raise AuthenticationError("Employee is not active")
    roles = report_roles(employee)
    permitted = {"my_departments"} if "hod" in roles else set()
    if "observer" in roles:
        permitted.add("observed")
    if roles:
        permitted.add("combined")
    if view not in permitted:
        raise AuthorizationError("You do not have access to this Performance view")
    return EmployeePerformanceScope(employee["employee_id"], identity_key(employee), view, course_status)
