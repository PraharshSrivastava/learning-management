# Learning Journeys module

Learning Journeys: authoring, learner state, reporting, certificates.

## Files

| File | What it does |
| --- | --- |
| `api.py` | Learning Journey endpoints for the Trainer app (authoring) and the Employee app (learning). |
| `certificates.py` | Learning Journey completion certificates: a branded, verifiable PDF. |
| `observers_repository.py` | Revisioned journey Observer selectors, the same model as course Observers. |
| `reporting.py` | Learning Journey results for the Performance report. |
| `repository.py` | Learning Journey persistence: journeys, their ordered steps, rules and per-employee state. |
| `schemas.py` | Learning Journey API contracts. |
| `service.py` | Learning Journey use cases: trainer authoring, per-employee sync and learner views. |
| `state.py` | Learning Journey lock rules for one employee and one journey. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/learning-journeys` |
| POST | `/api/learning-journeys` |
| GET | `/api/learning-journeys/certificates/{number}` |
| GET | `/api/learning-journeys/course-options` |
| DELETE | `/api/learning-journeys/{journey_id}` |
| GET | `/api/learning-journeys/{journey_id}` |
| PUT | `/api/learning-journeys/{journey_id}` |
| POST | `/api/learning-journeys/{journey_id}/disable` |
| POST | `/api/learning-journeys/{journey_id}/duplicate` |
| GET | `/api/learning-journeys/{journey_id}/observers` |
| PUT | `/api/learning-journeys/{journey_id}/observers` |
| POST | `/api/learning-journeys/{journey_id}/observers/apply` |
| POST | `/api/learning-journeys/{journey_id}/preview` |
| POST | `/api/learning-journeys/{journey_id}/publish` |
| GET | `/api/me/learning-journeys` |
| GET | `/api/me/learning-journeys/{journey_id}/certificate` |

## Tables created here

`learning_journey_assignments`, `learning_journey_certificates`, `learning_journey_observer_configs`, `learning_journey_observer_departments`, `learning_journey_observer_employees`, `learning_journey_observers`, `learning_journey_rules`, `learning_journey_stages`, `learning_journey_steps`, `learning_journeys`

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
