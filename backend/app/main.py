"""FastAPI application factory and explicit startup lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.generation import generation_jobs
from app.api.router import api_router
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import request_context_middleware
from app.core.settings import settings
from app.core.storage import ensure_storage_directories
from app.generation.runtime import recover_interrupted_generations
from app.repositories.schema import init_db
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    ensure_storage_directories(settings)
    init_db()
    recover_interrupted_generations()
    try:
        yield
    finally:
        generation_jobs.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="LMS Document Management System Backend", lifespan=lifespan)
    origins = list(settings.cors_allowed_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_context_middleware)
    install_exception_handlers(app)
    public_directories = {
        "audio": settings.audio_dir,
        "brand": settings.static_dir / "brand",
        "images": settings.image_dir,
        "layouts": settings.template_dir / "layouts",
        "slides": settings.slide_dir,
        "videos": settings.video_dir,
    }
    for asset_name, directory in public_directories.items():
        app.mount(
            f"/assets/{asset_name}",
            StaticFiles(directory=str(directory)),
            name=f"assets-{asset_name}",
        )
    app.include_router(api_router)

    @app.get("/health", response_model=HealthResponse)
    def health_check() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
