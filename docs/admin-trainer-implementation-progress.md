# LMS access implementation progress

Updated: 6 October 2026

## Confirmed scope change

Every active authenticated Trainer keeps all-course published performance visibility. Admin Trainer additionally receives read-only cross-owner course/content visibility. Both roles manage only their own courses. HOD and Observer use LMS Employees for scoped reports, with ordinary employee learning preserved. This supersedes earlier normal-Trainer own-course performance restrictions.

## Checkpoint 1: integration and shared Trainer reporting

Branch: `codex/admin-trainer-oversight`.

Checkout: `C:/Users/LPUSER/.codex/worktrees/admin-trainer-visibility/LMS_V1`.

- Reused the existing clean attached worktree and access branch; incorporated committed baseline `16adda0` before merging `feature/performance-tab` at `4e2fce9`.
- Snapshotted the Performance worktree's tracked patch and three untracked implementation/test files in the task-owned visualization directory, then applied them to the access worktree. The source worktree remains unchanged.
- Included employee summaries, scannable assignments, matching CSV exports and PostgreSQL employee grouping/pagination from the earlier Performance work.
- Added an explicit immutable Trainer reporting scope. The authenticated Trainer API requests all published-course performance; legacy internal string callers retain explicit owner-scoped behavior. Missing identities are rejected rather than interpreted as broad authority.
- Applied the same reporting scope to overview, lists, employee/course/assignment details, filter options, module metrics, and CSV exports. Published/active-rule/nonrevoked-assignment eligibility remains enforced.
- Revalidated sessions when loading subsequent export pages. Removed duplicate-title overview grouping by grouping courses using their stable course IDs.
- No authoring endpoint was broadened. Cross-owner content/assignment configuration still uses existing owner checks until Admin oversight is implemented.

## Validation

| Check | Result |
| --- | --- |
| Reporting, authorization, SMTP/email drafts and TTS focused tests | 136 passed |
| Read-only PostgreSQL parity checks on isolated demo | 15 passed |
| Final full backend suite, including opt-in PostgreSQL checks | 229 passed; one previously documented unchanged image-slide failure |
| Trainer frontend widget tests | 12 passed |
| Trainer Performance analyzer | Passed |
| Trainer and Employee frontend web release builds | Both passed |
| Ruff on affected reporting code and tests | Passed |
| SMTP notification/template/settings, TTS and deployment diff against `16adda0` | No changes |

The remaining full-suite failure is `tests/test_image_slide_flow.py::test_splits_third_landscape_image_to_separate_slide`: expects 3 slides, receives 4. Its source and test have no changes from the accepted baseline. It remains outside the access-feature change scope; the suite must not be described as entirely green.

Tests disabled outbound email delivery/scheduling and directory sync. PostgreSQL checks used the existing isolated demo instance on localhost port 55433 and read-only transactions. No production data, provisioning, migration, email transmission, or deployment occurred.

The existing Flutter 3.24 runtime resolves some packages differently from checked-in locks. Build-generated lockfile changes were restored; no dependency declarations or lock upgrades/downgrades are included. Ignored `.env` files point only at localhost. Repeat release checks using the final deployment toolchain and accepted dependency/SBOM commits.

## Remaining stages

1. Course-specific Observer grant storage, revision/apply/revoke behavior, and automatic capability discovery from active grants.
2. Scoped Employee report endpoints sharing the existing reporting engine; HOD/Observer union and revocation checks. Confirm the authoritative department-HOD contract before production HOD activation.
3. Existing product UI integration in both apps, role/scope cache isolation, Observer Include controls and admin read-only inspector.
4. Document/media access isolation, renderer/playback compatibility, final UAT, deployment and rollback evidence.

Checkpoint 1 is an integration foundation, not completion of the four-role feature. Application release, pushing, merging into the release branch, and deployment remain pending.


## Checkpoint 2: persistent Admin grants and capability discovery

Completed on the same isolated access branch. Added versioned additive access migration (advisory lock and ledger), stable-identity-bound Admin grants, audit/permission version in the same transaction, an operations-only CLI, and `GET /api/lms/me` with explicit app-audience authentication. Canonical identity linking uses directory UUID/employee ID without email fallback. Both the normal Trainer entitlement and all-course performance remain intact. Grants/version are read from one database snapshot; revoke affects an existing session on its next capability request. No automatic or name-based Admin promotion exists.

The Employee app receives learning capabilities only in this stage; stored Admin grants do not enable Trainer access through an Employee session. HOD/Observer reporting capabilities remain false until authoritative mappings/effective grants are implemented. The Admin library is not yet wired to resource APIs. Current login response shapes, Hub signatures/audiences and existing authoring/reporting endpoints are unchanged.

Checks: 152 focused access, Hub, reporting and SMTP/TTS tests passed. This includes ten PostgreSQL migration/grant/audit tests inside rolled-back isolated schemas: idempotence, preserved records, exact identity, active synced grant requirement, no-op versions, revoke, identity reuse protection, audit rollback and current-session grant/revoke. Last full backend run: 253 passed, the same unchanged image-slide failure; the final added Hub production-mode discovery test passed in the final focused run. Ruff passed. No frontend changes, so the checkpoint-1 frontend builds remain the last frontend verification. No production schema migration or Kiran grant was performed.

Operations runbook: `docs/admin-trainer-access-operations.md`. Next implementation stage: Admin cross-owner read-only course/assignment/generation visibility and creator-only mutation denial; normal Trainers retain report-only access to other creators’ metrics. Authoritative HOD source remains required before HOD activation.


## Checkpoint 3: Admin course oversight APIs and creator-only management

Implemented on `codex/admin-trainer-oversight` in the isolated attached checkout:

- `GET /api/trainer/course-library`: explicit `scope=own|all`, creator/status/generation-status/title filters; default own scope retained. Admin grants are checked from current canonical identity and persisted roles for every cross-owner/all-scope request. Normal Trainers cannot widen this authoring library. One PostgreSQL statement returns the full filtered total and a bounded metadata page (default 50, maximum 100). Ordering is deterministic by creation timestamp and course ID descending; version one uses validated offset pagination, not a frozen cursor snapshot. Concurrent insert/delete changes can shift later pages; refresh starts the library again.
- Existing course GET permits owner or current Admin, and adds creator display name, `can_manage`, and the server-derived read-only explanation. Assignment configuration GET and generation-job GET permit authorized Admin reads. Jobs are authorized against their actual course, including missing/deleted-course rejection. All successful privileged GETs disable caching.
- `GET /api/trainer/course-library/{course_id}/assignments` provides bounded assigned-learner reporting through the existing Performance engine with a server-fixed course and explicit owner scope. Published/active/nonrevoked eligibility is preserved; draft/disabled courses have no eligible report rows. Status counts/summary cards remain available through the existing course-filtered Performance APIs, rather than being counted from one inspector page.
- Editing, manual quiz edits, assignment saves/publication/disable, deletion, all generation stages, job creation and resume reject cross-owner Admin changes with HTTP 403 and the specified creator-only explanation before any mutation service call. Ordinary Trainers receive 404 for inaccessible content/resources. Original service/repository ownership checks remain in place, with the actual authenticated creator ID passed into mutations.
- Legacy own-course list and current Trainer all-course Performance behavior are preserved. Employee-app tokens cannot enter these Trainer authoring/oversight APIs even with a stored Admin grant. Revocation blocks the next cross-owner request in the same session. Inactive canonical Admin identities fail authentication.

Validation: 111 focused oversight/library/shared-reporting/PostgreSQL parity tests passed, including eight new rollback-only SQL tests for pagination, matching totals, duplicate titles/timestamps, literal search, injection strings, creator filters and minimal owner lookup. Final full backend suite: **306 passed, one unchanged image-slide failure**. Ruff passed. Existing learning/publishing helpers, SMTP/TTS generation internals, auth/Hub, Performance endpoints, frontend apps and deployment files have no changes from checkpoint 2. No production migration, grant, email or deployment occurred.

This is the backend oversight checkpoint. Existing deployed UI remains unchanged until its planned integration stage. Document/media URL isolation is still pending; resource authorization must not yet be represented as end-to-end file privacy. Next stage: revisioned course-specific Observer configuration and grants; HOD production activation stays gated on a verified authoritative directory mapping.


## Checkpoint 4: Observer/HOD reporting, product UI and private media

Completed locally on the existing isolated access branch. Production activation is not complete: the current directory feed has no verified department-HOD association, so the trusted adapter is tested but intentionally not wired to an inferred source. No production HOD/Admin grants or deployment occurred.

- Added normalized course-specific Observer grants, pending/active employee and department selectors, revisions, permission versions and durable transactional audit. Creator-only saves immediately restrict or revoke live scopes. Additions activate through explicit Apply Observers after successful Publish & Assign; disable suspends access, and re-publication requires another explicit Apply. Observer writes never enroll learners, change deadlines/progress, or schedule emails. Separate `is_active` and active selector fields prevent revoked configurations from resurfacing.
- Added stable department registry and verified-directory reconciliation adapter. Label-only records support Observer department selection but cannot authorize HOD. Partial updates preserve omitted HOD associations; explicit empty associations revoke; verified full snapshots reconcile removals. No designation/manager/own-department inference.
- Employee Performance endpoints reuse the existing reporting engine, including summary grouping, assignment pagination, details, options and both CSV exports. HOD department scope and Observer course selectors filter in SQL; Combined uses EXISTS/OR and counts each assignment once. Active identity, app audience, current grants and eligible published/active/nonrevoked assignments are checked on reads and each export page.
- Integrated the actual improved Performance UI in both applications. Normal Trainer authoring stays creator-only; every Trainer retains All Courses Performance and optional My Courses. Admin adds a bounded All Courses content inspector with creator attribution and read-only explanation; nested generation controls are disabled too. HOD/Observer enter through the Employee app, retain ordinary learning navigation, and receive Performance without authoring tabs. Capability refresh, identity/permission/membership cache keys, stale response checks and guarded open details clear obsolete reports.
- Added Observers under Assign -> Include, with employee/department selection, pending directory preview, active selector summary, duplicate/empty scope validation, revision conflict feedback, immediate restriction wording, Save and explicit Apply. Unsaved edits disable Apply. Fixed Assign header wrapping at the tested narrow desktop viewport; existing learner controls/logic remain intact.
- Authenticated document download/preview before conversion; protected generated audio/images/slides/video with short-lived signed media credentials and current resource checks. HLS playlists/relative segments and slide links retain credentials; byte ranges remain supported. Reporting grants alone never grant playback or source-document access. Brand/layout assets remain public. Course-outline generation verifies ownership of its source document.

### Final verification, 2026-10-06

- Backend: **335 passed, one pre-existing image-slide failure** (`test_splits_third_landscape_image_to_separate_slide`, expected 3, got 4). Unchanged source/test remains outside this access work.
- Ruff: all changed backend implementation/tests/fixture script passed. Frontend scoped analyzers passed; existing TrainingView web-only/style informational diagnostics and the existing assignment container informational diagnostic remain, with no analyzer errors. Both web release builds passed.
- Trainer widget suite: **14 passed**. Employee platform-independent playback/grading/scope tests: **8 passed**. The existing Employee main-app widget test imports web HLS/dart:html and cannot run on the native VM; a Linux Chrome test runner is unavailable. Actual browser role UAT supplements this limit; do not claim the complete Employee native suite passed.
- Actual local browser UAT: Admin sees three creators' library entries and cannot edit/generate another creator's course; normal Trainer sees only own two authoring courses and Performance totals 6 across creators / 3 under My Courses. Mapped Finance HOD sees 4 assignments for 2 employees despite own HR department. Legal Observer sees 1 Operations assignment on its granted course. Combined sees 5 assignments / 3 employees and switching contributions narrows totals. Include preserves a 3-learner preview; unsaved Observer removal disables Apply, Refresh restores persisted configuration. Normal Employee has its two assigned courses and no Performance entry; Admin browser playback reaches the end of the protected two-second synthetic clip.
- Real synthetic video HTTP UAT: owner, Admin and assigned learner receive 206 with valid 32-byte Range; report-only Observer receives 404. Automated tests cover HLS rewrite/range, current identity, expiry, revocation, asset lookup and document authorization before conversion.
- SMTP/TTS internals, configuration, notification implementation, dependencies/lockfiles and deployment files have no changes from checkpoint 3. Assignment disable adds only Observer suspension around existing logic. Hub middleware adds only a narrow viewer GET/HEAD delegation to independently authenticated file handlers. No outbound emails/directory sync/provider generation ran.

### Reviewable implementation choices / limits

Observer activation is deliberately explicit Save -> Publish & Assign -> Apply Observers, instead of altering the existing multi-transaction publishing/email path. This preserves that workflow and ensures pending expansions cannot leak on failed publication. There is no claim of a new atomic transaction spanning learner publishing and Observer application.

The shared backend is one report engine. The Employee UI reuses copies of the reviewed report components with its own authenticated provider adapter; the proposed separate Flutter package was not introduced, avoiding dependency/Docker/SBOM changes in this access patch. Future common UI fixes must be applied to both copies until a separate package extraction is approved.

Media credentials are resource-policy checked on every delivery but identity/app bound rather than one-file bound; they do not embed a reusable Hub bearer token. They expire in 15 minutes, capped by Hub session expiry. Same-user active Hub-cookie authentication can continue an expired credential for long playback. An already issued standalone credential is not invalidated solely by browser logout before its expiry; identity/role/assignment revocation does invalidate subsequent deliveries. A stable production Hub signing secret is required across backend workers. Old frontend deployments must be upgraded with the backend because generated media is now private.

### Local review demo

Trainer: http://127.0.0.1:8063 ; Employee: http://127.0.0.1:8064 ; task-owned backend: localhost:3063. All accounts are synthetic `uat-*`, contacts use example.invalid, delivery/scheduling and directory sync are disabled. Local development role pickers simulate tile access; production uses existing signed Hub audiences and disables these pickers.

Final demo schema: `access_uat_e48ffbf644e9457ebc70dadf43b86ba8` in localhost:55433 `lms_performance_demo`, storage `/tmp/lms-access-uat-7778`. `python -m scripts.create_access_uat_fixture --with-media` creates a NEW isolated schema, explicit three-learner rules and synthetic two-second clip/thumbnail without calling generation providers. It refuses other database names. Earlier task-owned schemas retained for inspection: `access_uat_7778c4895a6b4aee8df6a1200b548e50`, `access_uat_c54e4b20ab5f418a84e2b160b25c33c8`. Existing demo/public schema records were not reset. Cleanup must verify these exact schema names/database before dropping only task-owned fixtures.

Outstanding release steps: obtain verified stable department/HOD field contract and wire/test trusted directory adapter; review production schema/identity migration and coordinated backend/both-frontend release; run staging signed-Hub/media/rendering UAT with production toolchain; provision exact approved Admin identity; then approved rollout. Do not infer missing HOD data or deploy this gated capability blindly.
