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
    PerformanceOverview,
    PerformanceReportOptions,
)
from app.services import performance_reporting as reports
from app.services.analytics import api_trainer_performance
from app.services.auth import current_employee_from_request, current_trainer_from_request

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
    trainer = current_trainer_from_request(request, authorization)
    return api_trainer_performance(
        course_id=course_id,
        employee_id=employee_id,
        department=department,
        mailing_list=mailing_list,
        status=status,
        joined_less_than_days_ago=joined_less_than_days_ago,
        trainer_id=trainer["trainer_id"],
    )


def hod_team_performance(
    request: Request,
    authorization: str | None = Header(default=None),
    course_id: str | None = None,
    status: str | None = None,
):
    employee = current_employee_from_request(request, authorization)
    return api_trainer_performance(
        course_id=course_id,
        status=status,
        manager_employee_id=employee["employee_id"],
    )


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


def _trainer_id(request: Request, authorization: str | None) -> str:
    return current_trainer_from_request(request, authorization)["trainer_id"]


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
        _trainer_id(request, authorization),
        trend_days=trend_days,
        **_scope(course_id, employee_id, department, mailing_list, joined_less_than_days_ago),
    )


@router.get("/trainer/performance/options", response_model=PerformanceReportOptions)
def performance_options(request: Request, authorization: str | None = Header(default=None)):
    from app.repositories.performance_reporting import list_scope_options

    return list_scope_options(_trainer_id(request, authorization))


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
        _trainer_id(request, authorization),
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
        _trainer_id(request, authorization),
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
        _trainer_id(request, authorization),
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
    result = reports.assignment_detail(_trainer_id(request, authorization), assignment_id)
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
    trainer_id = _trainer_id(request, authorization)
    scope = _scope(course_id, employee_id, department, mailing_list, joined_less_than_days_ago)
    # Export every matching row while reusing exactly the list's filter rules.
    first = reports.assignment_list(
        trainer_id,
        status=status,
        search=search,
        sort=sort,
        descending=descending,
        page_size=1,
        **scope,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
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
    )
    batch = reports.assignment_list(
        trainer_id,
        status=status,
        search=search,
        sort=sort,
        descending=descending,
        page_size=max(first["total"], 1),
        **scope,
    )
    for row in batch["rows"]:
        values = [
            row.get(key)
            for key in (
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
        ]
        writer.writerow(
            [
                "'" + value
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                else value
                for value in values
            ]
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="performance-assignments.csv"',
            "X-Report-Generated-At": first["generated_at"],
            "X-Report-Assignment-Count": str(first["total"]),
        },
    )


router.add_api_route(
    "/employee/team-performance",
    hod_team_performance,
    methods=["GET"],
    response_model=TrainerPerformanceResponse,
)
