# Emails module

Course and journey emails: outbox, templates and the Email status report.

## Files

| File | What it does |
| --- | --- |
| `notifications.py` | Course assignment email outbox, scheduler, and SMTP delivery. |
| `status.py` | Email status report: what the system recorded about each course assignment email. |
| `status_api.py` | Trainer-only Email status endpoints. |
| `status_repository.py` | Reads for the Email status report: one consistent snapshot of a course's assignment emails. |
| `status_schemas.py` | Response contracts for the Email status report. |
| `templates.py` | Approved course-notification email templates. Learners and trainers know the LMS as PhillipAcademy. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/trainer/performance/emails` |
| GET | `/api/trainer/performance/emails/export` |
| POST | `/api/trainer/performance/emails/resend-failed` |
| POST | `/api/trainer/performance/emails/{notification_id}/resend` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
