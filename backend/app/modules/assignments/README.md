# Assignments module

Course assignment rules, deadlines, conflicts and saved groups.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Course assignment authoring and publication endpoints. |
| `conflicts.py` | Course-local employee/Observer role separation, evaluated under the course lock. |
| `deadlines.py` | Resolve fixed dates without changing legacy relative-deadline storage. |
| `repository.py` | Assignment-rule persistence and matching. |
| `saved_groups_repository.py` | Trainer-owned reusable assignment-group persistence. |
| `schemas.py` | Course-assignment API contracts. |
| `service.py` | Course assignment rules, publication, and employee matching use cases. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/assignment/courses` |
| GET | `/api/assignment/options` |
| GET | `/api/assignment/saved-groups` |
| POST | `/api/assignment/saved-groups` |
| DELETE | `/api/assignment/saved-groups/{saved_group_id}` |
| PUT | `/api/assignment/saved-groups/{saved_group_id}` |
| GET | `/api/courses/{course_id}/assignment` |
| PUT | `/api/courses/{course_id}/assignment` |
| POST | `/api/courses/{course_id}/assignment/employee-preview` |
| POST | `/api/courses/{course_id}/disable-assignment` |
| POST | `/api/courses/{course_id}/publish-assignment` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
