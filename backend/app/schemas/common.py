"""Shared API response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    """Base model for records and responses that may carry generated metadata."""

    model_config = ConfigDict(extra="allow")


class RequestSchema(BaseModel):
    """Strict HTTP input model: misspelled or unsupported fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class MessageResponse(ApiSchema):
    message: str


class HealthResponse(ApiSchema):
    status: str
