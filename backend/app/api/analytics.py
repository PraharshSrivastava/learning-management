"""Trainer reporting endpoints."""

from fastapi import APIRouter, Header, Request

from app.schemas.analytics import TrainerPerformanceResponse
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
router.add_api_route(
    "/employee/team-performance",
    hod_team_performance,
    methods=["GET"],
    response_model=TrainerPerformanceResponse,
)
