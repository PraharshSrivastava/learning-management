# Learning Journeys — Phase 1 implementation plan

Status: Track A implemented on `feature/learning-journeys` (from `origin/main` at `e0ba810`); not yet committed, reviewed or deployed. The feature ships switched off (`LEARNING_JOURNEYS_ENABLED=false`).
Demo: https://claude.ai/artifact/TbonvLpBkMBwyzT7nE2FnW

## Implementation status (2026-10-26, second pass)

Built as planned below, plus the changes in this section, which supersede the text further down where they differ.

### Journey courses are live courses that assign nobody directly
Reports, Observers, reminder emails and course Disable on `main` only see a course whose own course rule is published and active. So Publish & Assign on a journey now gives each of its courses a **published course rule that matches nobody**: nobody receives the course except through the journey. If a trainer had saved an unpublished draft rule, the draft is kept, and only the applied rule is "nobody".

Effects:
- Journey courses appear in Performance, the HOD report and Observer reports.
- They get reminder, due-soon and overdue emails.
- Course Observers can be added to them with no workaround.
- Course Disable works on them.

### Journey Observers
A journey has its own Observers, separate from course Observers. Each one watches chosen employees and/or departments.

- **What they see:** every course of the published journey, for the journey's learners they watch, in the existing Performance "Observed" view. A newly unlocked course appears with no per-course setup.
- **Not learners:** an Observer is never enrolled in the journey, and someone who already has the journey as a learner cannot be made its Observer.
- **When it applies:** saves take effect at once while the journey is published. Course Observers instead have a save step and a separate apply step.
- **Logged and refreshed:** each save is written to `lms_report_access_audit`, and the Observer's permission version is bumped, so their app refreshes.
- **Switch off:** journey Observers are hidden when `LEARNING_JOURNEYS_ENABLED` is false.
- **Code:** tables `learning_journey_observers`, `learning_journey_observer_employees` and `learning_journey_observer_departments`; routes `GET`/`PUT /api/learning-journeys/{id}/observers`; report access in `schemas/reporting_scope.py` (`owner_filter`) and `repositories/report_access.py` (`report_roles`).

### Bugs found by an independent review, now fixed
- **A journey that had opened could go back to "waiting"** and its courses were revoked, for example when a prerequisite was added later. Now a journey stays open once it has opened for someone (`available_at`).
- **Any active course assignment counted as journey progress.** A course someone got from its own course rule could unlock a later journey step, and its rule could then never take it away. Each journey assignment now records the courses the journey itself unlocked (`unlocked_course_ids`), and only those stay unlocked.
- **Switching the feature off would have revoked every journey course.** Now nothing new unlocks while it is off, but courses people already received stay assigned and visible.
- **A journey could become impossible to save** if one of its courses went back to draft. Draft courses are now listed as ineligible instead of being dropped.
- **A broken course link** in the employee app now keeps the journey that was open.

Not changed, accepted as low risk:
- **Deadline comparison.** When a course sits in two journeys with different deadline types, the earlier deadline is compared as text. This follows `main`'s mix of naive local and UTC times.
- **Publish is not one transaction.** If publishing fails part way, the courses can already be live with the "nobody" rule. Nobody receives them, and publishing again completes the job.

### Verified
- **Backend:**
  - 12 lock-engine unit tests;
  - 14 end-to-end PostgreSQL tests, adding to the first pass:
    - reports and reminders for journey courses;
    - the draft course rule kept;
    - a course Observer without the workaround;
    - a prerequisite added after the journey opened;
    - a course rule not skipping ahead;
    - the feature switched off and back on;
    - journey Observer visibility, roles, the learner conflict, and the feature switch.
  - The full existing suite passes. Two mocked reconcile tests now stub the journey lookup. Ruff is at `main`'s baseline.
- **Frontend:** 481 Vitest tests pass, including the journey Observer editor. ESLint and `tsc` are clean.
- **Not done yet:** not run in a browser against a live backend; no staging pilot.

### Known limits
- **Reconcile cost.** Each reconcile reads the published journeys once per employee. Cache it if reconcile time grows.
- **Prerequisites.** A prerequisite journey must belong to the same trainer and be published first.

## What changed from the first draft

The first draft was written against an old Flutter branch. `main` has since replaced both frontends with React apps (`apps/trainer`, `apps/employee`, `packages/shared`). It also gained Observers, fixed-date deadlines, saved-versus-applied assignment rules and a course Enable/Disable lifecycle. This revision follows `main`:

- **Frontend paths are React, not Flutter.** Trainer tabs are id-based (`apps/trainer/src/shell/search.ts`), so adding a tab shifts nothing. Employee navigation is index-based (`apps/employee/src/dashboard/search.ts`), so it is updated deliberately.
- **Journey setup and assignment both live in the new Journeys tab.** The existing Assign tab (`RuleView` and `AssignmentWorkspace`) is course-specific: it handles Observers, lifecycle revisions and employee preview paging. It stays unchanged in Phase 1. The Journeys tab reuses its group editor (`GroupList`) for "Who gets it".
- **The Performance tab and the HOD report are unchanged in Phase 1.** Journey courses already appear there as normal course rows. Journey-level progress (employee, current step, status) is shown in the Journeys tab. A journey filter inside the shared performance report is Phase 2.
- **Observers, disabled courses and fixed-date deadlines are handled explicitly** (see Lock rules).

## Goal

Add **Learning Journeys**: an ordered path of existing courses, assigned once, that unlocks one course at a time. Phase 1 publishes **New Joiner Induction**, **Markets Foundation** and **Compliance & Ethics**.

Authoring, the course player, module and quiz rules, progress, emails, the Assign tab and Performance keep working as they do now. A journey only decides **which courses an employee is assigned, and when**.

## Decisions (taken for Phase 1)

1. **Which courses a journey can include.** Only courses **created by the journey's trainer**, with status `ready` or `published`, that are fully generated (`course_is_publishable`) and not Disabled. This matches main's owner-only mutation model; Admin cross-owner manage is false. Publishing the journey sets its `ready` courses to `published` and gives any course without a published rule a published rule that matches nobody, so nobody gets the course except through the journey (see the implementation status above).
2. **Journey assignments do not expire with time-based filters.** Once someone has a journey, they keep it while they are active and the journey is published and active. "Joined in the last 30 days" decides only who **gets** Induction; it doesn't take it away on day 31.
3. **Course Disable keeps its current meaning: unavailable everywhere.** A Disabled course becomes an `unavailable` step and is skipped. Its assignments are revoked by the existing disable code. Re-enabling the course restores them on the next reconcile.
4. **A step can be unavailable for one employee.** This happens when the course is not published, is Disabled, or the employee is an **Observer** of that course (main forbids being both). The step is then skipped for unlocking and for completion.
5. **Prerequisites apply only to people assigned the prerequisite journey.** Existing staff who never get Induction start Markets Foundation directly.
6. **Feature switch.** The setting `learning_journeys_enabled` (environment variable `LEARNING_JOURNEYS_ENABLED`) defaults to false. When it is off:
   - the journey routes return 404;
   - the list endpoints return `enabled: false`, so both apps hide the feature;
   - reconcile ignores journeys.

## Core mechanism: a course is assigned when it unlocks

A normal `course_assignments` row is created only when a journey step **unlocks**. Locked steps have no assignment.

- My Courses, the course player, `module_progress`, Performance, the HOD report and emails all keep working from `course_assignments`.
- The existing "assigned" email (`_notification_transition` → `enqueue_assignment_notifications`) acts as the "next course unlocked" email.
- `UNIQUE (course_id, employee_id)` lets one row serve both a course rule and a journey. Progress is never duplicated.

## Backend

### Tables

Tables are created in `schema._create_tables` (`CREATE TABLE IF NOT EXISTS`) and listed in `TABLES`. Nothing existing is altered or backfilled.

- **`learning_journeys`**: `journey_id`, `trainer_id` → trainers, `title`, `description`, `target_audience`, `status` (`draft` | `published` | `disabled`), `prerequisite_journey_id` → `learning_journeys` (`ON DELETE SET NULL`, cannot point at itself), `certificate_enabled`, `published_at`, `disabled_at`, `created_at`, `updated_at`.
- **`learning_journey_stages`**: `stage_id`, `journey_id` (`CASCADE`), `position`, `title`, `UNIQUE (journey_id, position)`.
- **`learning_journey_steps`**: `step_id`, `journey_id` (`CASCADE`), `stage_id` (`CASCADE`), `course_id` → courses (`RESTRICT`), `position` (order across the whole journey), `unlock_rule` (`open` | `after_previous`), `is_required`, `UNIQUE (journey_id, course_id)` and `UNIQUE (journey_id, position)`.
- **`learning_journey_rules`**: `journey_id` PK (`CASCADE`), `rule_json` (the editable rule, the same shape as a course rule: include/exclude groups and the deadline), `applied_rule_json` (the snapshot taken at Publish), `updated_at`.
- **`learning_journey_assignments`**:
  - columns: `journey_assignment_id`, `journey_id` (`CASCADE`), `employee_id` → employees (`RESTRICT`), `status`, `assigned_at`, `available_at`, `deadline`, `started_at`, `completed_at`, `revoked_at`, `revoked_reason`, `updated_at`;
  - `status` is one of `waiting` | `pending` | `started` | `completed` | `overdue`;
  - `UNIQUE (journey_id, employee_id)`.

Course deletion (`delete_course_for_trainer`) gets a check: a course that is in any journey cannot be deleted. It returns a clear `ConflictError` instead of a foreign-key failure.

### Code layout

- `app/schemas/journey.py` — request and response models.
- `app/repositories/journeys.py` — persistence for the five tables.
- `app/services/journey_state.py` — the **pure** lock engine, with no database access.
- `app/services/journeys.py`:
  - trainer use cases;
  - employee reads;
  - `journey_wanted_courses(employee, progress, now)`, which syncs that employee's journey assignments and returns the unlocked courses with their deadlines.
- `app/api/journeys.py` — routes, registered in `app/api/router.py`.

Rule matching reuses `employee_matches_assignment_rule` and the deadline helpers in `assignment_deadlines.py` (`validate_deadline`, `resolve_deadline`, `deadline_expired`).

### Lock rules (`journey_state.py`)

For one employee and one journey:

1. **Availability**
   - With no prerequisite, the journey is available from the moment it is assigned.
   - With a prerequisite that the employee is **also assigned**, the journey is available once that journey is `completed`. Until then its status is `waiting` and it has no deadline.
   - If the employee is not assigned the prerequisite, the prerequisite counts as met.
   - On first availability, set `available_at` and the deadline. A relative deadline is `available_at + deadline_days`; a fixed deadline is the fixed date.
2. **Steps.** Steps are walked in `position` order. Each step's state is one of `passed`, `in_progress`, `available`, `locked` or `unavailable`.
   - `unavailable`: decision 4.
   - `passed`: a completed course assignment exists for that course. It counts from any source, including one completed before the journey existed, or one later revoked; this follows main's rule that completed results are kept.
   - **Unlocked:** the journey is available, and the step is first, is `open`, or the nearest earlier **required, available** step is `passed`.
   - **An unlocked step stays unlocked.** If an assignment already exists and is not revoked, a later journey edit never locks it again.
3. **Completion.** The journey is complete when there is at least one available required step and every available required step is `passed`.
4. **Status**: `waiting`, then `pending`, then `started` (any course started or passed), then `completed`. It becomes `overdue` after the deadline if the journey isn't complete.

### Changes to existing assignment code

- **`reconcile_assignments_for_employee`** (`services/assignments.py`)
  - First, compute `journey = journey_wanted_courses(...)`.
  - **Revoke loop:** a course still wanted by a journey (and still published) is kept, even if its course rule no longer matches.
  - **Create loop:** after the course-rule loop, create or reactivate assignments for journey-wanted courses that are not already active. These get the journey deadline and run under `course_transaction`. Observer checks happen first, so `EmployeeObserverConflict` is never raised.
- **`assign_published_course_to_matching_employees`** (course Publish & Assign): do not revoke employees whose journey wants this course.
- **`get_enriched_employee_courses`** and **`_assigned_progress_for_employee`** (`services/learning.py`): accept a course when the course rule matches **or** a journey wants it. Both still exclude revoked assignments.
- **Course completion** (`update_module_progress` and `update_course_status`): when a course becomes `completed`, reconcile the employee afterwards, outside the course transaction. The next step is then assigned at once, and its assigned email is queued by the existing progress-save hook.

### Trainer routes (trainer session, owner-only for changes)

| Route | Purpose |
|---|---|
| `GET /api/learning-journeys` | `{enabled, journeys}` for this trainer: counts, status, warnings |
| `POST /api/learning-journeys` | Create a draft |
| `GET /api/learning-journeys/course-options` | This trainer's courses that can be added (decision 1) |
| `GET /api/learning-journeys/{id}` | Details, stages, steps, rule, warnings |
| `PUT /api/learning-journeys/{id}` | Save details, stages, steps and rule. Validates: owned eligible courses, no duplicate course, a prerequisite that exists and makes no cycle, and the deadline |
| `DELETE /api/learning-journeys/{id}` | Only a draft that was never published |
| `GET /api/learning-journeys/{id}/preview` | Match count and 10 preview employees for the saved rule |
| `POST /api/learning-journeys/{id}/publish` | Validate, then: publish ready courses, snapshot the applied rule, set status published, reconcile matching and currently assigned employees, return counts |
| `POST /api/learning-journeys/{id}/disable` | Set status disabled, revoke the journey assignments, then reconcile those employees so courses only this journey wanted are revoked |
| `GET /api/learning-journeys/{id}/progress` | One row per assigned employee: status, step N of M, current course, deadline |

### Employee routes (employee session)

| Route | Purpose |
|---|---|
| `GET /api/me/learning-journeys` | `{enabled, journeys}`: each journey's status, deadline, progress, next step, and every step with its state |
| `GET /api/me/courses` (existing) | Each course gains `journeys: [{journey_id, title, step, step_count}]` |

## Trainer app (`apps/trainer`)

- **Tab:** add `{ id: 'journeys', label: 'Journeys' }` between Courses and Assign in `TRAINER_TABS`. Register `JourneysTab` in `tabPanels` and `tabQueries`, add `trainerKeys.journeys`, and add `journey` to the search schema.
- **Visibility:** the shell hides the tab when the list endpoint returns `enabled: false`.
- **`features/journeys/`**, laid out like the Assign desk:
  - **Sidebar:** journey list with status, course count and "+ New".
  - **Editor:**
    - **Details:** name, audience, description, "Starts after" and certificate.
    - **Stages and courses:** add or rename stages; add a course from `course-options`; unlock rule, Required, up/down and remove.
    - **Who gets it:** Include all / include groups / exclude groups, using the existing `GroupList`, with saved groups and options from the existing endpoints. Deadline: days or a fixed date.
    - **What employees will see** preview.
    - **Warnings.**
    - **Buttons:** Save, Publish & Assign, Disable.
    - **Progress table.**

## Employee app (`apps/employee`)

- **Navigation:** Dashboard · My Courses · **Learning Journeys** · Notifications · Performance.
  - `navigationIndex` and `viewForIndex` in `dashboard/search.ts` gain `journeys`; Notifications moves to index 3 and Performance to 4.
  - The performance gate in `EmployeeDashboard` and the AppBar label list are updated to match.
  - The menu item is hidden when the feature is off. Indexes are then computed from the visible destinations, so they never point at the wrong page.
- **Dashboard:** a "Your journeys" section above the metric tiles, shown only when the employee has journeys.
- **Learning Journeys page:** journey cards and a stage-by-stage roadmap. An unlocked course opens the existing course player.
- **Course cards** show "Markets Foundation · Step 4 of 6".
- **Course player:** a slim journey bar above the existing `CoursePlayback`, rendered by the dashboard. `CoursePlayback` itself is unchanged.

## The three Phase 1 journeys (content: Track B, made by the training team)

The same tables as before, created in the app by the trainer once the courses are published:

- **New Joiner Induction** (6 courses, in order):
  - rule: *joined in the last 30 days*;
  - deadline 14 days.
- **Markets Foundation** (6 courses, in order):
  - rule: all active employees;
  - deadline 45 days from availability;
  - starts after Induction.
- **Compliance & Ethics** (5 courses, any order):
  - rule: all active employees;
  - deadline 30 days.

The course titles are listed in the earlier draft, and SMEs and the compliance team confirm them. All courses in one journey must be created by the trainer account that owns the journey (decision 1).

## Out of scope for Phase 1

- Yearly renewal.
- Spreading deadlines across steps.
- Journey emails and PDF certificates.
- A journey filter in the shared Performance report and the HOD report.
- Cross-owner journeys.
- Role tracks.

## Tests

**Backend:**

- `tests/test_journey_state.py` covers the pure lock engine:
  - order and `open` steps;
  - optional steps;
  - unavailable steps;
  - an unlocked step that stays unlocked;
  - courses passed earlier;
  - prerequisites and waiting;
  - deadlines.
- `tests/test_learning_journeys_postgres.py` runs against isolated PostgreSQL, the same pattern as `test_assignment_workspace_postgres.py`. It covers:
  - publish assigns only the first step;
  - completing a course unlocks the next step and queues exactly one assigned email;
  - a journey course is not revoked by reconcile or by course Publish & Assign;
  - prerequisite waiting, then `available_at` and the deadline;
  - an employee without Induction starts Foundation directly;
  - a time-based rule drifting doesn't revoke the journey;
  - disabling the journey revokes only journey-only courses;
  - an Observer's step is unavailable;
  - owner-only validation;
  - the feature switch off means no effect.
- The full existing suite passes unchanged.

**Frontend:** Vitest for:
- employee navigation indexes, with the feature on and off;
- the journeys roadmap states;
- the trainer journey editor's save payload;
- the full existing suite passes unchanged.
