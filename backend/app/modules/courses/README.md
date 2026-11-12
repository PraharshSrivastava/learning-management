# Courses module

Course authoring, library, availability (enable/disable/delete).

## Files

| File | What it does |
| --- | --- |
| `access.py` | Shared course identity and readiness rules used by LMS services. |
| `api.py` | Course blueprint and authoring endpoints. |
| `artifacts.py` | Safe cleanup of generated files owned by one course. |
| `library_api.py` | Own library and authenticated Admin Trainer course oversight. |
| `library_schemas.py` | Bounded authoring library metadata; creator controls are server-derived. |
| `lifecycle.py` | Creator-only reversible course availability, with retained learning history. |
| `quiz_schemas.py` | Quiz contracts used by authoring endpoints. |
| `repository.py` | Course persistence queries backed by normalized LMS tables. |
| `schemas.py` | Course authoring and generation API contracts. |
| `service.py` | Course authoring business rules, independent of HTTP routing. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/courses` |
| POST | `/api/courses/generate` |
| DELETE | `/api/courses/{course_id}` |
| GET | `/api/courses/{course_id}` |
| PUT | `/api/courses/{course_id}` |
| POST | `/api/courses/{course_id}/lifecycle` |
| PUT | `/api/courses/{course_id}/modules/{module_number}/quiz` |
| GET | `/api/trainer/course-library` |
| GET | `/api/trainer/course-library/{course_id}/assignments` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
