# Documents module

Document text extraction and the AI Document Builder workflow.

## Files

| File | What it does |
| --- | --- |
| `builder/` | Document-builder implementation. |
| `builder/import_source.py` | Immutable owned source import, without course creation or source rewriting. |
| `builder/pdf_builder.py` | PDF renderer copied from the scratch document builder. |
| `builder/prompts.py` | Prompts copied verbatim from the validated scratch document builder. |
| `builder/workflow_export.py` | Canonical PDF export and approved-revision adapter into existing courses. |
| `builder/workflow_jobs.py` | Owned, revision-bound background operations with durable results/proposals. |
| `builder/workflow_model.py` | Bounded model adapter with strict task and semantic output validation. |
| `builder/workflow_prompts.py` | Task-specific prompts; imported text is evidence, never instructions. |
| `builder_api.py` | Integrated scratch document-builder endpoints. |
| `builder_service.py` | Document-builder orchestration with scratch-compatible behavior. |
| `drafts_api.py` | Feature-gated draft foundation; model operations are added in later phases. |
| `drafts_repository.py` | Atomic trainer-owned draft revisions; additive PostgreSQL persistence. |
| `extraction/` | Document type definitions and conversion helpers. |
| `extraction/conversion.py` | Small LibreOffice helper for converting Office docs to PDF. |
| `extraction/docx.py` | Native DOCX text, metadata, and image extraction for course blueprints. |
| `extraction/pptx.py` | Native PPTX text extraction and LLM metadata inference. |
| `workflow_schemas.py` | Strict, versioned contracts for persistent training-document drafts. |

## HTTP routes

| Method | Path |
| --- | --- |
| POST | `/api/document-builder/build-document` |
| GET | `/api/document-builder/capabilities` |
| GET | `/api/document-builder/drafts` |
| POST | `/api/document-builder/drafts` |
| GET | `/api/document-builder/drafts/{draft_id}` |
| PATCH | `/api/document-builder/drafts/{draft_id}` |
| POST | `/api/document-builder/drafts/{draft_id}/approve-outline` |
| POST | `/api/document-builder/drafts/{draft_id}/assets` |
| GET | `/api/document-builder/drafts/{draft_id}/assets/{asset_id}` |
| POST | `/api/document-builder/drafts/{draft_id}/copy` |
| POST | `/api/document-builder/drafts/{draft_id}/create-course` |
| POST | `/api/document-builder/drafts/{draft_id}/import` |
| GET | `/api/document-builder/drafts/{draft_id}/operations` |
| POST | `/api/document-builder/drafts/{draft_id}/operations` |
| GET | `/api/document-builder/drafts/{draft_id}/operations/{operation_id}` |
| POST | `/api/document-builder/drafts/{draft_id}/operations/{operation_id}/cancel` |
| POST | `/api/document-builder/drafts/{draft_id}/proposals/{operation_id}/accept` |
| POST | `/api/document-builder/drafts/{draft_id}/proposals/{operation_id}/reject` |
| POST | `/api/document-builder/drafts/{draft_id}/remove` |
| POST | `/api/document-builder/drafts/{draft_id}/render-pdf` |
| POST | `/api/document-builder/drafts/{draft_id}/restore` |
| GET | `/api/document-builder/drafts/{draft_id}/revisions` |
| GET | `/api/document-builder/drafts/{draft_id}/sources` |
| POST | `/api/document-builder/drafts/{draft_id}/sources/{source_id}/acknowledge` |
| GET | `/api/document-builder/drafts/{draft_id}/sources/{source_id}/original` |
| POST | `/api/document-builder/drafts/{draft_id}/undo-remove` |
| POST | `/api/document-builder/render-pdf` |
| POST | `/api/document-builder/save-pdf` |

## Tables created here

`document_builder_drafts`, `document_builder_operations`, `document_builder_removed_drafts`, `document_builder_resources`, `document_builder_revisions`

See [docs/ARCHITECTURE.md](../../../../docs/ARCHITECTURE.md) for how modules fit together.
