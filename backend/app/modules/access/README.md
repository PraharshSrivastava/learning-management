# Access module

LMS permissions: who may author, observe and see which reports.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Audience-specific permission discovery using existing authentication. |
| `course_authorization.py` | Course content oversight is distinct from all-course performance access. |
| `directory_report_access_repository.py` | Trusted directory adapter; no HTTP/manual HOD writer and no heuristics. |
| `report_access.py` | Validate the requested contribution; SQL intersects it with each row. |
| `report_access_repository.py` | Effective report roles and a safe department registry for observation selectors. |
| `reporting_scope.py` | Explicit trusted reporting scope; never constructed from browser role fields. |
| `repository.py` | Persisted grants are bound to stable directory identities, not email/name. |
| `schemas.py` | Capability discovery contracts; no client-supplied role requests. |
| `service.py` | Resolve LMS capabilities without changing existing Hub authoring access. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/lms/me` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
