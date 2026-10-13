# LMS Trainer Document Builder — combined implementation plan

Date: 13 October 2026
Status: Proposed implementation plan; application changes have not started.

## 1. Agreed outcome

Combine the earlier Setup / Outline / Editor visual design with the latest demonstrated workflow:

1. **Use Existing Content**
2. **Generate with AI**
3. **Start blank**

Use the corporate navy header, clear step navigation, spacious document canvas, formatting toolbar, module sidebar, and separate AI Assistant panel from `docs/design/document-builder/01-setup-concept.png`, `02-outline-concept.png`, and `03-editor-concept.png`. The interactive demo establishes the paths and interactions; its simplified controls are not the final editor design.

An uploaded document can proceed directly from approved outline to **Create Course**, or optionally open the editor first. Create Course continues into the existing Courses experience and its current videos, quizzes, notes, slides, scripts, audio, thumbnails, recovery, and publishing behavior. Do not introduce a replacement Videos / Quizzes / Both selector.

AI changes are proposals. The trainer accepts or rejects them. Drafts persist, course details stay editable, the original upload stays available, and previous content can be restored.

The plan reduces mistakes through explicit contracts, validation, and release gates. It cannot certify deployed-model quality before live evaluations have run.

## 2. Verified implementation baseline and gaps

Inspection performed against the current workspace on the date above.

| Area | Current behavior | Required change |
|---|---|---|
| Builder frontend | Local widget state; four metadata/settings/chat/draft panels | Persistent workflow state and the agreed editor layout |
| AI request | Message, previous instructions, full plain-text draft, applied settings | Task-specific requests with approved outline, relevant metadata, scoped content, source references, and revision identity |
| AI system prompt | Demands a complete module-only text replacement and explicitly ignores LMS metadata | Separate outline, module drafting, editing, and source-Q&A prompts |
| AI response parsing | Accepts free text or JSON-like output; attempts to salvage malformed content | Typed schemas and semantic validation; invalid output cannot update content |
| Editor | `contentEditable`, text/image blocks; whole-text replacement appends preserved images at the end | Canonical blocks, stable identities, supported formatting, targeted updates that preserve image positions |
| Metadata save | Local saved flags, rather than a durable draft record | Acknowledged backend save and honest save status |
| Missing-field reporting | Field values used as map keys; duplicate empty values collapse labels | Validate each named field independently |
| Export | ReportLab PDF from plain text and images; metadata plus `Module 1:` checks | Canonical structured export and complete content validation |
| Document naming | Trainer/filename upsert can reuse a document record; saved PDF names derive from course title | Immutable original uploads and uniquely identified draft exports |
| Create Course | Filename request invokes blueprint extraction, then selects the new course | Additional draft-revision handoff that uses approved modules without re-extraction |
| Full generation | `restart_from_blueprint=True` resets generated assets in current runtime; it does **not** itself re-extract the file | Preserve this behavior; distinguish asset regeneration from blueprint re-extraction |
| Blueprint recovery | Can call filename-based outline generation | Approved-builder courses recover from their stored snapshot instead |
| Model routing | `get_llm_endpoint(purpose=...)` currently ignores purpose and uses the shared configured model | Builder-specific optional configuration with backward-compatible shared-model fallback |
| Configuration | Settings default and `.env.example` specify `gemma-4-e4b` | Verify deployed alias, context limits, and structured-output capability; do not infer them from its name |
| Visibility | Builder visibility provider is declared in both portal and API-provider files | One authoritative workflow/visibility provider |

Key existing integration files:

- Frontend: `frontend/lib/features/documents/document_portal.dart`, `frontend/lib/features/dashboard_page.dart`, `frontend/lib/features/document_builder/*`, `frontend/lib/state/trainer/document_builder_provider.dart`, `frontend/lib/state/trainer/course_authoring_providers.dart`, `frontend/lib/state/trainer/generation_providers.dart`.
- Backend: `backend/app/api/document_builder.py`, `backend/app/services/document_builder.py`, `backend/app/document_builder/prompts.py`, `backend/app/document_builder/pdf_builder.py`, `backend/app/core/providers.py`, `backend/app/core/settings.py`.
- Extraction/handoff: `backend/app/documents/*`, `backend/app/generation/blueprint.py`, `backend/app/services/courses.py`, `backend/app/services/generation.py`, `backend/app/generation/runtime.py`, `backend/app/schemas/course.py`, `backend/app/repositories/courses.py`.
- Persistence: `backend/app/repositories/schema.py`, `backend/app/repositories/documents.py`, `backend/app/repositories/jobs.py`.

Existing unrelated workspace changes must remain untouched. Implement by small, independently reviewable phases.

## 3. Product flows and state rules

### Use Existing Content

1. Choose an already-uploaded trainer-owned source, upload PDF/DOCX/PPTX, or paste existing text.
2. Store the immutable source and extract readable text, headings, tables, and supported image references with page/slide/paragraph locations.
3. Display extraction coverage and actionable issues. No readable text means no approval; mixed readable/unreadable pages require an explicit completeness acknowledgement or corrected source.
4. Prefer deterministic boundaries for explicit module headings. When headings are ambiguous, AI proposes boundaries referencing extracted source spans. It does not rewrite the source.
5. Suggest missing course details and learning objectives; mark them as suggestions for trainer confirmation. Preserve supplied details.
6. Review title, objective, content preview, source location, and inclusion for every module. Support rename, reorder, split, merge, add, and exclude. Split/merge operate on identified source spans so content is not lost or duplicated.
7. Approve the resulting outline/content mapping and required metadata.
8. Choose **Create Course** immediately, or **Review in editor first**.

Original wording is preserved by default. An excluded appendix is a trainer decision, not an automatic assumption. Record excluded source spans; do not silently omit unassigned content. Image-only scanned uploads receive a clear limitation and recovery options; OCR is a separate capability, not something to claim in this release without implementing and validating it.

Import is a conversion into supported editor blocks, not a promise to reproduce every original Word/PDF/PowerPoint layout. Preserve supported content and report unsupported items. PPTX image extraction needs an explicit implementation and test; current text extraction alone does not establish image support.

### Generate with AI

1. Capture topic, course name, audience, objective, language, difficulty, description, and course type. Use editable suggested defaults where appropriate.
2. Capture module count and writing preferences. Keep current 2–8 module-count range initially for AI-created outlines; imports and manually authored documents are not subject to that AI-only range.
3. Optionally attach approved reference material. Source-grounded and general-topic drafting must be visibly distinguishable.
4. Generate **outline only**: proposed module titles, learning objectives, and planned sections. Save it separately from content.
5. Trainer edits and approves the outline. Approval records a structural fingerprint and metadata/settings used for generation.
6. Generate content **one module at a time**, with an approved course outline and bounded related context. Use a small backend concurrency limit; initially one module at a time.
7. Save each valid completed module. Show module-level progress and allow retry of failed/incomplete modules without rewriting completed modules.
8. Open the editor with generated content. Trainer reviews, optionally requests AI edits, previews, and creates the course.

Outline approval authorizes initial drafting into empty modules. It does not authorize overwriting trainer-written modules on retry. Regeneration of populated content creates a reviewable proposal. Changing approved structure during generation cancels/discards results for the previous fingerprint and requires outline reapproval. Changed generation preferences affect subsequent requests; existing content changes only through explicit regeneration or editing.

### Start blank

1. Enter initial course details and open an empty module in the same editor.
2. Write and format content, add modules and images, and optionally ask AI to create or improve scoped content.
3. Save drafts even when metadata or content is incomplete. Validate required details and included-module content before Create Course and final export.
4. Review and confirm the included module structure before Create Course. This can be a compact preflight in the editor rather than a mandatory earlier Outline screen.

### Shared state

- Persist entry mode, metadata, settings, sources, modules, blocks, pending proposals, approval fingerprints, and revision numbers.
- Workflow milestones: source/setup → outline review → editor → course handoff. Preview is a reversible editor view/action, not a mandatory gate.
- Keep draft status separate from operation status: draft can be saved while generation is running or partially failed.
- Structural changes invalidate outline approval. Body-only edits invalidate content acceptance for handoff, without forcing the trainer to rebuild the outline.
- Relevant metadata/settings changes invalidate outstanding AI proposals and generation snapshots; unrelated display changes need not invalidate outline approval.
- Back navigation, refresh, and reopen restore the draft and operation state. No progress is simulated in the actual product.

## 4. Canonical data and persistence

Introduce typed backend and matching Dart models before replacing the UI.

**Draft:** server-issued ID, trainer owner, entry mode, schema version, metadata, writing settings, source IDs, ordered modules, revision, outline approval fingerprint, timestamps, and last handoff reference.

**Module:** stable ID, title, objective, inclusion flag, ordered block IDs, source spans, generation status, and content provenance. Display numbers are derived from current included order; they are not identity.

**Block:** stable ID and explicit type. First release supports headings, paragraphs with bold/italic/link marks, ordered/unordered lists, supported tables, scenario/callout and takeaway blocks, and images with caption/width/alignment. Unsupported imported structures receive a visible conversion issue rather than silent flattening.

**Source:** trainer-owned document ID or pasted-text source ID, immutable content hash, extraction version, extracted spans, page/slide/paragraph locations, and conversion issues. Original storage paths and unrestricted asset URLs are never accepted from the browser.

**Revision:** immutable recoverable snapshot of canonical content and metadata, plus change reason (manual save/checkpoint, AI acceptance, structure change, restore, handoff). Restoration creates a new head revision rather than deleting history.

**Proposal:** server-issued proposal ID, action, target IDs/ranges, expected draft revision and target hash, validated replacement/insert blocks, summary, model/config/prompt versions, provenance references, and status. Backend binds it to a trainer and draft.

**Operation:** operation ID, draft ID, request/idempotency key, captured revision/fingerprint, task, module progress, valid results, cancellation flag, and structured error. Persist operations so refresh does not restart work or lose completed results.

Add trainer-scoped draft, revision, proposal, source-extraction, and operation persistence using existing PostgreSQL repository conventions. Extend schema initialization additively and provide a repeatable existing-database upgrade. Do not use `recreate_db` for migration. Verify rollback/feature disable leaves uploaded documents and courses usable. Give assets stable owned references; avoid copying large image data URLs into every revision.

Autosave uses a debounce and acknowledged server revision. Save status is `Unsaved changes`, `Saving`, `Saved`, or `Save failed`. A failed save keeps local edits, offers retry, and prevents handoff from using an older revision. Flush pending edits before accepting a proposal, leaving the editor, previewing, or creating a course. On simultaneous-tab conflicts, return 409 and offer reload or preserve a separate draft; do not silently overwrite.

## 5. Proposed API contracts

Keep the current endpoints available during migration. New paths below are proposed contracts, not existing routes.

| Route | Responsibility |
|---|---|
| `POST /api/document-builder/drafts` | Create owned draft from an entry mode; return ID and revision |
| `GET /api/document-builder/drafts` | List/reopen owned drafts |
| `GET /api/document-builder/drafts/{id}` | Read canonical draft and current operations |
| `PATCH /api/document-builder/drafts/{id}` | Save validated canonical changes with expected revision |
| `POST /api/document-builder/drafts/{id}/operations` | Start extraction, outline, module drafting, scoped editing, or source Q&A; return 202 and operation ID |
| `GET /api/document-builder/operations/{id}` | Read owned operation results/progress |
| `POST /api/document-builder/operations/{id}/cancel` | Cancel logical operation and suppress subsequent writes |
| `POST /api/document-builder/drafts/{id}/approve-outline` | Validate and approve exact structural fingerprint |
| `POST /api/document-builder/drafts/{id}/proposals/{proposal_id}/accept` | Atomic revision-checked acceptance and new snapshot |
| `POST /api/document-builder/drafts/{id}/proposals/{proposal_id}/reject` | Reject without modifying content |
| `GET /api/document-builder/drafts/{id}/revisions` | List available recovery points |
| `POST /api/document-builder/drafts/{id}/restore` | Restore chosen revision as a new revision |
| `POST /api/document-builder/drafts/{id}/render-pdf` | Preview/export specified canonical revision |
| `POST /api/document-builder/drafts/{id}/create-course` | Validate final revision, make immutable handoff, return existing CourseResponse |

Operation payload is a discriminated typed request by task, not a free-form action string interpreted by the model. Backend loads source text, metadata, approved outline, and target content from the owned draft. Client submits only the instruction, target IDs/range, expected revision, explicit options, and idempotency key.

Use 422 for invalid typed inputs, 409 for stale revisions/invalid workflow state, and structured operation errors for provider/unavailable/timeout/invalid-response/context-limit failures. Return safe messages plus retryability and correlation ID. Do not present provider failures as missing trainer fields. Non-JSON gateway errors must be handled safely by the frontend.

Verify ownership for every draft, source, asset, operation, proposal, revision, and course. Run extraction/model work in bounded background jobs, not long-running UI requests. Reuse compatible job infrastructure after checking its course-specific assumptions; builder operations must not create placeholder courses merely to obtain job tracking.

## 6. Model and response-generation design

### 6.1 Model configuration and capability gate

- Initial candidate is the project's configured `gemma-4-e4b` alias. This is not evidence of a particular public model release, actual deployment, context size, or quality.
- Verify the running proxy/model mapping, availability, authorized endpoint, tokenizer/context budget, output limit, finish reasons, and structured-output support in the deployment environment.
- Add optional builder model/prompt settings that default to existing shared settings. Do not change quiz/script/slide model behavior as a side effect.
- Prefer schema-constrained JSON only when this exact deployed endpoint supports it. Otherwise use explicit JSON prompting and strict backend validation. The fallback must be tested; unsupported schema capability must not make every user request fail and retry blindly.
- Capability selection is configured/verified once per deployment, not discovered through a costly probe on each trainer request.
- Keep initial temperature near current low setting, with per-task output budgets. Final values follow model evaluation, not assumptions about the alias.

### 6.2 Separate tasks and prompts

| Task | Model input | Validated result | Effect |
|---|---|---|---|
| Source outline | Extracted source spans, headings, confirmed metadata | Titles/objectives with valid source boundaries | Proposed structure only |
| AI outline | Topic, relevant metadata, settings, optional reference excerpts | Exact requested number of ordered modules and planned sections | Proposed structure only |
| Draft module | Approved outline, one module specification, metadata/settings, bounded source excerpts | Blocks for that one module | Initial content in empty module, saved only after validation |
| Simplify / improve / rewrite selection | Exact selection and nearby context, action, language/audience, allowed target | Replacement text/blocks for the allowed range | Pending proposal |
| Add example / scenario / section | Module context, explicit insertion location, optional sources | Allowed inserted blocks | Pending proposal |
| Source Q&A | Question and identified source excerpts | Answer with source IDs/locations or explicit insufficient evidence | Assistant answer; no document mutation |
| Whole-document revision | Explicit trainer request and all affected scope declarations | Coordinated per-module proposals and summary | Reviewable proposal set; no automatic replacement |

Write versioned prompts for these tasks. Retire the old full-document replacement prompt for new flows. Course metadata informs content but is not duplicated as module body fields. The latest instruction can override writing preferences within the authorized task; it cannot expand scope, alter permissions, or skip trainer approval.

Treat uploaded content and quoted draft passages as source data, not system instructions. Examples and scenario suggestions are clearly labeled when invented. For source-grounded company rules, deadlines, escalation contacts, numerical claims, and policies, missing evidence requires clarification/insufficient-evidence output rather than invention. Images are not treated as interpreted evidence unless a separately validated image-capable flow exists; captions/text can be used with appropriate provenance.

Do not request, store, or display chain-of-thought. Return concise summaries/objectives and source references. Do not reuse the existing `ModuleListSchema` unchanged for new tasks because it contains a `chain_of_thought` field.

### 6.3 Output contract and ownership

The backend envelope owns `operationId`, `draftId`, expected revision, target IDs, scope, and proposal ID. The model never chooses identities, revisions, asset paths, or permission boundaries.

Example model-only outline payload:

```json
{
  "modules": [
    {
      "title": "Handling customer complaints",
      "objective": "Acknowledge a complaint and confirm the next step.",
      "sections": ["Explanation", "Workplace scenario", "Key takeaways"]
    }
  ]
}
```

This illustrates one module record; the complete result must match the validated requested count. Backend assigns stable module IDs after validation.

Example model-only editing payload:

```json
{
  "replacementText": "Listen without interrupting. Summarize the concern and confirm your understanding before proposing the next step.",
  "summary": "Simplified the selected paragraph for new employees.",
  "sourceReferences": []
}
```

Selection-replacement schemas differ from insert/module schemas. For marked text, apply plain-text replacement through the canonical editor range adapter so surrounding formatting remains intact; show changed internal formatting in the proposal. Use grapheme-safe mapping and test Dart/JavaScript/backend offset differences, emoji, combining marks, and cross-block selections. V1 can restrict a selection to a supported contiguous range and explain unsupported ranges rather than corrupt content.

### 6.4 Validation before exposing success

1. Require a valid completion object, nonempty content, and an acceptable finish reason. Reject truncated (`length`), filtered, refusal, or unexpected output as task-specific failure; valid-looking partial JSON is not success.
2. Parse strictly into the selected Pydantic response schema. Allow only known harmless wrapping such as one complete JSON fence; do not reconstruct content from broken quoted JSON or arbitrary prose.
3. Check exact module count/order for AI outlines, nonempty unique IDs assigned by backend, valid titles/objectives, allowed block types, requested language, target bounds, output size, and source-reference existence. Language/semantic quality needs live evaluation in addition to deterministic rules.
4. Check grounded source boundaries: no overlap, no unexplained gaps, valid page/line/span mappings. Resolve model-proposed boundaries against actual extracted content. Referencing a valid source ID alone does not establish factual correctness; test evidence support separately.
5. Reject scope expansion, new unauthorized assets, HTML/scripts/unsafe links, unknown fields, unsupported metadata modifications, and malformed blocks. Sanitize imported and AI-derived content before rendering.
6. Recheck captured revision/fingerprint and cancellation status before any durable write. Older model responses cannot overwrite newer trainer edits.
7. Save the validated result and operation state transactionally. Invalid output leaves prior content, images, metadata, and approvals intact.

Transport and schema-repair retries share an operation-wide budget. Initially allow at most four physical provider requests per module/task (up to two logical completions, each with at most two transient transport attempts), plus a deployment-configured total deadline. Authentication errors, unsupported configuration, invalid trainer inputs, and unrecoverable context excess are not blindly retried. A schema repair receives concise validation errors and the same authorized scope. It cannot silently change requested module count or drop content.

Large requests are split at module/source-span boundaries before calling the provider. Reserve input/output context explicitly; do not silently truncate sources or chat history. Use bounded relevant context and task state instead of unbounded concatenated chat instructions. Oversized selections ask the trainer to narrow the scope or generate coordinated proposals. A failed module remains retryable; completed modules stay saved.

### 6.5 Editor interaction and response presentation

- Selection toolbar: Edit with AI, Simplify, Add example; module actions for wider scope.
- Assistant panel shows scope, instruction, concise response, source references where applicable, and proposed before/after content.
- Accept/reject/revise are available; reject never mutates the document.
- Ask/explain responses do not replace content. Drafted quiz examples are document suggestions, not final generated course quizzes.
- Whole-document rewriting requires an explicit scope choice and a reviewed summary of affected modules.
- Acceptance creates a recoverable revision and applies only validated server-bound operations. If target text changed, show a stale-proposal message and offer regeneration; do not apply stale edits.
- Initial outline/module generation produces draft candidates; it does not publish anything.

### 6.6 Diagnostics

Record task, model alias, prompt/schema version, request ID, captured revision, latency, tokens when reported, retry count, finish reason, validation category, and outcome. Reuse existing tracing where compatible. Avoid adding raw document text or secrets to routine logs; review existing tracing content behavior before enabling new flows. UI says `Generating outline`, `Drafting module 2 of 4`, or `Preparing suggestion`, not a hardcoded model name.

## 7. Course handoff: preserve approved content

The new draft-based Create Course endpoint must not simply invoke the existing filename extractor after outline approval.

1. Flush autosave and validate required metadata, approval fingerprint, content revision, included module bodies, asset ownership, and acknowledged extraction issues.
2. Freeze an immutable accepted revision; retain original source references and export a uniquely identified source PDF when required by existing document/course relationships.
3. Build the existing course blueprint from canonical modules, mapping camelCase document metadata to snake_case course fields. Preserve confirmed titles, order, text, image mappings/captions, and existing question-count defaults. Derive display module numbers contiguously.
4. Save a normal trainer-owned course through existing repository conventions and mark blueprint complete through runtime helpers. Store draft ID/revision/hash and accepted-input origin durably, not as extra fields that disappear on repository serialization.
5. Return the existing CourseResponse and select it in Courses. Both direct-upload and editor paths use this same adapter.
6. Use an idempotency key plus captured draft revision so retries/double clicks cannot create duplicate courses. Course naming follows current conventions.
7. Keep existing generation stages and controls. A fresh full generation should still run its normal asset reset and stage sequence; do **not** set `restart_from_blueprint=False` for a fresh job merely because the blueprint is approved, since that flag also controls recovery scheduling.
8. Protect explicit blueprint restart/recovery for accepted-input courses: restore the immutable approved snapshot, or require a new explicit trainer-approved extraction. Legacy filename-based courses retain current behavior.
9. Later document edits do not mutate an already-generated course. Offer an explicit new course from a newer revision. No implicit replacement of published/assigned course content.

Course type is currently required by PDF metadata but absent from the inspected CourseMetadataSchema/CourseResponse. Preserve it in draft/export metadata and map it only after auditing downstream support; do not assume it is currently a supported course API field. Additive provenance/image fields must be explicitly persisted and exposed where needed.

## 8. Editor, preview, and export

- Keep the LMS Flutter/Riverpod shell and corporate visual language.
- Separate screens/components for entry selection, setup/import, outline review, editor, and preview. Centralize state in a draft controller instead of duplicating local saved flags.
- Use a structured editor adapter around canonical blocks. First implement a browser-selection/rich-formatting spike against current HTML editor; retain/extend it only if stable range mapping, round trips, undo, IME input, and pasted-content sanitization pass. Choose a replacement only with demonstrated Flutter web compatibility and without serializing arbitrary HTML as the authoritative document.
- Preserve image placement and formatting during AI acceptance, module reorder, save/reopen, and undo. Upload images as owned assets with bounded dimensions and validated file types.
- Desktop: module navigation, document canvas, collapsible assistant. Narrow screens: module drawer/stack and assistant sheet with accessible actions. Avoid current forced 1520px horizontal layout.
- Render PDF from the canonical revision, supporting the agreed formatting, tables, images/captions, module headings, and sensible page breaks. Preview/export share the renderer.
- Invalidate cached PDF when its revision changes. Verify selected language glyph support before enabling language choices; current Helvetica/Times output does not establish multilingual PDF support. English is the baseline validated language, with others enabled after model/editor/font acceptance checks.
- Provide saved drafts and original uploads in Documents. Distinguish draft revision/export from original source without duplicate ambiguous titles.

## 9. Implementation phases and exit checks

### Phase 0 — baseline, contracts, and model/editor spikes

- Capture existing document upload, builder export, Create Course, stage generation, recovery, and publish baselines.
- Validate deployment model capabilities using synthetic/non-confidential examples; record configuration and evaluation results.
- Finalize canonical schemas, task schemas, revision/approval rules, scope mapping, and repository/API mapping.
- Run editor selection/formatting/IME and canonical round-trip spike. Verify image/table import limitations by format.
- Exit: contract review complete; no unresolved model-output or course-handoff assumptions; viable editor adapter demonstrated.

### Phase 1 — persistent draft foundation

- Add additive database upgrade, repositories, typed APIs, trainer ownership checks, immutable source handling, revisions, autosave/conflict behavior, and idempotent operations.
- Consolidate workflow provider, metadata validation, and error decoding.
- Exit: manual draft edits survive refresh/reopen; concurrency conflicts are safe; originals cannot be overwritten by exports.

### Phase 2 — existing-content path and course adapter

- Refactor reusable extraction away from course-creation side effects.
- Implement extraction quality display, boundary review, metadata confirmation, structural editing, and approval.
- Build accepted-revision-to-course adapter and recovery/provenance integration before exposing direct Create Course.
- Exit: direct and editor upload paths produce equivalent approved course content; excluded/reordered modules and source images remain correct; existing generation stages run unchanged.

### Phase 3 — Generate with AI

- Implement separate outline/module prompts, schema validation, configured capability mode, bounded requests/retries, cancellation, durable module progress, and resume.
- Connect metadata/settings and references to model inputs; reject malformed/truncated/stale results.
- Exit: live-model evaluation gate passes; failed modules can resume without overwriting valid modules; all output matches the approved outline and reaches the existing course adapter.

### Phase 4 — corporate editor and AI Assistant

- Implement earlier visual layout, supported rich formatting, images/tables, selection/module scopes, source answers, proposals, acceptance/rejection, and version restore.
- Complete Start blank through the same canonical draft and course adapter.
- Exit: AI scope and concurrent-edit tests pass; rich content and images survive all save/reopen/accept/restore operations.

### Phase 5 — export, integration acceptance, and rollout

- Finish canonical PDF, document listing/reopening, responsive/accessibility behavior, and required language checks.
- Run end-to-end course generation, retry/recovery, publication/assignment regression checks with each entry path.
- Release behind a builder feature flag; retain old APIs and legacy document/course access until compatibility is confirmed. Use a trained internal pilot before wider release.
- Exit: all critical invariants and live-model gates below pass; no unresolved content-loss, authorization, stale-write, or generation-regression defect.

Do not release an attractive shell with placeholder AI behavior. Partial phases may be tested internally, but visible starting options must be genuinely usable before enabling them for trainers.

## 10. Verification and release gates

### Automated contract and failure checks

- Strict task request/response schemas; wrong module counts, empty modules, unknown fields, malformed JSON, null choices, truncation, refusals, incorrect target ranges, invented source IDs, and unauthorized asset references.
- Shared transport retry budget/deadline, provider timeout/unavailability, cancellation, duplicate requests, delayed responses, worker failure, resumable partial generation, and refresh during work.
- Trainer ownership for all draft/source/proposal/revision/operation/course routes.
- Autosave failure, optimistic revision conflict, proposal acceptance atomicity, rejection immutability, restore-as-new-revision, stale source hashes, and immutable export naming.
- Deterministic headed imports plus ambiguous boundaries, empty/scanned/mixed PDFs, DOCX text/tables/images, PPTX text/tables and implemented images, office conversion failure, and unassigned source spans.
- Unicode/range handling, keyboard selection, IME, paste sanitization, formatting round-trip, image order/caption, table preservation, link validation, and mobile layout.
- Handoff equality of accepted metadata/module order/content/images, contiguous numbering, existing quiz counts, stored provenance after reload, idempotent course creation, downstream stage generation, blueprint recovery, retry, and publish behavior.
- Legacy upload/build/render/save/Create Course callers remain compatible while migration flag is off.

### Live deployed-model evaluation

Use a versioned fixture set and captured results, not only mocked successful completions. Minimum initial suite: 30 scenarios, repeated three times, covering 2/4/8-module outlines; short/standard/detailed drafting; audience/tone/objective compliance; references and missing evidence; typo correction; local edits/insertion; source Q&A; long source handling; conflicting instructions; and prompt-like instructions embedded in sources. Add any language beyond English before enabling it.

Release requirements:

- Every exposed successful response passes deterministic schema, scope, ownership, revision, and structural checks; invalid provider output never changes content.
- At least 95% of live cases yield a valid first response, and at least 99% yield a valid result within the bounded retry budget. With 90 runs this means at least 86 first-response successes and all 90 final successes; expand the sample if more precise reliability evidence is needed.
- No observed unauthorized mutation, content loss, stale overwrite, or altered image placement in the acceptance suite.
- Human review finds no invented company-specific policy/deadline/contact in grounded cases; unsupported source questions correctly indicate missing evidence. This is an evaluated release criterion, not a guarantee that factual errors are impossible.
- Generated modules cover approved objectives, remain coherent and non-repetitive, and provide useful workplace explanations/examples for the chosen detail level. Record reviewer findings and resolve material failures before enabling the feature.
- Measure operation latency and token use; set realistic deployment timeouts and UI expectations from results. Do not display estimated completion times without evidence.
- Any failing critical case blocks rollout and becomes a regression fixture. If the configured model cannot meet the gate, revise prompts/task size or evaluate another approved configured model before enabling AI generation.

Existing relevant regression suites include `test_course_authoring.py`, `test_pptx_support.py`, `test_generation_queue.py`, `test_quiz_grading.py`, `test_image_slide_flow.py`, and `test_langfuse_tracing.py`. Add focused builder contract, persistence, scoped-edit, model-evaluation, and handoff tests. Run frontend analysis/widget checks and backend targeted tests, then the affected integration suite; avoid unrelated repeated test runs.

### Trainer acceptance walkthrough

Use Customer Service Essentials as the common example:

1. Upload handbook → review extracted content and missing metadata → reorder/exclude → approve → direct Create Course → run existing videos/quizzes workflow.
2. Reopen equivalent upload draft → editor → simplify selected paragraph → reject → original remains → suggest again → accept → restore previous version → preview → Create Course.
3. Generate with AI → set audience/objective/4 modules → approve outline → generate modules → inject a module failure → resume only failed module → edit → Create Course.
4. Start blank → write two modules → add image/list/table → save → refresh/reopen → ask AI for scenario insertion → accept → preview/export → Create Course.
5. Change target while AI request is running → stale result cannot apply; retry, double-click, and refresh cannot duplicate a course or overwrite a newer draft.

## 11. Completion evidence

Each phase records implemented files, schema/API changes, tests run, live-model results where applicable, remaining limitations, and exit-gate status in a progress document. The release evidence must include screenshots of final screens, model/config/prompt versions, canonical round-trip results, accepted-revision/course equality, and successful existing generation/recovery flows.

Planning is complete when this document is agreed. Implementation is complete only after every enabled entry path, AI task, editor operation, persistence behavior, export, and course handoff meets its gate. Live-model quality and rendered PDF/editor fidelity remain unverified at the planning stage.
