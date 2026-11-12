# Uploads module

Source document uploads (PDF, PPTX, DOCX) and their catalog.

## Files

| File | What it does |
| --- | --- |
| `api.py` | PDF, PPTX, and DOCX upload, retrieval, and preview endpoints. |
| `repository.py` | Document catalog persistence for uploaded source PDFs. |
| `schemas.py` | Upload and stored-file API contracts. |
| `service.py` | Document upload storage operations independent of HTTP routing. |

## HTTP routes

| Method | Path |
| --- | --- |
| GET | `/api/files` |
| GET | `/api/files/{file_name}` |
| GET | `/api/files/{file_name}/preview` |
| POST | `/api/upload` |

## Tables created here

None in this folder. Its tables are created by `app/db/schema.py`.

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
