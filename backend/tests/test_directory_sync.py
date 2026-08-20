from datetime import datetime

from app.services import directory_scheduler
from app.services.directory_sync import (
    _apply_employee,
    _employee_from_change,
    _normalize_employee,
)


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


def test_live_change_log_changes_payload_is_flattened():
    employee = _employee_from_change(
        {
            "event_id": 12,
            "event_type": "updated",
            "occurred_at": "2026-08-20T03:40:00+00:00",
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "changes": {
                "name": {"old": "Asha", "new": "Asha Rao"},
                "department": "ARMG",
                "groups": [
                    {"dn": "CN=ARMG,OU=Groups,DC=example,DC=com", "cn": "ARMG"},
                ],
            },
        }
    )

    assert employee["hub_user_id"] == 321
    assert employee["directory_uuid"] == "dir-321"
    assert employee["name"] == "Asha Rao"
    assert employee["department"] == "ARMG"
    assert employee["directory_changed_at"] == "2026-08-20T03:40:00+00:00"


def test_delete_or_disable_change_marks_employee_inactive():
    employee = _employee_from_change(
        {
            "event_type": "employee_disabled",
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "changes": {"directory_status": "disabled"},
        }
    )

    assert employee["status"] == "inactive"
    assert employee["directory_status"] == "inactive"


def test_existing_employee_identity_survives_username_and_email_changes():
    existing = {
        "employee_id": "emp_hub_321",
        "name": "Asha Rao",
        "job_title": "Associate",
        "department": "ARMG",
        "join_date": "2026-08-01",
        "status": "active",
        "directory_uuid": "dir-321",
        "hub_user_id": 321,
        "email": "asha.old@example.com",
        "sam_account_name": "asha.old",
        "company": "PhillipCapital",
        "manager_directory_uuid": None,
        "manager_employee_id": None,
        "directory_status": "active",
        "source": "hub",
        "directory_changed_at": "2026-08-19T03:40:00+00:00",
    }

    employee, groups = _normalize_employee(
        {
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "email": "asha.new@example.com",
            "sam_account_name": "asha.new",
            "directory_changed_at": "2026-08-20T03:40:00+00:00",
        },
        existing,
    )

    assert employee["employee_id"] == "emp_hub_321"
    assert employee["email"] == "asha.new@example.com"
    assert employee["sam_account_name"] == "asha.new"
    assert employee["name"] == "Asha Rao"
    assert employee["department"] == "ARMG"
    assert groups is None


def test_new_employee_id_uses_stable_hub_or_directory_identifiers_not_email():
    by_hub, _ = _normalize_employee(
        {
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "email": "asha.rao@example.com",
        }
    )
    by_directory, _ = _normalize_employee(
        {
            "directory_uuid": "9f6e2f75-31b8-45a0-9c84-8cfe80f019b2",
            "email": "rahul@example.com",
        }
    )

    assert by_hub["employee_id"] == "emp_hub_321"
    assert by_directory["employee_id"] == "emp_dir_9f6e2f75_31b8_45a0_9c84_8cfe80f019b2"


class _FakeEmployees:
    def __init__(self, existing=None):
        self.existing = existing
        self.upserts = []

    def get_by_directory_uuid(self, directory_uuid):
        if self.existing and self.existing.get("directory_uuid") == directory_uuid:
            return self.existing
        return None

    def get_by_hub_user_id(self, hub_user_id):
        if self.existing and self.existing.get("hub_user_id") == hub_user_id:
            return self.existing
        return None

    def get(self, employee_id):
        if self.existing and self.existing.get("employee_id") == employee_id:
            return self.existing
        return None

    def upsert(self, employee, groups=None):
        self.upserts.append((employee, groups))
        return employee


class _FakeTrainers:
    def __init__(self):
        self.refreshed = []

    def refresh_existing_from_employee(self, employee):
        self.refreshed.append(employee)
        return None


def test_incremental_stale_event_is_skipped_without_upsert(monkeypatch):
    from app.services import directory_sync

    fake_employees = _FakeEmployees(
        {
            "employee_id": "emp_hub_321",
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "directory_changed_at": "2026-08-20T03:40:00+00:00",
        }
    )
    monkeypatch.setattr(directory_sync, "_employees", fake_employees)
    monkeypatch.setattr(directory_sync, "_trainers", _FakeTrainers())

    employee_id, applied = _apply_employee(
        {
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "name": "Older Asha",
            "directory_changed_at": "2026-08-19T03:40:00+00:00",
        },
        skip_stale=True,
    )

    assert employee_id == "emp_hub_321"
    assert applied is False
    assert fake_employees.upserts == []


def test_partial_change_preserves_groups_by_passing_none(monkeypatch):
    from app.services import directory_sync

    fake_employees = _FakeEmployees(
        {
            "employee_id": "emp_hub_321",
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "name": "Asha Rao",
            "job_title": "Associate",
            "department": "ARMG",
            "join_date": None,
            "status": "active",
            "email": "asha@example.com",
            "sam_account_name": "asha",
            "company": None,
            "manager_directory_uuid": None,
            "manager_employee_id": None,
            "directory_status": "active",
            "source": "hub",
            "directory_changed_at": "2026-08-19T03:40:00+00:00",
        }
    )
    fake_trainers = _FakeTrainers()
    monkeypatch.setattr(directory_sync, "_employees", fake_employees)
    monkeypatch.setattr(directory_sync, "_trainers", fake_trainers)

    employee_id, applied = _apply_employee(
        {
            "hub_user_id": 321,
            "directory_uuid": "dir-321",
            "department": "Risk",
            "directory_changed_at": "2026-08-20T03:40:00+00:00",
        },
        skip_stale=True,
    )

    assert employee_id == "emp_hub_321"
    assert applied is True
    saved_employee, groups = fake_employees.upserts[0]
    assert saved_employee["department"] == "Risk"
    assert saved_employee["name"] == "Asha Rao"
    assert groups is None
    assert fake_trainers.refreshed == [saved_employee]


def test_next_directory_sync_run_uses_0910_ist(monkeypatch):
    monkeypatch.setattr(directory_scheduler.settings, "directory_sync_time", "09:10")
    monkeypatch.setattr(directory_scheduler.settings, "directory_sync_timezone", "Asia/Kolkata")

    before = datetime.fromisoformat("2026-08-20T09:00:00+05:30")
    after = datetime.fromisoformat("2026-08-20T09:11:00+05:30")

    assert directory_scheduler.next_directory_sync_run(before).isoformat() == "2026-08-20T09:10:00+05:30"
    assert directory_scheduler.next_directory_sync_run(after).isoformat() == "2026-08-21T09:10:00+05:30"
