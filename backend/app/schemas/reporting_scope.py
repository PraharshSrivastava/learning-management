"""Explicit trusted reporting scope; never constructed from browser role fields."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainerPerformanceScope:
    trainer_id: str
    all_courses: bool = False
    course_status: str = "active"

    def __post_init__(self) -> None:
        if not isinstance(self.trainer_id, str) or not self.trainer_id.strip():
            raise ValueError("A verified trainer identity is required")
        if not isinstance(self.all_courses, bool):
            raise ValueError("all_courses must be a boolean")


@dataclass(frozen=True)
class EmployeePerformanceScope:
    employee_id: str
    identity_key: str
    view: str
    course_status: str = "active"

    def __post_init__(self):
        if not self.employee_id or not self.identity_key or self.view not in ("my_departments", "observed", "combined"):
            raise ValueError("A verified employee reporting scope is required")


TrainerReportScope = str | TrainerPerformanceScope | EmployeePerformanceScope


def _journeys_enabled() -> bool:
    from app.core.settings import settings

    return bool(settings.learning_journeys_enabled)


_JOURNEY_OBSERVER = """EXISTS(SELECT 1 FROM learning_journey_observers jo
            JOIN employees jop ON jop.employee_id = jo.observer_employee_id AND jop.status = 'active' AND jop.directory_status = 'active'
                AND jo.identity_key = CASE WHEN jop.directory_uuid IS NOT NULL THEN 'directory:' || jop.directory_uuid ELSE 'hub:' || jop.hub_user_id::text END
            JOIN learning_journeys jj ON jj.journey_id = jo.journey_id AND jj.status = 'published'
            JOIN learning_journey_steps js ON js.journey_id = jo.journey_id AND js.course_id = c.course_id
            JOIN learning_journey_assignments ja ON ja.journey_id = jo.journey_id
                AND ja.employee_id = e.employee_id AND ja.revoked_at IS NULL
            WHERE jo.observer_employee_id = ? AND jo.identity_key = ?
            AND (EXISTS(SELECT 1 FROM learning_journey_observer_employees jx
                WHERE jx.journey_id = jo.journey_id AND jx.observer_employee_id = jo.observer_employee_id
                AND jx.employee_id = e.employee_id
                AND jx.identity_key = CASE WHEN e.directory_uuid IS NOT NULL THEN 'directory:' || e.directory_uuid
                    ELSE 'hub:' || e.hub_user_id::text END)
            OR EXISTS(SELECT 1 FROM learning_journey_observer_departments jd JOIN lms_departments d USING(department_id)
                WHERE jd.journey_id = jo.journey_id AND jd.observer_employee_id = jo.observer_employee_id
                AND d.active AND d.name = e.department)))"""


def owner_filter(scope: TrainerReportScope) -> tuple[str, tuple[str, ...]]:
    if isinstance(scope, EmployeePerformanceScope):
        hod = """EXISTS(SELECT 1 FROM hod_department_access h JOIN lms_departments d USING(department_id)
            JOIN employees hp ON hp.employee_id = h.hod_employee_id AND hp.status = 'active' AND hp.directory_status = 'active'
                AND h.identity_key = CASE WHEN hp.directory_uuid IS NOT NULL THEN 'directory:' || hp.directory_uuid ELSE 'hub:' || hp.hub_user_id::text END
            WHERE h.hod_employee_id = ? AND h.identity_key = ? AND h.active AND d.active
                AND d.source = 'directory' AND d.name = e.department)"""
        observer = """EXISTS(SELECT 1 FROM course_observer_grants og
            JOIN employees op ON op.employee_id = og.observer_employee_id AND op.status = 'active' AND op.directory_status = 'active'
                AND og.identity_key = CASE WHEN op.directory_uuid IS NOT NULL THEN 'directory:' || op.directory_uuid ELSE 'hub:' || op.hub_user_id::text END
            WHERE og.observer_employee_id = ? AND og.identity_key = ? AND og.active AND og.course_id = c.course_id
            AND (EXISTS(SELECT 1 FROM course_observer_employees os
                WHERE os.course_id = og.course_id AND os.observer_employee_id = og.observer_employee_id
                AND os.phase = 'active' AND os.employee_id = e.employee_id
                AND os.identity_key = CASE WHEN e.directory_uuid IS NOT NULL THEN 'directory:' || e.directory_uuid
                    ELSE 'hub:' || e.hub_user_id::text END)
            OR EXISTS(SELECT 1 FROM course_observer_departments os JOIN lms_departments d USING(department_id)
                WHERE os.course_id = og.course_id AND os.observer_employee_id = og.observer_employee_id
                AND os.phase = 'active' AND d.active AND d.name = e.department)))"""
        key = (scope.employee_id, scope.identity_key)
        observer_key: tuple[str, ...] = key
        if _journeys_enabled():
            # A journey Observer sees every course of the journey for the journey's learners
            # they watch, while the journey is published.
            observer = "(" + observer + " OR " + _JOURNEY_OBSERVER + ")"
            observer_key = (*key, *key)
        if scope.view == "my_departments":
            return hod + " AND ", key
        if scope.view == "observed":
            return observer + " AND ", observer_key
        return "(" + hod + " OR " + observer + ") AND ", (*key, *observer_key)
    if isinstance(scope, TrainerPerformanceScope):
        if scope.all_courses:
            return "", ()
        return "c.trainer_id = ? AND ", (scope.trainer_id,)
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("An explicit reporting scope is required")
    return "c.trainer_id = ? AND ", (scope,)
