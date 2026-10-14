# LMS access foundation operations

Updated: 6 October 2026. Branch: `codex/admin-trainer-oversight`.

This checkpoint stores Admin Trainer grants and exposes capability metadata. The Admin cross-owner library and HOD/Observer reporting have not been implemented yet. Granting Admin now does not bypass existing owner-only course APIs. No production identities were provisioned during implementation.

## Migration

Normal backend `init_db()` applies additive migration `20261006_authoring_access_v1` within its existing schema transaction, protected by a PostgreSQL advisory lock and recorded in `lms_schema_migrations`. Fresh initialization and the upgrade path use the same runner. It creates `lms_authoring_roles`, `lms_access_versions`, and `lms_access_audit`; it does not backfill, reset or change existing course/assignment/progress/outbox records. Do not use `recreate_db()` for rollout. Back up and verify in staging before normal production rollout.

## Existing Trainer access

Existing active Trainer-app authentication through Hub remains the source of normal Trainer entitlement. All-course published performance is preserved. A trainer projection alone or an Employee-app session does not grant capabilities through the new discovery endpoint. No blanket backfill from trainer projections occurs. Operations CLI in this stage manages Admin Trainer only; it does not grant/revoke the existing Hub Trainer-tile entitlement. Removing Admin returns a valid Trainer session to normal Trainer capabilities, including all-course reporting. Removing actual Trainer access remains a Hub entitlement/active-identity operation.

## Inspect and provision Admin Trainer

Run from the backend directory in an authorized operations environment with the intended DATABASE_URL. Use an exact employee ID, not a name or email match.

```sh
python -m scripts.set_lms_authoring_role inspect --employee-id VERIFIED_EMPLOYEE_ID
python -m scripts.set_lms_authoring_role grant --employee-id VERIFIED_EMPLOYEE_ID --identity-key 'directory:VERIFIED_DIRECTORY_UUID' --operator VERIFIED_OPERATOR --reason 'Approved Admin Trainer oversight'
python -m scripts.set_lms_authoring_role revoke --employee-id VERIFIED_EMPLOYEE_ID --identity-key 'directory:VERIFIED_DIRECTORY_UUID' --operator VERIFIED_OPERATOR --reason 'Remove Admin Trainer oversight'
```

Use the exact `identity_key` returned by inspect; some identities use `hub:VERIFIED_HUB_ID`. Grant requires an active employee synced from Hub. Revoke also works for disabled identities. No match or identity mismatch fails without mutation. The CLI refuses grant/revoke without a verified identity key, operator and reason. Repeat identical requests are no-ops and do not create extra versions/audit events.

A grant is bound to the employee ID and current stable directory/Hub identity. Name/email changes preserve it. Replacing that stable identity denies the previous grant until an operator explicitly provisions the new identity, with an audit event. An identity acquiring a directory UUID after initial Hub-ID provisioning therefore requires review/regrant; privileges never transfer automatically.

Every real mutation records the actor, reason, action, identity, previous/next active state, UTC database timestamp and permission version in one transaction. An audit failure rolls back both grant and version. The operator field is supplied by trusted operations; there is no public grant HTTP endpoint or in-app role promotion.

## Capability discovery

```text
GET /api/lms/me?app=trainer
GET /api/lms/me?app=employee
```

Each request validates its corresponding existing app session or development token. One app's token cannot authenticate as the other. The app parameter chooses which audience to validate; it does not grant a role. Invalid/missing identity returns 401. Production Hub signature/cookie/audience behavior and existing login response shapes are unchanged.

Trainer response: canonical employee/trainer identity, effective Trainer/Admin label, stored permission version, own-course authoring, all-course reporting, and Admin-only cross-owner read capability metadata. Cross-owner manage is always false. Employee response: canonical identity and independent learning, without Trainer/Admin reporting or authoring. HOD/Observer discovery flags remain false until their authoritative mappings/effective grants are integrated; there is no manager/title/name heuristic. Frontend consumers will be wired in a later checkpoint.

Grants are queried again on every capability request. Roles and version are read in one PostgreSQL statement. A role change therefore affects the existing session's next discovery response. Original authoring/reporting APIs retain their existing gates in this checkpoint; capability metadata alone is not a replacement for server-side resource checks.

## Verification and rollback

Access integration tests use a randomly named schema inside the isolated `lms_performance_demo` database; all changes are rolled back, including the schema itself. Tests refuse any other database. Run with `LMS_ACCESS_POSTGRES_TESTS=true`. Existing reporting parity tests remain read-only. Email delivery/scheduling and directory sync are disabled during checks.

To withdraw Admin oversight, use the audited revoke operation and retain established Trainer access. If disabling capability discovery, keep additive tables/audit history and ordinary learning/Trainer reporting intact. Do not restore databases just to remove a role. Do not remove SMTP, TTS, signature/audience checks or other accepted fixes as part of rollback.


## Admin oversight API checkpoint

After the approved additive access migration and exact-identity Admin grant, the Trainer-app session can request `/api/trainer/course-library?scope=all`. Default library requests and the legacy `/api/courses` array remain own-course. Course inspection returns `creator_name`, `can_manage` and `read_only_reason`; assignment settings and generation monitoring are read-only across creators. Every cross-owner request checks the current grant. Revoking Admin removes this content oversight on the next request while retaining base Trainer entitlement and all-course Performance. Cross-owner edits/publication/disable/delete/generation return 403 with the creator-only explanation; no Admin override exists.

The library uses bounded offset pagination and a deterministic sort. Under concurrent course creation/deletion, refresh the first page rather than assuming a multi-request snapshot. The assigned-learner inspector reuses eligible published-course reporting; draft/disabled/revoked assignments are excluded. Its summary counts come from existing course-filtered Performance APIs.

UI integration and document/media authorization are pending. Do not treat this backend checkpoint as production rollout readiness. No Kiran grant has been applied by development tests.


## Final feature operations (supersedes earlier checkpoint-only limitations)

Capability discovery now includes effective HOD/Observer roles, report views, permission version and directory membership version. UI integration and private document/media delivery are implemented locally. HOD production mapping remains disabled until a verified directory department external ID/name and HOD stable UUID contract can be wired to `reconcile_verified_departments`; there is no manual HOD HTTP/CLI fallback and no manager/title heuristic. A missing field on a partial update preserves associations; explicit empty HOD lists revoke; authoritative full snapshots deactivate omitted departments. Run only from a trusted directory integration, with exact upstream semantics verified.

Creator Observer flow: open own ready/published course -> Assign -> Include -> Observers -> choose distinct active synced observer plus observed departments/employees -> Save Observers. Saving restrictions/removals takes effect immediately; additions stay pending. Publish & Assign using the existing learner workflow, then Apply Observers with the current revision. Unsaved form changes block Apply. Conflict 409 requires refresh and review. Revocation is Save with the observer removed; disabling the course suspends all its Observer grants and re-publication requires explicit owner Apply. Observer configuration and audit/version writes commit together, independently of existing learner publish transactions. It never enrolls observers or changes learner counts, deadlines, progress or email scheduling.

Read/write APIs: GET/PUT `/api/courses/{course_id}/observers`, POST `/api/courses/{course_id}/observers/apply`, trainer-authenticated GET `/api/observer/options`. GET permits owner/Admin; PUT/Apply require exact creator. Employee Performance uses `/api/employee/performance/{overview,options,courses,employees,assignments,...,export,employees/export}` with the same report response/export contracts as Trainer. Pure report roles cannot open Trainer management APIs or source files. Legacy employee team-performance now returns the shared overview shape; the Employee UI has been migrated to the new report family.

Release must coordinate backend and both frontend builds: old raw generated-asset URLs now require authentication/tickets. Keep the same stable Hub signing secret on all backend workers; credentials last at most 15 minutes and are checked against current identity/resource authorization on each request. Cookie-backed long playback can continue with an active matching Hub session; standalone credentials expire and are not individually invalidated by logout before expiry. No session bearer token is embedded in generated media URLs. Verify production proxy Range support, source viewer conversion, HLS nested playlists/segments, slide assets and cookie settings in staging before rollout.

Additive schema migration runs under the existing advisory lock/ledger. Back up production and verify the intended database before release; do not run test fixtures/reset scripts there. Retain role/Observer/directory tables and audit history during rollback. To withdraw visibility, audited Admin revoke and creator Observer revoke/disable remove access without resetting learner records. Stop consuming authoritative HOD updates only after reviewing intended current revocations; merely stopping sync does not revoke stored mappings. Roll back frontend entries/feature exposure while preserving private media delivery and server authorization; reverting to the old publicly served asset backend would undo privacy controls. No database destructive rollback is required. Preserve accepted SMTP/TTS/dependency/SBOM changes.

See `admin-trainer-implementation-progress.md` for final test counts, browser role matrix, local review URLs and exact retained task-owned fixture schema names. Production release/provisioning and verified HOD source integration are still outstanding.
