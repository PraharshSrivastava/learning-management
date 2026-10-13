# Document Builder implementation progress

Date: 13 October 2026
Branch: `codex/document-builder-workflow`
Plan: [Combined implementation plan](document-builder-combined-implementation-plan.md)

## Current checkpoint

The three creation paths and their backend integrations are implemented for internal validation. The workflow remains disabled by default while the remaining release gates are completed. This checkpoint is not a production rollout.

| Phase | Current state | Outstanding acceptance |
|---|---|---|
| 0 — contracts/model/editor | Strict contracts and browser adapter verified; deployed model now responding | Broader semantic/source-injection and large-content evaluation; real keyboard/paste/undo stress checks |
| 1 — persistent drafts | Autosave/reopen/conflicts, revisions/restore, separate-copy recovery, owned immutable resources and durable jobs implemented | Multi-worker recovery/queue load and full refresh-during-generation acceptance |
| 2 — existing content/course adapter | PDF/DOCX/PPTX and pasted content import, extraction warnings, review/split/merge, direct and editor handoffs implemented | Complex document fidelity; AI boundary proposals for ambiguous documents; asynchronous source extraction |
| 3 — Generate with AI | Metadata/preferences → proposed outline → approval → incremental module drafting, cancellation and partial retry implemented | Human content-quality review and long/source-bound scenarios |
| 4 — editor/assistant | Corporate editor, text marks, images/list/table properties, selected/module/document proposals, scenario insertion and source answers implemented | Broader rich content/undo/mobile accessibility testing; collapsible assistant polish |
| 5 — export/integration/rollout | Canonical PDF and idempotent approved revision handoff into normal courses implemented | Full live videos/quizzes pipeline across all entry paths; legacy image-slide regression; internal pilot and rollout |

## Implemented behavior

- Entry order: **Use Existing Content**, **Generate with AI**, **Start blank**.
- Existing content is copied to immutable owned storage. Source spans and images remain associated with the draft; exports never overwrite originals.
- PDF text/images, DOCX paragraphs/tables/images, PPTX slide content and pasted notes are imported without creating a course as a side effect. Explicit module headings are retained as reviewed titles. Ambiguous content uses a manual-review module rather than speculative boundaries.
- Extraction limitations are shown and require acknowledgment before outline approval. Scanned PDFs report missing text; OCR is not provided by this release.
- Outline review allows titles/objectives, inclusion/order, split and merge. After approval, imported content can go directly to Create Course or through the editor.
- AI setup includes audience/objectives/difficulty, module count/detail, tone/focus, requested scenarios/comparisons/takeaways/mistakes, and optional source references.
- AI outline and assistant results remain proposals until accepted. Backend assigns trusted IDs, validates model output, rechecks revisions, and blocks stale/cancelled writes.
- Module drafting saves valid completed modules independently. Retry skips populated modules. Model requests have bounded timeouts/context and at most four physical calls per task.
- Assistant supports a selected range, current module, or explicitly confirmed whole-document scope. Larger revisions are split into ordered batches. A practical scenario is a separate insertion proposal. Source Q&A never edits the document.
- Revision acceptance is atomic and recoverable. Selection edits preserve outside text marks; rewritten interiors use plain text. Images and structured blocks remain intact during text revision.
- Autosave retains edits made during an in-flight save; conflicts preserve local content and offer reload or a separate copy with remapped owned references.
- Canonical PDF preview/export uses the same saved revision. English is the validated baseline language.
- Create Course validates details, included bodies, assets and approval, freezes a revision/hash, preserves reviewed titles/order/text/images, and retries idempotently. Existing downstream generation controls are retained. Accepted blueprint recovery avoids re-extraction.

## Verification evidence

| Check | Result |
|---|---|
| Backend contract/model/repository/source/jobs tests | 63 passed after added Unicode/copy checks |
| Generation handoff/recovery routing tests | 2 passed |
| Real PostgreSQL on isolated `big-coding` container | 4 passed; repeated additive schema initialization, competing revisions, acceptance/restore, direct handoff idempotency, cancellation |
| Frontend controller tests | 4 passed: in-flight save, conflicts, gateway errors, Unicode hash |
| Compiled Trainer UI in headless Chrome | All three creation paths passed: pasted source review/editor, AI outline approval/module drafting, blank content autosave |
| Standalone browser editor | Selection/emoji/outside formatting/images/stale proposal, IME autosave suppression and stable new-paragraph identities passed |
| Focused Flutter analysis | No issues found |
| Release Flutter web build | Passed |
| Focused backend Ruff checks | Passed |
| Canonical PDF visual review | Basic metadata/module sample rendered and inspected; no clipping or layout overlap |
| Live model, prompt-only output | 78 valid / 90; insufficient for release |
| Live model, structured JSON schema | **90 valid / 90, all first attempt**, configured alias `gemma-4-e4b` |
| Live module revision/scenario insertion | **2 valid / 2** synthetic probes |
| Existing generation baseline | 35 passed, 1 pre-existing image-slide failure |

The 90-case result establishes structured response compatibility and schema validity, not perfect factual quality. Spot review found inconsistent `insufficientEvidence` flags on some source answers. Evidence support, missing-fact behavior and content-quality review remain release gates. The current suite does not establish long-source coverage or complex import fidelity.

The existing unchanged failure is `test_image_slide_flow.py::test_splits_third_landscape_image_to_separate_slide` (expected 3 slides, received 4). It remains a separate downstream acceptance issue.

Model evaluation artifacts are in `docs/design/document-builder/`: `model-schema-evaluation-2026-10-13.json`, `model-assistant-scopes-2026-10-13.json`, and earlier prompt-mode comparison reports. All live probes used synthetic customer-service content; no trainer uploads were submitted.

The actual compiled editor screenshot is `docs/design/document-builder/implemented-editor-preview.png`.

## Configuration and rollout

```text
DOCUMENT_BUILDER_WORKFLOW_ENABLED=false
DOCUMENT_BUILDER_MODEL=
DOCUMENT_BUILDER_OUTPUT_MODE=json_schema
DOCUMENT_BUILDER_MODEL_TIMEOUT_SECONDS=90
DOCUMENT_BUILDER_OPERATION_DEADLINE_SECONDS=240
```

An empty builder model uses the configured shared model alias. The schema output mode was selected after live proxy capability verification. Other providers/tasks retain their existing behavior.

No production migration, deployment, publication or assignment was performed. Database acceptance used only a temporary PostgreSQL container with no volume and a dedicated database name. No live LMS data was changed.

## Remaining work

1. Finish grounded-answer semantic evaluation, ambiguous-source boundaries, source extraction jobs and richer editor round-trip/undo/paste acceptance.
2. Verify complex documents and multi-worker recovery, load, mobile/accessibility behavior.
3. Run a synthetic full course through videos/quizzes and recovery for each entry path; resolve the separate image-slide baseline expectation.
4. Enable an isolated internal pilot only after critical invariants pass, then perform the planned rollout.
