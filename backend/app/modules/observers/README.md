# Observers module

Course Observers (people who may watch a course's results).

## Files

| File | What it does |
| --- | --- |
| `api.py` | Creator-managed course observers; Admin cross-owner reads only. |
| `repository.py` | Revisioned Observer selectors with immediate restriction and explicit apply. |
| `schemas.py` | Observer configuration is independent of learner Include/Exclude filters. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/courses/{course_id}/observers` |
| PUT | `/api/courses/{course_id}/observers` |
| POST | `/api/courses/{course_id}/observers/apply` |
| GET | `/api/observer/options` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
