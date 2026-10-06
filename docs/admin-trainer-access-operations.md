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
