# LMS Performance parity and course lifecycle: implementation plan

> Local follow-up implemented (not pushed/deployed): the user approved simplifying the trainer workflow to Enable/Disable. See [Enable/Disable simplification plan](enable-disable-simplification-plan.md); it supersedes the Archive/Restore recommendations below. The deployed baseline still has the original lifecycle UI.

Status: implementation completed on this branch; automated verification recorded below. Live authenticated browser UAT and release sign-off remain pending.
Updated: 12 October 2026.
Branch: `codex/observer-performance-parity`.
Base: local `codex/lms-sbom-release`, commit `8876a34ccbacc7027bca995fc2ed9a0633fe8bac`.
Workspace: `C:/Users/LPUSER/.codex/worktrees/observer-performance-parity/LMS_V1`.

## Objective and approved scope

Implement two connected improvements:

1. Bring Employee Observer/HOD Performance search into parity with Trainer: searchable Course, Department and Mailing list selectors; course-name/ID search with pagination; automatic employee-report search.
2. Integrate the approved course action menu into the existing Trainer UI, with reversible Disable/Enable, Archive/Restore, permanent deletion restricted to unused courses, employee exclusions that withdraw access without destroying learning history, and historical records in the existing Performance tab.

Preserve creator-only course mutation. Admin Trainer retains read-only access to other creators' content. All authenticated active Trainers retain All Courses/My Courses reporting. Observer access remains course-specific; HOD access remains mapped to authorized departments; Combined is their deduplicated union. Improvements to the shared Employee Performance portal also apply to authorized HOD/Combined views. Employee sessions must never acquire Trainer All Courses/My Courses visibility or authoring controls.

The approved interaction uses an action menu, not a row of separate destructive buttons. Employee Exclusions handles individual removals; do not add a separate Revoke employee action. Do not add View historical reports to the action menu: reporting belongs in the existing app-wide Performance tab. Keep Apply Observers as a separate explicit operation.

## UI reference and current layout

Approved preview: `C:/Users/LPUSER/.codex/visualizations/2026/10/09/01a11f7d-e6e5-7bd2-9d32-098d4e29a5de/lms-existing-layout-actions.html`.

This is an interactive design reference with sample data, not an implemented screen or a captured authenticated LMS session. It supersedes the earlier previews that placed navigation tabs inside a course.

The existing UI was inspected through `frontend/lib/features/dashboard_page.dart`, `features/assignments/assignment_portal.dart`, `features/courses/course_portal.dart`, `features/performance/performance_report_portal.dart` and `core/theme/app_theme.dart`:

- Preserve app-wide Documents, Blueprint, Courses, Assign and Performance tabs.
- Preserve Assign's left Assignable Courses list and right Assign Course panel; do not replace the application shell with per-course Content/Assign/Performance tabs.
- Preserve the stacked sections: Target Employees, Performance Observers, Employee Exclusions, Completion Deadline and Assignment Preview. Keep existing employee selectors, saved groups, relative/fixed deadlines, preview pagination and refresh behavior.
- Preserve PhillipCapital styling: primary blue `#00317A`, existing typography, rounded white cards, blue/pink/gray section strips, pill-shaped buttons and responsive layout.
- Add the Course actions menu near the selected course's existing header, accessible in Courses/Assign as appropriate. It must act on the explicitly selected course and respect read-only mode.
- Courses retains its existing course list/content layout; add a status filter including Archived. Performance remains the separate global reporting screen.
- The prototype's simplified selectors/sample data do not authorize replacing the real assignment controls, reducing report functionality or using fabricated counts in product UI.

## Verified gaps in current code

- Trainer Performance uses `SearchableReportFilter` for Course, Department and Mailing list; Employee Performance still uses plain `_Drop` controls.
- Trainer course reporting uses `CourseReportBrowser` with local name/ID search and 12-card pages; Employee renders all cards without this browser.
- Trainer employee-report search debounces for 350 ms and supports immediate Enter; Employee currently submits only on Enter.
- Employee reporting providers already own view, filters, search, pagination, reset version and permission-aware context; existing `ReportAccessGuard` protects report details.
- Disable currently marks every assignment revoked, including completed assignments, and suspends course Observers. Progress data is retained, but published/active/nonrevoked reporting predicates hide these records.
- Applying employee-rule changes currently skips completed assignments during exclusion-based removal. Save Rule alone does not immediately reconcile existing assignments.
- Delete currently permits creator-owned published courses and cascades through assignments/progress, except when generation is pending/running. The UI warns about this loss; the new policy must also be enforced on the server.
- Archive/Restore and course-status historical reporting are proposed additions, not existing functionality.

## Approved states, actions and placement

| Course state | Primary action in Assign | Course actions menu | Reporting |
|---|---|---|---|
| Ready, never assigned | Publish & Assign | Delete permanently, only when deletion eligibility passes | No assignment history yet |
| Active | Update Assignments | Disable, Archive | Current records; excluded employees retained in history |
| Disabled | Enable | Enable, Archive | Historical learning records remain accessible |
| Archived | None; assignment controls read-only | Restore | Historical learning records remain accessible |

Unused drafts may also be deleted when generation is not pending/running. Content preparation still controls whether Publish & Assign is enabled. Existing creator/read-only rules apply to every row. Menu actions and Assign's primary action may expose the same Enable operation in context; implement one backend operation and consistent confirmation.

State transitions:

- Ready -> Publish & Assign -> Active.
- Active -> Disable -> Disabled; Disabled -> Enable -> Active.
- Active or Disabled -> Archive -> Archived.
- Archived -> Restore -> Disabled; review employee rules -> Enable -> Active.
- Unused draft/ready -> Delete permanently -> removed, with no normal recovery action.

Restore must never automatically reopen learner access, enroll employees, resume reminders or reactivate Observers. Use the short label Restore; explain its disabled result in the confirmation and success message. Archive need not require Disable first. Delete need not require Disable/Archive first, but must reject courses with assignment history.

## Stage 1: contracts, lifecycle and data model

1. Recheck current integration-target changes before implementation; preserve newer work instead of copying whole files over it.
2. Inventory current course status, assignment-rule activity, revoked progress payloads, deadline restoration, grants, content authorization, report predicates and notification jobs.
3. Define a single derived public lifecycle state shared by UI/API. Keep content readiness/generation state separate from availability. Prefer additive lifecycle metadata (archive timestamp/actor and necessary state/version fields); do not overload generation statuses or replace them without a migration design.
4. Separate assignment access from recorded learning status. Completed remains completed even when course access is withdrawn; progress, quiz scores, completion dates and learning events must survive Disable, Archive and Exclusions.
5. Plan backward-compatible migration for existing revoked records. Recover learning state only from reliable stored prior status/progress/completion evidence; do not invent completion history. Preserve older reasons/timestamps and document unrecoverable cases.
6. Define optimistic concurrency/version checks and audit entries for Disable, Enable, Archive, Restore and Delete. Use the same course lock/transaction boundary as assignment and Observer writers. Prevent stale or concurrent operations from restoring access or deleting a newly assigned course.
7. Verify all authorized filter options/course summaries are complete. Respect endpoint pagination before claiming full-list local search. Confirm employee search matches name, employee ID and course.
8. Finalize request/response fields for lifecycle, access availability/reason, actual mutation counts and historical inclusion; update models in both clients without breaking existing API consumers.

## Stage 2: Observer Performance search parity

1. Adapt Trainer `searchable_report_filter.dart` into Employee with Employee imports/theme. Replace Course, Department and Mailing list dropdowns, preserving widths, callbacks, selected values, active-filter counts and Clear filters behavior.
2. Match dialog behavior: label/key search using case-insensitive all-word matching, lazy results, matching count, selection checkmark, clear search, scoped All, Cancel and no-match state. Typing searches options locally; selecting changes the report.
3. Guard open selectors using the captured Employee report context and `ReportAccessGuard`; reject stale returned selections. All always means the current authorized scope.
4. Adapt `course_report_browser.dart`: local name/ID search, clear, matching counts, 12-card pages, previous/next, loading and no-match states, existing responsive cards/detail callbacks.
5. Keep course search independent of employee search/global filters/exports. Reset on identity, permission, report-view or Clear filters changes; reset page on query change and clamp it when results shrink.
6. Add a cancellable 350 ms employee-search debounce. Trim text, submit Enter immediately without a delayed duplicate and reset report pagination using the existing notifier.
7. Cancel delayed work on disposal, context/view changes and Clear filters; preserve stale-response protection, quick statuses, details, filters and exports.

## Stage 3: Disable/Enable and Archive/Restore

1. Disable atomically makes assignments unavailable, blocks new automatic assignments and suspends Observer grants. Retain content and recorded learning states/history. Keep the course in normal Trainer lists with a Disabled badge.
2. Archive performs the same access withdrawal and moves the course to Archived lists. Keep content, employee rules, Observer configuration and learning records. Archived assignment controls are read-only until restored.
3. Restore removes archive state and returns the course to Disabled. Preserve rules and history; require review and Enable before access resumes.
4. Enable validates creator permission, readiness, current employee eligibility/exclusions, learner/Observer separation and deadlines. Restore access only to currently eligible employees and preserve their recorded progress. Apply existing deadline/reactivation policy consistently and explain any changed deadlines before confirmation; do not reset completed learning or silently start a new training cycle.
5. Keep saved Observers suspended after Enable/Restore until explicit Apply Observers; preserve current save/restriction/revocation semantics and backend activation prerequisites.
6. Check learner APIs, lists, progress writes and private media/document authorization against access availability and archive state. Hiding a course in UI must not leave direct URLs accessible.
7. Block reconciliation and assignment/reminder jobs for disabled/archived courses. Preserve existing SMTP infrastructure and intended recipient rules; prevent duplicate new-assignment notifications for unchanged employees. Check queued notification behavior at delivery time where required by current contracts.
8. Return truthful assigned/reactivated/removed/deadline-update counts and success messages. Refresh affected lists, selection and capabilities without displaying stale success under another course.

## Stage 4: Employee Exclusions and permanent deletion

1. Keep Employee Exclusions as the sole individual access-removal workflow. Applying Update Assignments withdraws excluded employees' access, including completed employees, while preserving their learning history.
2. Exclusions take precedence over explicit employee, department, mailing list and other include matches; automatic reconciliation cannot reassign an excluded person.
3. Save Rule saves configuration only; immediately applying access changes requires Update Assignments (or Publish & Assign/Enable in the appropriate state). Keep this distinction explicit and test background reconciliation so saved rules do not unexpectedly apply destructive access changes before the intended action.
4. Removing an exclusion can restore eligibility on the next explicit application using the established assignment policy. Preserve saved learning results; do not implicitly restart completion.
5. Enforce Delete eligibility in the backend, not just in the menu: creator-owned, no current or historical assignments/progress, and no pending/running generation. Check dependent learning history even if no currently active enrollment remains.
6. Reject permanent deletion of a course with assignment history with a clear Use Archive explanation. No broad delete-anyway exception is included in this scope.
7. Eligible deletion removes the course and generated artifacts, retains the uploaded source document and uses the existing cleanup-failure reporting strategy. Require a confirmation naming the course and explicit DELETE input for this irreversible action.

## Stage 5: historical reporting and authorization

1. Extend the existing Performance tab in both clients with a Course status filter: Active, Disabled, Archived and All course states. Default to Active to preserve normal reporting behavior; users deliberately choose other states to view history.
2. Retain Overview, Courses and Employees reporting views, current selectors/search, detail drilldowns, sorting/pagination and CSV exports. Apply lifecycle filters consistently across options, summaries, details and both exports; a lifecycle filter must not be confused with learning-status chips such as Completed/Overdue.
3. Display learning status and course access separately. Excluded/disabled/archived records retain actual progress/completion, with an unavailable-access reason. Include retained unavailable assignments when viewing history; summaries must clearly distinguish eligible/current assignments from historical records.
4. Refactor the shared published/active/nonrevoked predicates deliberately rather than removing them globally. Learner-access queries still exclude unavailable assignments; authenticated report queries may include retained history only under an explicitly authorized reporting mode/filter.
5. Apply current permissions to historical reads. Trainers retain established all-course reporting; HOD remains restricted to authorized departments; Observer remains restricted to currently effective course-specific grants. Suspension/revocation must not be bypassed by selecting Disabled, Archived or All course states.
6. A suspended Observer cannot regain that course's historical data merely through a status filter. A person with independent HOD authority may retain only the rows authorized by that authority. Combined remains an OR union with each assignment counted once, including retained historical rows.
7. Inspect all direct detail, options and CSV paths for scope widening. Preserve identity/grant checks, export-page authorization and permission/membership cache isolation. Reset filters/search/open dialogs when context changes.
8. Show lifecycle badges in Courses/Assignable Courses and appropriate Archived filtering. Do not add a redundant historical-report action to the course menu.

## Stage 6: integrate the approved UI

1. Use the existing dashboard shell and source components. Add a selected-course action menu in the current header/toolbar instead of inventing another navigation hierarchy.
2. Assign keeps Save Rule, coordinated Refresh and the state-appropriate primary action: Publish & Assign, Update Assignments or Enable. Menu contents derive from current server lifecycle and deletion eligibility, never from guessed client status.
3. Courses uses the same lifecycle operations/action availability and provides Archived filtering; Restore transitions to Disabled and updates the selected course in Assign.
4. Preserve creator/read-only behavior, existing selection widgets, previews, observers, deadline controls, section order and narrow-width wrapping. Keep course lifecycle UI available without hover and ensure keyboard/focus support.
5. Confirmations show the selected course and real impact when available: employees losing/regaining access, Observer suspension and retained history. Cancel has no side effects; successful mutations followed by refresh failures remain successful with a reload warning.
6. Keep explanatory text user-facing. No implementation terminology, invented counts or fake reporting data from the mockup should enter production.

## Validation and acceptance

- Focused widget tests: option matching/selection/Cancel/scoped All, course-name/ID search and pagination, debounce/Enter/clearing/context cancellation, state-dependent menu/primary labels, confirmation cancellation and read-only controls.
- Database integration tests: allowed/denied lifecycle transitions, repeated requests, stale revisions and concurrent publish/archive/delete; history preservation and migration behavior; restore staying disabled; deletion eligibility including revoked/completed history.
- Exclusion tests: completed and unfinished employees lose access, other employees remain unaffected, history survives, include-group overlap cannot override exclusions, and background reconciliation does not undo the explicit workflow.
- Access tests: disabled/archived/excluded employees cannot load content or mutate progress via direct routes; saved/restored progress and deadlines behave correctly on Enable.
- Reporting tests: matching counts across summaries/list/detail/options/export for every lifecycle filter; actual completion states preserved; search/page/filter resets; no duplicate Combined rows; revoked/suspended Observers cannot use historical filters to widen access.
- Observer tests: Save restrictions/removal revoke immediately, additions require Apply, Disable/Archive suspend, Restore/Enable do not auto-apply, and learner/Observer separation remains enforced.
- Notification tests: disabled/archived eligibility gates, queued delivery checks and no duplicate assignment emails from label changes/repeated updates. Do not send live mail during UAT.
- Run relevant backend suites on the approved isolated PostgreSQL environment; the earlier Windows driver limitation has been resolved for test execution as recorded below.
- Run Trainer and Employee Flutter analysis, focused/relevant existing tests and web builds with approved SDK/tooling.
- Browser UAT on an authenticated test build at desktop and narrow widths: existing shell/layout; all course states and menu actions; Exclusions; deadlines/preview/refresh; Observer save/apply; historical Performance filters/details/exports; Observer/HOD/Combined scope cases.
- Test Archive -> Courses status Archived -> Restore -> Disabled -> review rules -> Enable -> Apply Observers, and verify completed learning survives throughout.
- Completion requires both original search parity and approved lifecycle/history behavior, with actual commands/results recorded. The implementation is local to this branch; it has not been published or deployed.

## Planned file areas

- Trainer dashboard/theme and course/assignment UI: `frontend/lib/features/dashboard_page.dart`, `features/courses/course_portal.dart`, `features/training/training_portal.dart` as needed, `features/assignments/assignment_portal.dart`, `observer_include_panel.dart`, related providers/models.
- Both Performance portals/providers/models: lifecycle filters, historical access display, options/details/exports and cache isolation.
- New Employee components: `employee_frontend/lib/features/performance/searchable_report_filter.dart` and `course_report_browser.dart` adapted from Trainer.
- Backend course/assignment APIs, services/repositories, progress, lifecycle schema/migrations, private-media authorization, report access/reporting and notification eligibility as identified during contract review.
- Focused Trainer/Employee Flutter tests and backend authorization, lifecycle, reporting, assignment and notification integration tests.

## Existing verification evidence

The Combined-scope regression coverage below remains useful evidence from before production implementation. It does not establish readiness of the newly planned lifecycle/history changes.

## Combined HOD + Observer code verification — 9 October 2026

Reviewed `backend/app/schemas/reporting_scope.py`, report role discovery, request scope authorization, reporting repository reads and Employee view/context handling.

- Combined is a parenthesized HOD EXISTS OR Observer EXISTS predicate applied to assignment rows. Grant matches do not join extra rows into results, so overlapping permissions do not multiply assignments.
- HOD uses active authoritative directory department mappings, not the viewer's own department. Observer grants require the matching course and active employee/department selectors.
- Request authorization permits only granted Employee views; Trainer All Courses/My Courses requests from Employee sessions are denied. Repository reads apply the shared scope to report rows, options and details; normal assignment eligibility checks remain in place.
- Added `backend/tests/test_combined_reporting_scope.py`: eight passing tests execute the production predicate against synthetic SQLite rows, with only PostgreSQL `::text` casts removed for dialect compatibility. Coverage includes exact union, overlap count, course limits, each contribution's independent revocation, no grants, inactive/recycled viewer identity and pending/recycled observed subject identity.
- Command: existing local Python environment running `-m unittest discover -s tests -p test_combined_reporting_scope.py -v`. Result: 8 passed.
- Attempted `-m pytest tests/test_employee_report_access.py tests/test_observer_reporting_postgres.py -q`; both modules failed during collection because psycopg cannot load its database wrapper (Windows application control blocks `_ssl`, and no fallback libpq is installed). These API/PostgreSQL suites were not executed successfully. The PostgreSQL suite also requires its explicit opt-in and isolated `lms_performance_demo` database.
- No defect found in the reviewed Combined predicate; no production authorization changes made. This focused check does not replace full PostgreSQL/API integration verification. Rerun those suites in the approved database environment before release.


## Implementation and verification — 12 October 2026

The following supersedes the earlier Windows-driver testing limitation. A working bundled Windows Python runtime runs the unit/API suites, and a WSL Python environment runs real PostgreSQL checks against the isolated `lms_performance_demo` database. Tests create their own schemas and clean them up; production data and live email delivery were not used.

| Stage | Implemented result |
| --- | --- |
| 1: contracts and authorization | Lifecycle/access fields, trusted availability filters and revision checks; creator-only mutations and deduplicated HOD/Observer scope retained. |
| 2: Observer search parity | Searchable Course/Department/Mailing list selectors, course name/ID search with 12-item pages, employee debounce and cancellation when reporting context changes. |
| 3: employee access and applied rules | Published rule snapshots isolate saved drafts from reconciliation. Exclusions withdraw unfinished and completed employee access while preserving completion, scores, answers, attempts and deadlines. Learning writes share the course lock. |
| 4: course action menu | Courses and Assign use eligible actions with confirmations and actual impact counts. Delete requires typing DELETE and is restricted by the backend to unused draft/ready content. Archive retains history; Restore leaves the course Disabled. Enable reviews the employee preview/deadline and does not reapply Observers. Generation and stale content writes cannot reopen Archived courses. |
| 5: reporting history | Active/Disabled/Archived/All filters, separate learning and access displays, current/historical totals and CSV access columns. Historical links retain availability scope; suspended Observers cannot regain history through a filter. |
| 6: automated verification | Backend/API checks, real PostgreSQL lifecycle/access/migration tests, Flutter search/menu/detail/refresh tests and release web builds. Live authenticated browser UAT is still a release acceptance item. |

Verification results:

- Backend full suite: `python -m pytest -o addopts='-p no:cacheprovider' -q`: **355 passed, 71 skipped, 1 failed**. The one failure is the existing `test_splits_third_landscape_image_to_separate_slide`, independently reproduced in the original checkout. It concerns image-slide generation outside this change. Skipped tests have explicit integration opt-ins.
- Real PostgreSQL: `LMS_ACCESS_POSTGRES_TESTS=true`, running `test_assignment_workspace_postgres.py`, `test_course_lifecycle_postgres.py`, `test_observer_reporting_postgres.py` and `test_media_access_postgres.py`: **34 passed**. Coverage includes complete score/answer/attempt preservation, migration idempotence, draft isolation, stale/concurrent lifecycle writes, deletion eligibility/audit, suspended Observer historical reads and generation guards.
- Trainer: `flutter test --no-pub`: **44 passed**, including eligible menu actions, DELETE confirmation cancellation, responsive reporting components, scope cancellation and assignment/Observer refresh behavior.
- Employee: focused reporting, playback, quiz-result and runtime-URL suites: **21 passed**. The separate Chrome app-shell smoke test did not progress beyond loading and was cancelled; it is not recorded as passed.
- Both clients: release `flutter build web --no-pub --release --no-wasm-dry-run` builds succeeded. The existing video player's `dart:js_util` analyzer error remains under the available SDK; JavaScript web compilation succeeds. VM execution of the Employee app-shell test cannot import its existing web-only libraries, so it must use a browser platform.
- Ruff checks on all changed Python files pass. `git diff --check` passes.

Migration behavior and remaining acceptance:

- Schema initialization applies the additive versioned `20261009_course_lifecycle_v1` migration. It adds applied include/exclude snapshots, lifecycle revisions and audit records. Legacy revoked learning status is reconstructed only from stored completion/start/module evidence; no completion is invented.
- Historical reporting remains inside Performance. No separate View historical reports shortcut and no individual Revoke action were added.
- Before release, perform the authenticated desktop/narrow-width browser UAT listed above, especially Archive → Restore → Disabled → Enable → Apply Observers. Do not treat the successful isolated tests/builds as a production rollout or completed live UAT.


## Follow-up VM readiness review — 12 October 2026

Verdict: ready to push this branch to the coding VM for integration testing. Promotion to on-prem UAT is conditional on completing the VM acceptance checklist in `docs/observer-performance-vm-readiness.md`.

The additional review fixed two issues before recommending that push:

- The legacy Trainer report excluded only `status=revoked`; it now also excludes withdrawals recorded in `revoked_at`, so retained completion status cannot inflate its current-assignment totals.
- Lifecycle actions now acquire the generation advisory lock and course row lock on one shared database connection, in that order. The previous nested connections could exhaust a busy connection pool. A real PostgreSQL test verifies Archive/Restore with a pool limited to one connection.

Follow-up evidence: **356 passed, 72 skipped, 1 existing image-slide failure** in the full backend unit/API run; **53 passing** PostgreSQL lifecycle/permission/library tests plus **15 passing** seeded report aggregation/search/sort parity tests, for **68 real PostgreSQL tests passed**. Synthetic report data was seeded only in a disposable schema in the isolated local `lms_performance_demo` database; that schema was removed afterwards. Both Flutter clients build with the actual Dockerfile flags (`--release --no-pub --pwa-strategy=none --no-web-resources-cdn`) and the pinned Flutter 3.44.0 SDK. The existing analyzer/video-player limitation and pending live browser UAT remain as previously recorded. No remote push or VM/on-prem deployment was performed by this review.
