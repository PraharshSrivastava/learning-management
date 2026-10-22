# React workflow parity fixes

Date: 22 October 2026

Branch: `codex/react-workflow-parity-fixes`, based on GitHub main `7f16ddd`.

Status: Implemented and locally verified. Not pushed, merged or deployed.

## Scope and sequence

This work addresses the confirmed 16 October audit findings while keeping the
approved simplified React workspace. Caption authorization, generation and backfill
are explicitly deferred. Deployment is a later step after review and verification.
The original local checkout contains unrelated uncommitted work and is preserved.

1. Add regression coverage for destructive text formatting, autosave persistence,
   stable quiz module identity and late grading responses.
2. Preserve inline formatting during text edits; restore focused formatting, list,
   block movement, image sizing/alignment and outline organization controls.
3. Restore debounced autosave with revision/concurrency safeguards, history and
   restore, reference attachment, and source questions/citations. Keep AI suggestions
   separate from accepted content and preserve source acknowledgement requirements.
4. Restore new-module AI drafting and the choice of direct course creation or editor
   review after approving imported content. Ready uploads open Blueprint directly;
   upload failure/cancellation must never start course creation.
5. Bind quiz state/results to course and module identity across live updates; restore
   completed-course review and scrolling to a watched module's unfinished quiz.
6. Run focused tests, the React regression suite, TypeScript, lint, production builds,
   and browser checks with synthetic data. Review the integrated diff for regressions
   and verify the caption and unrelated Performance/Observer paths are untouched.

## Verification log

- Ready-upload regression reproduced the missing automatic handoff before the fix.
- Ready upload and existing upload/list tests: 22 passing after the fix. These cover
  server-assigned filenames, no duplicate Builder path, cancellation, upload errors
  and malformed upload responses.
- Full React regression suite: **435 tests passing across 60 files** (398 on the
  previous main release). New coverage includes module reorder/removal, stale
  grading/video-save responses, inactive-module republishing, first-save URL echo,
  failed initial draft loading, concurrent edits, revision restore, reference-only
  source attachment, cited source answers and direct approved-document handoff.
- Existing backend contract/API/assistant-scope/simplified-workflow suites:
  **40 tests passing**. No backend code or schema changed.
- Workspace TypeScript and ESLint passed. Both React production builds passed.
  Scoped Prettier checks passed with the existing platform line endings preserved.
- Chrome checks against the compiled local apps passed formatting-preserving
  autosave, history access, empty-module drafting, live module reorder and the
  completed-course review landing. Synthetic APIs and WebSockets were used.
- The existing compiled desktop/mobile AI workflow acceptance passed: ready-file
  Blueprint handoff, queued outline proposal, explicit acceptance/approval, body
  drafting, table persistence, scoped assistant review/acceptance and draft reload.
- Independent cross-review found and corrected background module completion leakage,
  first-autosave URL reload data loss, failed-load accidental draft creation,
  source-only provenance loss during splitting and link-scheme incompatibility.

## Implemented behavior

- Text editing retains codepoint-based bold/italic/link ranges and source references.
  Formatting controls apply to a selected range; a formatted preview is available
  for marked text. This uses a text editor with preview, rather than a full
  contenteditable word processor. Link inputs remain collapsed until needed.
- Bullet/numbered lists, block movement, saved image width/alignment, module goals,
  module ordering/split/merge and new empty-module AI drafting are available.
- Autosave debounces edits for one second and serializes expected-revision writes.
  Failed saves retain local edits and show an explicit retry. History restore first
  saves current edits, uses the returned revision, and reopens the appropriate stage.
- Sources and history are secondary controls. Trainers can upload/select references,
  attach notes, inspect original sources/excerpts and ask cited source questions.
  Source answers do not replace document content or expose an Accept changes action.
- Ready uploads open Blueprint automatically. Imported ready documents offer
  approval plus direct course creation alongside editor review; AI body drafting is
  not required for that direct handoff.
- Employee state follows stable module numbers and the current question/video
  content. Replaced/removed modules lose stale local progress, and late results
  cannot apply to another quiz. Completed courses offer explicit review from the
  first module; watched modules with unfinished quizzes scroll to the quiz on entry.

## Validation limits

- The PDF source-import test could not be collected locally because Windows
  Application Control blocked the installed PyMuPDF native DLL. No attempt was made
  to bypass that policy. The other 40 selected backend checks passed separately.
- No new real RunPod/model, TTS, PDF extraction, full video-generation or isolated
  PostgreSQL acceptance run was performed. Those integrations are unchanged.
- An already-submitted server progress request cannot be undone by client guards.
  The UI suppresses stale results/optimistic patches and refetches authoritative data.
- Production builds retain the existing large-chunk advisory; it is not a build
  failure. Broader bundle optimization is outside this fix scope.

## Release boundary

No live employee data, model requests, deployment settings or running containers are
modified by this implementation's tests. A passing local suite does not establish
live model availability or replace a post-deployment acceptance check.
