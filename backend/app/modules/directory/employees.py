"""Employee directory use cases."""

from app.modules.directory.employees_repository import EmployeeRepository

_employees = EmployeeRepository()


def list_employees() -> list[dict]:
    return _employees.list()
