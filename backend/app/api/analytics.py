"""Trainer reporting endpoints."""

import csv
import io
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.schemas.analytics import TrainerPerformanceResponse
from app.schemas.performance_reporting import (
    AssignmentDetailReport,
    AssignmentListReport,
    CourseDetailReport,
    CourseListReport,
    EmployeeDetailReport,
    EmployeeListReport,
    PerformanceOverview,
    PerformanceReportOptions,
)
from app.services import performance_reporting as reports
from app.services.analytics import api_trainer_performance
from app.services.auth import current_trainer_from_request
from app.services.report_access import current_report_scope

router = APIRouter(prefix="/api", tags=["analytics"])


def trainer_performance(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    status: str | None = None,
    joined_less_than_days_ago: int | None = None,
):
    # Shared read-only reporting is available to every authenticated trainer.
    # Authoring and assignment mutation endpoints retain their owner checks.
    trainer = current_trainer_from_request(request, authorization)
    view = request.query_params.get("view", "all_courses") if "query_string" in request.scope else "all_courses"
    if view not in {"all_courses", "my_courses"}:
        raise HTTPException(status_code=403, detail="Use the scoped Performance endpoints for this view")
    return api_trainer_performance(
        trainer_id=trainer["trainer_id"] if view == "my_courses" else None,
        course_id=course_id,
        employee_id=employee_id,
        department=department,
        mailing_list=mailing_list,
        status=status,
        joined_less_than_days_ago=joined_less_than_days_ago,
    )


def hod_team_performance(
    request: Request, authorization: str | None = Header(default=None),
    course_id: str | None = None,
):
    return reports.overview(current_report_scope(request, authorization, app="employee"), course_id=course_id)



router.add_api_route(
    "/trainer/performance",
    trainer_performance,
    methods=["GET"],
    response_model=TrainerPerformanceResponse,
)


def _scope(
    course_id: str | None,
    employee_id: str | None,
    department: str | None,
    mailing_list: str | None,
    joined_less_than_days_ago: int | None,
) -> dict:
    return {
        "course_id": course_id,
        "employee_id": employee_id,
        "department": department,
        "mailing_list": mailing_list,
        "joined_less_than_days_ago": joined_less_than_days_ago,
    }


def _trainer_scope(request: Request, authorization: str | None):
    # Audience comes from the matched server route, never a browser role/app flag.
    route = request.scope.get("route")
    path = getattr(route, "path", "")
    app = "employee" if path.startswith("/api/employee/performance") else "trainer"
    return current_report_scope(request, authorization, app=app)



@router.get("/trainer/performance/overview", response_model=PerformanceOverview)
def performance_overview(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    trend_days: int = Query(default=30),
):
    if trend_days not in (30, 90):
        raise HTTPException(status_code=422, detail="trend_days must be 30 or 90")
    return reports.overview(
        _trainer_scope(request, authorization),
        trend_days=trend_days,
        **_scope(course_id, employee_id, department, mailing_list, joined_less_than_days_ago),
    )


@router.get("/trainer/performance/options", response_model=PerformanceReportOptions)
def performance_options(request: Request, authorization: str | None = Header(default=None)):
    from app.repositories.performance_reporting import list_scope_options

    return list_scope_options(_trainer_scope(request, authorization))


@router.get("/trainer/performance/employees", response_model=EmployeeListReport)
def performance_employees(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    search: str | None = Query(default=None, max_length=120),
    attention: Literal["needs_attention", "overdue", "completed"] | None = None,
    sort: Literal["employee", "assigned", "completion", "overdue", "score"] = "employee",
    descending: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return reports.employee_list(
        _trainer_scope(request, authorization),
        search=search,
        attention=attention,
        sort=sort,
        descending=descending,
        page=page,
        page_size=page_size,
        **_scope(course_id, None, department, mailing_list, joined_less_than_days_ago),
    )


def _csv_report(first, load_page, columns, fields, *, filename, count_header):
    """Stream bounded pages with identical filtering and CSV-formula protection."""
    batch_size = 100

    def chunks():
        page = 1
        batch = first
        while True:
            output = io.StringIO()
            writer = csv.writer(output)
            if page == 1:
                writer.writerow(columns)
            for row in batch["rows"]:
                writer.writerow(
                    [
                        "'" + value
                        if isinstance(value := row.get(key), str)
                        and value.lstrip().startswith(("=", "+", "-", "@"))
                        else value
                        for key in fields
                    ]
                )
            yield output.getvalue()
            if page * batch_size >= first["total"] or not batch["rows"]:
                break
            page += 1
            batch = load_page(page)

    return StreamingResponse(
        chunks(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Generated-At": first["generated_at"],
            count_header: str(first["total"]),
        },
    )


@router.get("/trainer/performance/employees/export")
def performance_employee_export(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    search: str | None = Query(default=None, max_length=120),
    attention: Literal["needs_attention", "overdue", "completed"] | None = None,
    sort: Literal["employee", "assigned", "completion", "overdue", "score"] = "employee",
    descending: bool = False,
):
    _trainer_scope(request, authorization)
    scope = _scope(course_id, None, department, mailing_list, joined_less_than_days_ago)

    def load_page(page):
        trainer_id = _trainer_scope(request, authorization)
        return reports.employee_list(
            trainer_id,
            search=search,
            attention=attention,
            sort=sort,
            descending=descending,
            page=page,
            page_size=100,
            **scope,
        )

    columns = (
        "employee_id",
        "employee_name",
        "department",
        "assigned",
        "completed",
        "in_progress",
        "not_started",
        "completion_rate",
        "overdue",
        "due_soon",
        "inactive",
        "repeated_failures",
        "average_score",
        "scored_modules",
        "last_learner_activity_at",
        "needs_attention",
    )
    return _csv_report(
        load_page(1),
        load_page,
        columns,
        columns,
        filename="performance-employees.csv",
        count_header="X-Report-Employee-Count",
    )


@router.get("/trainer/performance/employees/{employee_id}", response_model=EmployeeDetailReport)
def performance_employee_detail(
    employee_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
):
    result = reports.employee_detail(
        _trainer_scope(request, authorization),
        employee_id,
        course_id=course_id,
        department=department,
        mailing_list=mailing_list,
        joined_less_than_days_ago=joined_less_than_days_ago,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Employee report not found")
    return result


@router.get("/trainer/performance/courses", response_model=CourseListReport)
def performance_courses(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
):
    return reports.course_list(
        _trainer_scope(request, authorization),
        **_scope(course_id, employee_id, department, mailing_list, joined_less_than_days_ago),
    )


@router.get("/trainer/performance/courses/{course_id}", response_model=CourseDetailReport)
def performance_course_detail(
    course_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
):
    result = reports.course_detail(
        _trainer_scope(request, authorization),
        course_id,
        employee_id=employee_id,
        department=department,
        mailing_list=mailing_list,
        joined_less_than_days_ago=joined_less_than_days_ago,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Course report not found")
    return result


@router.get("/trainer/performance/assignments", response_model=AssignmentListReport)
def performance_assignments(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    status: Literal[
        "assigned",
        "pending",
        "started",
        "completed",
        "overdue",
        "due_soon",
        "inactive",
        "repeated_failures",
    ]
    | None = None,
    search: str | None = Query(default=None, max_length=120),
    sort: Literal[
        "employee", "course", "deadline", "progress", "score", "last_activity", "status"
    ] = "deadline",
    descending: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return reports.assignment_list(
        _trainer_scope(request, authorization),
        status=status,
        search=search,
        sort=sort,
        descending=descending,
        page=page,
        page_size=page_size,
        **_scope(course_id, employee_id, department, mailing_list, joined_less_than_days_ago),
    )


@router.get(
    "/trainer/performance/assignments/{assignment_id}", response_model=AssignmentDetailReport
)
def performance_assignment_detail(
    assignment_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    result = reports.assignment_detail(_trainer_scope(request, authorization), assignment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assignment report not found")
    return result


@router.get("/trainer/performance/export")
def performance_export(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    employee_id: str | None = None,
    department: str | None = None,
    mailing_list: str | None = None,
    joined_less_than_days_ago: int | None = Query(default=None, ge=1),
    status: Literal[
        "assigned",
        "pending",
        "started",
        "completed",
        "overdue",
        "due_soon",
        "inactive",
        "repeated_failures",
    ]
    | None = None,
    search: str | None = Query(default=None, max_length=120),
    sort: Literal[
        "employee", "course", "deadline", "progress", "score", "last_activity", "status"
    ] = "deadline",
    descending: bool = False,
):
    trainer_id = _trainer_scope(request, authorization)
    scope = _scope(course_id, employee_id, department, mailing_list, joined_less_than_days_ago)
    # Keep each database read and CSV chunk bounded for large VM datasets.
    batch_size = 100
    first = reports.assignment_list(
        trainer_id,
        status=status,
        search=search,
        sort=sort,
        descending=descending,
        page_size=batch_size,
        **scope,
    )
    columns = [
        "employee_id",
        "employee_name",
        "department",
        "course_id",
        "course_name",
        "status",
        "progress_percent",
        "average_score",
        "scored_modules",
        "total_attempts",
        "assigned_at",
        "deadline",
        "completed_at",
        "last_learner_activity_at",
    ]
    fields = (
        "employee_id",
        "employee_name",
        "department",
        "course_id",
        "course_name",
        "status",
        "completion_percent",
        "average_score",
        "scored_modules",
        "total_attempts",
        "assigned_at",
        "deadline",
        "completed_at",
        "last_learner_activity_at",
    )

    def load_page(page):
        trainer_id = _trainer_scope(request, authorization)
        return reports.assignment_list(
            trainer_id,
            status=status,
            search=search,
            sort=sort,
            descending=descending,
            page=page,
            page_size=batch_size,
            **scope,
        )

    return _csv_report(
        first,
        load_page,
        columns,
        fields,
        filename="performance-assignments.csv",
        count_header="X-Report-Assignment-Count",
    )


router.add_api_route(
    "/employee/team-performance",
    hod_team_performance,
    methods=["GET"],
    response_model=PerformanceOverview,
)


# Capture existing route entries before adding their employee counterparts.
for route in list(router.routes):
    if route.path.startswith("/api/trainer/performance/"):
        router.add_api_route(
            route.path.replace("/api/trainer/performance/", "/employee/performance/"),
            route.endpoint, methods=list(route.methods), response_model=route.response_model,
            name="employee_" + route.name,
        )
