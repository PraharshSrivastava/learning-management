from app.services.directory_sync import _normalize_employee


def test_directory_employee_department_is_separate_from_group_cn_mailing_lists():
    employee, groups = _normalize_employee(
        {
            "employee_id": "emp_0001",
            "name": "Asha Rao",
            "department": "ARMG",
            "title": "Associate",
            "groups": [
                {
                    "dn": "CN=AI-Team,OU=Mailing Lists,DC=example,DC=com",
                    "cn": "AI-Team",
                },
                {
                    "group_dn": "CN=ARMG-Managers,OU=Mailing Lists,DC=example,DC=com",
                    "group_cn": "ARMG-Managers",
                },
            ],
        }
    )

    assert employee["department"] == "ARMG"
    assert [group["group_cn"] for group in groups] == ["AI-Team", "ARMG-Managers"]
    assert [group["group_dn"] for group in groups] == [
        "CN=AI-Team,OU=Mailing Lists,DC=example,DC=com",
        "CN=ARMG-Managers,OU=Mailing Lists,DC=example,DC=com",
    ]
