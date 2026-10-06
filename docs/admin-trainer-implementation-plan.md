# LMS access implementation plan: Admin Trainer, Trainer, HOD, Observer

Updated: 6 October 2026  
Branch: `codex/admin-trainer-oversight`  
Starting commit: `35c4ce714e5bb7a679e08547c3f34cc1020b07d0`  
Starting branch: `fix/smtp-approved-internal-relay`

This is the implementation plan and tracking record. The user authorized step-by-step implementation on 6 October 2026; deployment is not part of that authorization. The implementation has now started in the isolated access checkout; this plan records the updated scope and stages. The branch was originally created from the SMTP relay checkout; checkpoint 1 reconciles the improved Performance work and newer committed fixes in the isolated checkout. Preserve unrelated working changes, including the existing untracked `tts-openapi.json`.

## 0. Existing branches and integration strategy

Verified from local Git refs and a read-only worktree inspection on 6 October 2026. Remote-tracking refs are local snapshots; fetch and verify the remote state when integration begins.

| Branch / checkout | Verified state | Intended use |
| --- | --- | --- |
| `feature/performance-tab` | Tip `4e2fce9`; checked out at `C:/Users/LPUSER/.codex/worktrees/performance-demo/LMS_V1` | Existing improved Performance dashboard. Include its reviewed uncommitted work before integrating. |
| `codex/admin-trainer-oversight` | Exists at `35c4ce7`; originally based on `fix/smtp-approved-internal-relay` | Reuse for the four-access-type implementation and Performance integration. No new branch is necessary. |
| Current workspace: `codex/lms-sbom-remediation` | HEAD `16adda0`; has unrelated SBOM/dependency/container/font changes in progress | Do not switch, stash, commit, overwrite, or incorporate its dirty files merely to begin access work. Bring in accepted committed fixes deliberately. |
| Local `main` | `e3ddd3e`; the Performance tip is not an ancestor of this local ref | Do not assume the improved dashboard is already in the release base. Recheck remote and deployed release before integration. |
| Existing `admin-trainer-visibility` worktree | Detached HEAD `89c7ab1`, shown by Git worktree inventory | Its suitability/content is not verified by this plan; inspect its status and purpose before reusing it. |

Performance worktree inspection found tracked modifications in README, analytics API, reporting repository/schema/service/tests, Performance portal and providers, plus untracked employee-summary panel, its frontend test, and PostgreSQL reporting tests. This includes the employee summary UI, scope/filter-correct employee CSV export, and database-side employee grouping/pagination described in the other session. Merging the branch tip alone will omit these changes. Preserve and review them in that worktree, run focused checks, and include them in explicit Performance commits before integration. Do not mix access-role work into that checkout's existing dirty changes.

Use a separate suitable checkout attached to the existing `codex/admin-trainer-oversight` branch when implementation starts, keeping this shared SBOM workspace untouched. Inspect existing artifacts/worktrees first. If the detached checkout contains useful changes, preserve and reconcile them before reuse; do not reset it. Creating a worktree does not require creating another branch.

Integration sequence:

1. Record verified remote/deployment base, branch tips, and clean/dirty status. Preserve the Performance worktree's tracked and untracked changes and the current workspace's unrelated changes.
2. Review and checkpoint the complete Performance implementation, including uncommitted export/pagination/employee-summary fixes, with its tests. The prior session's successful test results are evidence of prior work, not validation of this integration.
3. Reconcile the access branch with the accepted release base and newer committed SMTP/security/TTS fixes. Review deployment-specific notification changes against the current release rather than reverting them to the older plan's baseline. Incorporate SBOM work only from its accepted commits when ready.
4. Integrate the complete Performance commits, resolve overlapping analytics/provider changes deliberately, then implement the policy and frontend phases below. Do not cherry-pick a subset that omits schema, detail, export, or test files.
5. Record integrated commit IDs and conflict decisions in the PR/runbook. Create a draft PR when the actual implementation is reviewable; publishing/merging/deployment are separate actions.

Updated decision, confirmed 6 October 2026: preserve committed change `16adda0`: every authenticated active Trainer, including Admin Trainer, can view all eligible published-course performance. This supersedes the earlier Trainer own-course reporting restriction throughout this plan. Authoring/content access remains own-course for normal Trainer; Admin Trainer additionally gets read-only cross-owner course/content/assignment-configuration visibility. Reporting permission never grants cross-owner mutation, content preview, answer keys, source documents, or Observer configuration. Preserve broad reporting tests and extend every improved report/detail/options/export path to the same all-course performance policy.

## 1. Product behavior and scope

Implement four composable access types: Admin Trainer, Trainer, HOD, and Observer. Kiran receives Admin Trainer; Karneeshkar receives Trainer. Existing legitimate trainer authoring access is preserved, but opening the management app must not automatically grant authoring access to an HOD or Observer.

Example: Karneeshkar creates Excel Basics, publishes it, and assigns it to 20 employees. He manages this course in his own workspace. Kiran opens All Trainers' Courses, previews the course, sees Karneeshkar as its creator, inspects assignment rules and learner progress, and filters the library by Karneeshkar. Drafts and failed or running generations are visible too, with content shown only when available.

Confirmed requirements: both authoring roles create, publish, and manage their own courses. Admin Trainer can view all trainers' courses and all performance but cannot edit, regenerate, assign, disable, or delete another trainer's course. Show: "This course was created by another trainer. You can view it and its performance, but only its creator can make changes." Deny a direct mutation request with the same explanation for an admin-visible course. Normal Trainers see only their own authoring course library and can view performance for all eligible published courses, regardless of creator. Observer grants apply only to the course where they are configured. HOD scope is department-wide, mapped automatically from authoritative directory data. Roles combine; they do not replace each other.

Publication approval, cross-owner management, ownership transfer, and admin/observer-wide email subscriptions are outside this feature. Admin Trainer is an oversight role, not permission to change every resource.

Initial administrative scope is the current LMS deployment. The repository has no explicit organization/tenant boundary in the trainer/course contracts inspected. If this deployment serves several organizations, add a trusted organization identifier and enforce it before deployment-wide oversight. HOD department membership is an authorization boundary; optional report department filters only narrow the authorized scope.

| Action | Trainer | Admin Trainer | HOD only | Observer only |
| --- | --- | --- | --- | --- |
| Upload/create/publish/assign | Own workspace/courses | Own workspace/courses | No | No |
| Edit/generate/resume/disable/delete | Own courses | Own courses | No | No |
| Course library/content preview | Own courses | All courses in scope | No | No |
| Generation job and assignment configuration reads | Own courses | All visible courses, read-only | No | No |
| Performance | All published courses in scope | All published courses in scope | Learners in mapped departments, across published courses | Granted learners/departments on granted published courses |
| Configure observers | Own courses | Own courses | No | No |
| Source documents | Own documents | Documents attached to visible courses | No | No |
| Saved assignment groups | Own groups | Own groups | No | No |
| Privileged LMS functions | Authoring and Performance | Authoring and Performance | Performance only, plus independent employee learning | Performance only, plus independent employee learning |

Employees continue to receive only published, actively assigned courses. Reporting access does not enroll HODs/Observers, expose editable course content, or write learning progress. HOD/Observer course options are report selectors with minimal metadata, not course-library access. Published-course performance with no assignments is an empty state; draft generation status remains an admin course-preview concern rather than employee performance.

Combined example: Karneeshkar is Trainer + Finance HOD + Observer for selected Operations learners on Kiran's course. His authoring tabs contain only his courses. Performance provides All Courses (default), My Courses, My Department, and Observed Employees as useful narrowing views. All Courses already contains every permitted reporting contribution for an active Trainer; a redundant Combined choice can be omitted. He cannot edit Kiran's course. Combined results deduplicate by assignment ID, not employee ID, because one employee can have several courses. Revoking Observer removes only that grant; independent Trainer/HOD access remains.

### 1.1 Hub entry and automatic access discovery

Keep two existing Hub tiles. Trainer/Admin Trainer opens **LMS Trainer** for authoring and permitted Performance views. HOD/Observer opens **LMS Employees**: existing Dashboard, My Learning/My Courses, and Notifications remain available as employee functions; add a Performance entry only when the backend returns at least one reporting capability. Do not add a third tile or require Trainer-tile entitlement merely to observe performance. HOD/Observer's new privilege is reporting only; it does not remove their ordinary assigned learning access.

Hub establishes the verified employee identity through its signed launch/session. LMS resolves current permissions from stored authoring grants, authoritative department-HOD associations, and effective course Observer grants. `/api/lms/me` returns capabilities and available scope descriptors; frontend role labels and navigation derive from this response. A user never chooses a production role at login. The preview's role picker is synthetic demonstration only.

HOD detection requires an explicit stable employee-to-department leadership mapping, not the person's own department or manager/title. Observer detection requires an effective course grant saved by the course creator; directory sync supplies selectable identities/departments but does not create Observer grants. Normal employees with neither mapping receive no reporting capability. Empty HOD reports are distinguishable from absence of HOD access. Pending Observer additions confer no live reporting access. Removing the final effective grant removes the Observer reporting entry on permission refresh; any independent HOD grant remains.

Combined Trainer+HOD/Observer users can use LMS Trainer for authoring and their permitted combined reports, and LMS Employees for their own learning and employee-app report views. The employee app exposes HOD/Observer scopes only in version one; it does not automatically expose admin course-library/authoring functions or all-course oversight. Backend authorization always intersects the requested operation with both authenticated app audience and effective permission. Identical HOD/Observer views produce identical reporting results from either authorized entry. Keep employee and trainer cookies/token audiences distinct.

### 1.2 Integrate the improved Performance dashboard

Reuse the actual `feature/performance-tab` dashboard and its latest reviewed local changes: Overview, Courses, Employees, employee-summary and scannable assignment modes, course/employee/assignment drill-downs, existing filters, CSV exports, and PostgreSQL grouping/pagination. Do not rebuild the interface from the HTML role prototype or maintain another independent analytics engine.

Add a reporting **View** selector above those sections: All Courses (Trainer/Admin default), My Courses (Trainer/Admin optional narrowing), My Department(s) (HOD), Observed Employees (Observer), and Combined for multiple report-only contributions. Department Performance is a scope within Performance, not a competing dashboard. The report's Overview, Courses, Employees, summary mode, assignment mode, details, options, counts, and CSV export all use the same selected authorized scope. Filters only narrow it.

Example: Meera opens LMS Employees -> Performance -> My Department -> Employees. She sees Finance employees' learning snapshots across creators; an employee detail lists only Finance-authorized assignments. Neha opens the same tile -> Performance -> Observed Employees and sees Operations learners only on granted Excel Basics assignments. Kiran uses All Courses in the Trainer app; Karneeshkar also defaults to All Courses and can narrow to My Courses. Combined counts deduplicate assignment IDs; unique employee counts are separately distinct employee IDs.

Preserve the repository/deployed product design: PhillipCapital branding, Trainer top navigation, Employee blue sidebar, existing fonts, palette, spacing, controls, learning cards, and improved Performance interactions. Verify the actual deployed release and screenshots at baseline; repository source alone is not proof of exact deployed appearance. New scope/creator/read-only/Observer controls follow existing components. `127.0.0.1:6972` is a synthetic preview address, not the production deployment or a completed authorization implementation.

## 2. Findings from this checkout

| Current implementation | Consequence / required change |
| --- | --- |
| `api/courses.py` passes the current trainer ID into every course operation; repository summary SQL includes `WHERE c.trainer_id = ?` | Add explicit read scope while retaining owner-only writes. |
| `CourseRepository.get_draft_for_trainer` checks ownership even for course detail reads | Course detail must support read access without weakening mutation checks. |
| `services/assignments.py` uses `_owned_draft_course` for assignment reads and writes | Separate viewing assignment rules from changing/publishing/disabling them. |
| `services/generation.py` uses `draft()` for both status reads and generation operations | Separate job visibility from permission to run or resume generation. |
| Original access-branch analytics passed trainer ID; newer committed `16adda0` removes it for the legacy trainer endpoint; improved reporting on `feature/performance-tab` has separate SQL paths | Preserve `16adda0` all-course Trainer reporting across all paths; separate reporting-only course metrics from authoring/content access. |
| Trainer schemas have no role; trainer identity is upserted on Hub login and directory refresh | Persist the role separately from synced identity fields and return it in all session responses. |
| Original providers were keyed only by trainer identity; improved Performance has its own provider and pending local changes | Review integrated versions, extend scope/permission cache identity, and protect every asynchronous response. |
| Flutter `Course` model discards `trainer_id` | Preserve owner identity through parsing, summaries, detail hydration, and `copyWith`. |
| `/api/files/{file_name}` and its preview route have no request authentication | Protect original and converted documents with identity and document/course authorization. |
| Generated audio/images/slides/videos are served through public static mounts | API roles alone do not protect direct media URLs. Course media needs an authorized delivery design. |
| Analytics groups courses by title | Identically named courses from different trainers can merge; group by course ID and label with title/creator. |
| Analytics filter options use the full employee assignment directory for trainer reports | Scope performance options to authorized course assignments; retain directory access where assignment authoring actually needs it. |
| Blueprint edits invalidate generated content and save a draft; manual quiz saves also save a draft | Check lifecycle effects before extending access; avoid accidental unpublication or invalidation from read-only preview. |
| HOD report currently calls analytics with `manager_employee_id`; employee sync stores department and manager fields but no explicit HOD-to-department contract | Replace direct-report report scope with an authoritative HOD department mapping. A manager field alone is insufficient. |
| Hub trainer login automatically upserts a trainer projection | Separate management-app authentication from authoring entitlement before admitting report-only users. |
| Assignment schemas/repositories contain learner include/exclude groups but no observation grants | Add independent course observation records; never reuse learner inclusion as observation access. |

These findings started from the original branch baseline and are updated for inspected local refs above; re-inventory the integrated checkout before coding. They are not a fresh production security assessment. The separate image-slide test failure and image vulnerability notes in `docs/security/vapt-2026-09-25.md` are historical and need re-verification before release. Concurrent SBOM changes are separate work and must not be lost or assumed released.

## 3. Role storage, migration, and provisioning

1. Do not use one exclusive `trainers.role` enum for all four types. Add normalized `lms_authoring_roles` for stable-identity-bound grants. The first implementation stores audited Admin Trainer grants; existing verified Trainer-app entitlement remains the source of normal Trainer access to preserve current behavior. The table supports future explicit Trainer grants, but operations in this stage manage Admin only. Derive HOD from directory-managed department mappings and Observer from course grants. Admin Trainer implies own-course authoring without needing a second Trainer grant. Link existing trainer projections to canonical employees by stable directory/Hub identity; keep existing `courses.trainer_id` and documents intact.
2. Use an additive, versioned migration with a migration ledger and transactional/advisory locking. Introduce the minimal migration runner needed for this feature; do not rewrite every historical schema operation. Fresh database initialization and the migration path must produce the same trainer schema.
3. Preserve confirmed existing Trainer-app entitlements without a blanket role backfill. If a future rollout needs explicit Trainer grants, reconcile against the trusted Hub inventory first. Projection rows alone are not proof of entitlement because development login permits synced employees; reconcile against the trusted Hub access inventory and identify historical creators needing continuity. Do not default every employee, HOD, or Observer to Trainer. Do not change course IDs, owners, source documents, assignments, progress, outbox records, or generated files. Never use the database recreation/reset script for this rollout.
4. Update trainer contracts/repository plus shared identity/session contracts. Identity upserts update name, email, directory UUID, and active status only; authorization grants are independently stored and preserved. New identity projections confer no authoring role. Add `permissions_version` to the canonical access identity and resource/grant revisions where needed.
5. Provision Kiran through a dedicated operations CLI, proposed `backend/scripts/set_lms_authoring_role.py`, using her verified stable employee/trainer identity. Resolve exactly one active synced employee; fail on ambiguity. Provisioning writes only the canonical employee Admin grant; the existing authenticated Trainer launch continues to manage its projection. A pure HOD/Observer requires no trainer projection.
6. Do not infer admin access from a name, email substring, designation, or a client-provided role. Review the existing email fallback in trainer upsert: authoritative directory UUID/employee identity should take precedence, and conflicting identities must not inherit an admin role through a recycled email address.
7. The CLI supports Admin grant, revoke, and inspect; it does not revoke the existing Hub Trainer-tile entitlement. Role changes increment `permissions_version` and write an audit record in the same transaction: target identity, old/new role, UTC time, operation reason, and operator identity/source. No default Admin Trainer and no first-login promotion.
8. Resolve current persisted authoring grants, HOD department mappings, and course observation grants for every authenticated API request. Signed Hub sessions/local development tokens establish identity, not immutable role authority. Disabled identities fail authentication immediately. Access changes increment versions and invalidate affected client/report caches.

Operations access to the CLI/database is the provisioning authority for version one. Admin Trainer does not grant itself permission to promote other users.

### 3.1 HOD directory mapping

Current sync normalizes employee department, manager UUID/ID, and group membership; the inspected contracts do not identify a department's HOD explicitly. Before finalizing the production HOD integration, validate a real directory export or its trusted schema for a department HOD UUID, department-owner record, or an authoritative HOD group with an exact department association. Other feature implementation can proceed using explicit HOD fixtures while production HOD activation remains gated. This is a directory integration dependency, not a decision to fall back to direct reports.

Add normalized departments with stable IDs/external keys and `hod_department_access(hod_employee_id, department_id, source, source_key, active, synced_at)`. Support multiple departments per HOD and multiple HODs if supplied. Do not infer leadership from job title, being someone's manager, the HOD's own department, or text similarity. If the export lacks a trusted association, extend the Hub/directory feed or its authoritative configuration; an operator-maintained LMS fallback would require a separately agreed deviation from automatic mapping.

Report scope is employees whose current authoritative department ID matches an active mapped HOD department. Membership updates and HOD reassignment take effect after the authoritative sync commits. Department renames preserve scope through IDs; null/ambiguous departments grant no access. Partial events preserve omitted mapping fields, while explicit removals/full authoritative reconciliation revoke old mappings. Soft-disabled HODs lose access while course/progress history remains. Keep sync freshness and unresolved associations visible operationally.

Reporting membership and notification recipients are separate policies. Keep the existing direct-manager HOD email recipient logic initially; expanding department-wide reports must not automatically email every employee's progress to new recipients. Any notification change requires its own requirement, scoped recipient validation, and regression tests.

### 3.2 Course-specific Observer grants

Add `course_observer_grants(grant_id, course_id, observer_employee_id, status, revision, granted_by_trainer_id, created_at, updated_at, revoked_at)` with a unique course/observer association, plus normalized employee and department selector child tables. Store observation selectors separately from learner include/exclude JSON and saved learner groups. Foreign keys use stable employee/department IDs; add indexes for observer/course/status lookup and selector matching. Audit grant creation, scope edits, publication, and revocation with actor and before/after scope.

Only the course creator can configure observers, whether their role is Trainer or Admin Trainer. Kiran cannot change Karneeshkar's observers. Choose observers from active synced employees; selecting one provides Observer access derived from its effective grants, not a global report privilege. Multiple observers per course can have different employee/department selections. Selecting both explicit employees and departments means their union, intersected with that course's eligible assignments. Empty scope grants no access; no implicit all-departments default. Observers are never added to learner include groups or learner match counts unless independently selected as learners.

Department selectors are dynamic: new eligible learners joining a selected department become visible; learners leaving it stop matching. Explicit employee selections remain explicit even if their department changes. In both cases the learner must have an eligible assignment on the granted course. Employee/department filters in Performance can only narrow this result. Overlapping observer selectors/grants are deduplicated.

Save new Observer configuration as pending when the course assignment is not published. Activate it during successful Publish & Assign together with the corresponding course/rule revision. On an already published course, additions/expansions remain pending until explicitly applied; removals/restrictions take effect immediately on save. Implement this through active/pending selector revisions, never by changing learner matching. Preserve omitted observer fields from older clients; an explicit empty list revokes all observers for that course. Grant-only updates must not republish learner assignments, reset deadlines, reset progress, or queue assignment emails.

Disabling assignment suspends Observer visibility on that course; unpublished/deleted courses and revoked/disabled observers cannot be queried. Re-enabling can restore nonrevoked grants only after owner review/application. Retain audit history on course deletion using durable identifiers/snapshots, while live grant rows follow the course lifecycle. HOD/admin reporting of inactive assignment history must be explicitly labeled and must not broaden Observer scope silently.

## 4. Central authorization and API design

Create a shared access policy module, proposed `backend/app/services/lms_access.py`. Keep course readiness functions in the existing `course_access.py` intact. Build a canonical authenticated principal with employee ID, optional trainer projection ID, effective roles/capabilities, mapped department IDs, and permissions version. Authoring routes explicitly require authoring capability; a valid management-app session alone is insufficient.

Policy inputs are the authenticated principal, resource owner, operation, requested view, and course/employee reporting relationship. Suggested operations: `course.read`, `course.manage`, `assignment.read`, `assignment.manage`, `observer.manage`, `generation.read`, `generation.run`, `performance.read`, and `document.read`. Return explicit resource capabilities, including `can_edit`, `can_generate`, `can_assign`, `can_manage_observers`, `can_delete`, and `can_view_performance`. Performance-only visibility must never imply `course.read` or authoring access.

- Own-resource reads/writes are permitted only to active principals with Trainer/Admin Trainer entitlement and matching creator ID.
- Cross-owner reads are permitted only to Admin Trainer in authorized deployment scope.
- Cross-owner writes remain denied even for Admin Trainer.
- HOD/Observer-only users cannot upload, author, list courses/documents, inspect source content/jobs, change learner assignments, or manage observation grants. They can read permitted performance rows and minimal report metadata.
- For each performance row, allow access if active Trainer/Admin Trainer has its verified Trainer-app entitlement; or HOD maps to the learner's department; or an effective course Observer grant matches the learner. Apply common deployment/course/assignment eligibility constraints before this union. Explicit views select one authorized contribution; combined view unions them.
- An omitted trainer ID must never mean administrative authority in an HTTP operation. Internal worker/system calls needing broad access remain explicit and separate from user-facing entry points.
- Add a typed 403 authorization exception in `core/exceptions.py`. Use 401 for missing/invalid identity; use 403 for forbidden scopes/actions on a visible resource; use 404 for nonexistent or hidden resources. Apply consistently across routes/services.

Proposed API contract:

| API | Planned behavior |
| --- | --- |
| Hub session and local development login | Add shared `principal`, `roles[]`, `permissions_version`, capabilities, and permitted performance views. Retain employee/trainer payloads for compatible callers; report-only users need no trainer projection. |
| `GET /api/lms/me` (new) | Return current persisted identity/permissions and report scope descriptors; used on startup, focus refresh, and permission errors. |
| `GET /api/courses` | Preserve existing own-course list response and default; do not silently broaden it. |
| `GET /api/trainer/course-library` (new) | Paginated oversight/own library with `scope=own|all`, optional `owner_trainer_id`, course status, generation status, search, and stable sort with bounded offset pagination in version one. Normal trainers cannot request all/another owner in this authoring/content library, even though their Performance view includes all published courses. |
| `GET /api/courses/{course_id}` | Owner or authorized Admin Trainer read; include creator summary and resource capabilities. |
| `GET /api/courses/{course_id}/assignment` | Owner or authorized Admin Trainer read of rule/deadline/active status. |
| `GET /api/trainer/course-library/{course_id}/assignments` (new) | Paginated authorized assigned-learner view through the shared reporting engine; use existing course-filtered Performance APIs for separate status counts and summary cards. |
| Existing generation job GET | Authorize against the job's course; Admin Trainer can monitor, not resume it. |
| Improved Performance endpoint family, adapted to shared reporting service | Reuse Overview, options, Courses, Employees, assignments, details, and exports from the improved implementation. Carry `view=my_courses|all_courses|my_departments|observed|combined` through every operation. |
| `GET /api/trainer/performance` | Compatible active Trainer/Admin wrapper preserving all eligible published-course reporting by default; optional own-course narrowing. |
| `GET /api/employee/team-performance` | Compatible HOD wrapper changed to mapped department-wide reporting; verified HOD capability required. Do not retain direct-report fallback. |
| `GET /api/courses/{course_id}/observers` (new) | Course creator or Admin Trainer read; HOD/Observer cannot inspect other observer identities/scopes. |
| `PUT /api/courses/{course_id}/observers` (new) | Creator-only revisioned save/revoke with validated employee/department selections; optimistic concurrency conflict is 409. |
| Publish/apply Observer configuration | Validate ownership and revision; activate pending configuration only after publication/application succeeds. Extend Publish & Assign compatibly. |
| All authoring/generation/assignment mutation routes | Owner-only management policy, including manual quizzes, publish, disable, delete, and resume. |
| Document download/preview | Authenticate, resolve document by record, and authorize before resolving/converting/streaming files. |

Preserve existing response shapes used by current clients. Add the paginated library endpoint rather than replacing the existing course-list array with an envelope. Extend the improved Performance contracts compatibly with bounded page metadata; totals must describe the full authorized filtered set, not just the current page. Existing assignment CSV and the pending employee-summary CSV must both reuse current authorization, submitted filters, attention filters, mode, and deterministic ordering. Employee CSV is one row per employee within authorized assignments; assignment CSV is one row per authorized assignment. Authorize every export request and chunk, reject widened views, handle revocation without returning subsequent unauthorized chunks, and keep bounded queries. Do not preserve owner-only checks on some detail routes while broadening lists inconsistently.

Version-one routing approach: retain `/api/trainer/performance/...` response contracts for existing Trainer clients and adapt their service/repository to accept the canonical reporting scope. Add an employee-authenticated `/api/employee/performance/...` family for HOD/Observer with corresponding overview/options/courses/employees/assignments/detail/export operations. Both families call one reporting service; they do not delegate employee tokens to trainer authentication. Include employee-summary routes and CSV from the final reviewed Performance worktree, even though those are absent from its current committed tip. Inventory exact routes after integration; no extra monolithic `/api/lms/performance` replacement is required. Retain `/api/employee/team-performance` as a mapped-HOD compatibility wrapper, and preserve the broad legacy `/api/trainer/performance` behavior for active Trainers described in section 0.

Trainer filter options come from owners of courses in the authorized library, including inactive owners where historical courses remain. Browser parameters can narrow authorized results but cannot grant access. SQL uses bound values and an allowlist for dynamic sort fields.

HOD/Observer reporting launches through the existing Employee tile and employee session. No Trainer-tile provisioning is required for those permissions. Add Employee-app reporting routes with effective permission checks and shared reporting services, preserving signed app audience checks. A combined authoring user may invoke Trainer-app reporting with that app's valid session and permitted scopes. Do not accept an employee-app token as a trainer-app token, promote an employee to Trainer on login, or trust client role/scope IDs. Development pickers can simulate each role but remain disabled outside development.

## 5. Queries, counts, lifecycle, and performance

Extend course repository methods with explicit read scope, not a loosely interpreted nullable trainer ID. Join trainers once for creator display names/status; load lightweight summaries without all module content. Preserve `courses.trainer_id` as creator/owner in this release.

Course lifecycle remains `draft`, `ready`, `published`, `archived`. Running/failed generation comes from `course_generation_status`, not a new course status. An admin can see a draft with failed generation and a published course with disabled assignments as distinct states.

Aggregate assigned/completed/overdue counts in pre-aggregated subqueries or CTEs. Joining modules, assignments, and progress directly can multiply rows; prevent double counting. Assignment status and deadlines use the same rules as the existing performance view, including disabled rules and retained historical progress. Specify whether each metric is active assignment count or historical count; the initial library shows active learning metrics with inactive assignment history separately labeled.

Use deterministic pagination ordered by creation time plus course ID. Search/filter indexes follow measured query needs; review existing `(trainer_id, status)` index before adding owner/time or status/time indexes. Verify representative query plans and avoid one query per course/learner.

Refactor the integrated `performance_reporting.py` repository/service and legacy analytics wrappers to filter authorized course-assignment rows before loading module details. HOD needs a department join; Observer needs correlated course-grant/selector matches; combined access uses `EXISTS` or a deduplicated assignment-ID relation to avoid multiplying rows. Reuse this authorized relation for rows, employee grouping, attention filters, summaries, breakdowns, filter options, module details, and both CSV exports. Preserve the reviewed PostgreSQL employee grouping/sorting/pagination fixes instead of returning to Python-wide assignment loading. Paginate rows and lazily fetch expensive detail if needed; calculate full aggregates independently. Identify course breakdowns by course ID, trainer breakdowns by trainer ID, and show creator labels to distinguish repeated titles. Employee dropdowns expose only eligible learners, never the full directory for a performance-only user.

Before changing course mutation code, reproduce current ready/published edit behavior. Add guards for pending/running generation so editing cannot race with workers. Do not let no-op metadata/quiz requests unexpectedly demote published courses. Content changes that require regeneration must have a deliberate lifecycle rule and reconcile existing assignments/progress/notifications through current services. If published content editing needs course versioning, keep that as a separate change rather than resetting learner history in this feature.

Keep the existing atomic delete/generation lock, readiness/thumbnail checks, resumable checkpoints, and employee notification broadcasts intact.

## 6. Document and generated media access

Protect source documents first. Owners can open their own documents. Admin Trainer can open a document attached to a visible course; a course relationship does not permit editing/regenerating that document. Unattached uploads remain in their owner's workspace. Resolve ownership from document records, never filename prefixes alone. Authorize before PPTX/DOCX preview conversion.

For generated course assets, add an asset-to-course lookup/manifest and an authorized media delivery layer. Global brand/style assets stay public. Private slides, images, audio, MP4, HLS playlists, and HLS segments require one of:

- owner/authorized Admin Trainer preview access; or
- employee access under existing published-course, active assignment, and playback rules.

HOD/Observer performance visibility does not grant source-document or generated content playback access. If these users are separately assigned as learners, their employee identity retains ordinary learning access through that independent assignment.

Use browser cookies where available; for embedded players that cannot send bearer headers, issue short-lived asset-scoped tickets only after authorization. Validate current identity/permission/assignment at delivery, with safe cache behavior. Do not put reusable session tokens in URLs. A media URL is never enough to authorize a course or expose quiz answer keys to learners.

Internal generation renderers also read slide/image assets. Supply an explicit internal rendering credential or loopback service access; do not break Playwright rendering by enforcing browser sessions on workers. Update rendered slide references and player URLs consistently. Retire public course-media aliases after the authorized paths work; keeping an unprotected alias would bypass the new policy. Preserve path containment, content types, HTTP range requests, HLS relative segment resolution, HEAD requests, and proxy streaming behavior.

Document route protection belongs in this release. Complete media protection before claiming end-to-end private course isolation. If media work is delivered separately, record the remaining direct-URL exposure explicitly as a release limitation.

## 7. Trainer and Employee frontends

Update both apps' auth/session contracts with canonical principal, `roles[]`, permissions version, available report views, and resource capabilities. Update Trainer course models with owner summaries. Preserve fields across parsing, `copyWith`, detail hydration, and cache updates. Missing capabilities default to no privileged access. HOD/Observer Employee reporting requires no trainer projection. Trainer dashboard still requires its valid app session and authoring entitlement for authoring controls.

Reuse the improved Performance components/providers rather than the role-preview HTML. Share role-aware report models, components, and scope/filter behavior through a small local Flutter reporting package, proposed `packages/lms_performance_ui`, consumed by both frontends. Inject each app's authenticated API adapter, refresh hook, and existing theme; the package must not import Trainer authoring state or accept app tokens directly. Keep web CSV download support in the adapter. Extract only reporting components needed by both apps, not a wholesale frontend rewrite. Both builds must resolve the local package in Docker build contexts and CI; retain concurrent accepted SBOM lock/font changes when adjusting builds.

Add an Admin Trainer badge and a My Courses / All Trainers' Courses switch within Courses. The admin library shows creator, title, lifecycle, generation status, created/published date, assignment active status, assigned count, and completion. Add creator/status/search filters, loading/error/empty states, pagination, and a visible read-only label when opening another trainer's course.

Keep Documents, Blueprint, and Assign as own-course authoring workspaces. Admin preview uses a read-only inspector for content, generation status, assignment rule/learners, and a performance link. Do not route another trainer's course through mutable global blueprint/assignment selection. Render edit, quiz update, generation, publish, disable, and delete controls from resource capabilities. Backend checks remain authoritative.

Display other trainers' courses as read-only with the confirmed creator-only explanation. If a disabled action/deep link or stale editor attempts a change, show that message and restore read-only state; the API performs no write. Do not show edit controls as enabled just to trigger an error.

In Assign -> Include panel, add a visually separate Observers section alongside learner selectors. Each observer card has an active employee picker, observed department multi-select and/or explicit employee selector, preview of eligible observed learners, and remove/scope-edit controls. Label it "Performance access only; this does not enroll the observer." Observer scopes apply only to this course. Learner include/exclude logic and match counts remain independent. Preview pending vs effective scope and apply/revoke effects clearly; block duplicate observers and empty scopes.

In LMS Employees, retain Dashboard, ordinary My Courses/My Learning, and Notifications. Add Performance for effective HOD/Observer access, and a Department Performance/Observed Performance shortcut if it fits existing dashboard components. A Performance deep link opens the correct scope; normal tile launch keeps the existing employee landing page. Employee My Courses means independently assigned learning and is different from Trainer course authoring. Do not expose Documents, document builder, Blueprint, course management, Assign, or generation controls to pure HOD/Observer users; forged deep links are denied. Ordinary employees receive no reporting entry. Combined authoring roles expose Trainer tabs only when justified by authoring capability. Available Trainer-app Performance choices: All Courses (Trainer/Admin default), My Courses (Trainer/Admin optional narrowing), My Department(s) (HOD), Observed Employees (Observer), and Combined only when it adds useful information; All Courses already includes the Trainer reporting union. Employee-app choices: My Department(s), Observed Employees, Combined of these contributions. A department selector is restricted to mapped departments for HOD and granted departments/eligible employees for Observer.

Extend Performance with role-specific/combined views and trainer filtering for Admin Trainer. Add creator attribution to report rows/course options. Explain the access source where useful; a learner appearing under several roles still yields one assignment row in Combined. Owner email links default to My Courses. HOD links resolve the new authorized department view, and any incompatible filter must be cleared with an explanation. URL parameters never grant a reporting scope. Admin/HOD/Observer access does not enable answer-key browsing; include completion, attempts, scores, and module performance metrics only.

Fix state lifecycle throughout course/detail, performance, assignment, documents, and generation providers:

1. Cache identity includes canonical employee/session identity, permissions version, selected report view, grant/mapping revisions as needed, filters, and page/cursor.
2. Clear privileged data on logout, user switch, downgrade, or invalid authentication. A same-ID role change still invalidates state.
3. Give each async request a generation counter/key; discard responses from old identities, scopes, filters, or roles. The current performance provider particularly needs this protection.
4. Refresh current permissions on startup, app focus, and 401/403; use a bounded refresh while oversight remains open. Server revocation takes effect on the next request; frontend refresh removes already rendered privileged data.
5. Opening/closing read-only preview does not mutate selection used for authoring or employee progress. Avoid background retries of denied mutations.

The employee app contains `trainer_preview` providers/screens. Confirm reachability; apply the same capability rules or remove the entry point. Existing employee learning identity remains; HOD team reports deliberately change from direct reports to authorized departments. HOD/Observer reporting is integrated into the Employee app rather than a separate management workspace. Preserve ordinary learner playback/progression when sharing reporting components.

## 8. Existing fixes to preserve and regression coverage

| Area | Required regression evidence |
| --- | --- |
| Hub launch/local development login | Signed app/session validation remains; local pickers remain development-only; no client role injection. |
| Directory sync | Stable identities, partial-update merge, soft-disable, and existing course/progress retention remain; authoring grants survive sync, and authoritative HOD mappings/membership reconcile correctly. |
| Assignment matching | Include/exclude groups, departments, mailing lists, new employees, deadlines, disable/re-enable, and saved-group ownership remain correct. |
| Learning and quiz grading | Assigned-only visibility, watched-video gate, linear module progression, server-side grading, attempts, completion, and WebSocket refresh remain. |
| Notifications | Owner trainer/direct-manager recipient scope, digest cadence, lifecycle dedupe, stale item cancellation, and authorized deep links remain. No automatic admin/observer CC; Observer-only changes produce no learner assignment emails. |
| SMTP | Verified TLS, explicit approved plaintext relay opt-in, no TLS fallback, single-mailbox envelope validation, and guarded UAT allowlist/test settings remain. |
| Generation | Queue limits, locks, failed checkpoints, continuation, thumbnail readiness/fallback, PPTX/image flows, TTS normalization, tracing, and artifacts remain. |
| Media/deployment | HLS/range playback, Nginx WebSocket-only upgrade handling, numeric container users, and current image pins remain. |
| Existing release notes | Re-run the historically failing image-slide test; do not call the whole suite green based on the old note. Re-scan final images if deployment files/dependencies change. |

Role visibility does not require changing SMTP relay settings, TTS configuration, container versions, or the durable generation queue architecture. Track unrelated failures and production-hardening work separately, with exact evidence and ownership.

## 9. Implementation order and reviewable checkpoints

| Checkpoint | Deliverables | Completion gate |
| --- | --- | --- |
| A. Integration and baseline | Preserve/checkpoint dirty Performance work; reconcile accepted release fixes on existing access branch; inventory all legacy/improved endpoints and deployed UI | Complete Performance fixes present, shared SBOM workspace untouched, all-course Trainer policy preserved; reproducible focused-test baseline. |
| B. Identity and access | Canonical principal, role-grant migration, audit/CLI, directory department/HOD contract, Employee-tile report discovery | Verified existing trainer entitlements preserved; HOD/Observer Employee login never grants authoring; directory mapping dependency resolved before HOD activation. |
| C. Access/read API | Central policy, owner-only mutations, scoped course library/detail/jobs/assignment reads | Direct API tests prove cross-owner read and write differences, including forged scopes. |
| D. HOD/Observer reports | Department-wide HOD scope, course-specific observer storage/revisions, shared scope across improved reports/details/options/exports, employee-summary SQL pagination | Course creator controls grants; cross-department observation works; no enrollment/duplicate rows; HOD scope and both CSV modes match screen filters. |
| E. Frontend and related fixes | Shared improved reporting components, both app adapters, principal/models, admin library, Observer Include section, scope selector, cache race fixes | Product UI preserved; HOD/Observer uses Employee tile with reporting and independent learning; normal employee has no report access; combined roles retain scoped access. |
| F. Files/media | Authorized documents, course media mapping/delivery, renderer compatibility | Direct URL tests and employee playback prove the advertised access boundary. |
| G. Release | Full regression results, UAT scenario, deployment/rollback runbook | Feature acceptance passes and remaining limitations/failures are explicitly recorded. |

Prefer small commits in this order on this branch. No approval workflow or cross-owner write feature is included implicitly. Coordinate schema/backend/frontend deployment so old clients keep working during the transition.

## 10. Verification and acceptance

Add backend API tests with Trainer A/B, Admin Trainer, pure HOD, pure Observer, combined Trainer+HOD+Observer, Employee, inactive identities, and unauthenticated caller. Exercise every report view and route through authentication. Add PostgreSQL integration tests for migrations, preserved grants, identity linking, HOD reconciliation, observer revisions, joins/counts, audit, and pagination.

Required cases:

- Trainer A cannot list/read B's authoring course content, assignment configuration, generation job, source document, or media through Trainer privileges. Trainer A can read B's eligible performance metrics, report details and exports. Reporting routes do not expose source content or quiz answer keys.
- Admin Trainer can read B's draft/ready/published/archived course and running/failed generation state, but cannot update quiz, edit, generate, resume, publish, assign, disable, or delete it.
- Admin Trainer still manages its own courses; another trainer's saved groups remain private.
- Anonymous document/media requests are rejected; learner requests remain published/assigned and cannot access trainer quiz answers.
- Grant/revoke and disabled identity are enforced with an already-issued session. Role survives Hub projection refresh, directory sync, and email/name changes without identity reassignment.
- Same-title courses stay separate; two modules and twenty assignments still count twenty assignments. Pagination does not alter totals or skip/duplicate stable results.
- HOD sees every eligible learner in its mapped departments, including learners reporting to another manager, across creators' courses. Unmapped departments and unverified HODs are denied. Department moves, renames, partial sync, explicit HOD removal, multiple mapped departments, and disabled HODs are covered.
- Observer sees only eligible employee/course pairs on its effective grants, including cross-department employees. Forged course/department IDs, unassigned learners, draft courses, revoked grants, pending additions, empty selections, duplicate grants, and inactive observers do not widen access.
- Course owner alone can add/change/revoke observers. Admin Trainer cannot modify another creator's grants. Observer configuration is separate from learner include/exclude rules; omitted legacy fields preserve grants and explicit empty configuration revokes them.
- Grant-only edits do not create assignments/emails, change deadlines, or reset progress. Failed publication cannot activate pending observation access. Revision conflicts are rejected without overwriting a concurrent owner's change.
- Pure HOD/Observer cannot access any authoring API or media via management privileges. Management login and development role simulation cannot silently create authoring entitlements.
- Opening the same Employee tile as a normal employee, mapped HOD, active Observer, and HOD+Observer produces the appropriate navigation from backend capabilities. No role picker is present in production. Learning and Notifications continue for each. Revoking the last grant removes only the reporting entry/capability.
- Every legacy and improved report endpoint, course/employee/assignment detail, filter-options query, and both CSV modes enforce identical scope. The `16adda0` broad-trainer route remains available only to active authenticated Trainers. Existing broad-access tests remain; new improved report paths follow the same all-course policy. Normal employees/HOD/Observers cannot invoke this Trainer privilege.
- Employee-summary and assignment export follow the selected view, submitted search/attention filters, and report mode. Out-of-scope employee/course/assignment IDs are denied even if a valid object ID is known. Revocation/directory moves during multi-request export stop unauthorized later chunks.
- PostgreSQL employee grouping and page totals match scoped assignment calculations; requests for one employee do not load all authorized assignments into Python. Empty scopes, overlapping department grants, multiple course creators, same-title courses, and multiple assignments for one employee are covered.
- Trainer and Employee sessions remain audience-isolated. Shared report UI gets authenticated data only through its app adapter. Docker and CI build both frontends with the local package and accepted dependency/font changes.
- Combined views deduplicate overlapping assignment IDs, retain distinct courses for one employee, and expose only authorized filter options/module details. Removing one role/grant preserves independent allowed scopes.
- Admin preview never writes learning progress, course content, assignment rules, or generation state.
- Flutter tests simulate logout, same-ID role downgrade, user/scope switch, and out-of-order responses with no stale privileged content.
- Published edit/no-op behavior and edit/delete while generation runs follow the specified lifecycle rule without losing learner history.

Run the focused auth/Hub, analytics, directory, assignment, course-authoring/deletion, generation-queue, quiz, email, and HLS suites first, then the full backend suite. Run Ruff on changed backend files and `flutter analyze` plus relevant tests/builds for both frontends. Media authorization requires browser playback checks through the deployed proxy, not only unit tests.

UAT example: Karneeshkar creates Excel Basics and assigns twenty Finance/Operations employees. He adds Neha as Observer for Operations on that course. Another trainer creates a same-title published course and a failed draft. Kiran opens LMS Trainer and sees all courses and published-course performance; her attempt to edit Karneeshkar's course returns the creator-only message. Karneeshkar also sees all eligible published-course performance, but cannot open/manage another trainer’s course content or Observer configuration. Neha opens LMS Employees -> Performance -> Observed Employees and sees eligible Operations learners only on Excel Basics, with no authoring or automatic enrollment. Finance HOD Meera opens LMS Employees -> Performance -> My Department and sees all Finance learners across both published courses, including learners managed by Suresh. Normal employee Rahul opens the same tile and has only ordinary learning features. All these users retain their own independently assigned learning. Grant Karneeshkar HOD and Observer access for another creator's course: his authoring remains own-only and Trainer-app Combined deduplicates report rows. Compare common HOD/Observer scopes across apps. Export employee summaries and assignments after filtering, open every detail type, revoke Neha's grant and reassign the HOD through directory sync: access refresh removes old scopes without resetting employee progress. Repeat user/scope switches with delayed network responses. Verify learner completion, owner/HOD email delivery, and generation resume separately.

## 11. Rollout and rollback

1. Follow section 0 and verify branch lineage against the deployment's tested base. This branch originally included `35c4ce7`; include complete reviewed Performance work and accepted newer fixes without losing security/SMTP/SBOM changes. Explicitly preserve the all-course Trainer report policy from `16adda0`.
2. Back up database and storage; run the additive migration in staging. Do not reset data.
3. Deploy backend with verified existing authoring entitlements preserved and no new automatic privileges, then both frontend changes. Enable authoritative HOD sync and Employee-app reporting. Both Hub tile audiences remain intact; HOD/Observer needs no Trainer-tile entitlement. Apply media/proxy changes after renderer/playback checks. Keep new report paths capability-gated until their migration and policy are ready.
4. Provision Kiran by verified stable identity through the operations CLI. Publish a controlled Observer grant and verify department-wide HOD mappings; run all four-role and combined-role UAT cases.
5. Log denied permissions and role changes without tokens or source content; monitor API/query latency, stale UI responses, job failures, playback errors, and notification delivery.
6. To disable the feature, suspend new admin/HOD/Observer reporting paths and grants while keeping established owner authoring entitlements and ordinary employee learning. Leave additive tables/audit intact; restore database/storage only for a verified data issue. Retain the explicit authoring capability guard and active-Trainer authentication guard on legacy and improved reports during rollback; all-course Trainer reporting is an intentional preserved behavior. Do not silently restore direct-report HOD reporting as department-wide reporting. Coordinate shared-package/both-frontend/media/proxy rollback and document any restored public exposure.

Release completion means: Kiran oversees all in-scope courses/performance with creator-only changes; Trainers author/read their own courses; HOD sees mapped departments; Observer sees effective course-specific learner scope; all active Trainers retain all-course reporting; combined employee roles union reporting without enlarging authoring rights. Directory mapping/Hub launch dependencies, migrations, grant lifecycle, regressions, and rollback are verified; any media limitations are stated accurately.

## 12. File-level implementation map

| Area | Existing files and proposed additions |
| --- | --- |
| Identity, Hub, capabilities | `services/auth.py`, `api/auth.py`, `api/hub.py`, `security/hub_launch.py`, trainer/employee schemas; proposed `services/lms_access.py`, access principal schema, `api/lms_access.py`. Preserve signature/audience checks. |
| Persistence/provisioning | `repositories/schema.py`, trainer/employee repositories; new access-role, department/HOD, observer-grant, audit repositories; migration runner and role operations script. |
| Directory mapping | `services/directory_sync.py`, employee schemas/repository, directory sync tests; normalize authoritative department IDs and HOD mapping without replacing existing manager fields. |
| Course/assignment policy | Course, assignment, upload, generation APIs/services; course/assignment schemas; central read-vs-manage policy and observer request/response schema. |
| Performance | `api/analytics.py`, legacy analytics service/schema plus integrated `repositories/performance_reporting.py`, `services/performance_reporting.py`, `schemas/performance_reporting.py`; shared scoped relation, both app route families, summaries/details/options and CSV. |
| Frontend | Trainer models/auth/course/assignment providers, `features/dashboard_page.dart`, course/assignment portals, integrated `performance_report_portal.dart`, employee-summary/assignment components and report providers; canonical principal and read-only state. |
| Shared reporting UI | Proposed `packages/lms_performance_ui`, both `pubspec.yaml` files, Docker build contexts/CI; report models/components with injected app API adapters and existing theme. |
| Employee app | Auth/session models, `features/dashboard/employee_dashboard_page.dart`, report navigation/scope/deep links, reporting adapter, any reachable trainer preview; preserve ordinary learning identity and progression. |
| Files/media | Upload routes/services, asset mounting/delivery in `main.py`, static asset APIs, renderer/player URLs, streaming/proxy checks. |
| Verification | Existing Hub, directory, analytics, assignment, authoring/deletion, email, generation, quiz, HLS suites; new access matrix, observer, migration/integration, and frontend race/role tests. |

Resolved product decisions are recorded in section 1. Remaining integration inputs are the authoritative directory HOD/department association, verified existing Trainer/Kiran identities and entitlements, and the accepted deployed release/complete Performance work to integrate. Employee-tile reporting is the agreed launch path; report-only Trainer-tile provisioning is no longer a dependency. Pending grant activation, dynamic department selectors, and active-assignment Observer eligibility are implementation defaults proposed here; they are not additional user-confirmed business requirements. Implement them with visible apply/revoke behavior and verify in UAT.

## 13. Error-prevention gates and implementation handoff

No plan can guarantee zero mistakes. Require evidence at each checkpoint and halt the affected rollout when its gate fails; independent implementation work can continue.

Before coding: verify complete branch/worktree inventory and accepted base; capture deployed Trainer/Employee UI for comparison; enumerate every read/write/report/export/media endpoint in the integrated code; specify eligibility/metric semantics using the existing improved report behavior; obtain representative authoritative HOD mapping data. If HOD mapping is unavailable, build/test with explicit fixtures and keep production HOD capability disabled; do not infer leadership or silently substitute manager reports.

Before migration: take and test a staging backup/restore, inventory identities/course ownership, dry-run grant backfill with zero ambiguous automatic promotions, compare before/after row counts and identifiers for courses, assignments, progress, outbox, and documents. Migration must be repeatable and additive. Validate foreign keys/indexes and directory partial-update/removal semantics on PostgreSQL.

Before frontend integration: backend API matrix must distinguish own-course manage, all-course admin read, HOD department reports, and Observer course/learner reports; legacy all-course Trainer routes must remain authenticated and must not grant employee-app reporting callers Trainer privileges. Confirm effective/pending Observer revisions and restrictive updates are atomic and stale saves return 409. Do not rely on disabled UI controls as authorization.

Before release: run integrated focused tests and full backend suite, Ruff, analyzer/tests/release builds for both Flutter apps, real browser tests through the intended proxy/Hub launches, export/filter comparisons, permission downgrade/race tests, and renderer/playback regression checks. Compare UI to the deployed product rather than accepting the prototype as a replacement. Record actual commands/results, unresolved failures, query plans/representative data sizes, and rollback rehearsal. Prior branch/session test counts do not establish current integration correctness.

Reviewable implementation commits should follow checkpoints A-G, with the permission/API contract reviewed before UI wiring and migration/backfill reviewed before staging deployment. Each commit/PR description states the behavior changed, evidence, and limitations. Preserve course ownership, generated content, assignments, learner history, notifications, and accepted unrelated fixes. Production provisioning, pushing, merging to the release branch, and deployment have not occurred. Implementation starts with the isolated integration checkpoint recorded below.


## 14. Implementation progress: checkpoint 1 (6 October 2026)

Completed in the attached `admin-trainer-visibility` checkout on `codex/admin-trainer-oversight`: integrated the committed Performance branch and a preserved snapshot of its pending fixes; carried forward committed SMTP/TTS fixes from `16adda0`; added an explicit authenticated all-course reporting scope across improved reporting lists, summaries, details, options and exports; separated same-title course overview groups by course ID; rechecked authentication before subsequent streamed CSV pages. Original Performance worktree and the shared SBOM workspace were not switched or modified.

Verified: 136 focused reporting/SMTP/TTS tests, 15 read-only PostgreSQL reporting comparisons, 12 Trainer frontend tests, targeted Flutter analyzer and both frontend release builds. Final combined backend suite: 229 passed, one known failure in `test_splits_third_landscape_image_to_separate_slide` (expected 3 slides, got 4); generation source and this test are unchanged from `16adda0`. Ruff passed for the affected reporting code/tests. SMTP notifications/templates/settings, TTS configuration and deployment files have zero diff from the accepted `16adda0` baseline.

Local builds used the existing Flutter 3.24 toolchain and ignored localhost `.env` files. Generated lockfile resolution changes were restored rather than committed; accepted dependency declarations/locks remain intact. Release validation must rerun with the final deployed toolchain/accepted SBOM changes. No actual email was sent and no production directory sync, migration, provisioning or deployment was performed.

Next checkpoints remain: persistent roles/capability discovery and authoritative HOD contract; admin cross-owner read-only library; HOD/Observer storage, revisioned grants and scoped Employee reports; shared role-aware frontend components; protected document/media delivery; full release UAT/rollback. This checkpoint is not completion of the four-role feature. See `docs/admin-trainer-implementation-progress.md` for the execution record.


## 15. Implementation progress: checkpoint 2 (6 October 2026)

Added additive access migration/ledger, stable-identity-bound Admin grants with atomic audit/versioning, operations-only inspect/grant/revoke CLI, and audience-validated `GET /api/lms/me?app=trainer|employee`. Existing normal Trainer entitlement and all-course reporting remain unchanged. Roles/version are read in a single database statement; current-session capability refresh observes Admin revocation. Employee sessions cannot inherit Trainer/Admin reporting from stored grants. HOD/Observer flags remain disabled pending their mappings/grants; no leadership is inferred from directory department/manager/title.

Validated 152 focused access/Hub/reporting/SMTP/TTS tests, including ten transaction-isolated PostgreSQL grant/migration tests. The last full backend run had 253 passing tests and the same unchanged image-slide failure; the subsequently added production-mode Hub discovery test passed in the final focused run. Ruff passed. No existing auth/login response shapes, reporting code, SMTP/TTS, deployment files or frontend files changed in this checkpoint. Temporary test schemas and grants are rolled back; no person was provisioned. The Admin library, HOD/Observer reporting, frontend capability consumption and production HOD contract remain upcoming work. Operations procedure: `docs/admin-trainer-access-operations.md`.


## 16. Checkpoint 3 implementation record (6 October 2026)

Admin oversight APIs now read fresh stable-identity-bound grants for cross-owner/all-scope requests. Added bounded course-library metadata with creator/status/generation/search filters and deterministic offset pagination, authorized course inspection metadata, assignment configuration and generation monitoring, and a course-fixed assigned-learner report wrapper. Normal Trainer Performance remains deployment-wide for eligible published courses. Cross-owner authoring/configuration/generation mutations deny current Admins with the required creator-only message; the existing mutation services still enforce the original creator identity. Existing own-course listing stays compatible.

Version-one library pagination uses offset/limit (50 by default, 100 maximum) and a single-statement filtered total/page snapshot; it does not freeze a library across several requests. Counts and summary cards for assigned learners reuse existing course-filtered Performance APIs. New frontend controls and role refresh/cache isolation are pending the UI stage; public/document/media access hardening remains a later required stage. No actual Admin provisioning or production changes occurred.

Validation: 111 focused oversight/shared Performance/PostgreSQL checks passed; full backend suite 306 passed and the same unchanged image-slide failure; Ruff passed. See `admin-trainer-implementation-progress.md` for endpoint and preservation details. Next stage is Observer grant storage and apply/revoke behavior. Authoritative HOD mapping remains a production activation prerequisite.
