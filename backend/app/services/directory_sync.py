"""Hub directory export import and incremental sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
import time
from typing import Any

import requests

from app.core.exceptions import DomainValidationError, ProviderError
from app.core.settings import settings
from app.repositories.database import advisory_lock
from app.repositories.employees import (
    EmployeeRepository,
    get_sync_state,
    mark_missing_hub_employees_inactive,
    resolve_employee_managers,
    update_sync_state,
)
from app.services.assignments import reconcile_assignments_for_employee

logger = logging.getLogger(__name__)

_employees = EmployeeRepository()
_CN_PATTERN = re.compile(r"(?:^|,)CN=([^,]+)", re.IGNORECASE)


@dataclass
class DirectorySyncResult:
    mode: str
    pages: int = 0
    received: int = 0
    upserted: int = 0
    changed_employee_ids: set[str] = field(default_factory=set)
    next_after_id: int | None = None
    has_more: bool = False
    history_complete_from: str | None = None
    managers_resolved: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "pages": self.pages,
            "received": self.received,
            "upserted": self.upserted,
            "changed_employee_ids": sorted(self.changed_employee_ids),
            "next_after_id": self.next_after_id,
            "has_more": self.has_more,
            "history_complete_from": self.history_complete_from,
            "managers_resolved": self.managers_resolved,
        }


def _require_config() -> tuple[str, str]:
    if not settings.directory_exports_base_url or not settings.directory_exports_api_key:
        raise DomainValidationError(
            "DIRECTORY_EXPORTS_BASE_URL and DIRECTORY_EXPORTS_API_KEY are required"
        )
    return settings.directory_exports_base_url.rstrip("/"), settings.directory_exports_api_key


def _request(path: str, params: dict[str, Any]) -> dict[str, Any]:
    base_url, api_key = _require_config()
    response = requests.get(
        f"{base_url}{path}",
        headers={"X-API-Key": api_key},
        params=params,
        timeout=settings.directory_sync_timeout_seconds,
    )
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        try:
            wait_seconds = min(max(int(retry_after or "1"), 1), 60)
        except ValueError:
            wait_seconds = 1
        time.sleep(wait_seconds)
        response = requests.get(
            f"{base_url}{path}",
            headers={"X-API-Key": api_key},
            params=params,
            timeout=settings.directory_sync_timeout_seconds,
        )
    if response.status_code in {401, 422, 429}:
        raise ProviderError(f"Directory export failed: {response.status_code} {response.text[:300]}")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ProviderError("Directory export returned an invalid response shape")
    return payload


def _first(data: dict, *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _active_status(data: dict) -> str:
    raw = str(_first(data, "status", "directory_status", "account_status", "userAccountControl") or "active")
    normalized = raw.strip().lower()
    if normalized in {"inactive", "disabled", "deleted", "terminated", "deactivated"}:
        return "inactive"
    return "active"


def _directory_status(data: dict) -> str:
    raw = str(_first(data, "directory_status", "ad_status", "status") or "active").strip().lower()
    if raw in {"inactive", "disabled", "deleted", "terminated", "deactivated"}:
        return "inactive"
    if raw in {"unknown", "missing"}:
        return "unknown"
    return "active"


def _hub_user_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _group_cn_from_dn(group_dn: str) -> str | None:
    match = _CN_PATTERN.search(group_dn)
    if not match:
        return None
    return match.group(1).strip() or None


def _normalize_groups(data: dict, synced_at: str) -> list[dict]:
    raw_groups = (
        _first(data, "groups", "employee_groups", "memberOf", "member_of", "mailing_lists")
        or []
    )
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]
    groups = []
    for item in raw_groups:
        if isinstance(item, dict):
            group_dn = _first(item, "group_dn", "dn", "distinguished_name", "distinguishedName")
            group_cn = _first(item, "group_cn", "cn", "name")
        else:
            group_dn = str(item)
            group_cn = _group_cn_from_dn(group_dn)
        if not group_dn:
            continue
        groups.append(
            {
                "group_dn": str(group_dn),
                "group_cn": str(group_cn) if group_cn else _group_cn_from_dn(str(group_dn)),
                "synced_at": synced_at,
            }
        )
    return groups


def _fallback_employee_id(data: dict) -> str:
    for key in ("sam_account_name", "sAMAccountName", "email", "mail", "directory_uuid", "objectGUID"):
        value = _first(data, key)
        if value:
            safe = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).split("@")[0]).strip("_").lower()
            if safe:
                return f"emp_{safe}"
    raise ProviderError("Directory employee row is missing employee_id and stable identifiers")


def _normalize_employee(data: dict) -> tuple[dict, list[dict]]:
    synced_at = datetime.now().isoformat()
    employee = {
        "employee_id": str(_first(data, "employee_id", "employeeId", "lms_employee_id") or _fallback_employee_id(data)),
        "name": str(_first(data, "name", "displayName", "display_name", "cn") or ""),
        "job_title": str(_first(data, "job_title", "title", "designation") or ""),
        "department": _first(data, "department"),
        "join_date": _first(data, "join_date", "whenCreated", "when_created", "created_at"),
        "status": _active_status(data),
        "directory_uuid": _first(data, "directory_uuid", "objectGUID", "object_guid", "guid"),
        "hub_user_id": _hub_user_id(_first(data, "hub_user_id", "hubUserId", "user_id", "id")),
        "email": _first(data, "email", "mail", "userPrincipalName", "user_principal_name"),
        "sam_account_name": _first(data, "sam_account_name", "sAMAccountName", "samAccountName"),
        "company": _first(data, "company"),
        "manager_directory_uuid": _first(
            data,
            "manager_directory_uuid",
            "manager_objectGUID",
            "manager_object_guid",
        ),
        "manager_employee_id": _first(data, "manager_employee_id"),
        "directory_status": _directory_status(data),
        "source": "hub",
        "directory_changed_at": _first(data, "directory_changed_at", "whenChanged", "when_changed"),
        "synced_at": synced_at,
        "updated_at": synced_at,
    }
    return employee, _normalize_groups(data, synced_at)


def _extract_items(payload: dict, *keys: str) -> list[dict]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for value in payload.values():
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
    return []


def _employee_from_change(change: dict) -> dict | None:
    for key in ("employee", "after", "snapshot", "data", "current"):
        value = change.get(key)
        if isinstance(value, dict):
            merged = {**change, **value}
            return merged
    return change


def _apply_employee(data: dict) -> str:
    employee, groups = _normalize_employee(data)
    saved = _employees.upsert(employee, groups)
    return saved["employee_id"]


def bootstrap_full_directory(limit: int | None = None) -> dict:
    with advisory_lock("directory_sync:full_bootstrap"):
        result = DirectorySyncResult(mode="full")
        cursor: str | None = None
        try:
            while True:
                params: dict[str, Any] = {
                    "full": "true",
                    "limit": limit or settings.directory_sync_page_limit,
                }
                if cursor:
                    params["cursor"] = cursor
                payload = _request("/api/v1/directory-exports/employees", params)
                items = _extract_items(payload, "employees", "data", "items", "results")
                result.pages += 1
                result.received += len(items)
                for item in items:
                    employee_id = _apply_employee(item)
                    result.upserted += 1
                    result.changed_employee_ids.add(employee_id)
                cursor = payload.get("next_cursor")
                result.has_more = bool(payload.get("has_more"))
                if not result.has_more:
                    break
            result.managers_resolved = resolve_employee_managers()
            missing_employee_ids = mark_missing_hub_employees_inactive(result.changed_employee_ids)
            result.changed_employee_ids.update(missing_employee_ids)
            for employee_id in result.changed_employee_ids:
                reconcile_assignments_for_employee(employee_id, notify=True)
            update_sync_state("full_bootstrap", status="success", stats=result.as_dict(), success=True)
            return result.as_dict()
        except Exception as exc:
            update_sync_state("full_bootstrap", status="failed", error=str(exc), stats=result.as_dict())
            raise


def sync_directory_changes(after_id: int | None = None, limit: int | None = None) -> dict:
    with advisory_lock("directory_sync:employee_change_logs"):
        state = get_sync_state("employee_change_logs")
        next_after_id = after_id if after_id is not None else int((state or {}).get("cursor") or 0)
        result = DirectorySyncResult(mode="incremental", next_after_id=next_after_id)
        try:
            while True:
                payload = _request(
                    "/api/v1/directory-exports/employee-change-logs",
                    {
                        "after_id": next_after_id,
                        "limit": limit or settings.directory_sync_page_limit,
                    },
                )
                items = _extract_items(payload, "change_logs", "employee_change_logs", "logs", "data", "items")
                result.pages += 1
                result.received += len(items)
                result.history_complete_from = payload.get("history_complete_from")
                for item in items:
                    employee_data = _employee_from_change(item)
                    if not employee_data:
                        continue
                    employee_id = _apply_employee(employee_data)
                    result.upserted += 1
                    result.changed_employee_ids.add(employee_id)
                if payload.get("next_after_id") is not None:
                    next_after_id = int(payload["next_after_id"])
                    result.next_after_id = next_after_id
                result.has_more = bool(payload.get("has_more"))
                if not result.has_more:
                    break
            result.managers_resolved = resolve_employee_managers()
            for employee_id in result.changed_employee_ids:
                reconcile_assignments_for_employee(employee_id, notify=True)
            update_sync_state(
                "employee_change_logs",
                cursor=result.next_after_id or next_after_id,
                status="success",
                stats=result.as_dict(),
                success=True,
            )
            return result.as_dict()
        except Exception as exc:
            logger.exception("directory_incremental_sync_failed")
            update_sync_state(
                "employee_change_logs",
                cursor=next_after_id,
                status="failed",
                error=str(exc),
                stats=result.as_dict(),
            )
            raise
