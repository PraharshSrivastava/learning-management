"""Operations-only Admin Trainer provisioning; never a public HTTP mutation."""

import argparse
import json

from app.core.exceptions import ApplicationError
from app.repositories.employees import EmployeeRepository
from app.repositories.lms_access import access_snapshot, identity_key, set_admin_grant


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect, grant or revoke Admin Trainer using an exact synced employee ID. Existing Trainer entitlement remains managed through Hub."
    )
    parser.add_argument("action", choices=("inspect", "grant", "revoke"))
    parser.add_argument("--employee-id", required=True)
    parser.add_argument(
        "--identity-key", help="Exact directory:<UUID> or hub:<ID> shown by inspect"
    )
    parser.add_argument("--operator", help="Audited operations identity")
    parser.add_argument("--reason", help="Required reason for changing access")
    args = parser.parse_args(argv)
    if args.action != "inspect" and not all((args.identity_key, args.operator, args.reason)):
        parser.error("grant/revoke require --identity-key, --operator and --reason")
    try:
        if args.action == "inspect":
            employee = EmployeeRepository().get(args.employee_id)
            if not employee:
                parser.error("Exact employee ID was not found")
            roles, version = access_snapshot(employee)
            result = {
                "employee_id": employee["employee_id"],
                "identity_key": identity_key(employee),
                "status": employee["status"],
                "stored_roles": sorted(roles),
                "permissions_version": version,
            }
        else:
            result = set_admin_grant(
                args.employee_id,
                active=args.action == "grant",
                expected_identity=args.identity_key,
                operator=args.operator,
                reason=args.reason,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except ApplicationError as error:
        parser.exit(1, error.message + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
