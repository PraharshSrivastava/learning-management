"""Observer configuration is independent of learner Include/Exclude filters."""

from pydantic import Field, model_validator

from app.schemas.common import ApiSchema, RequestSchema


class ObserverSelection(RequestSchema):
    observer_employee_id: str = Field(min_length=1)
    employee_ids: list[str] = Field(default_factory=list, max_length=1000)
    department_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def nonempty_scope(self):
        if not self.employee_ids and not self.department_ids:
            raise ValueError("Select employees or departments for each observer")
        return self


class ObserverSaveRequest(RequestSchema):
    revision: int = Field(ge=0)
    observers: list[ObserverSelection] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_observers(self):
        ids = [item.observer_employee_id for item in self.observers]
        if len(ids) != len(set(ids)):
            raise ValueError("An observer can only appear once per course")
        return self


class ObserverApplyRequest(RequestSchema):
    revision: int = Field(ge=0)


class ObserverConfigResponse(ApiSchema):
    course_id: str
    revision: int
    observers: list[dict]
