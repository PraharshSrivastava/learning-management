# Simplified Documents tab and Document Builder — implementation plan

Date: 14 October 2026
Branch: `codex/document-builder-workflow`
Status: Implemented in the Flutter application and supporting API for coding-VM acceptance. Actual compiled browser journeys and local regression checks passed; deployment of this revision is still required.

This plan supersedes the product layout and setup flows in the earlier combined plan. Its canonical-content, ownership, autosave, immutable-source, structured-model-response and downstream course protections remain applicable. The earlier baseline describes the pre-workflow code; use the current implementation progress report for completed work.

## 1. Approved product outcome

Documents opens directly to three areas:

1. **Create a training document:** Use existing content, Generate with AI, Start blank, in that order.
2. **Continue your drafts:** owned persistent drafts, with title, meaningful status, last edited time and Open draft. Empty state instead of a fictional draft.
3. **Your documents:** uploaded/completed files with preview and Create course from this document. Opening a file does not create a draft or a course.

Remove the separate Upload Document and Open Document Builder cards from the enabled experience. No Document Builder breadcrumb on the landing page. Retain Documents navigation on inner screens. Setup, outline and editor remain within the Documents tab; course handoff selects the existing course/blueprint destination used by the application. Do not accidentally change the current tab index based on its display label.

Keep the navy brand accent, quiet neutral surfaces, readable document canvas, one editable module heading, short navigation labels derived from full titles, compact formatting toolbar and optional AI panel. Shortening navigation must never change canonical titles. Show full titles accessibly when truncated.

## 2. Verified code dependencies

| Location | Current implementation | Planned change |
|---|---|---|
| `frontend/lib/features/dashboard_page.dart` | Documents switches between upload/list/preview and `DocumentBuilderEntry` using a visibility boolean | Capability-aware Documents landing and typed workflow entry/navigation; preserve legacy fallback |
| `frontend/lib/features/documents/document_portal.dart` | UploadCard, CreateDocumentCard, DocumentListCard, PDFViewerCard | Reuse upload/list/preview services; replace duplicated cards only in enabled layout; source-specific shortcut |
| `frontend/lib/features/document_builder/document_workflow_portal.dart` | Home/setup/source/outline/editor; all metadata fields; fixed assistant and text-only step label | Simplified screens, one outline review, on-demand assistant and accurate navigation labels |
| `frontend/lib/state/trainer/document_workflow_controller.dart` | Owned drafts, autosave, operations, accept/reject, approve and restore | Typed entry intent, validation/readiness state, operation-specific errors, combined user action orchestration |
| `backend/app/schemas/document_workflow.py` | All metadata required by `missing_fields`; writing settings default to four modules and all content options enabled | Stage-specific validation and explicit creation defaults; maintain existing draft compatibility |
| `backend/app/repositories/document_drafts.py` | Approval checks all metadata; outline fingerprint includes metadata/settings | Relax only approval requirements; preserve current fingerprint initially; explicit confirmation on invalidation |
| `backend/app/document_builder/workflow_jobs.py` | Three fields required for outline, exact configured module count, approved outline required for initial drafting | Retain bounded jobs and incremental drafting; submit the selected integer count, with four as the default |
| `backend/app/document_builder/workflow_export.py` | Complete metadata/body validation; revision-bound course handoff and PDF | Preserve final validation and idempotency; expose actionable missing-field state |

Do not replace the durable draft model with the demo's browser state. Localhost prototype uses illustrative content and simulated AI; it is a design reference, not a model integration test.

## 3. Required flows

### Existing content

Default ready-document flow: Use existing content → upload/select an owned document → existing course outline extraction → Blueprint → Generate Course for videos/quizzes. No builder draft, metadata form or builder approval is required. Optional Edit first and pasted notes use the reviewed builder flow below.

- Support the actual accepted upload formats: PDF, DOCX and PPTX, up to the current 20 MB limit. TXT support in a prototype does not authorize claiming TXT upload support in production; paste is the existing text path.
- The default library Create course from document action submits the stored filename to the existing ownership-checked course-generation endpoint. A separate Edit first action creates an owned editable draft and imports the document ID. Neither route requires a second upload.
- Preserve original source and imported wording. No writing settings or automatic rewriting in this flow.
- Show conversion warnings when present. Missing readable content blocks approval; actionable completeness warnings require acknowledgement against the original.
- Source review offers original preview/download and locations. Imported images/tables retain supported blocks and report unsupported conversion.
- Title/learning goals may be suggested; audience and unsupported company facts must not be invented. Distinguish source-derived values, suggested values and trainer-confirmed values.
- Editing metadata can happen in the review section; missing final course details are visible before handoff, not hidden in a collapsed section.

### Generate with AI

Three visible fields: **Topic or title**, **Who is this for?**, **What should employees be able to do?**

Optional Customize generation: **Default — 4 modules** or an explicit module count, concise/standard/detailed length, illustrative scenarios, optional reference documents. Advanced legacy writing preferences remain supported in stored drafts but are not all shown initially.

- Default tone is professional, focus practical, key takeaways enabled. For new drafts, comparisons/common mistakes are not separately forced into every module. Existing saved choices are retained.
- Display **Default — 4 modules** for the four-module option. This is the application default, not an AI recommendation. It maps directly to integer `moduleCount: 4` in the existing strict 2–8 module schema; no new sentinel value is sent to the model. Other choices display their count, such as **3 modules**. Retain saved counts on reopen and allow outline adjustment before approval. A future adaptive count is separate evaluated work.
- Generate outline → one editable review → **Approve & generate document** → editor.
- The single user action saves edited proposed titles/objectives/sections, accepts the validated proposal, explicitly records approval, then starts drafting. Backend operations remain separate and revision-checked. Failure between operations resumes at the saved state; it must not regenerate an accepted outline or overwrite populated modules.
- Current proposed-outline accept uses the model result; implement an explicit validated edited-proposal payload/accept contract or equivalent atomic acceptance mechanism so browser edits are not silently discarded. Verify source references, count, unique IDs and ownership. The application assigns identities.
- Show real per-module progress. Cancellation keeps valid completed modules; retry writes only empty/failed modules.

### Start blank

Title → editor immediately. Audience, goals, level and description do not block manual writing or draft saving.

- Add audience/goals before AI drafting when needed, or before final course creation.
- New empty-module drafting is a scoped proposal with review, not an automatic approval of the entire document.
- Before handoff, review and explicitly confirm included structure in a compact preflight. No duplicate setup/outline journey merely to complete course details.

## 4. Validation, approval and defaults

Replace broad all-fields approval checks with explicit stage rules:

| Stage | Required information |
|---|---|
| Save/open a draft | Valid canonical structure and ownership; incomplete metadata/content permitted |
| AI outline | Title/topic, audience, learning goals; resolved generation settings |
| Initial AI module drafting | Approved current outline and sufficient audience/goals/settings |
| Imported outline approval | Title, at least one included module, valid source mapping, extraction acknowledgements |
| Blank outline approval | Title and at least one included module; permits empty content while editing |
| Scoped edit | Valid selection/module target and instruction; preserve existing fact/scope checks |
| Course creation/final export | Complete course metadata, current explicit approval, nonempty included bodies, valid assets and sources, saved revision |

Use Beginner, English and Training guide as application defaults. A description can be suggested from confirmed learning goals and shown in course details for review; do not fabricate goals/audience merely to satisfy validators. Display a field-specific readiness checklist and expand/focus missing fields automatically.

Keep current fingerprint invalidation rules initially to avoid an unnoticed migration of existing approvals. If metadata/settings change after approval, show the changed information and request explicit reconfirmation. Remove `createCourse()`'s unconditional call to `controller.approve()`. Handoff verifies existing approval; it never silently supplies approval. Body-only edits still flush and capture the exact reviewed handoff revision.

No automatic replacement of imported/written content. AI outline, revision and insertion results remain proposals. Generation uses configured defaults even when advanced controls are hidden.

## 5. Editor and assistant behaviour

- Header: title, honest Saved/Saving/Save failed status, Preview, Create course, More.
- More: Training details, Edit outline, Version history, export where supported. Course details must open details, not outline.
- Left: module navigation and Add module. Rename uses stable module identity; reorder/split/merge preserve blocks, sources, images, selection invalidation and inclusion.
- Centre: one editable module heading; optional learning goal; document body. Enter creates a paragraph naturally. Toolbar: bold, italic, heading and Insert menu (list/table/image).
- Rich list/table editing must be represented honestly: the current adapter uses a properties dialog. Preserve it until real inline editing is implemented and verified. Do not make mock toolbar actions imply unsupported production behaviour.
- Assistant is collapsed by default, visibly available. It reflows on smaller screens. Module is the default target; a real editor selection enables selected-text targeting and displays a selection preview. Do not guess scope from the prompt.
- Improve content and Ask about source are separate modes; source mode is available only with an owned source. Each has a task-specific prompt and independent field.
- Simplify provides a defined instruction. Add scenario always inserts into the current module. Draft this module appears only when empty and never overwrites populated content.
- Whole-document scope is advanced, explicitly confirmed, and produces per-module review with accept/reject protection. Preserve the existing batch limits and image/structured-block integrity.
- Source answers show clickable source locations and insufficient-evidence states; they never edit the document.
- Accept/reject is revision-checked; changed text invalidates pending proposals. Acceptance creates a recovery point. Preview/export reflects canonical saved content and inclusion, not demo summary text.

## 6. Implementation sequence and completion gates

### Step 1 — state and contracts

Define typed Documents entry intents (new mode, owned source ID, reopen draft ID) and return destinations. Add stage-specific validators and readiness responses. Specify edited-outline proposal acceptance and scoped empty-module drafting. Keep source/job/approval ownership rules. Add meaningful contract tests before connecting new buttons.

Gate: incomplete blank/import drafts remain saveable; AI still requires three essentials; handoff still requires complete metadata/content and current approval. Old drafts and feature-disabled clients remain compatible.

### Step 2 — Documents landing integration

Build the direct three-choice landing, persistent drafts and document library. Reuse existing preview/list services. Wire owned source shortcuts. Retain a small Upload only option inside existing-content entry so storing a file does not force course creation. Existing library upload/deletion/download/preview behaviour remains available.

Gate: all three options start the correct mode; a library shortcut selects the intended source once; back/refresh/reopen preserve identity and state; empty/error/loading states are truthful. Capability-off renders the legacy view without exposing new unsupported routes.

### Step 3 — simplified setup and one review

Implement three-field AI setup, title-only blank setup, import-focused source screen and optional controls. Normalize defaults in new drafts without changing old drafts. Editable outline review has inline title/order/inclusion and optional goals; split/merge under row actions. One explicit approval action advances the appropriate flow.

Gate: title/objective edits to proposed AI outline survive acceptance; reordering never loses content; approval is invalidated on relevant changes. AI approval/drafting partial failure resumes correctly. Imports can hand off directly without editor.

### Step 4 — focused editor and contextual assistant

Apply corporate styling, single heading, toolbar/Insert menu, accurate More actions, collapsible assistant and separate source mode. Retain autosave, IME handling, revision conflict recovery, selection hashes and version restore. Use actionable Retry upload/Retry generation/Retry save messages rather than a generic save action.

Gate: editing/selection/formatting/paste/undo/rich blocks/IME round-trip correctly; acceptance affects only authorized targets; dismiss leaves content unchanged. Keyboard/touch/mobile controls work and no document text is clipped.

### Step 5 — preflight and existing course handoff

Show readiness and missing details; enable creation only when valid. No output selector, second invented Generate course action, auto-approval, or alternate video/quiz pipeline. Freeze the reviewed source revision and navigate to the existing course workflow, where normal generation remains available.

Gate: repeat click/retry does not duplicate a course; unsaved/stale/unapproved states cannot hand off; included title/order/body/assets survive; existing videos/quizzes/slides/scripts/audio/recovery remain functional.

### Step 6 — pilot verification and rollout

Run focused backend/controller/editor checks and browser journeys, then the release web build and targeted analysis. Verify real PostgreSQL and live deployed-model responses in the isolated pilot. Reuse the current big-coding pilot rather than creating another pilot/database. Rebuild only the pilot with the reviewed commit and refresh its frontend; preserve production configuration and credentials. Rollout remains gated by the existing full-pipeline acceptance issues.

Gate: both new Documents navigation and all three creation flows pass live integration; no regressions in unchanged course tabs; rollback to capability-off retains uploads, drafts and courses.

## 7. Model verification requirements

Reuse the deployed builder endpoint and verified structured JSON mode. Do not switch model/provider as part of visual simplification. Record actual deployment alias/configuration at test time rather than assuming the earlier alias is still running.

Test topic/audience/goal adherence, distinct outline coverage, every length/scenario option, English defaults, source-grounding, missing evidence, source-injection resistance, selected/module/document scope, schema errors, provider timeout, cancellation, stale revisions and partial retry. Visible controls must map to validated request settings; unsupported output must not mutate content.

Company policies/deadlines/contacts/numbers require supplied evidence. Illustrative scenarios are labeled. No chain-of-thought is displayed. Previous schema-pass counts prove format compatibility, not factual correctness. Human review of synthetic and authorized representative examples remains required.

## 8. Review checklist

- [ ] Documents directly contains three creation choices, drafts and library.
- [ ] No duplicate Upload/Create cards or landing breadcrumb.
- [ ] Existing file shortcut avoids upload/setup repetition and preserves the original.
- [ ] Blank starts with a title only; AI starts with three essentials.
- [ ] Optional controls affect generation; stored legacy preferences are preserved.
- [ ] One editable AI outline review and one explicit approval action.
- [ ] Outline changes/content reorder cannot silently lose content or retain stale approval.
- [ ] Editor has a single heading and optional assistant with truthful target scope.
- [ ] AI results remain proposals; source answers link to evidence.
- [ ] Missing metadata/errors/retries are specific and actionable.
- [ ] Course creation uses the existing handoff and normal generation workflow.
- [ ] Preview, drafts, restore, refresh and conflict recovery are verified.
- [ ] Real model/full video-quiz pipeline and responsive accessibility gates pass.

## 9. Local review demo

Local demo: `http://127.0.0.1:18764/` (also `http://localhost:18764/`).

Export: `docs/design/document-builder/simplified-local-demo/index.html`.
Source: thread visualization `documents-tab-simplified.html`.

This demo opens on Documents directly, including draft continuation, a sample library item, source preview and source-specific outline shortcut. It simulates AI/course outputs locally and does not connect to the existing pilot backend or replace `localhost:16969`. The separate demo remains a design reference. The actual application implementation below has now passed compiled browser acceptance; a local demo alone is not evidence of deployment.

Local review verification, 14 October 2026: Chrome loaded the HTTP demo and passed all three entry journeys, library preview/direct outline shortcut, explicit approval, AI accept/dismiss, current-content preview, content-preserving reorder, example course handoff and quiz review. No JavaScript runtime errors were reported. Layout checks at 1024, 736, 390 and 320 pixels had no horizontal overflow. These checks validate the prototype only, not live RunPod responses or real video/quiz generation.

Implementation checkpoint: the module selector wording is now implemented in the workflow Flutter screen on `codex/document-builder-workflow`: four displays **Default — 4 modules**, and the submitted setting remains integer four. The localhost prototype uses the same wording. Steps 1–6 above remain the broader simplified-workspace implementation scope; this label change does not mark those steps complete.

## Combined integration checkpoint — 14 October 2026

The isolated integration checkout merges origin/main at 1e76ba1 into the Document Builder history. Both 7402617 (Trainer Performance/Observer selection) and 5b9e67e (Observer parity and availability filters) are verified ancestors; relevant Performance/report access files match current main. Merge resolutions retain both draft tables and access/lifecycle migration initialization, and both caption bootstrap and mount-scoped service-worker cleanup. Pilot prepare accepts the maintained Flutter 3.44 Dockerfile as well as the original 3.24 patch path.

Combined focused verification: 95 backend tests, 17 Trainer tests, 9 Employee/Observer tests passed; both JavaScript release web builds passed. Live VM database/model/full generation acceptance is still required. The shared VM routes are http://35.238.33.238:8006/lms/trainer/ and /lms/employee/, with existing intelligence_layer Compose project, path-routing/edge-network overlays and /opt/lms/storage. Do not confuse these with the standalone local design demo or isolated loopback pilot. The complete simplified Documents layout remains planned; this integration includes the implemented builder and default-label change.

## Simplified application checkpoint — 14 October 2026

The approved workspace is now implemented in Flutter and the API, not only in the HTML demo. Enabled Documents opens directly to the three choices, drafts and library, with the original feature-disabled layout preserved. AI setup has three essentials and optional generation settings; blank setup has one title field. The old navy toolbar and text stepper are removed. The editor uses one module heading, compact Insert/More controls and a collapsed assistant. Source questions use an independent input and source locations open readable evidence excerpts.

Edited AI titles, goals, inclusion and ordering are validated and accepted through an optional typed edited-outline payload; the single approval action then approves and drafts. Pending proposal edits commit at approval. Imported/manual structure approval permits incomplete final metadata, while handoff still checks complete metadata, included bodies, assets and current approval. Handoff never approves silently. Course details completion expands when needed, and description is suggested from confirmed learning goals while preserving a manually edited description. A title-only draft can be previewed. New AI module drafting is a scoped proposal for an empty module and cannot overwrite populated content.

Verification: 111 focused backend/repository/model/reporting tests; 17 Trainer controller/editor/Performance tests; 9 Employee/Observer tests passed. Changed builder Dart analysis and backend Ruff checks passed. Both JavaScript release web builds passed. The compiled Trainer browser check covers the direct landing, existing-library shortcut, pasted import, explicit preflight approval, optional editor, three-field AI setup, edited outline acceptance, title-only blank draft and autosave. Responsive landing checks at 1024/736/390 pixels and feature-disabled legacy fallback passed. Screenshots under docs/design/document-builder/implemented-simplified-*.png show the actual compiled application. Browser AI/course responses use synthetic fixtures; real deployed-model and video/quiz checks remain VM acceptance, not claimed completed by these UI checks.

Performance and Observer ancestry includes 7402617 and 5b9e67e. No new Performance/Observer application files or model/provider/deployment secrets are changed by this UI implementation. Original shared-checkout uncommitted work was preserved.
## Ready-made document route correction — 14 October 2026

Ready-made documents now use the existing CourseGenerationNotifier and /api/courses/generate endpoint directly. Library Create course from document and Upload & open Blueprint route to the normal Blueprint tab and its extraction progress. Merely choosing Use existing content does not create an empty builder draft. No builder metadata/approval is requested in this path. The existing ownership check and later Generate Course video/quiz controls are unchanged; opening Blueprint does not automatically render videos. Edit first, Upload to edit first, and pasted notes retain the optional editable-copy/review workflow. AI and blank creation remain unchanged.

The compiled browser suite tests both ready library selection and a real file-picker upload with synthetic API responses; it asserts the stored filename is sent to the original endpoint and that no builder draft/import operation is created. Optional editor, pasted-source, AI outline, blank autosave, responsive and feature-disabled fallback checks remain included. This updates the previously approved mandatory import/review default in response to the trainer's ready-made-course requirement.
