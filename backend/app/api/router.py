"""Single API composition point for the FastAPI application."""

from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.assignments import router as assignment_router
from app.api.auth import router as auth_router
from app.api.courses import router as course_router
from app.api.employees import router as employee_router
from app.api.generation import router as generation_router
from app.api.learning import router as learning_router
from app.api.static_assets import router as static_router
from app.api.uploads import router as upload_router

api_router = APIRouter()
api_router.include_router(upload_router)
api_router.include_router(auth_router)
api_router.include_router(course_router)
api_router.include_router(generation_router)
api_router.include_router(employee_router)
api_router.include_router(assignment_router)
api_router.include_router(learning_router)
api_router.include_router(analytics_router)
api_router.include_router(static_router)
