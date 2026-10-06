# Assign HOD — future implementation plan

Status: planning only, approved direction on 2026-10-06. No Assign HOD application code or schema is included in the current feature branch. The existing Admin Trainer/Trainer/Observer/HOD-report foundation remains unchanged.

## 1. Agreed behavior

Maintain the four entities: Admin Trainer, Trainer, HOD and Observer. Assigned HOD is another source of HOD reporting access, not a fifth authoring role.

- Official directory HOD: automatically receives department-wide Performance across eligible published courses, without Trainer action. The person's own employee department does not determine the department they head.
- Suggested/default HOD: Assign -> Include -> HOD displays each selected learner department and its verified official HOD. A Use Directory HOD action may acknowledge the default; it must not manufacture a manual grant or enlarge directory authority. Doing nothing leaves directory defaults active.
- Explicit Assigned HOD: the course creator selects an active synced employee and the exact employees on this course that person will supervise. This adds course-specific reporting for those employees only. It does not appoint an official department HOD, remove the official HOD, enroll anyone, or authorize other creators' content.
- Missing mapping: show Directory HOD unavailable and allow explicit course-level selection. Do not substitute manager, designation, name, email or the employee's own department for a verified HOD association.
- Existing Observer behavior and all-course Performance for every active Trainer remain intact. Admin can inspect another creator's HOD configuration but cannot change it.

Example: Excel Basics is assigned to Priya and Ravi in Finance. Directory says Kiran heads Finance, so she automatically sees Finance department Performance. Trainer explicitly selects Meera to supervise Priya/Ravi on Excel Basics. Meera sees these two employees on this course; Kiran continues to see her official department. Meera receives no Finance-wide or other-course authority through this selection.

## 2. Source contract and prerequisites

Before enabling directory defaults, confirm the authoritative department external ID/name, one-or-many HOD stable directory UUIDs, active status, partial-update semantics and full-snapshot semantics with the Hub/directory owner. Wire the existing verified reconciliation adapter only to that source. Explicit empty HOD lists revoke; omitted partial fields preserve; authoritative full snapshots reconcile missing mappings. Retain source/audit evidence. A label-only department registry supports department labels, not HOD authority.

Manual course HOD can be implemented independently of this integration. Production automatic defaults cannot be represented as complete until the source contract is verified and connected.

## 3. Data and policies

Use a separate additive migration for course HOD configuration so existing directory mappings and Observer grants are not repurposed:

- Per-course HOD config revision.
- Per-course assigned-HOD grant, stable employee identity key, active flag, creator actor and timestamps; unique course/assignee pair.
- Normalized pending/active target employees, each bound to current stable identity. No department-wide selector for manual grants in version one.
- Durable before/after audit plus affected recipients' permission-version updates in the same transaction. Keep active flag and active selector fields distinct.

Use the course/config locking and optimistic revision pattern already used for Observers. Creator-only mutation; Admin cross-owner read-only. Validate active synced assignee, unique recipients, nonempty targets and current employee identity. Targets must be within the creator's selected learner cohort for this course; application must additionally confirm eligible published assignments. Never accept client-supplied creator, role, identity key or department authority.

Saved manual targets are an explicitly reviewed employee set, not a dynamic department grant. Adding learners to a course does not silently expand an assigned HOD's targets. Removed/revoked learners immediately disappear from reports through assignment eligibility. Expansion requires explicit review/save/apply. If directory identity is replaced, the old grant must not transfer.

## 4. Lifecycle and activation

Preserve existing learner publishing/progress/deadline/SMTP behavior. Follow the current explicit access workflow:

1. Edit HOD configuration and Save HOD. Removals/restrictions immediately narrow effective access; expansions remain pending.
2. Publish & Assign the learner course through the existing workflow.
3. Apply HOD with the current revision after successful publication. Revalidate identities and actual assignment eligibility; grant/version/audit commit atomically together.

Unsaved form changes block Apply. 409 requires refresh/review. Failed publication or Apply cannot broaden manual access. Disabling suspends the course's manual HOD grants; re-publication requires explicit Apply. Deletion removes course-bound grants/selectors while retaining durable audit. Revocation removes access without learner enrollment/progress/email side effects. Directory HOD access is independently evaluated and is not revoked by a course creator's manual selection.

## 5. API design

Proposed additive routes, retaining existing report response contracts:

- GET /api/courses/{course_id}/hod: owner/Admin reads pending/effective manual configuration and source labels, no-store.
- PUT same path: creator-only revisioned save/restrict/revoke.
- POST /api/courses/{course_id}/hod/apply: creator-only activation on eligible published course.
- GET /api/courses/{course_id}/hod-suggestions: owner/Admin sees verified HODs grouped by departments of the selected cohort. Restrict discovery to this course/context rather than exposing a new report-user directory endpoint.

Reuse existing creator assignment-option employee picker. Derive stable identities and suggestions on the server. Bound response sizes and paginate target previews; do not send every full directory record. No public role-provisioning endpoint.

Extend /api/lms/me with source-aware HOD reporting capability/view metadata. Employee sessions remain Employee sessions; no Trainer projection or third Hub tile.

## 6. Reporting integration

Add an immutable assigned-HOD scope contribution and a correlated EXISTS policy against active course grants/identity-bound targets. Combine directory HOD, assigned HOD and Observer using OR/EXISTS, never a multiplicative join. Continue filtering eligible published, active-rule, nonrevoked assignments before aggregation.

Employee Performance views:

- My Department(s): official directory departments only.
- Assigned HOD: explicitly assigned course/employee scopes only.
- Observed Employees: existing Observer scopes only.
- Combined: authorized union, with assignment-ID deduplication and distinct employee counts.

Trainer All Courses stays unchanged; My Courses remains optional narrowing. Assigned HOD does not grant course/source inspection, playback, answer keys, authoring or assignment mutation. Separately enrolled learners retain their normal learning access. Reuse the identical scope for overview, options, course/employee/assignment detail, module metrics, summaries and both exports; reauthorize each export page.

Access refresh/version/cache keys must reflect manual grant changes, directory identity/membership changes and eligibility changes. Reject stale requests, clear incompatible filters with an explanation, and guard already-open details. Do not show employees/course options outside the chosen scope.

## 7. UI in the existing product

Add a separate HOD section alongside Observers under Assign -> Include. Keep existing PhillipCapital styling, learner counts and publish controls.

- Directory default area: department -> verified HOD name, source Directory, automatically active when authoritative mapping exists. Multiple departments/HODs shown explicitly; unavailable mapping clearly labeled.
- Explicit assignment area: Assign HOD/Add HOD, active employee picker, course-target employee multiselect, pending/effective eligible target preview, remove, Save HOD and Apply HOD.
- Explain: Performance access for this course and these employees only. This does not replace the official department HOD or enroll the assignee.
- Block duplicates/empty targets, unsaved Apply and cross-owner edits. Show effective versus pending scopes and revision conflicts.

No new top-level authoring tab for HOD. In LMS Employees, expose the Assigned HOD choice inside existing Performance and optionally a source-labeled shortcut where the existing layout fits. Ordinary Employees retain Dashboard/My Courses/Notifications. Update both current report UI copies consistently; package extraction remains separate work.

## 8. Implementation stages and acceptance checks

A. Rebase/review against the actually merged main in a new clean branch, proposed codex/course-assigned-hod. Preserve existing SMTP/TTS/SBOM and accepted access work; do not work in the dirty shared checkout. Confirm directory contract separately.

B. Add additive tables/migration and transactional repository/API tests. Test idempotence, exact creator, Admin read-only, app audience, optimistic conflict, audit rollback, pending expansion, immediate restriction, disable/reapply, deletion and identity replacement.

C. Extend shared SQL scopes/capability discovery and tests. Demonstrate Kiran directory-wide visibility versus Meera's one-course subset; overlap with Observer/directory produces one row per assignment, matching full counts, summaries, details, options and CSV. Forged IDs and unauthorized view widening return denied responses. All-course Trainer reporting remains unchanged.

D. Integrate HOD Include panel/Employee views and lifecycle guards. Browser UAT all four entities plus combined access and a normal Employee; check missing mapping, multiple departments, unsaved Apply, conflicts, revocation while a detail/export is open, and narrow viewport layout. Verify report-only HOD cannot retrieve content/media.

E. Run targeted access/learning/publishing/SMTP/TTS regressions, frontend scope/widget checks, both web builds and real private-media compatibility checks. Keep existing unrelated failures separately documented. Review migration/rollout/rollback evidence before production provisioning/deployment.

## 9. Rollout and rollback

Ship as a separate reviewed PR after the current access branch is merged. Coordinate backend/both frontends without altering SMTP/TTS/dependency/SBOM configuration. Automatic HOD defaults remain gated until authoritative mapping is verified. Provision no real grants in dummy tests.

To withdraw manual visibility, creator revokes/suspends course-bound HOD grants; preserve directory HOD and Observer authority independently, audit history and learner progress. Retain additive tables rather than destructive rollback. Reverting private-media protection is not part of rollback.

## 10. Current branch boundary

codex/admin-trainer-oversight contains the already implemented access foundation and this planning document only. It does not contain the proposed Assign HOD button, manual HOD tables/APIs or Assigned HOD report view. Merging this branch does not activate this future feature and does not resolve the outstanding authoritative directory contract. Git merge itself is not deployment unless the repository's deployment pipeline explicitly performs that action.
