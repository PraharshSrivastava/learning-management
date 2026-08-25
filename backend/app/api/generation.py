"""Generation-stage and background-job endpoints."""

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.settings import settings
from app.generation.runtime import PipelineStageError
from app.schemas.course import CourseResponse
from app.schemas.generation import GenerationJobResponse
from app.services.auth import current_trainer_from_request
from app.services.generation import build_generation_service

router = APIRouter(prefix="/api", tags=["generation"])
service = build_generation_service(settings)
generation_jobs = service.jobs


@router.post("/courses/{course_id}/generate-quiz", response_model=CourseResponse)
def generate_quiz(course_id: str, request: Request, authorization: str | None = Header(default=None)):
    trainer = current_trainer_from_request(request, authorization)
    return service.generate_quiz(course_id, trainer["trainer_id"])


@router.post("/courses/{course_id}/generate-slides", response_model=CourseResponse)
def generate_slides(course_id: str, request: Request, authorization: str | None = Header(default=None)):
    trainer = current_trainer_from_request(request, authorization)
    return service.generate_slides(course_id, trainer["trainer_id"])


@router.post("/courses/{course_id}/generate-scripts", response_model=CourseResponse)
def generate_scripts(course_id: str, request: Request, authorization: str | None = Header(default=None)):
    trainer = current_trainer_from_request(request, authorization)
    return service.generate_scripts(course_id, trainer["trainer_id"])


@router.post(
    "/courses/{course_id}/modules/{module_number}/generate-video",
    response_model=CourseResponse,
)
def generate_video(
    course_id: str,
    module_number: int,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return service.generate_video(course_id, module_number, trainer["trainer_id"])


@router.post("/courses/{course_id}/generate-full-course", response_model=CourseResponse)
def generate_full_course(
    course_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    try:
        return service.generate_full_course(course_id, trainer["trainer_id"])
    except PipelineStageError as exc:
        raise HTTPException(
            status_code=502,
            detail={"stage": exc.stage, "message": str(exc)},
        ) from exc


@router.post(
    "/courses/{course_id}/generation-jobs",
    response_model=GenerationJobResponse,
    status_code=202,
)
def create_generation_job(
    course_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return service.start_full_course_job(course_id, trainer["trainer_id"])


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
def get_generation_job(
    job_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    return service.get_job(job_id, trainer["trainer_id"])


@router.post("/courses/{course_id}/continue-generation", response_model=CourseResponse)
def continue_generation(
    course_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    trainer = current_trainer_from_request(request, authorization)
    try:
        return service.continue_generation(course_id, trainer["trainer_id"])
    except PipelineStageError as exc:
        raise HTTPException(
            status_code=502,
            detail={"stage": exc.stage, "message": str(exc)},
        ) from exc
