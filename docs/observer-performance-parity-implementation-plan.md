# Observer Performance parity: implementation plan

Status: planned; no application code changed.
Date: 9 October 2026.
Branch: `codex/observer-performance-parity`.
Base: local `codex/lms-sbom-release`, commit `8876a34ccbacc7027bca995fc2ed9a0633fe8bac`.
Workspace: `C:/Users/LPUSER/.codex/worktrees/observer-performance-parity/LMS_V1`.

## Objective and scope

Bring the Employee application's Observer Performance search experience into parity with Trainer. Implement searchable Course, Department and Mailing list selectors, course-list search and pagination, and automatic employee-report search. Retain the existing metrics, report sections, details, exports and responsive styling.

Report visibility remains role-specific: an Observer sees only authorized observed employees and courses; HOD and Combined views remain available only when granted. All Courses and My Courses are Trainer views and must not be enabled for Observers. Because the Employee Performance portal is shared by Observer/HOD users, these UI improvements also apply to their authorized views.

## Verified baseline

- Trainer `frontend/lib/features/performance/performance_report_portal.dart` uses `SearchableReportFilter` for Course, Department and Mailing list. Employee `employee_frontend/lib/features/performance/performance_report_portal.dart` still uses plain `_Drop` selectors for these fields.
- Trainer `searchable_report_filter.dart` searches option labels and keys, case-insensitively by all entered words. It includes matching counts, selection indicators, clear search, All and Cancel, and lazily builds results.
- Trainer `course_report_browser.dart` adds local course-name/ID search, matching counts, clear search and 12-card pagination. Employee renders the complete course-card list without that browser.
- Trainer employee-report search uses a 350 ms debounce and immediate Enter submission. Employee currently submits only on Enter. Both use the existing report notifier search path.
- Employee `state/employee/performance_report_providers.dart` already owns report view, filters, search, pagination, reset version and permission-aware request context. Existing `ReportAccessGuard` protects open report details.

## Stage 1: confirm contracts

1. Recheck the branch against the integration target before implementation; preserve newer Employee/Trainer changes rather than overwriting entire files.
2. Verify Employee option responses include all authorized options, and that the course-summary response is complete for the active filters. If either endpoint paginates, consume all permitted pages or implement scope-preserving server search before claiming full-list search.
3. Confirm employee report search matches name, employee ID and course in the shared backend reporting engine. Use the Trainer hint only after ID matching is verified; add focused coverage if it is absent.
4. Review context keys, request generation checks and grant-revocation handling before adding local controllers or asynchronous callbacks.

## Stage 2: searchable Filter reports controls

1. Adapt Trainer `searchable_report_filter.dart` into Employee `features/performance/`, using Employee imports and theme. Follow the existing adapted-component approach; no new shared package is needed for this change.
2. Replace only the Course, Department and Mailing list `_Drop` controls with the adapted component. Preserve filter values, callbacks, responsive widths, active-filter count and Clear filters behavior.
3. Provide the same dialog search, matching count, clear action, selected checkmark, scoped All option, Cancel and empty state. Typing searches options locally; only selecting an option changes report filters.
4. Wrap dialogs with Employee `ReportAccessGuard` using the captured report context. Reject a returned selection if its context became stale. All means all options inside the current authorized scope.

## Stage 3: searchable course browser

1. Adapt Trainer `course_report_browser.dart` into Employee and integrate it with existing `_CourseCard` and course-detail callbacks.
2. Match Trainer behavior: case-insensitive name/ID search, all-word matching, clear action, matching count, 12-card pages, previous/next controls, loading and no-match messages, and existing responsive one/two-column cards.
3. Keep course search local to the course section; it must not alter employee-report search, global filters, metric totals or export scope.
4. Reset search and page on identity/permission/view changes and Clear filters using the existing report context/reset version. Reset to page 1 when the query changes and clamp the page when results shrink.

## Stage 4: automatic employee-report search

1. Add a cancellable 350 ms debounce to the Employee portal. Trim submitted text and reuse `PerformanceReportNotifier.setSearch`, which resets report pagination.
2. Enter cancels the pending debounce and submits immediately; avoid duplicate requests for the same submitted query where practical. Clearing text must restore the current scoped result set.
3. Cancel pending callbacks on disposal, view/context changes and Clear filters. Capture/check context for delayed callbacks so a previous identity or permission scope cannot drive a new report request.
4. Preserve current provider stale-response protection, filter interactions, quick-status chips, details and export behavior.

## Validation and acceptance

- Add focused Employee widget tests for searchable selector matching by label/key, scoped All, Cancel, no matches and selection behavior.
- Test course name/ID matching, a result beyond the first 12 cards, pagination, clearing, shrinking results and scope/reset changes.
- Test debounce timing, immediate Enter without a delayed duplicate, empty search, report-page reset and cancellation on disposal/context changes.
- Verify unauthorized options/courses never appear; revocation or scope switching closes/invalidates open selectors and prevents stale search responses from restoring old data.
- Run Employee Flutter analysis, relevant tests and a web build using the repository's approved SDK/tooling. Run existing reporting authorization tests if provider/backend behavior changes.
- Browser UAT: compare Trainer and Observer at desktop and narrow widths with a scoped Observer account. Exercise all three selectors, course search/pagination, employee name/ID/course search, Clear filters, Refresh, detail opening and CSV exports. Also check HOD/Combined views where available.
- Completion requires parity for the three search features with unchanged authorized visibility and report totals. Record actual commands/results and any limitations; no deployment is included in this planning request.

## Planned file changes

- `employee_frontend/lib/features/performance/performance_report_portal.dart`: integrate selector/course components and employee-search lifecycle.
- `employee_frontend/lib/features/performance/searchable_report_filter.dart`: adapted searchable selector.
- `employee_frontend/lib/features/performance/course_report_browser.dart`: adapted course search/pagination.
- Focused tests under `employee_frontend/test/` following existing conventions.
- Modify Employee providers or backend only if contract/lifecycle verification reveals a concrete gap; preserve Employee-scoped endpoints and current authorization.

Implementation has not started. The branch contains this plan only; the original checkout and its existing work remain separate.
