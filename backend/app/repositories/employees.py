"""Employee persistence queries."""

from __future__ import annotations

import json
from datetime import datetime

from psycopg.types.json import Jsonb

from app.repositories.database import get_connection
from app.schemas.employee import EmployeeResponse


def _row_to_employee(row, groups: dict[str, dict] | None = None) -> dict:
    employee_id = row["employee_id"]
    employee_groups = (groups or {}).get(employee_id, {})
    return {
        "employee_id": employee_id,
        "name": row["name"],
        "job_title": row["job_title"],
        "department": row["department"],
        "mailing_lists": employee_groups.get("mailing_lists", []),
        "join_date": row["join_date"],
        "status": row["status"],
        "directory_uuid": row.get("directory_uuid"),
        "hub_user_id": row.get("hub_user_id"),
        "email": row.get("email"),
        "sam_account_name": row.get("sam_account_name"),
        "company": row.get("company"),
        "manager_directory_uuid": row.get("manager_directory_uuid"),
        "manager_employee_id": row.get("manager_employee_id"),
        "directory_status": row.get("directory_status") or "active",
        "source": row.get("source") or "hub",
        "directory_changed_at": row.get("directory_changed_at"),
        "synced_at": row.get("synced_at"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

def _employee_group_summary(connection, employee_ids: list[str] | None = None) -> dict[str, dict]:
    params: list[str] = []
    where = ""
    if employee_ids is not None:
        if not employee_ids:
            return {}
        placeholders = ", ".join("?" for _ in employee_ids)
        where = f"WHERE employee_id IN ({placeholders})"  # nosec B608
        params = employee_ids
    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query
    rows = connection.execute(
        f"""
        SELECT employee_id, group_cn, group_dn
        FROM employee_groups
        {where}
        ORDER BY employee_id, group_cn, group_dn
        """,
        params,
    ).fetchall()
    summary: dict[str, dict] = {}
    for row in rows:
        employee = summary.setdefault(
            row["employee_id"],
            {"mailing_lists": []},
        )
        if row["group_cn"]:
            employee["mailing_lists"].append(row["group_cn"])
    return summary

def list_employees(include_inactive: bool = False) -> list[dict]:
    query = "SELECT * FROM employees ORDER BY department, name" if include_inactive else "SELECT * FROM employees WHERE status = 'active' ORDER BY department, name"
    with get_connection() as connection:
        rows = connection.execute(query).fetchall()
        groups = _employee_group_summary(connection, [row["employee_id"] for row in rows])
        return [_row_to_employee(row, groups) for row in rows]

def get_employee_assignment_options() -> dict:
    employees = list_employees()
    job_titles = sorted({employee["job_title"] for employee in employees if employee["job_title"]})
    return {
        "employees": employees,
        "departments": sorted({employee["department"] for employee in employees if employee["department"]}),
        "mailing_lists": sorted(
            {
                mailing_list
                for employee in employees
                for mailing_list in employee.get("mailing_lists", [])
                if mailing_list
            }
        ),
        "job_titles": job_titles,
    }

def get_employee(employee_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
        groups = _employee_group_summary(connection, [employee_id]) if row else {}
    return _row_to_employee(row, groups) if row else None


def get_employee_by_hub_user_id(hub_user_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM employees WHERE hub_user_id = ?",
            (hub_user_id,),
        ).fetchone()
        groups = _employee_group_summary(connection, [row["employee_id"]]) if row else {}
    return _row_to_employee(row, groups) if row else None


def get_employee_by_directory_uuid(directory_uuid: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM employees WHERE directory_uuid = ?",
            (directory_uuid,),
        ).fetchone()
        groups = _employee_group_summary(connection, [row["employee_id"]]) if row else {}
    return _row_to_employee(row, groups) if row else None


def upsert_employee(employee: dict, groups: list[dict] | None = None) -> dict:
    now = datetime.now().isoformat()
    employee_id = str(employee["employee_id"])
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO employees (
                employee_id, name, job_title, department, join_date, status,
                directory_uuid, hub_user_id, email, sam_account_name, company,
                manager_directory_uuid, manager_employee_id, directory_status,
                source, directory_changed_at, synced_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id) DO UPDATE SET
                name = excluded.name,
                job_title = excluded.job_title,
                department = excluded.department,
                join_date = excluded.join_date,
                status = excluded.status,
                directory_uuid = excluded.directory_uuid,
                hub_user_id = excluded.hub_user_id,
                email = excluded.email,
                sam_account_name = excluded.sam_account_name,
                company = excluded.company,
                manager_directory_uuid = excluded.manager_directory_uuid,
                manager_employee_id = excluded.manager_employee_id,
                directory_status = excluded.directory_status,
                source = excluded.source,
                directory_changed_at = excluded.directory_changed_at,
                synced_at = excluded.synced_at,
                updated_at = excluded.updated_at
            """,
            (
                employee_id,
                employee.get("name") or "",
                employee.get("job_title") or "",
                employee.get("department"),
                employee.get("join_date"),
                employee.get("status") or "active",
                employee.get("directory_uuid"),
                employee.get("hub_user_id"),
                employee.get("email"),
                employee.get("sam_account_name"),
                employee.get("company"),
                employee.get("manager_directory_uuid"),
                employee.get("manager_employee_id"),
                employee.get("directory_status") or "active",
                employee.get("source") or "hub",
                employee.get("directory_changed_at"),
                employee.get("synced_at") or now,
                employee.get("created_at") or now,
                employee.get("updated_at") or now,
            ),
        )
        if groups is not None:
            connection.execute("DELETE FROM employee_groups WHERE employee_id = ?", (employee_id,))
            for group in groups:
                group_dn = group.get("group_dn")
                if not group_dn:
                    continue
                connection.execute(
                    """
                    INSERT INTO employee_groups (employee_id, group_dn, group_cn, synced_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(employee_id, group_dn) DO UPDATE SET
                        group_cn = excluded.group_cn,
                        synced_at = excluded.synced_at
                    """,
                    (
                        employee_id,
                        group_dn,
                        group.get("group_cn"),
                        group.get("synced_at") or now,
                    ),
                )
        connection.commit()
    return get_employee(employee_id) or employee


def resolve_employee_managers() -> int:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT child.employee_id, manager.employee_id AS manager_employee_id
            FROM employees child
            JOIN employees manager
              ON manager.directory_uuid = child.manager_directory_uuid
            WHERE child.manager_directory_uuid IS NOT NULL
              AND child.manager_employee_id IS DISTINCT FROM manager.employee_id
            """
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                UPDATE employees
                SET manager_employee_id = ?, updated_at = ?
                WHERE employee_id = ?
                """,
                (row["manager_employee_id"], datetime.now().isoformat(), row["employee_id"]),
            )
        connection.commit()
    return len(rows)


def mark_missing_hub_employees_inactive(active_employee_ids: set[str]) -> list[str]:
    if not active_employee_ids:
        return []
    now = datetime.now().isoformat()
    placeholders = ", ".join("?" for _ in active_employee_ids)  # nosec B608
    with get_connection() as connection:
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query
        rows = connection.execute(
            f"""
            SELECT employee_id
            FROM employees
            WHERE source = 'hub'
              AND status = 'active'
              AND employee_id NOT IN ({placeholders})
            """,
            list(active_employee_ids),
        ).fetchall()
        missing_ids = [row["employee_id"] for row in rows]
        if missing_ids:
            missing_placeholders = ", ".join("?" for _ in missing_ids)  # nosec B608
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query
            connection.execute(
                f"""
                UPDATE employees
                SET status = 'inactive',
                    directory_status = 'inactive',
                    synced_at = ?,
                    updated_at = ?
                WHERE employee_id IN ({missing_placeholders})
                """,
                [now, now, *missing_ids],
            )
        connection.commit()
    return missing_ids


def next_sync_due_seconds(job_name: str, interval_seconds: float) -> float:
    state = get_sync_state(job_name)
    last_success_at = (state or {}).get("last_success_at")
    if not last_success_at:
        return 0
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(last_success_at)).total_seconds()
    except (TypeError, ValueError):
        return 0
    return max(0, interval_seconds - elapsed)


def get_sync_state(job_name: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM directory_sync_state WHERE job_name = ?",
            (job_name,),
        ).fetchone()
    if not row:
        return None
    stats = row.get("stats_json") or {}
    if isinstance(stats, str):
        stats = json.loads(stats or "{}")
    return {**row, "stats_json": stats}


def list_sync_states() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM directory_sync_state
            ORDER BY job_name
            """
        ).fetchall()
    states = []
    for row in rows:
        stats = row.get("stats_json") or {}
        if isinstance(stats, str):
            stats = json.loads(stats or "{}")
        states.append({**row, "stats_json": stats})
    return states


def update_sync_state(
    job_name: str,
    *,
    cursor: int | None = None,
    status: str,
    error: str | None = None,
    stats: dict | None = None,
    success: bool = False,
) -> None:
    now = datetime.now().isoformat()
    with get_connection() as connection:
        existing_row = connection.execute(
            "SELECT * FROM directory_sync_state WHERE job_name = ?",
            (job_name,),
        ).fetchone()
        existing = dict(existing_row) if existing_row else {}
        next_cursor = cursor if cursor is not None else int((existing or {}).get("cursor") or 0)
        connection.execute(
            """
            INSERT INTO directory_sync_state (
                job_name, cursor, last_attempt_at, last_success_at,
                last_status, last_error, stats_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_name) DO UPDATE SET
                cursor = excluded.cursor,
                last_attempt_at = excluded.last_attempt_at,
                last_success_at = excluded.last_success_at,
                last_status = excluded.last_status,
                last_error = excluded.last_error,
                stats_json = excluded.stats_json
            """,
            (
                job_name,
                next_cursor,
                now,
                now if success else (existing or {}).get("last_success_at"),
                status,
                error,
                Jsonb(stats or {}, dumps=lambda item: json.dumps(item, ensure_ascii=False)),
            ),
        )
        connection.commit()

class EmployeeRepository:
    @staticmethod
    def _validated(employee: dict) -> dict:
        EmployeeResponse.model_validate(employee)
        return employee

    def list(self, *, include_inactive: bool = False) -> list[dict]:
        return [self._validated(employee) for employee in list_employees(include_inactive=include_inactive)]

    def get(self, employee_id: str) -> dict | None:
        employee = get_employee(employee_id)
        return self._validated(employee) if employee else None

    def get_by_hub_user_id(self, hub_user_id: int) -> dict | None:
        employee = get_employee_by_hub_user_id(hub_user_id)
        return self._validated(employee) if employee else None

    def get_by_directory_uuid(self, directory_uuid: str) -> dict | None:
        employee = get_employee_by_directory_uuid(directory_uuid)
        return self._validated(employee) if employee else None

    def upsert(self, employee: dict, groups: list[dict] | None = None) -> dict:
        return self._validated(upsert_employee(employee, groups))

    def assignment_options(self) -> dict:
        return get_employee_assignment_options()
