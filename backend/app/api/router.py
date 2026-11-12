"""Single API composition point for the FastAPI application."""

from fastapi import APIRouter

from app.api.static_assets import router as static_router
from app.modules.access.api import router as lms_access_router
from app.modules.assignments.api import router as assignment_router
from app.modules.auth.api import router as auth_router
from app.modules.auth.hub_api import router as hub_router
from app.modules.courses.api import router as course_router
from app.modules.courses.library_api import router as course_library_router
from app.modules.directory.api import router as directory_router
from app.modules.directory.employees_api import router as employee_router
from app.modules.documents.builder_api import router as document_builder_router
from app.modules.documents.drafts_api import router as document_drafts_router
from app.modules.emails.status_api import router as email_status_router
from app.modules.generation.api import router as generation_router
from app.modules.journeys.api import router as journey_router
from app.modules.learning.api import router as learning_router
from app.modules.learning.media_api import router as media_router
from app.modules.observers.api import router as observers_router
from app.modules.reporting.api import router as analytics_router
from app.modules.uploads.api import router as upload_router

api_router = APIRouter()
api_router.include_router(hub_router)
api_router.include_router(upload_router)
api_router.include_router(document_builder_router)
api_router.include_router(document_drafts_router)
api_router.include_router(auth_router)
api_router.include_router(course_router)
api_router.include_router(course_library_router)
api_router.include_router(directory_router)
api_router.include_router(generation_router)
api_router.include_router(employee_router)
api_router.include_router(assignment_router)
api_router.include_router(learning_router)
api_router.include_router(journey_router)
api_router.include_router(analytics_router)
api_router.include_router(email_status_router)
api_router.include_router(static_router)

api_router.include_router(lms_access_router)

api_router.include_router(observers_router)

api_router.include_router(media_router)
