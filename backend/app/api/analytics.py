"""Trainer reporting endpoints."""

from fastapi import APIRouter

from app.schemas.analytics import TrainerPerformanceResponse
from app.services.analytics import api_trainer_performance

router = APIRouter(prefix="/api", tags=["analytics"])
router.add_api_route(
    "/trainer/performance",
    api_trainer_performance,
    methods=["GET"],
    response_model=TrainerPerformanceResponse,
)
