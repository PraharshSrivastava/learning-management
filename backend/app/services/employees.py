"""Employee directory use cases."""

from app.repositories.employees import EmployeeRepository

_employees = EmployeeRepository()


def list_employees() -> list[dict]:
    return _employees.list()
