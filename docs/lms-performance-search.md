# Trainer Performance search

Implemented locally on `codex/lms-performance-search`, based on main `1b734ab`.

## Behaviour

- Course, Department and Mailing list filters open a searchable selection dialog. Typing searches every permitted option; selecting a result applies the existing report filter. Cancel preserves the current selection. All options clears that filter only.
- Course options can be searched by course name or ID; department and mailing list options by name. Course IDs distinguish duplicate course titles.
- Courses has a separate name/ID search, result count and 12 cards per page. This search changes only the displayed course cards, not report totals or export scope. Changing report scope or Clear all resets this search. Refresh preserves its search and current page while loading.
- Employee summary and Course assignments search after a 350 ms typing pause; Enter still submits immediately. Employee summary searches name/ID through the existing paginated API. Course assignments also searches course names.
- Report access guard protects filter dialogs when user, permissions, report scope or filters change. Existing all-course Trainer performance visibility remains enforced by the unchanged backend.
- Existing AppTheme navy/pale blue palette and inherited fonts are retained. Pickers use lazy scrolling; course cards are limited to 12 rendered results per page.

## Validation

- Full Trainer Flutter suite: 34 passed, including large-option search, narrow pickers, course paging and opening the correct searched course, employee debounce/clear, and existing assignment/Observer refresh coverage.
- Trainer release web build passed locally.
- Analysis of changed components/tests passed after lint cleanup; full-project analysis still includes existing informational findings.
- Git whitespace check passed.
- VM browser UAT is pending. No push, merge or deployment is part of this local change.

## Scope and scale

Frontend Performance code and tests only. No backend, role, SMTP, assignment, database, deployment or dependency changes. Employee frontend is unchanged.

Option lists and course aggregates still come from the existing complete, permission-scoped report APIs. Lazy rendering and paging reduce UI work; this change does not introduce server-side course/option pagination. If payload size becomes a bottleneck at larger volumes, add permission-scoped option search and course pagination as a separately measured backend change.

## VM UAT after merge

1. Open Hub → LMS Trainer → Performance.
2. Search and select a course, department and mailing list; confirm report counts and exports follow the selected filters.
3. Cancel a picker and verify its earlier selection stays. Choose All and verify only that field clears.
4. In Courses, search a full/partial title and ID; page through results and open a course.
5. In Employees, type a name/ID, clear it, change filters and inspect an employee’s course details.
6. Refresh and confirm report scope/search remain correct. Clear all and confirm searches and filters reset.
7. Check another Trainer’s all-course performance visibility and narrower permitted report views.

Use the existing on-prem image and edge-network overlays for deployment; do not recreate the frontend with a default-only Compose command.
