"""Trainer API and persistence contracts."""

from pydantic import Field

from app.schemas.common import ApiSchema, RequestSchema


class TrainerResponse(ApiSchema):
    trainer_id: str
    name: str
    status: str = "active"


class TrainerRecord(TrainerResponse):
    created_at: str
    updated_at: str


class TrainerDemoLoginRequest(RequestSchema):
    trainer_id: str = Field(min_length=1)


class TrainerLoginResponse(ApiSchema):
    token: str
    trainer: TrainerResponse
