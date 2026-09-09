"""Seed local development employees that can be used as trainers.

Local trainer login lists active employees whose source is "hub", then creates
trainer projections from the selected employee. These rows give local dev a
small realistic directory without requiring the Hub export service.
"""

from __future__ import annotations

from app.repositories.employees import EmployeeRepository
from app.repositories.schema import init_db


LOCAL_EMPLOYEES = (
    {
        "employee_id": "trainer-asha",
        "name": "Asha Rao",
        "job_title": "Learning Program Manager",
        "department": "Learning and Development",
        "join_date": "2022-04-18",
        "status": "active",
        "directory_uuid": "local-trainer-asha",
        "hub_user_id": 900001,
        "email": "asha.rao.local@example.com",
        "sam_account_name": "asha.rao.local",
        "company": "PhillipCapital",
        "directory_status": "active",
        "source": "hub",
    },
    {
        "employee_id": "trainer-rohan",
        "name": "Rohan Mehta",
        "job_title": "Sales Training Lead",
        "department": "Sales Enablement",
        "join_date": "2021-09-06",
        "status": "active",
        "directory_uuid": "local-trainer-rohan",
        "hub_user_id": 900002,
        "email": "rohan.mehta.local@example.com",
        "sam_account_name": "rohan.mehta.local",
        "company": "PhillipCapital",
        "directory_status": "active",
        "source": "hub",
    },
    {
        "employee_id": "trainer-neha",
        "name": "Neha Iyer",
        "job_title": "Compliance Trainer",
        "department": "Compliance",
        "join_date": "2020-11-23",
        "status": "active",
        "directory_uuid": "local-trainer-neha",
        "hub_user_id": 900003,
        "email": "neha.iyer.local@example.com",
        "sam_account_name": "neha.iyer.local",
        "company": "PhillipCapital",
        "directory_status": "active",
        "source": "hub",
    },
    {
        "employee_id": "trainer-vikram",
        "name": "Vikram Shah",
        "job_title": "Product Training Specialist",
        "department": "Product",
        "join_date": "2023-02-13",
        "status": "active",
        "directory_uuid": "local-trainer-vikram",
        "hub_user_id": 900004,
        "email": "vikram.shah.local@example.com",
        "sam_account_name": "vikram.shah.local",
        "company": "PhillipCapital",
        "directory_status": "active",
        "source": "hub",
    },
)

LOCAL_GROUPS = {
    "trainer-asha": [
        {
            "group_dn": "CN=LMS Trainers,OU=Local,DC=example,DC=com",
            "group_cn": "LMS Trainers",
        },
        {
            "group_dn": "CN=Learning Admins,OU=Local,DC=example,DC=com",
            "group_cn": "Learning Admins",
        },
    ],
    "trainer-rohan": [
        {
            "group_dn": "CN=LMS Trainers,OU=Local,DC=example,DC=com",
            "group_cn": "LMS Trainers",
        },
        {
            "group_dn": "CN=Sales Enablement,OU=Local,DC=example,DC=com",
            "group_cn": "Sales Enablement",
        },
    ],
    "trainer-neha": [
        {
            "group_dn": "CN=LMS Trainers,OU=Local,DC=example,DC=com",
            "group_cn": "LMS Trainers",
        },
        {
            "group_dn": "CN=Compliance,OU=Local,DC=example,DC=com",
            "group_cn": "Compliance",
        },
    ],
    "trainer-vikram": [
        {
            "group_dn": "CN=LMS Trainers,OU=Local,DC=example,DC=com",
            "group_cn": "LMS Trainers",
        },
        {
            "group_dn": "CN=Product,OU=Local,DC=example,DC=com",
            "group_cn": "Product",
        },
    ],
}


def main() -> None:
    init_db()
    repository = EmployeeRepository()
    for employee in LOCAL_EMPLOYEES:
        repository.upsert(employee, LOCAL_GROUPS.get(employee["employee_id"], []))
        print(f"Seeded local trainer employee: {employee['employee_id']} - {employee['name']}")


if __name__ == "__main__":
    main()
