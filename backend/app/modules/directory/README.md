# Directory module

Employee and trainer directory, and Hub directory sync.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Admin endpoints for Hub directory import. |
| `employee_schemas.py` | Employee and authentication API contracts. |
| `employees.py` | Employee directory use cases. |
| `employees_api.py` | Employee directory endpoints. |
| `employees_repository.py` | Employee persistence queries. |
| `scheduler.py` | Optional background scheduler for daily Hub directory sync. |
| `sync.py` | Hub directory export import and incremental sync. |
| `trainer_schemas.py` | Trainer API and persistence contracts. |
| `trainers_repository.py` | Trainer persistence queries. |

## HTTP routes

| Method | Path |
| --- | --- |
| POST | `/api/directory/sync/full` |
| POST | `/api/directory/sync/incremental` |
| GET | `/api/directory/sync/status` |
| GET | `/api/employees` |
| GET | `/api/me` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
