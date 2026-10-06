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

1. Persistent role storage, audit/provisioning, capability discovery; confirm the authoritative department-HOD contract before production HOD activation.
2. Admin cross-owner read-only library/details and explicit creator-only denial, with all-course reporting retained for normal Trainers.
3. Course-specific Observer grant storage, revision/apply/revoke behavior, and automatic capability discovery from active grants.
4. Scoped Employee report endpoints sharing the existing reporting engine; HOD/Observer union and revocation checks.
5. Existing product UI integration in both apps, role/scope cache isolation, Observer Include controls and admin read-only inspector.
6. Document/media access isolation, renderer/playback compatibility, final UAT, deployment and rollback evidence.

Checkpoint 1 is an integration foundation, not completion of the four-role feature. Application release, pushing, merging into the release branch, and deployment remain pending.


## Checkpoint 2: persistent Admin grants and capability discovery

Completed on the same isolated access branch. Added versioned additive access migration (advisory lock and ledger), stable-identity-bound Admin grants, audit/permission version in the same transaction, an operations-only CLI, and `GET /api/lms/me` with explicit app-audience authentication. Canonical identity linking uses directory UUID/employee ID without email fallback. Both the normal Trainer entitlement and all-course performance remain intact. Grants/version are read from one database snapshot; revoke affects an existing session on its next capability request. No automatic or name-based Admin promotion exists.

The Employee app receives learning capabilities only in this stage; stored Admin grants do not enable Trainer access through an Employee session. HOD/Observer reporting capabilities remain false until authoritative mappings/effective grants are implemented. The Admin library is not yet wired to resource APIs. Current login response shapes, Hub signatures/audiences and existing authoring/reporting endpoints are unchanged.

Checks: 152 focused access, Hub, reporting and SMTP/TTS tests passed. This includes ten PostgreSQL migration/grant/audit tests inside rolled-back isolated schemas: idempotence, preserved records, exact identity, active synced grant requirement, no-op versions, revoke, identity reuse protection, audit rollback and current-session grant/revoke. Last full backend run: 253 passed, the same unchanged image-slide failure; the final added Hub production-mode discovery test passed in the final focused run. Ruff passed. No frontend changes, so the checkpoint-1 frontend builds remain the last frontend verification. No production schema migration or Kiran grant was performed.

Operations runbook: `docs/admin-trainer-access-operations.md`. Next implementation stage: Admin cross-owner read-only course/assignment/generation visibility and creator-only mutation denial; normal Trainers retain report-only access to other creators’ metrics. Authoritative HOD source remains required before HOD activation.
