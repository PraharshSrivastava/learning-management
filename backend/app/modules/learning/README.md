# Learning module

Learner course access, playback media, progress and live updates.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Authenticated learner course and progress endpoints. |
| `media_access.py` | Short-lived media credentials with current identity/resource checks on every read. |
| `media_api.py` | Media URLs do not grant reporting users course-content access. |
| `notifications.py` | Learner-course WebSocket connections and update broadcasts. |
| `progress_repository.py` | Learner assignment and module-progress persistence queries. |
| `progress_schemas.py` | Learner progress API contracts. |
| `schemas.py` | Learner course response contracts. |
| `service.py` | Learner course access, status, and module-progress use cases. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/me/courses` |
| WS | `/api/me/courses/ws` |
| PUT | `/api/me/courses/{course_id}/modules/{module_number}` |
| PUT | `/api/me/courses/{course_id}/status` |
| GET | `/api/media-ticket` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
