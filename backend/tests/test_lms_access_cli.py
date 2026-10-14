"""Provisioning rejects missing audit/identity inputs before touching grants."""

import json

import pytest

from scripts import set_lms_authoring_role as cli


def test_mutation_requires_explicit_identity_operator_and_reason(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Must validate input before database mutation")

    monkeypatch.setattr(cli, "set_admin_grant", forbidden)
    with pytest.raises(SystemExit) as error:
        cli.main(["grant", "--employee-id", "employee-1"])
    assert error.value.code == 2


def test_cli_grant_uses_exact_identity_and_audit_fields(monkeypatch, capsys):
    calls = []

    def grant(employee_id, **kwargs):
        calls.append((employee_id, kwargs))
        return {"changed": True, "permissions_version": 1}

    monkeypatch.setattr(cli, "set_admin_grant", grant)
    assert (
        cli.main(
            [
                "grant",
                "--employee-id",
                "employee-1",
                "--identity-key",
                "directory:uuid-1",
                "--operator",
                "ops-1",
                "--reason",
                "approved oversight",
            ]
        )
        == 0
    )
    assert calls == [
        (
            "employee-1",
            {
                "active": True,
                "expected_identity": "directory:uuid-1",
                "operator": "ops-1",
                "reason": "approved oversight",
            },
        )
    ]
    assert json.loads(capsys.readouterr().out)["permissions_version"] == 1
