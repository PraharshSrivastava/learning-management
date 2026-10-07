# LMS Assign improvements: implementation and verification

Date: 7 October 2026.
Branch: `codex/lms-assign-ui-polish`; baseline `ccf94fe` from origin/main.
Status: implemented and checked locally. Not pushed, merged or deployed.

## Delivered

- Approved Option 1 corporate cards and action buttons with blue guidance, amber prerequisites/conflicts, green confirmed publication success and subdued exclusion/disable styling.
- Panels: Target Employees, Performance Observers, Employee Exclusions, Completion Deadline and Assignment Preview. API include/exclude identifiers and custom group names retain compatibility.
- Relative deadline days remain available alongside a calendar date. Fixed dates expire at the end of the selected day in Asia/Kolkata; the stored cutoff is UTC. Saving a deadline draft does not replace the published deadline used for subsequent automatic assignments.
- Explicit Refresh reloads options, saved groups, selected-course rule/status, preview and assigned totals. Observer configuration/effective access reload through the refresh generation. Drafts are retained, changed server revisions are reported, and confirmed reload actions recover the saved version. Observer loading/errors remain visible in its panel. A failed source retains its prior data and reports failure.
- Preview displays “Check your employees before publishing.” It distinguishes matching employees from current assigned employees, including completed assignments, with search and pagination covering all records. Revoked assignments are excluded from current totals.
- Publish confirmation is displayed only after successful server publication and reports actual totals and changes; it does not claim email delivery or automatic Observer activation.
- Conflict validation covers saved and unsaved Observer selections, final matching employees after exclusions, existing non-revoked assignments including completed employees, Save Rule, Save Observers, Publish, Apply and automatic enrolment/reactivation. Stable directory/Hub identity is checked so stale grants do not follow a replacement employee.
- Course row locks and shared transactions serialize conflicting writes and roll back publication/rule/progress/outbox changes together on failure. Existing notification broadcasts are deferred until successful commit; SMTP settings, recipients and timing policy are unchanged.
- Apply Observers is disabled when the course assignment is inactive. Existing creator-only writes and all-Trainer Performance visibility are retained. HOD assignment remains deferred.

## Storage decision

The original plan proposed additional deadline columns. The implementation instead stores additive deadline metadata in the existing assignment-rule filter JSON. Old rules default to relative mode. No destructive migration or physical column migration is required. Applied deadline metadata is separate from saved deadline metadata. Deploy the matching backend and Trainer frontend together.

## Local verification

- Focused backend checks: 21 passed, including isolated PostgreSQL concurrency, rollback, full preview, directory changes, stable identities and fixed-deadline checks.
- Full backend suite: 334 passed, 15 skipped, 1 failed. The previously observed failure is `tests/test_image_slide_flow.py::test_splits_third_landscape_image_to_separate_slide`, expecting three slides when the unchanged generator returns four. No generation fix is included in this task.
- Trainer Flutter suite: 22 passed. Refresh coverage includes same-course refresh, draft preservation, partial failure, session expiry, stale course responses and unsaved Observer conflict prevention.
- Trainer release web build succeeded.
- Ruff passed for all changed backend files. Flutter analysis reported no errors or warnings and 44 informational style recommendations across the frontend; these are not a clean lint result.
- Git whitespace check passed. Docker, dependency manifests/locks, SMTP configuration and Employee frontend files were not changed. The separate SBOM checkout was not modified.

Checks used the available cached local Flutter dependencies and the isolated PostgreSQL demo database. They do not establish parity with the production Flutter toolchain or constitute Big Coding browser verification.

## Before rollout on Big Coding

The VM repository is `/home/karphi/intelligence_layer`, normally on main, with compose services `backend`, `frontend` and `employee_frontend`. Preserve its environment and storage configuration. Publication must not be tested against real employees without an intentional test course and designated test accounts.

1. Review this branch and its known test failure; explicitly authorize push/merge before rollout. The private-media proxy correction on separate branch `codex/lms-private-media-proxy` is still a separate deployment dependency and has not been included here.
2. Run the read-only conflict audit against the intended database before rollout or activation. From the backend directory use `PYTHONPATH=. python scripts/audit_assignment_observer_conflicts.py`; optional `--course-id <id>` restricts it to one course. In the backend container use `PYTHONPATH=/app` and copy/run the script from a temporary location if the image does not include the scripts directory. Exit 1 identifies conflicts; no assignments, progress or grants are deleted. Resolve each conflict explicitly before publishing/applying that course.
3. Build and deploy matching backend and Trainer frontend with the VM's current deployment procedure, keeping the compose project, environment and mounted storage unchanged. Do not remove PostgreSQL volumes or run blanket ownership changes.
4. Sign in through Hub. Verify the five panels at desktop and narrow widths, calendar selection, inactive controls, and green success text using a test course.
5. In two sessions, change directory/options, saved employee rule and Observer configuration; Refresh must load fresh data while retaining local drafts. Check both header Refresh and Observer Refresh, revision warnings, explicit saved-version reload and visible failure states.
6. Verify every assigned employee is reachable through pagination/search; matching and assigned totals are distinct. Verify zero new assignments is reported truthfully on repeat publication.
7. Verify a designated Observer cannot also be a matching/assigned employee, including cross-department scope and completed assignments. Confirm exclusions allow a clean selection, and rejected mutations retain all prior data. Verify simultaneous publish/Observer saves cannot create overlap.
8. Verify fixed-date and relative-date behavior, completion preservation, department-change reconciliation, creator-only course changes, all-Trainer Performance, HOD department scope and Observer scope. Check Employee learning and existing SMTP notification processing as regression smoke checks.
9. Record actual browser/VM results before marking deployment complete. None of these VM checks has been performed from this session.
