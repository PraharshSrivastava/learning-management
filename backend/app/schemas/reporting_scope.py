"""Explicit trusted reporting scope; never constructed from browser role fields."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainerPerformanceScope:
    trainer_id: str
    all_courses: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.trainer_id, str) or not self.trainer_id.strip():
            raise ValueError("A verified trainer identity is required")
        if not isinstance(self.all_courses, bool):
            raise ValueError("all_courses must be a boolean")


# Legacy internal callers retain their explicit owner-scoped behavior.
TrainerReportScope = str | TrainerPerformanceScope


def owner_filter(scope: TrainerReportScope) -> tuple[str, tuple[str, ...]]:
    if isinstance(scope, TrainerPerformanceScope):
        if scope.all_courses:
            return "", ()
        return "c.trainer_id = ? AND ", (scope.trainer_id,)
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("An explicit reporting scope is required")
    return "c.trainer_id = ? AND ", (scope,)
