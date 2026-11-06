# Trainer search — implementation plan

Date: 2026-11-06
Base: `origin/main` at `8ee2b9b` (React trainer app, `apps/trainer`)
Goal: every Trainer list that grows with the number of employees, courses or journeys can be
searched, and the employee pickers stay fast at go-live headcount.

Nothing here changes the backend, the database or any API. All changes are front-end only, in
`apps/trainer/src/features/assignments` and `apps/trainer/src/features/journeys`.

---

## 0. Ground rules (to avoid errors)

1. **Branch from fresh `main`, not from this local checkout.** The local branch
   (`codex/document-builder-workflow`) is stale and still has the old Flutter folders.
   Start with `git fetch origin` and `git switch -c feat/trainer-search origin/main`.
2. **Reuse what already exists. Don't build new components where one already works:**
   - `SearchBox` in `features/assignments/controls.tsx`: the picker search input
     (`type="search"`, so tests find it as `searchbox`; `aria-label` = placeholder; optional clear
     button).
   - `matchesWords(query, haystack)` in `@lms/shared/performance/format`: multi-word,
     case-insensitive match that the Performance screens already use. Use it everywhere below so
     every search box behaves the same way (typing "ravi sales" matches "Ravi K, Sales").
3. **The search state lives inside the dialog body, and the body mounts only while the dialog is
   open** (the `{open && <Body/>}` pattern already used in `pickers.tsx`). That way the search clears
   every time a dialog opens, and the filtering does no work while the dialog is closed.
4. **Searching only hides rows. It never changes what is saved.** Selected IDs are never dropped
   because a row is filtered out of view.
5. **Keep every existing label and role** that tests or users rely on ("Select all", "Clear all",
   "Done", "Course to add", "N selected"). Add new labels; don't rename old ones.
6. Run the full check list in §6 before opening the PR.

---

## 1. Observer "Employees to observe" dialog — priority 1

**File:** `apps/trainer/src/features/assignments/ObserverPanel.tsx` (the field dialog at the bottom,
roughly lines 215–280, used for both *Employees to observe* and *Departments to observe*).

**Today:** every active employee is listed as a checkbox, with no search. Only "Select all" and
"Clear all".

**Change:**
1. Move the dialog content into an inner `ObserverFieldBody` component and render it as
   `{choosing != null && <ObserverFieldBody … />}`, so the search state resets on every open.
2. Add `SearchBox` at the top, with placeholder **"Search employees"** (or **"Search
   departments"** for the departments field), plus `onClear` and `autoFocus`.
3. Filter `options` with `matchesWords(query, label + ' ' + id)`. The label already contains name
   and department, and the id is the employee ID.
4. Count line: keep **"N selected"** as it is. While searching, add **"M of T shown"**.
5. **Select all / Clear all with a search active:**
   - No search → "Select all" adds every option (unchanged behaviour; the existing test depends on
     it).
   - Search active → the button label becomes **"Select all shown"** and adds only the matching
     options. This prevents a trainer from searching "Sales", pressing Select all and
     unknowingly selecting the whole company.
   - "Clear all" always clears the whole selection (unchanged).
   - The `allPicked` "disabled" check uses the shown options while searching.
6. Empty state: "No employees match your search." / "No departments match your search."
7. Apply the row cap from §4.

**Risks and how they're avoided:**
- The existing test `ObserverPanel.test.tsx` "Select all and Clear all…" clicks **Select all**
  with no search and expects `3 selected`. That still passes because the label and behaviour
  don't change when there is no search.
- The observer *person* picker (`SearchablePicker`) is a different dialog and already has a
  `searchbox`. The test finds it with `within(picker)`, so a second search box in a different
  dialog can't clash.

**New tests (same file):**
- Typing in the search shows only matching rows; the "N selected" count is unaffected.
- With a search active, "Select all shown" selects only matches; clearing the search and
  "Clear all" still works.
- Closing and reopening the dialog clears the search.
- Departments field: search filters department names.

---

## 2. Journeys → "Course to add" — priority 2

**File:** `apps/trainer/src/features/journeys/JourneyCourses.tsx` (the `picking === stageIndex`
block, roughly lines 274–310).

**Today:** a native `<select>` holds every eligible course, plus disabled ones with a reason.

**Change (low-risk version: keep the `<select>`, add a filter above it):**
1. Add a `SearchBox` with placeholder **"Filter courses"** (aria-label is the same) above the
   select, inside the same dashed box.
2. Filter both `available` and `unavailable` with
   `matchesWords(query, courseName + ' ' + courseId)`.
3. **Keep the chosen course valid:** when the filter text changes and the current `pick` is no
   longer among the shown available options, reset `pick` to `''`. That keeps "Add" disabled and
   stops a hidden course from being added by mistake.
4. When the filter matches nothing, show a placeholder option: "No courses match "…"".
5. Reset the filter text when the picker opens or closes (`picking` changes) and after "Add".

**Why the `<select>` stays:** the existing test in `JourneysTab.test.tsx` (lines ~151–156) finds
`combobox "Course to add"`, checks that a draft course is a disabled option and uses
`selectOptions(picker, 'c2')`. Keeping the select means that test passes unchanged and keyboard
behaviour stays native.

**New test (JourneysTab.test.tsx):** type a part of a course name → only that course remains in
the combobox → pick and Add works; type text that no longer matches the picked course → "Add"
becomes disabled.

---

## 3. Journeys → left list of learning journeys — priority 3

**File:** `apps/trainer/src/features/journeys/JourneysTab.tsx` (sidebar, roughly lines 133–195).

**Change:** copy the Assign sidebar pattern exactly (`features/assignments/Sidebar.tsx`, lines
34–52), so it looks and behaves like the other tabs:
1. `const [search, setSearch] = useState('')` in the sidebar.
2. Insert a `<label className="assign-course-search">` with `<Icon name="search" />` and
   `<input type="search" aria-label="Search learning journeys" placeholder="Search journeys…">`
   between the header ("Learning journeys" + New) and the scroll area. The CSS class already
   exists in `AssignStyles.css`, so no new CSS is needed.
3. `shown = journeys.filter(j => matchesWords(search, j.title))`.
4. Empty states:
   - No journeys at all → keep the existing "No learning journeys yet".
   - Journeys exist but none match → "No matching journeys. Try a different search."
5. **Don't touch the selection logic.** A selected journey that is filtered out of the list stays
   open on the right. The search only hides list rows, and doesn't change `?journey=`, so the
   unsaved-changes blocker (`useBlocker`) isn't triggered by typing.

**New test (JourneysTab.test.tsx):** with 2+ journeys, typing filters the list; the open journey
stays open; the no-match message appears.

---

## 4. Keep employee pickers fast at go-live — row cap

**Problem:** the pickers get the whole active employee list from `/api/assignment/options` and
render **every matching row** on each keystroke. With a few thousand employees, opening the
dialog and typing will lag.

**Change (front end only, no API change):**
1. Add to `features/assignments/controls.tsx`:
   ```ts
   export const PICKER_ROW_LIMIT = 100
   /** Note under a capped picker list. Renders nothing when everything is shown. */
   export function MoreRowsHint({ shown, total }: { shown: number; total: number })
   // → "Showing the first 100 of 2,340. Type to narrow the list."
   ```
2. In each picker, keep filtering over the **full** list but render only
   `filtered.slice(0, PICKER_ROW_LIMIT)`, followed by `<MoreRowsHint>`:
   - `pickers.tsx` → `EmployeePickerBody` (single employee picker, also used for Journey observers)
   - `pickers.tsx` → `EmployeeMultiPickerBody` (Assign "Add employees", Journey "Employees this
     observer watches")
   - `SearchablePicker.tsx` → `PickerDialogBody` (Observer person picker)
   - `ObserverPanel.tsx` → `ObserverFieldBody` from §1
3. **Counts and bulk actions always use the full filtered list, never the capped slice.** The
   "{filtered} of {total} active employees", "N matching options" and "Select all / Select all
   shown" lines all count the full filtered list. Only the rendering is capped.
4. Department, designation, mailing list and saved group pickers are small lists, so they get no cap.

**Risk check:** all current test fixtures have far fewer than 100 employees, so no existing test
changes. Add one unit test that renders 150 employees, checks that 100 rows plus the hint show,
then types a name that is past row 100 and checks that it appears.

**Later (not in this PR):** if headcount goes past ~10,000, move employee search to the server
with pages, the way `/assignment/employee-preview` already works. That needs a backend change, so
it should be its own PR.

---

## 5. Optional — Journeys → "Starts after" (earlier journey)

**File:** `JourneysTab.tsx` (`Starts after` select, roughly lines 871–890). Do this only when there
are more than ~10 journeys, otherwise skip it.

Same pattern as §2: a "Filter journeys" box above the select. **One extra rule:** the currently
saved `prerequisiteJourneyId` is always kept in the options even if it doesn't match the filter.
Otherwise the select would show the wrong value and a save could clear the prerequisite.

---

## 6. Verification checklist (must pass before the PR)

Run from the repo root on the feature branch:

```bash
pnpm install --frozen-lockfile
```
```bash
pnpm typecheck
```
```bash
pnpm lint
```
```bash
pnpm format:check
```
```bash
pnpm test
```
```bash
pnpm build
```

Then check by hand in the trainer app (`pnpm dev:trainer`), with a trainer account that can see many
employees:

| # | Screen | Check |
|---|---|---|
| 1 | Assign → Observers → Employees (N) | Search narrows the list; "Select all shown" picks only matches; Done → count on the button is right; Save Observers saves the right IDs |
| 2 | Assign → Observers → Departments (N) | Search narrows departments; selection keeps hidden picks |
| 3 | Assign → Add employees | Opens fast; hint shows when more than 100; a person past row 100 is found by typing |
| 4 | Journeys → sidebar | Search filters; open journey stays open; no "unsaved changes" prompt from typing |
| 5 | Journeys → Courses → Add existing course | Filter narrows; Add is disabled when the pick is filtered out; disabled courses still show their reason |
| 6 | Journeys → Observers → add / employees watched | Search and cap work |
| 7 | Phone width (375px) | Search boxes don't overflow; dialogs scroll |
| 8 | Keyboard | Tab reaches every search box; Esc closes dialogs; the clear (×) button works |

## 7. Delivery

- One PR, `feat/trainer-search`, about 4 files changed plus tests. No backend, database, settings
  or Docker change, so deployment is the usual trainer front-end rebuild only.
- Suggested commit order (each one passes the checks on its own): §4 cap helpers → §1 observer
  dialog → §2 course filter → §3 journey sidebar → (§5 optional).
- Rollback: revert the PR. No data or API depends on it.
