# Document Builder implementation progress

Date: 13 October 2026
Branch: `codex/document-builder-workflow`
Plan: [Combined implementation plan](document-builder-combined-implementation-plan.md)

## Current milestone

The initial contracts, strict model adapter, persistent draft backend foundation,
and an isolated browser editor spike are implemented. This is an implementation
milestone, not completion of the combined workflow. The new workflow remains
disabled by default; the existing Documents and course-generation screens remain
in use. The existing metadata missing-field reporting bug has been fixed.

| Phase | State | Remaining work |
|---|---|---|
| 0 — baseline/contracts/model/editor spikes | In progress | Live completion capability/quality evaluation; full paste/IME/grapheme/editor acceptance |
| 1 — persistent draft foundation | Backend foundation implemented and locally tested | Real PostgreSQL upgrade/locking acceptance, frontend autosave/reopen/conflict integration, immutable sources/assets and operation persistence |
| 2 — existing content/course adapter | Pending | Extraction review and accepted-revision handoff |
| 3 — Generate with AI | Model adapter implemented; orchestration pending | Owned background jobs, approved outline/module orchestration, deployed-model release evaluation |
| 4 — corporate editor/AI Assistant | Selection adapter spike implemented | Final product screens, formatting/structure editor, proposal storage/acceptance, Start blank integration |
| 5 — export/integration/rollout | Pending | Canonical PDF and all-path course-generation acceptance |

## Implemented

- Created the branch from the existing checkout and preserved unrelated workspace changes.
- Added strict canonical schema contracts for course details, settings, ordered modules,
  text/list/table/image blocks, text marks, source references, draft revisions, and selections.
- Stable module/block identities and source references are separate from model-generated content.
- Structural approval fingerprints invalidate on metadata/settings/outline changes, while body
  edits retain structural approval. Course-content acceptance will be a separate handoff check.
- Added separate outline, module, selected-edit, and source-question prompts, without
  chain-of-thought fields or full-document replacement semantics.
- Added a workflow model adapter that receives metadata/settings, checks context budgets,
  validates schemas and source references, rejects truncated/empty/wrong-count responses,
  and supports cancellation and a bounded operation deadline.
- A maximum of four physical model requests per task, with no nested legacy transport retries.
  Tests include the existing provider's `PipelineStageError` wrapping.
- Builder model override is optional and does not modify other generation models.
  Structured-output mode is configured; it is not presumed supported by the deployed alias.
- Added trainer-scoped PostgreSQL draft/revision tables through additive schema initialization,
  and feature-gated create/list/read/save/approve/revision/restore routes.
- Saves use `SELECT ... FOR UPDATE`, expected revisions, atomic snapshots and approval updates.
  Restore creates a new head revision; cross-trainer reads/writes return not found.
- The early manual-draft endpoints reject image/source claims and generation statuses until
  owned source/asset/job infrastructure is implemented. Do not enable the feature yet.
- Added an isolated editor adapter and browser harness proving a single-block selection edit
  can preserve neighboring content, stable IDs, image order/caption, and outside formatting.
  Fixed range extraction to read cloned DOM fragment text rather than Dart `Range.toString()`.
- Fixed existing frontend metadata validation so identical empty values report every missing field.

## Verification evidence

| Check | Result |
|---|---|
| New backend contract/model/repository/API tests | **53 passed** |
| Metadata regression tests using matching workspace Flutter SDK | **2 passed** |
| Standalone headless Chrome editor spike | **Passed**: DOM selection, Unicode offsets, scoped replacement, outside marks, images, neighboring text, stale rejection |
| Focused Flutter analysis of new adapter/models/tests | **No issues found** |
| Focused backend Ruff lint | **Passed** |
| Git whitespace check | **Passed** |
| Existing generation regression baseline | **35 passed, 1 failed** |
| Deployed model catalog | HTTP **200**; configured `gemma-4-e4b` alias listed |
| Minimal synthetic deployed chat completion | HTTP **404**; no usable completion |
| Workflow synthetic smoke suite | **0 valid / 1 attempted / 4 expected**, stopped on provider failure |
| Real PostgreSQL upgrade/concurrency | **Not run**: Docker daemon unavailable locally |

The existing regression failure is
`test_image_slide_flow.py::test_splits_third_landscape_image_to_separate_slide`
(expected 3 slides, received 4). Neither the image-slide implementation nor this test
was changed by this milestone. Keep it separate from new builder tests and resolve
its expected behavior before final course-generation acceptance.

Repository behavior tests use an explicitly documented SQLite SQL adapter in tests
only. Production remains PostgreSQL. These tests establish save/restore/ownership
behavior; they do not establish PostgreSQL locking or migration correctness.

The standard Flutter Chrome test runner stalled in this environment. The isolated
Dart adapter was compiled directly to JavaScript and tested in headless Chrome using
Playwright instead. Full Flutter editor integration/browser checks remain pending.

The initially selected older Flutter SDK was incompatible with the workspace's
existing package configuration. Subsequent checks used `tmp/captions/flutter`, which
matches that configuration; no dependency files were changed for this milestone.

## Model gate and configuration

Synthetic checks use only Customer Service Essentials fixture prompts. They do not
read or send trainer uploads. The evaluation runner supports a deployment env file
and only consumes model-related settings, including the existing `LITELLM_API_KEY`
alias. It does not print credentials or raw provider failures.

The catalog result does not establish the actual upstream model version or a
functioning completion route. Resolve the HTTP 404 and verify the proxy/upstream
deployment before claiming AI generation works. Do not change the shared model or
enable the new workflow to bypass this gate.

Smoke results are in
`docs/design/document-builder/model-smoke-2026-10-13.json`.
The runner has 30 synthetic scenarios and a three-repeat release mode; human content
review, additional edge-case fixtures, and deployment capability checks are still
required by the plan. The current fixture set is a foundation, not the complete
release evidence (long-source/prompt-injection/language cases need expansion).

New optional settings:

```text
DOCUMENT_BUILDER_WORKFLOW_ENABLED=false
DOCUMENT_BUILDER_MODEL=
DOCUMENT_BUILDER_OUTPUT_MODE=prompt
DOCUMENT_BUILDER_MODEL_TIMEOUT_SECONDS=90
DOCUMENT_BUILDER_OPERATION_DEADLINE_SECONDS=240
```

No live database migrations, new course generation, publication, or deployment were
performed. The new model adapter has not replaced the legacy builder calls.

## Next implementation work

1. Finish editor normalization/paste/IME/grapheme acceptance and implement full Dart draft contracts.
2. Finish Phase 1 frontend draft API integration with acknowledged autosave/reopen/conflicts.
3. Add immutable owned sources/assets and durable builder-operation tracking.
4. Implement reviewed extraction and the approved-revision course adapter, preserving existing generation behavior.
5. Complete AI orchestration and final screens; keep model release gated until deployment checks pass.
