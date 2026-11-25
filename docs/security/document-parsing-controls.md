# Document parsing controls (LMS backend)

Answers vendor finding F-08. Describes how files uploaded by trainers are handled before and during parsing. Last reviewed 20 November 2026.

## Who can upload

Only a signed-in trainer. `POST` upload calls resolve the trainer from the session (`current_trainer_from_request`) and store the file under that trainer's id. Learners cannot upload documents.

## Checks before any parser runs

| Check | Where | Behaviour |
|---|---|---|
| Size | nginx, `client_max_body_size 200M` in both front-end proxies | Larger requests are refused before they reach the backend |
| File type by extension | `UploadService.save_document` | Only `.pdf`, `.docx`, `.pptx` |
| File type by content | `UploadService.save_document` | The first bytes must match the extension (`%PDF-` for PDF, the ZIP signature for DOCX and PPTX). A mismatch is refused and nothing is written to disk |
| File name | `UploadService.sanitize_filename` | Path parts are dropped; anything outside `A-Z a-z 0-9 . _ -` becomes `_`; the stored name is prefixed with the trainer id |
| Location | `UploadService`, `SourceImporter.load` | A file is only read back if it resolves to a direct child of the upload directory |

## Where parsing runs

Inside the backend container only. Nothing is parsed in the browser or in the database.

- The container runs as user `10001`, not root.
- `cap_drop: [ALL]` and `no-new-privileges` are set in `docker-compose.yml`.
- The backend port is published on the server's loopback address only by default; users reach it through the front-end nginx proxies.

## Parsers and their settings

| Format | Library | Notes |
|---|---|---|
| PDF text, layout and images | pdfplumber (pdfminer.six) with pypdfium2 for rendering | PyMuPDF was removed in November 2026. No JavaScript, form or embedded-file handling is invoked |
| DOCX | python-docx | Its lxml parser is created with `resolve_entities=False` |
| PPTX | python-pptx | Its lxml parser is created with `resolve_entities=False` |
| DOCX/PPTX to PDF | LibreOffice, headless | Started with an argument list (no shell), a throw-away profile directory per conversion, and a time limit |
| Images inside documents | Pillow | Images above 25 million pixels are refused in the Document Builder import; Pillow's decompression-bomb guard is active |

The application code does not parse XML itself. `backend/app` has no call into `lxml.etree`, `xml.etree` or `xml.dom`; the only XML handling is inside python-docx and python-pptx, with entity resolution off. The backend image ships a patched libxml2 (2.15.4) and Expat (2.8.5).

## Resource limits

| Limit | Value | Where |
|---|---|---|
| Upload size | 200 MB | nginx |
| Office conversion time | 180 s (`DOCUMENT_CONVERSION_TIMEOUT_SECONDS`) | `convert_office_to_pdf` |
| Image pixel count | 25,000,000 | `SourceImporter` |
| Document Builder image upload | 10 MB, and the file must open as an image | `document_drafts.upload_asset` |
| Text chunk size | 18,000 characters | `SourceImporter` |

Not set today: a memory or CPU cap on the backend container, and a time limit on PDF parsing itself. Both are deployment settings (`mem_limit`, `cpus`, `pids_limit` in the compose file). They are not set in this change because video generation shares the container and the right values need to be measured on the UAT server. Owner: DevOps. Review date: 20 February 2027.
