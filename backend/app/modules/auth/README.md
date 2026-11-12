# Auth module

Sign-in: Hub SSO launch, sessions and current-user resolution.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Local development authentication endpoints. |
| `hub_api.py` | Hub SSO launch and session endpoints. |
| `service.py` | Development authentication state and current-employee resolution. |

## HTTP routes

| Method | Path |
| --- | --- |
| POST | `/api/auth/local/employee-login` |
| POST | `/api/auth/local/trainer-login` |
| GET | `/api/auth/local/trainers` |
| GET | `/api/hub/launch/employee` |
| GET | `/api/hub/launch/trainer` |
| POST | `/api/hub/logout/employee` |
| POST | `/api/hub/logout/trainer` |
| GET | `/api/hub/session/employee` |
| GET | `/api/hub/session/trainer` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
