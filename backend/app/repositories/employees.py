"""Employee persistence queries."""

from __future__ import annotations

import sqlite3

from app.repositories.database import get_connection
from app.schemas.employee import EmployeeResponse


def _row_to_employee(row: sqlite3.Row) -> dict:
    employee_id = row["employee_id"]
    return {
        "employee_id": employee_id,
        "name": row["name"],
        "job_title": row["job_title"],
        "department": row["department"],
        "join_date": row["join_date"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

def list_employees(include_inactive: bool = False) -> list[dict]:
    query = "SELECT * FROM employees ORDER BY department, name" if include_inactive else "SELECT * FROM employees WHERE status = 'active' ORDER BY department, name"
    with get_connection() as connection:
        return [_row_to_employee(row) for row in connection.execute(query).fetchall()]

def get_employee_assignment_options() -> dict:
    employees = list_employees()
    job_titles = sorted({employee["job_title"] for employee in employees if employee["job_title"]})
    return {
        "employees": employees,
        "departments": sorted({employee["department"] for employee in employees if employee["department"]}),
        "job_titles": job_titles,
    }

def get_employee(employee_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
    return _row_to_employee(row) if row else None

class EmployeeRepository:
    @staticmethod
    def _validated(employee: dict) -> dict:
        EmployeeResponse.model_validate(employee); return employee
    def list(self, *, include_inactive: bool = False) -> list[dict]:
        return [self._validated(employee) for employee in list_employees(include_inactive=include_inactive)]
    def get(self, employee_id: str) -> dict | None:
        employee = get_employee(employee_id); return self._validated(employee) if employee else None
    def assignment_options(self) -> dict:
        return get_employee_assignment_options()
