"""Assignment-rule persistence and matching."""

from __future__ import annotations

import json
from datetime import datetime

from psycopg.types.json import Jsonb

from app.core.dates import parse_date_like
from app.repositories.database import get_connection
from app.repositories.employees import list_employees
from app.schemas.assignment import AssignmentRuleRecord


def _filters(
    *,
    employee_ids: list[str] | None = None,
    departments: list[str] | None = None,
    mailing_lists: list[str] | None = None,
    job_titles: list[str] | None = None,
    joined_within_days: int | None = None,
    include_all: bool | None = None,
    match_mode: str | None = None,
    groups: list[dict] | None = None,
) -> dict:
    data = {
        "employee_ids": list(employee_ids or []),
        "departments": list(departments or []),
        "mailing_lists": list(mailing_lists or []),
        "job_titles": list(job_titles or []),
        "joined_within_days": joined_within_days,
    }
    if include_all is not None:
        data["include_all"] = include_all
    if match_mode:
        data["match_mode"] = match_mode
    if groups:
        data["groups"] = groups
    return data


def default_assignment_rule(course_id: str) -> dict:
    return {
        "course_id": course_id,
        "include_all": True,
        "include_match_mode": "all",
        "include_groups": [],
        "include_employee_ids": [],
        "include_departments": [],
        "include_mailing_lists": [],
        "include_job_titles": [],
        "joined_less_than_days_ago": None,
        "exclude_groups": [],
        "exclude_employee_ids": [],
        "exclude_departments": [],
        "exclude_mailing_lists": [],
        "exclude_job_titles": [],
        "deadline_days": 7,
        "applied_deadline_days": None,
        "published_at": None,
        "is_active": True,
        "disabled_at": None,
        "disabled_by_trainer_id": None,
        "include_inactive": False,
        "updated_at": None,
    }


def _loads(value) -> dict:
    if isinstance(value, dict):
        return value
    return json.loads(value or "{}")


def _ensure_course_for_rule(connection, course_id: str) -> None:
    if connection.execute("SELECT 1 FROM courses WHERE course_id = ?", (course_id,)).fetchone():
        return
    raise ValueError(f"Course ID '{course_id}' not found in courses database.")


def _row_to_assignment_rule(row) -> dict:
    include = _loads(row["include_filters_json"])
    exclude = _loads(row["exclude_filters_json"])
    return {
        "course_id": row["course_id"],
        "include_all": bool(include.get("include_all", True)),
        "include_match_mode": include.get("match_mode", "all"),
        "include_groups": include.get("groups") or [],
        "include_employee_ids": include.get("employee_ids") or [],
        "include_departments": include.get("departments") or [],
        "include_mailing_lists": include.get("mailing_lists") or [],
        "include_job_titles": include.get("job_titles") or [],
        "joined_less_than_days_ago": include.get("joined_within_days"),
        "exclude_groups": exclude.get("groups") or [],
        "exclude_employee_ids": exclude.get("employee_ids") or [],
        "exclude_departments": exclude.get("departments") or [],
        "exclude_mailing_lists": exclude.get("mailing_lists") or [],
        "exclude_job_titles": exclude.get("job_titles") or [],
        "deadline_days": row["deadline_days"],
        "applied_deadline_days": row["applied_deadline_days"],
        "published_at": row["published_at"],
        "is_active": bool(row["is_active"]),
        "disabled_at": row["disabled_at"],
        "disabled_by_trainer_id": row["disabled_by_trainer_id"],
        "include_inactive": bool(row["include_inactive"]),
        "updated_at": row["updated_at"],
    }


def get_assignment_rule(course_id: str) -> dict:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM assignment_rules WHERE course_id = ?", (course_id,)
        ).fetchone()
    return _row_to_assignment_rule(row) if row else default_assignment_rule(course_id)


def save_assignment_rule(
    course_id: str,
    rule: dict,
    publish: bool = False,
    disable: bool = False,
    disabled_by_trainer_id: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    existing = get_assignment_rule(course_id)
    normalized = default_assignment_rule(course_id)
    normalized.update(existing)
    normalized.update(
        {
            "include_all": bool(rule.get("include_all", normalized["include_all"])),
            "include_match_mode": rule.get("include_match_mode", normalized["include_match_mode"]),
            "include_groups": list(rule.get("include_groups") or []),
            "include_employee_ids": list(rule.get("include_employee_ids") or []),
            "include_departments": list(rule.get("include_departments") or []),
            "include_mailing_lists": list(rule.get("include_mailing_lists") or []),
            "include_job_titles": list(rule.get("include_job_titles") or []),
            "joined_less_than_days_ago": rule.get("joined_less_than_days_ago"),
            "exclude_groups": list(rule.get("exclude_groups") or []),
            "exclude_employee_ids": list(rule.get("exclude_employee_ids") or []),
            "exclude_departments": list(rule.get("exclude_departments") or []),
            "exclude_mailing_lists": list(rule.get("exclude_mailing_lists") or []),
            "exclude_job_titles": list(rule.get("exclude_job_titles") or []),
            "deadline_days": max(1, int(rule.get("deadline_days") or normalized["deadline_days"])),
            "applied_deadline_days": existing.get("applied_deadline_days"),
            "published_at": rule.get("published_at", existing.get("published_at")),
            "is_active": bool(rule.get("is_active", existing.get("is_active", True))),
            "disabled_at": rule.get("disabled_at", existing.get("disabled_at")),
            "disabled_by_trainer_id": rule.get(
                "disabled_by_trainer_id", existing.get("disabled_by_trainer_id")
            ),
            "include_inactive": bool(rule.get("include_inactive", existing.get("include_inactive", False))),
            "updated_at": now,
        }
    )
    if normalized["include_match_mode"] not in {"all", "any"}:
        normalized["include_match_mode"] = "all"
    if publish:
        normalized["published_at"] = now
        normalized["applied_deadline_days"] = normalized["deadline_days"]
        normalized["is_active"] = True
        normalized["disabled_at"] = None
        normalized["disabled_by_trainer_id"] = None
    if disable:
        normalized["is_active"] = False
        normalized["disabled_at"] = now
        normalized["disabled_by_trainer_id"] = disabled_by_trainer_id

    include_filters = _filters(
        employee_ids=normalized["include_employee_ids"],
        departments=normalized["include_departments"],
        mailing_lists=normalized["include_mailing_lists"],
        job_titles=normalized["include_job_titles"],
        joined_within_days=normalized["joined_less_than_days_ago"],
        include_all=normalized["include_all"],
        match_mode=normalized["include_match_mode"],
        groups=normalized["include_groups"],
    )
    exclude_filters = _filters(
        employee_ids=normalized["exclude_employee_ids"],
        departments=normalized["exclude_departments"],
        mailing_lists=normalized["exclude_mailing_lists"],
        job_titles=normalized["exclude_job_titles"],
        groups=normalized["exclude_groups"],
    )
    with get_connection() as connection:
        _ensure_course_for_rule(connection, course_id)
        connection.execute(
            """
            INSERT INTO assignment_rules (
                course_id, include_filters_json, exclude_filters_json, deadline_days,
                is_active, include_inactive, applied_deadline_days, published_at,
                disabled_at, disabled_by_trainer_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                include_filters_json = excluded.include_filters_json,
                exclude_filters_json = excluded.exclude_filters_json,
                deadline_days = excluded.deadline_days,
                is_active = excluded.is_active,
                include_inactive = excluded.include_inactive,
                applied_deadline_days = excluded.applied_deadline_days,
                published_at = excluded.published_at,
                disabled_at = excluded.disabled_at,
                disabled_by_trainer_id = excluded.disabled_by_trainer_id,
                updated_at = excluded.updated_at
            """,
            (
                course_id,
                Jsonb(include_filters, dumps=lambda item: json.dumps(item, ensure_ascii=False)),
                Jsonb(exclude_filters, dumps=lambda item: json.dumps(item, ensure_ascii=False)),
                normalized["deadline_days"],
                bool(normalized["is_active"]),
                bool(normalized["include_inactive"]),
                normalized["applied_deadline_days"],
                normalized["published_at"],
                normalized["disabled_at"],
                normalized["disabled_by_trainer_id"],
                normalized["updated_at"],
            ),
        )
        connection.commit()
    return normalized


def _normalize_assignment_groups(rule: dict, prefix: str) -> list[dict]:
    groups = list(rule.get(f"{prefix}_groups") or [])
    if groups:
        return groups
    if prefix == "exclude":
        return [
            *({"employee_ids": [value]} for value in rule.get("exclude_employee_ids") or []),
            *({"departments": [value]} for value in rule.get("exclude_departments") or []),
            *({"mailing_lists": [value]} for value in rule.get("exclude_mailing_lists") or []),
            *({"job_titles": [value]} for value in rule.get("exclude_job_titles") or []),
        ]
    group = {
        "employee_ids": list(rule.get("include_employee_ids") or []),
        "departments": list(rule.get("include_departments") or []),
        "mailing_lists": list(rule.get("include_mailing_lists") or []),
        "job_titles": list(rule.get("include_job_titles") or []),
        "joined_within_days": rule.get("joined_less_than_days_ago"),
        "joined_less_than_days_ago": rule.get("joined_less_than_days_ago"),
    }
    return [group] if any(group.values()) else []


def _employee_matches_group(employee: dict, group: dict, as_of: datetime | None = None) -> bool:
    has_assignment_filter = False
    checks = (
        ("employee_ids", "employee_id"),
        ("departments", "department"),
    )
    for group_key, employee_key in checks:
        allowed = set(group.get(group_key) or [])
        if allowed:
            has_assignment_filter = True
            if employee.get(employee_key) not in allowed:
                return False
    allowed_mailing_lists = set(group.get("mailing_lists") or [])
    if allowed_mailing_lists:
        has_assignment_filter = True
        if allowed_mailing_lists.isdisjoint(employee.get("mailing_lists") or []):
            return False
    days = group.get("joined_within_days", group.get("joined_less_than_days_ago"))
    if days is not None:
        has_assignment_filter = True
        joined = parse_date_like(employee.get("join_date"))
        if joined is None:
            return False
        if ((as_of or datetime.now()).date() - joined).days >= int(days):
            return False
    return has_assignment_filter


def employee_matches_assignment_rule(
    employee: dict, rule: dict, as_of: datetime | None = None
) -> bool:
    if employee.get("status") != "active":
        return False
    if any(
        _employee_matches_group(employee, group, as_of)
        for group in _normalize_assignment_groups(rule, "exclude")
    ):
        return False
    include_groups = _normalize_assignment_groups(rule, "include")
    if rule.get("include_all", True):
        return True
    return bool(include_groups) and any(
        _employee_matches_group(employee, group, as_of) for group in include_groups
    )


def matching_employees_for_assignment_rule(rule: dict, limit: int | None = None) -> list[dict]:
    matches = [
        employee
        for employee in list_employees()
        if employee_matches_assignment_rule(employee, rule)
    ]
    return matches[:limit] if limit is not None else matches


class AssignmentRepository:
    @staticmethod
    def _validated(rule: dict) -> dict:
        AssignmentRuleRecord.model_validate(rule)
        return rule

    def get(self, course_id: str) -> dict:
        return self._validated(get_assignment_rule(course_id))

    def save(
        self,
        course_id: str,
        rule: dict,
        *,
        publish: bool = False,
        disable: bool = False,
        disabled_by_trainer_id: str | None = None,
    ) -> dict:
        return self._validated(
            save_assignment_rule(
                course_id,
                rule,
                publish=publish,
                disable=disable,
                disabled_by_trainer_id=disabled_by_trainer_id,
            )
        )

    def matches_employee(self, employee: dict, rule: dict, as_of: datetime | None = None) -> bool:
        return employee_matches_assignment_rule(employee, rule, as_of)

    def matching_employees(self, rule: dict, limit: int | None = None) -> list[dict]:
        return matching_employees_for_assignment_rule(rule, limit=limit)
