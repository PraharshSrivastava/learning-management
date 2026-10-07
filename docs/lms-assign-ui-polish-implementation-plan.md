# LMS Assign improvements: implementation plan

Status: implemented locally; deployment verification pending. See `lms-assign-ui-polish-implementation-progress.md` for evidence and rollout checks.
Date: 7 October 2026.
Implementation branch: `codex/lms-assign-ui-polish`, created from `origin/main` (`ccf94fe`) in an isolated managed checkout.

## Scope and baseline

Implement the approved Option 1 styling, employee terminology, calendar deadline, reliable refresh, truthful publication confirmation, complete employee preview, and per-course employee/Observer conflict prevention.

The primary checkout currently contains unrelated work on `codex/lms-sbom-remediation`. Do not switch, reset, stash or include that work. The inspected feature checkout is `C:/Users/LPUSER/.codex/worktrees/admin-trainer-visibility/LMS_V1`; rebase the implementation inventory on current main before editing, rather than copying its files over newer work.

Preserve creator-only mutation permissions, every Trainer's all-course Performance visibility, Admin Trainer oversight, HOD scope and Observer grant semantics. Preserve learning progress, course generation, SMTP recipients/transport/timings, TTS and unrelated features. Assign HOD remains deferred. The private-media Nginx correction is a separate deployment dependency; do not bundle or assume it is merged.

## Verified current gaps

- `frontend/lib/state/trainer/assignment_providers.dart`: `refreshOptionsAndGroups()` calls only `fetchOptions()` and `fetchSavedGroups()`. It does not reload the selected course's saved rule, employee preview, assignment totals, course status or Observer configuration.
- `loadForCourse()` returns early for the already-loaded course, so calling it unchanged is insufficient for explicit Refresh.
- Saved-group fetch failures are swallowed; concurrent state writes can clear another request's error or end loading before the full refresh completes.
- `AssignmentState.copyWith()` uses nullable fallbacks, so passing null cannot clear `assignedCount`; distinguish absent values from explicit null when adding typed state.
- `frontend/lib/features/assignments/observer_include_panel.dart`: Observer configuration is local widget state. `load()` calls `accept()`, which replaces selections and clears `dirty`; the Observer Refresh can discard edits. It must participate in coordinated refresh without losing a draft.
- Assignment preview currently returns a total matching count but only up to 10 employee rows. `assigned_count` from Publish means new assignments created, not total currently assigned employees.
- Deadline is currently relative `deadline_days`. A fixed calendar date is a functional addition, not merely a replacement input.
- Assignment synchronization can create/reactivate assignments outside explicit Publish; enforcing conflicts only in button endpoints would be incomplete.

## Stage 1: contracts and data definitions

1. Record existing assignment, Observer and publication API contracts and inspect current transactions, lazy assignment reconciliation, directory synchronization and notification integration.
2. Define separate fields for draft matching count, current assigned total, new assignments created, restored assignments, removed assignments and updated deadlines. Do not reinterpret an existing response field.
3. Define "assigned employees" as employees with a current, non-revoked course assignment, including completed learners. Include disabled-course assignments if retained by existing storage semantics, with the course's disabled state clearly labelled. Historical/revoked records must not inflate current totals or be deleted.
4. Keep a saved server baseline and separate editable drafts for employee rules and Observer selections. Track dirty state, server revisions and a course/request generation identifier.
5. Keep API keys and database enum values such as `include_groups`, `exclude_groups`, and group type `include`/`exclude` unchanged. Rename user-visible labels and default display names, not stored identifiers or trainer-created custom group names.

## Stage 2: Refresh implementation requirements

Replace the header button's narrow refresh path with a course-aware coordinator, conceptually `refreshAssignmentWorkspace(courseId, preserveDrafts: true)`. Use a separate load operation for initial course selection; do not recursively call the new coordinator from that loader.

The header Refresh must reload:

| Data | Required source and handling |
| --- | --- |
| Active employee, department and mailing-list options | Existing authenticated assignment options and authoritative directory-backed options |
| Saved groups | Existing saved-group endpoint; failures must be visible |
| Selected course's status and saved rule | Fresh course/assignment responses; bypass the same-course loading shortcut |
| Matching employee count and full paginated list | Recompute from the current editable draft without saving it |
| Current assigned employee total and full paginated list | Actual assignment records, independent of the draft filters |
| Observer options, revision, pending configuration and effective status | Fresh Observer endpoints, preserving unsaved local selections |

Implementation rules:

- Expose one consistent refresh/loading lifecycle. Disable repeated Refresh and conflicting mutations while it runs. Fetch independent read-only resources concurrently, collect all outcomes, then update state deliberately.
- Add a non-mutating, creator-authorized preview endpoint for draft rules if none exists. Refresh must never invoke Save, Publish, Apply Observers, notification enqueueing or rule mutation. Audit lazy read-time assignment writes and avoid them for preview/count endpoints.
- With clean forms, replace the draft with fresh saved state. With dirty forms, preserve all selections, names, deadlines and Observer edits; refresh server metadata separately and show a stale-baseline notice when another session changed the saved configuration. Do not silently adopt the latest Observer revision to authorize overwriting somebody else's edits.
- Keep selected IDs that disappeared from directory options visible as unavailable; flag them rather than silently dropping them or assigning different employees.
- Recompute preview from a captured draft. Discard responses for another course, an earlier refresh, an earlier search/page, or a draft changed while the request was running. Dirty rule changes should mark preview stale and trigger a debounced read-only preview.
- Give each failed section an actionable message and retry. Retain its last successful data with a stale indicator. Never label a partial refresh as complete success. Authentication failures follow existing re-login handling without displaying unauthorized stale data.
- Connect the Observer-specific Refresh to the same draft-preserving mechanism, scoped to Observer data where appropriate. A header refresh refreshes both employee and Observer state.
- Label the header tooltip "Refresh assignment data" to match the expanded scope. Retain clear Observer-specific tooltip text.
- After Save/Publish/Disable/Observer Save/Apply, invalidate only the relevant data. A successful mutation followed by a failed reload remains a successful mutation with a reload warning, not a misleading "publication failed" error.

Acceptance: refreshing on the same course issues fresh authenticated reads, shows updated directory/groups/status/counts/lists/grants, does not publish or discard edits, and cannot apply a stale response after switching courses.

## Stage 3: complete Assignment Preview

- Subtitle: **Check your employees before publishing.** Small but clearly legible text with sufficient contrast.
- Provide clearly separated views for "Employees matching current selection" and "Assigned employees", each with its own total, search and pagination. All records must be reachable; no hard-coded first-10 cap presented as the entire list.
- Display employee name, department and available job title; use employee IDs internally. Paginate server-side with stable ordering and deterministic ID tie-breaking. Restrict returned identity fields to what this creator-authorized workspace needs.
- Counts and rows use the same filters, scope and assignment-state predicate. Do not derive current assigned total from Performance aggregates or the last publication's new-assignment count.
- The unsaved draft affects matching preview only. Assigned employee rows come from persisted assignment records. Show empty, loading, stale and failure states explicitly.

## Stage 4: employee/Observer overlap protection

Constraint: the same verified directory employee identity cannot be a learner and a designated Observer for the same course. It can hold different roles on different courses. Observed subject employee IDs are learners to monitor, not designated Observer IDs; do not confuse those lists.

Build one shared validator comparing designated pending/effective Observer identities against final matching employees after exclusions and existing non-revoked assignments. Treat completed but still assigned employees as assigned. Do not infer identity from display names or email addresses.

Invoke it for Save Rule, Save Observers, Publish & Assign and Apply Observers. Validate proposed state: allow explicit removal/restriction of a conflicting Observer instead of blocking the repair because the old state overlaps. Removing an employee from future selection alone does not remove an existing assignment; explain that distinction and preserve progress.

Use the same per-course database lock and transaction across all assignment/Observer writers. Existing repositories must accept the transaction connection: a validator on one connection followed by writes on another does not provide atomic enforcement. Include assignment rows, rule/grant revision changes and notification scheduling in the existing consistent mutation boundary, respecting existing notification delivery semantics. Do not send SMTP within the transaction.

Audit automatic assignment, reactivation, login-time reconciliation and directory-driven eligibility changes. Those paths must use the same lock and guard. If an active Observer becomes eligible through a directory change, prevent creation/reactivation of that learner assignment, record an actionable conflict and expose it to the course creator; do not revoke Observer access or delete learning progress silently. Existing valid assignments continue following current behavior. Reports must make blocked matches clear instead of claiming all matching employees were assigned.

Return HTTP 409 with a structured code, readable message, bounded conflict details and count. Example message: "Aditya is selected as both an employee and an Observer for this course. Remove him from one selection to continue." Preserve the API's established error envelope and teach both clients to handle structured `detail` consistently.

Before enabling enforcement, perform a read-only audit of existing overlaps. Existing conflicts are reported for explicit resolution; there is no automatic destructive cleanup. Creator-authorized APIs and the UI must show only course identities the requester can manage. Do not introduce a block that prevents removing grants or disabling a course to resolve a conflict.

## Stage 5: calendar deadline

- Preserve the relative mode and existing saved `deadline_days`. Add an explicit fixed-date mode and nullable date/timezone fields through additive, versioned migrations and validated request schemas.
- Propose a specific date interpreted as end of that date in Asia/Kolkata, converted to an unambiguous UTC instant. The UI must say "Due by the end of this date (Asia/Kolkata)". Validate no past dates, permit today until its cutoff, and reject conflicting mode inputs. Store the date as a date, not an accidental browser-timezone midnight.
- Use Flutter's accessible date picker with keyboard navigation and direct readable date display. Existing fields and relative deadlines retain behavior.
- Use a central deadline resolver for new assignments, reactivation, reconciliation and publication deadline updates. Preserve existing relative-mode semantics; fixed-date mode must not extend the selected cutoff on reactivation. Define behavior for later new employees after a fixed deadline: reject new enrolment/reactivation with a clear expired-deadline status until the creator republishes with a valid deadline.
- Verify the existing Performance and email code reads the resulting per-employee deadline correctly. Keep notification schedules/recipients unchanged. Completed learning progress remains intact.
- Test exact cutoff, midnight/timezone boundaries, unchanged legacy rules, republishing and restored assignments before release.

## Stage 6: corporate UI and truthful feedback

Use approved Option 1 white cards with soft header strips. Titles: Target Employees, Performance Observers, Employee Exclusions, Completion Deadline, Assignment Preview. Replace "Audience" in affected user-facing Assign screens, errors, empty states, help and accessibility labels using grammatical employee wording. Do not rename unrelated product concepts.

Use navy primary actions, pale blue guidance, amber prerequisites/conflicts, muted rose exclusions and destructive feedback, and pale green confirmed success. Include icons/text, adequate contrast and visible keyboard focus. Apply these styles locally to Assign; do not change the shared app theme globally.

Save Rule uses a navy outline, Publish & Assign solid navy, Disable a muted burgundy outline. Keep callback authorization/enablement semantics. Use consistent size, responsive wrapping, clear busy labels/spinners and duplicate-click protection.

After confirmed publication, show an inline dismissible green banner naming the course. State new assignments truthfully; zero new assignments must not claim new enrolment. Retain restored/removed/deadline-update counts where relevant, and display current assigned total separately. Do not claim emails were delivered or Observer grants applied. Ensure failure or stale success from another selected course cannot be shown as current success.

## Stage 7: focused validation and Big Coding UAT

Backend tests:

- Matching AND within a group, OR across groups, deduplication and exclusion precedence remain unchanged.
- Paginated matching/assigned views, full traversal, correct totals, completed/revoked/disabled states and unauthorized creator access.
- All four conflict endpoints, existing assignments, pending/effective grants, same-person different-course permission, identity deduplication and repair actions.
- Concurrent Publish/Observer writes with the shared transaction lock; rollback leaves no partial assignment, grant or notification side effects.
- Automatic assignment/reactivation and directory changes cannot introduce forbidden overlaps.
- Fixed/relative deadline resolver and migration compatibility; existing SMTP/progress behavior remains valid.

Frontend/provider tests:

- Header Refresh fetches each required resource on the already-loaded course; Observer Refresh preserves its draft.
- Dirty selections/deadlines remain intact; stale revisions are not silently overwritten; disappeared options remain visible.
- Partial failures/auth expiry, concurrent responses, rapid course changes, preview requests and pagination do not corrupt selected-course state.
- Publication success versus mutation failure versus follow-up reload failure; zero assignments, restored/removed/deadline counts; duplicate-click prevention.
- Calendar selection and legacy rule loading. Build the Trainer web release; build/test Employee where deadline/API compatibility affects it. Use meaningful targeted tests, not cosmetic snapshot churn.

Big Coding rollout after review/merge:

1. In `/home/karphi/intelligence_layer`, inspect tracked changes and preserve `.env`/storage. Take the standard database backup and record the deployed revision/images. Verify separate private-media correction availability.
2. Pull reviewed main and build affected images; retain existing SMTP/TTS/Hub configuration and dependency/security fixes from main. Apply additive migrations only; never reset the database or remove volumes.
3. Check service health and Nginx syntax; open LMS through Hub. Trainer endpoint was `http://35.238.33.238:6969/`; verify the actual address at rollout.
4. Change a test saved group/directory option in a separate authorized session, then Refresh the same selected course: updated values must appear without losing an unsaved rule or Observer selection. Check fresh network requests, counts, complete paginated lists and pending/active Observer status.
5. Publish a controlled test assignment and verify real response counts, persisted assignments, success/error messages and repeat-click behavior. Test the conflict via department membership and an already-assigned employee.
6. Verify fixed-date employee deadlines and existing course progress/Performance. Keep SMTP UAT recipient controls as configured; do not turn on production email for this test.
7. Document outcomes and any blockers. Do not declare Big Coding Refresh verified solely because a local unit test or health endpoint passes.

## Delivery order and completion criteria

Implement in reviewable stages: contracts/state and Refresh; complete previews; transaction-safe overlap enforcement; deadline support; corporate styling and feedback; focused regression tests and VM UAT. Keep each stage's diff scoped. No GitHub push, merge or deployment is implied by this plan.

Done means every listed behavior is implemented and tested, all employees are reachable in preview, no same-course employee/Observer overlap can be newly created through supported writers, Refresh actually reloads data without discarding drafts, deadline modes preserve old rules, and Big Coding UAT is recorded. List limitations candidly rather than promising an error-free release.
