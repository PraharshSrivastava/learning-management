"""Development authentication endpoints."""

from fastapi import APIRouter

from app.schemas.employee import DemoLoginRequest, LoginResponse
from app.schemas.trainer import (
    TrainerDemoLoginRequest,
    TrainerLoginResponse,
    TrainerResponse,
)
from app.services.auth import demo_login, list_demo_trainers, trainer_demo_login

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/demo-login", response_model=LoginResponse)
def login(payload: DemoLoginRequest):
    return demo_login(payload)


@router.get("/auth/trainers", response_model=list[TrainerResponse])
def trainers():
    return list_demo_trainers()


@router.post("/auth/trainer-demo-login", response_model=TrainerLoginResponse)
def trainer_login(payload: TrainerDemoLoginRequest):
    return trainer_demo_login(payload)
