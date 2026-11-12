# Reporting module

Trainer analytics and the Performance report.

## Files

| File | What it does |
| --- | --- |
| `analytics.py` | Trainer performance analytics use cases. |
| `analytics_schemas.py` | Typed trainer analytics response contracts. |
| `api.py` | Trainer reporting endpoints. |
| `performance.py` | Trainer performance metrics shared by dashboard, detail views, and exports. |
| `repository.py` | Set-based reads for trainer performance reports. |
| `schemas.py` | Response contracts for trainer performance reporting. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/employee/performance/assignments` |
| GET | `/api/employee/performance/assignments/{assignment_id}` |
| GET | `/api/employee/performance/courses` |
| GET | `/api/employee/performance/courses/{course_id}` |
| GET | `/api/employee/performance/employees` |
| GET | `/api/employee/performance/employees/export` |
| GET | `/api/employee/performance/employees/{employee_id}` |
| GET | `/api/employee/performance/export` |
| GET | `/api/employee/performance/journeys` |
| GET | `/api/employee/performance/journeys/{journey_id}` |
| GET | `/api/employee/performance/journeys/{journey_id}/certificates/{employee_id}` |
| GET | `/api/employee/performance/options` |
| GET | `/api/employee/performance/overview` |
| GET | `/api/employee/team-performance` |
| GET | `/api/trainer/performance` |
| GET | `/api/trainer/performance/assignments` |
| GET | `/api/trainer/performance/assignments/{assignment_id}` |
| GET | `/api/trainer/performance/courses` |
| GET | `/api/trainer/performance/courses/{course_id}` |
| GET | `/api/trainer/performance/employees` |
| GET | `/api/trainer/performance/employees/export` |
| GET | `/api/trainer/performance/employees/{employee_id}` |
| GET | `/api/trainer/performance/export` |
| GET | `/api/trainer/performance/journeys` |
| GET | `/api/trainer/performance/journeys/{journey_id}` |
| GET | `/api/trainer/performance/journeys/{journey_id}/certificates/{employee_id}` |
| GET | `/api/trainer/performance/options` |
| GET | `/api/trainer/performance/overview` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
