"""Application errors and their HTTP translation."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    status_code = 500
    code = "application_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class AuthenticationError(ApplicationError):
    status_code = 401
    code = "authentication_error"


class NotFoundError(ApplicationError):
    status_code = 404
    code = "not_found"


class ConflictError(ApplicationError):
    status_code = 409
    code = "conflict"


class DomainValidationError(ApplicationError):
    status_code = 400
    code = "validation_error"


class ProviderError(ApplicationError):
    status_code = 502
    code = "provider_error"


def install_exception_handlers(app: FastAPI) -> None:
    async def application_error_handler(_: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    async def not_found_handler(_: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "code": "not_found"},
        )

    async def validation_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "code": "validation_error"},
        )

    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(FileNotFoundError, not_found_handler)
    app.add_exception_handler(ValueError, validation_handler)
