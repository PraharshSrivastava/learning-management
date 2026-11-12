"""Local development authentication endpoints."""

from fastapi import APIRouter

from app.modules.auth.service import list_local_trainers, local_employee_login, local_trainer_login
from app.modules.directory.employee_schemas import LocalEmployeeLoginRequest, LoginResponse
from app.modules.directory.trainer_schemas import (
    TrainerLocalLoginRequest,
    TrainerLoginResponse,
    TrainerResponse,
)

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/local/employee-login", response_model=LoginResponse)
def login(payload: LocalEmployeeLoginRequest):
    return local_employee_login(payload)


@router.get("/auth/local/trainers", response_model=list[TrainerResponse])
def trainers():
    return list_local_trainers()


@router.post("/auth/local/trainer-login", response_model=TrainerLoginResponse)
def trainer_login(payload: TrainerLocalLoginRequest):
    return local_trainer_login(payload)
