"""Course content oversight is distinct from all-course performance access."""

from app.core.exceptions import AuthorizationError, NotFoundError
from app.repositories import courses, lms_access
from app.services.lms_access import _employee_for_trainer

READ_ONLY_MESSAGE = (
    "This course was created by another trainer. You can view it and its "
    "performance, but only its creator can make changes."
)


def is_admin_trainer(trainer: dict) -> bool:
    roles, _ = lms_access.access_snapshot(_employee_for_trainer(trainer))
    return "admin_trainer" in roles


def course_owner_for_read(course_id: str, trainer: dict) -> str:
    owner = courses.get_course_owner(course_id)
    if owner is None:
        raise NotFoundError("Course not found")
    if owner == trainer["trainer_id"] or is_admin_trainer(trainer):
        return owner
    # Ordinary Trainers cannot discover another creator's authoring resources.
    raise NotFoundError("Course not found")


def require_course_creator(course_id: str, trainer: dict) -> None:
    owner = courses.get_course_owner(course_id)
    if owner is None:
        raise NotFoundError("Course not found")
    if owner == trainer["trainer_id"]:
        return
    if is_admin_trainer(trainer):
        raise AuthorizationError(READ_ONLY_MESSAGE)
    raise NotFoundError("Course not found")
