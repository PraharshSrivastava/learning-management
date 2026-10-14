# Enable/Disable lifecycle simplification

Status: implemented locally; verification recorded below. Not pushed or deployed.
Date: 12 October 2026.
Branch: codex/observer-performance-parity. Deployed baseline: 71584a5.

This follow-up supersedes Archive/Restore UI and lifecycle recommendations in the original implementation plan. Observer Performance search parity, access boundaries and historical reporting remain required.

## Final trainer experience

| State | Assign primary action | Actions menu |
| --- | --- | --- |
| Draft | Prepare/generate content as today | Delete only when eligible |
| Ready, never published | Publish & Assign | Delete only when eligible |
| Active | Update Assignments | Disable |
| Disabled | Enable | Enable (opens the same assignment review) |

Keep the existing Actions menu. Use Active/Disabled availability labels alongside Draft/Ready preparation states. Remove Archive/Restore from menus, banners, confirmations and normal course/report filters. Keep all historical reporting inside Performance, using Active/Disabled/All filters. Delete remains permanently restricted to creator-owned, never-assigned Draft/Ready courses with no pending/running generation. Employee Exclusions remains the individual withdrawal mechanism.

Disable confirmation: "Employees will lose course access. Progress and results will remain saved. Observer access will be suspended." Include the existing real employee/Observer impact counts. Enable opens Assign, previews current matches and the deadline, and requires confirmation. It must not blindly toggle a flag. Observer selections are retained but Apply Observers remains explicit.

## Verified scope

- Trainer course_actions_menu.dart currently offers Archive/Restore and dispatches them directly to the lifecycle endpoint.
- Courses, All Courses library and Assign have archive filters, read-only branches, banners and provider eligibility checks.
- Both Performance clients offer an Archived availability option; backend report scope/predicates and row access reasons recognize it.
- course_lifecycle.py owns archive/restore transitions; courses, generation and jobs contain archived-content guards. Course status and assignment-rule activity are separate storage fields.
- Enable already uses api_publish_course_assignment with preview, expected revision, reconciliation, deadline handling and audit; preserve that operation.
- Read-only VM inventory on 12 October: no archived courses; 11 published active and 1 published disabled. Ready courses with an active draft rule are still Ready, not Active. Availability must continue to depend on publication, not the rule flag alone.

## Implementation sequence

1. Add a NEW versioned, transactional, idempotent migration; do not modify/replay 20261009_course_lifecycle_v1. For archived courses, preserve content and prior audit, return storage status to published while keeping assignment rules disabled, assignment withdrawals intact and Observer grants suspended. Validate published assignment evidence; fail with a diagnostic if an anomalous archived record cannot safely become Disabled. Increment lifecycle revision and append a system migration audit entry so old tabs cannot mutate using stale revisions. Never enroll employees, clear withdrawals, reset deadlines, send mail or reactivate Observers. Back up and compare affected-row/history counts.
2. Enforce the simplified backend contract: Disable uses the existing transaction, ownership, generation and revision guards; Enable continues through reviewed publish/reconciliation. Reject new Archive mutations with a clear unsupported-action/refresh message, including old-client requests. Remove Restore from the advertised API; retain only any explicitly needed compatibility handler, never a public second workflow. Preserve legacy schema/status parsing and historical audit strings where needed for old data rather than dropping tables or rewriting audit history.
3. Update Trainer UI and providers together: remove Archive/Restore menu entries and descriptions; remove archive-only read-only presentation and filters after normalization; keep Disabled content editable and generation guarded as appropriate. Use the same Enable review from Courses and Assign. Refresh selected-course, list, assignment and report caches after actions. All Courses read-only users still cannot mutate creator courses. Do not rename unrelated Published/generation storage statuses globally.
4. Update both Performance clients, backend queries/scopes and exports: Active/Disabled/All options; include converted historical records under Disabled/All with correct unavailable labels. Define legacy archived filter compatibility explicitly (normalize to Disabled), and reset/remap cached selectors so old contexts do not crash or hide records. Retain original archive audit/access reasons as historical evidence. HOD/Observer/Combined authorization must remain identical; unavailable history does not restore revoked Observer scope.
5. Replace lifecycle/UI tests with Active -> Disable -> Disabled -> Enable -> Active cases; retain migration fixtures for archived records. Verify completion/answers/attempts/deadlines, explicit Observer reapply, published snapshot isolation from Save Rule, creator-only changes, stale revisions, generation conflicts, unused Delete and one-connection pool behavior. Verify old Archive requests cannot create new archived records and migration runs once without reopening access. Verify both client filters, report details/CSV totals, noncreator read-only UI and no visible Archive/Restore workflow.
6. Run appropriate backend and real-PostgreSQL suites, Trainer/Employee focused tests and both production web builds. Preserve maintained-priority-runtime, security patches, dependency locks and the pinned Poppler snapshot. Commit/push after checks; build new tagged images and run fresh security scans. Deploy coding VM first with existing Compose overlays and backup; repeat authenticated role/lifecycle/playback/report UAT. On-prem UAT follows passing VM checks and documented known findings.


## Filter Reports panel: additional approved changes

Apply to both Trainer and Employee/Observer Performance, including HOD and Combined views wherever these five controls appear. Preserve the existing LMS theme and all report behavior.

Verified cause: each portal computes four columns at desktop width and places five controls inside Wrap; Joined within days therefore wraps. Course availability uses a default DropdownButtonFormField while searchable selectors use custom OutlinedButtons, producing inconsistent font sizes, labels, borders and heights. The centered dot in "All · includes history" is literal display copy, not a status indicator.

1. Use one nonwrapping horizontal row, ordered Course availability, Course, Department, Mailing list, Joined within days. Allocate five columns from the actual panel width (subtract four consistent gaps before dividing). Align tops/bottoms, padding and a common fixed/minimum control height. Joined within days must stay in the same row; do not add redundant panel height for a second line.
2. On desktop at the supplied screenshot width, all five controls must fit without scrolling. At narrower widths or larger text scaling, keep the row and allow horizontal scrolling within the filter panel with an accessible visible scrollbar; do not wrap, clip the final input, overflow the page or shrink text to force a fit. Use a readable minimum control width; verify keyboard traversal and scroll-to-focused-control behavior.
3. Use shared explicit typography/style tokens across availability, searchable selectors and the joined-days input: the existing font family, a consistent 13px selected-value/input size and weight, 11px caption-label size and weight, matching hint style, icon sizes, border treatment, corner radius and control height. Labels should consistently appear above values inside each control, including Course availability and Joined within days. The joined-days field retains numeric entry, existing submission/clear behavior and an understandable empty hint. Labels and values may differ by hierarchy, but each hierarchy is identical across all five controls. Long selected values truncate with a full-value tooltip; avoid increasing row height.
4. Replace "All · includes history" with "All courses". Course availability choices are "All courses", "Active", "Disabled" after lifecycle simplification. Keep internal API value all and all existing authorization/history semantics; do not turn it into an unrestricted scope or remove history. Put explanation in the availability tooltip/help: "Includes active and disabled courses and retained learning records." Do not put punctuation separators or historical-report jargon in the option label.
5. Preserve Course/Department/Mailing list searchable dialogs, selection guards, report resets, active-filter counts, Clear all, debounce, course pagination and CSV/detail scope. Course availability remains distinct from course-name selection. Do not reset filters just because layout changes.
6. Validate both clients at screenshot-equivalent desktop width, common laptop width, narrow viewport and increased text scale. Assert five controls share a row on desktop and remain one scrollable row when narrow, typography/height agree, no overflow occurs, keyboard access works, and All courses still includes permitted disabled/history rows. Include long course/department/group names and joined-days entry. These checks are added to the lifecycle verification and VM acceptance gate.

Implementation order: perform this layout/copy work alongside the two-client Performance filter changes in step 4, before the tests/builds in steps 5-6. The UI implementation is complete locally; no VM deployment has been performed.

## Acceptance gate

No Archive/Restore choice remains in the normal trainer workflow. Active/Disabled accurately reflect access. Previously archived records are Disabled and retain all history. Only explicit reviewed Enable reopens learning; Observer access remains suspended until Apply Observers. Historical reporting remains available to authorized viewers. No data reset or automatic deployment is part of preparing this plan.

## Implementation and verification record

- Lifecycle API now advertises only Disable. Archive/Restore requests are rejected; Enable continues through assignment review and publish/reconciliation. Normal menus and filters omit Archive/Restore.
- New migration 20261012_enable_disable_v1 runs after access tables exist. It validates archived publication evidence, preserves learning/history, suspends access, increments revisions and records archived_to_disabled audit. Startup and rerun idempotence are covered. Legacy archive read-only server guards remain as a defensive check for anomalous/unmigrated data; normal migrated records use Disabled and editable content. Old archived report URLs normalize to Disabled without expanding authorization.
- Both filter panels now use five aligned controls, a minimum readable width and a horizontal scrollbar on narrow views. Shared label/value styles and height scale with accessibility text size. All courses replaces All · includes history; help text explains retained records. Joined-days numeric entry and search/scope behavior are preserved.
- Migration testing uncovered mixed naive/offset timestamp subtraction in deadline reactivation. Enable now normalizes both formats before calculating remaining time; real PostgreSQL tests exercise the case.
- Backend regression: 356 passed, 75 explicit integration skips, one previously documented image-slide assertion failure. Isolated PostgreSQL: 56 passed across migration/startup, retained completion, lifecycle, snapshot, access, media and library suites. Ruff checks on changed Python files pass.
- Trainer tests: 45 passed. Employee focused tests: 23 passed. Both production web builds pass using Docker build flags. Row tests cover desktop alignment, narrow scrolling, 2x text size and joined-days submission.
- Security Dockerfiles, source hashes and dependency locks were not changed by this follow-up. New container builds/scans and authenticated proxy/Hub VM acceptance remain required after pushing. The existing video-player analyzer finding and image-slide baseline issue remain documented.
