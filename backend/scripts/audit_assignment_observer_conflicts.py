"""Read-only pre-rollout audit; never removes assignments, progress or grants."""

import argparse
import json

from app.repositories.database import get_connection
from app.services.assignment_conflicts import EmployeeObserverConflict, validate_separation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id")
    args = parser.parse_args()
    with get_connection() as db:
        rows = db.execute(
            "SELECT course_id FROM courses WHERE (?::text IS NULL OR course_id = ?) ORDER BY course_id",
            (args.course_id, args.course_id),
        ).fetchall()
        problems = []
        for row in rows:
            try:
                validate_separation(row["course_id"], db=db)
            except EmployeeObserverConflict as error:
                problems.append({"course_id": row["course_id"], "message": str(error)})
    print(json.dumps({"courses_checked": len(rows), "conflicts": problems}, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
