"""Hub directory export import and incremental sync."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
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
from app.repositories.trainers import TrainerRepository
from app.services.assignments import reconcile_assignments_for_employee

logger = logging.getLogger(__name__)

_employees = EmployeeRepository()
_trainers = TrainerRepository()
_CN_PATTERN = re.compile(r"(?:^|,)CN=([^,]+)", re.IGNORECASE)
_GROUP_KEYS = {"groups", "employee_groups", "memberOf", "member_of", "mailing_lists"}


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
    stale_events_skipped: int = 0

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
            "stale_events_skipped": self.stale_events_skipped,
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


def _has_any(data: dict, *keys: str) -> bool:
    return any(key in data for key in keys)


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


def _safe_id_fragment(value: Any) -> str | None:
    if value in (None, ""):
        return None
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_").lower()
    return safe or None


def _fallback_employee_id(data: dict) -> str:
    hub_user_id = _hub_user_id(_first(data, "hub_user_id", "hubUserId", "user_id", "id"))
    if hub_user_id is not None:
        return f"emp_hub_{hub_user_id}"
    directory_uuid = _safe_id_fragment(_first(data, "directory_uuid", "objectGUID", "object_guid", "guid"))
    if directory_uuid:
        return f"emp_dir_{directory_uuid}"
    sam_account_name = _safe_id_fragment(_first(data, "sam_account_name", "sAMAccountName", "samAccountName"))
    if sam_account_name:
        return f"emp_sam_{sam_account_name}"
    raise ProviderError("Directory employee row is missing employee_id and stable identifiers")


def _existing_employee_for(data: dict) -> dict | None:
    directory_uuid = _first(data, "directory_uuid", "objectGUID", "object_guid", "guid")
    if directory_uuid:
        existing = _employees.get_by_directory_uuid(str(directory_uuid))
        if existing:
            return existing
    hub_user_id = _hub_user_id(_first(data, "hub_user_id", "hubUserId", "user_id", "id"))
    if hub_user_id is not None:
        existing = _employees.get_by_hub_user_id(hub_user_id)
        if existing:
            return existing
    employee_id = _first(data, "employee_id", "employeeId", "lms_employee_id")
    if employee_id:
        return _employees.get(str(employee_id))
    return None


def _value_or_existing(data: dict, existing: dict | None, output_key: str, *input_keys: str) -> Any:
    if _has_any(data, *input_keys):
        return _first(data, *input_keys)
    return (existing or {}).get(output_key)


def _status_or_existing(data: dict, existing: dict | None) -> str:
    if _has_any(data, "status", "directory_status", "account_status", "userAccountControl"):
        return _active_status(data)
    return (existing or {}).get("status") or "active"


def _directory_status_or_existing(data: dict, existing: dict | None) -> str:
    if _has_any(data, "directory_status", "ad_status", "status"):
        return _directory_status(data)
    return (existing or {}).get("directory_status") or "active"


def _groups_from_payload(data: dict, synced_at: str) -> list[dict] | None:
    if not _has_any(data, *_GROUP_KEYS):
        return None
    return _normalize_groups(data, synced_at)


def _normalize_employee(data: dict, existing: dict | None = None) -> tuple[dict, list[dict] | None]:
    synced_at = datetime.now().isoformat()
    employee_id = _first(data, "employee_id", "employeeId", "lms_employee_id")
    if employee_id is None and existing:
        employee_id = existing["employee_id"]
    employee = {
        "employee_id": str(employee_id or _fallback_employee_id(data)),
        "name": str(_value_or_existing(data, existing, "name", "name", "displayName", "display_name", "cn") or ""),
        "job_title": str(_value_or_existing(data, existing, "job_title", "job_title", "title", "designation") or ""),
        "department": _value_or_existing(data, existing, "department", "department"),
        "join_date": _value_or_existing(data, existing, "join_date", "join_date", "whenCreated", "when_created", "created_at"),
        "status": _status_or_existing(data, existing),
        "directory_uuid": _value_or_existing(data, existing, "directory_uuid", "directory_uuid", "objectGUID", "object_guid", "guid"),
        "hub_user_id": _hub_user_id(_value_or_existing(data, existing, "hub_user_id", "hub_user_id", "hubUserId", "user_id", "id")),
        "email": _value_or_existing(data, existing, "email", "email", "mail", "userPrincipalName", "user_principal_name"),
        "sam_account_name": _value_or_existing(data, existing, "sam_account_name", "sam_account_name", "sAMAccountName", "samAccountName"),
        "company": _value_or_existing(data, existing, "company", "company"),
        "manager_directory_uuid": _first(
            data,
            "manager_directory_uuid",
            "manager_objectGUID",
            "manager_object_guid",
        ) if _has_any(data, "manager_directory_uuid", "manager_objectGUID", "manager_object_guid") else (existing or {}).get("manager_directory_uuid"),
        "manager_employee_id": _value_or_existing(data, existing, "manager_employee_id", "manager_employee_id"),
        "directory_status": _directory_status_or_existing(data, existing),
        "source": "hub",
        "directory_changed_at": _value_or_existing(data, existing, "directory_changed_at", "directory_changed_at", "whenChanged", "when_changed"),
        "synced_at": synced_at,
        "updated_at": synced_at,
    }
    return employee, _groups_from_payload(data, synced_at)


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
    changes = change.get("changes")
    if isinstance(changes, dict):
        normalized_changes = {}
        for key, value in changes.items():
            if isinstance(value, dict):
                normalized_changes[key] = _first(value, "new", "after", "current", "value")
            else:
                normalized_changes[key] = value
        merged = {**change, **normalized_changes}
        if "occurred_at" in change and "directory_changed_at" not in merged:
            merged["directory_changed_at"] = change["occurred_at"]
        event_type = str(change.get("event_type") or "").lower()
        if any(marker in event_type for marker in ("disable", "inactive", "delete", "terminate", "deactivate")):
            merged["status"] = "inactive"
            merged["directory_status"] = "inactive"
        return merged
    for key in ("employee", "after", "snapshot", "data", "current"):
        value = change.get(key)
        if isinstance(value, dict):
            merged = {**change, **value}
            return merged
    return change


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_stale_change(existing: dict | None, data: dict) -> bool:
    existing_changed_at = _timestamp((existing or {}).get("directory_changed_at"))
    incoming_changed_at = _timestamp(_first(data, "directory_changed_at", "whenChanged", "when_changed", "occurred_at"))
    if not existing_changed_at or not incoming_changed_at:
        return False
    return incoming_changed_at < existing_changed_at


def _apply_employee(data: dict, *, skip_stale: bool = False) -> tuple[str, bool]:
    existing = _existing_employee_for(data)
    if skip_stale and _is_stale_change(existing, data):
        return existing["employee_id"], False
    employee, groups = _normalize_employee(data, existing)
    saved = _employees.upsert(employee, groups)
    _trainers.refresh_existing_from_employee(saved)
    return saved["employee_id"], True


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
                    employee_id, applied = _apply_employee(item)
                    if not applied:
                        result.stale_events_skipped += 1
                        continue
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
                    employee_id, applied = _apply_employee(employee_data, skip_stale=True)
                    if not applied:
                        result.stale_events_skipped += 1
                        continue
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
