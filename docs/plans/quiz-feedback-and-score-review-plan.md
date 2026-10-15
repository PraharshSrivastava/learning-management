# Employee quiz review, course resume, and Trainer notification fixes

Status: Implemented locally following user approval. Deployment pending. The approved plan is preserved below; implementation checks are recorded in `employee-feedback-verification.md`.
Date: 2026-10-15

## Findings

1. Confirmed: successful non-final module quizzes immediately navigate to the next module. In `employee_frontend/lib/features/learning/course_playback_page.dart`, `_submitQuiz` calls `_onModuleChanged` and returns before the result dialog. The learner cannot review the completed quiz before navigation.
2. Confirmed: reviewing a passed quiz displays the correct answer as the selected radio value, even if the employee selected a different option. `_buildQuestionCard` uses `correctAnswer` for the radio group whenever `isAlreadyPassed` is true and suppresses red styling for an incorrect actual choice in that state. A genuine 2/3 passing attempt can therefore look like three correct selections.
3. Not reproduced: three correct answers receiving 66.67% from the grading calculation. Direct execution of backend `_grade_quiz` returns `correct_count=3`, `total_questions=3`, and `quiz_score=1.0` for 3/3; 2/3 returns `quiz_score=0.6666666666666666`. Six focused existing grading/answer-disclosure tests passed. The pass threshold is exactly two-thirds and is separate from the achieved score.
4. Additional code defect: option keys are derived using `question.options.indexOf(optionText)`. Duplicate answer text aliases later options to the first matching index. Address this in the same answer-display scope with index-based iteration.
5. Timing risk to verify: the passed-score banner prefers widget progress over the local submission score, while the provider asynchronously refreshes courses. Test stale versus current results before deciding whether an additional score-state change is necessary.

Read-only VM verification: repository HEAD `154c20a`; running Employee image `intelligence_layer-employee_frontend:document-builder-44a07fb`. The VM source contains the confirmed navigation and answer-review defects; Employee playback source has not changed between that image's application revision and the current repository revision. No live employee answers were submitted or changed during this investigation.

The original user's exact attempt has not been identified. The UI defect explains how 66.67% can appear alongside apparently correct answers, but does not prove what that employee submitted. Do not claim their score was calculated incorrectly or rewrite their progress without evidence.

## Intended learner experience

After submitting a module quiz, stay in that module and show a result summary above a question-by-question review:

- `Quiz passed — 3 of 3 correct (100%)` or `Quiz passed — 2 of 3 correct (66.67%)`.
- Each question shows `Your answer`, `Correct answer`, `Correct` or `Incorrect`, and its explanation when available.
- The employee's saved choice remains selected. Correct-answer highlighting is a separate visual cue.
- A passed non-final module provides `Continue to Module N`; only that action changes modules.
- A passed final module provides `Finish course` after the same result review.
- A failed attempt shows the actual result and feedback, then an explicit `Rewatch lesson` action consistent with the existing replay requirement.
- Use the actual question count; do not assume every quiz contains three questions.

## Implementation sequence after approval

### 1. Establish regression cases

Add deterministic cases covering 3/3, 2/3, 1/3, different answer keys, and both supported quiz data shapes. Confirm score, counts, selected answers, and pass status agree. Extend the existing response-parser tests for both 3/3 and 2/3.

For a separately identified reported attempt, inspect only its stored selected answers, score, and current published answer key. If the course changed after submission and the old quiz version was not retained, mark any retrospective recalculation inconclusive. Do not treat the current key as historical evidence.

### 2. Correct answer review

Keep the selected radio value bound to the employee's actual selection for fresh, passed, and reopened attempts. Mark an incorrect actual choice visibly even when the overall quiz passed. Render the correct option separately with an explicit label and icon; do not rely on color alone.

Iterate options by index rather than searching by text. Preserve the current backend/frontend option ordering contract. If saved answers are unavailable, show `Answer unavailable` rather than substituting the answer key.

### 3. Show results before navigation

Replace automatic next-module navigation with a persistent, scrollable review state in the current module. Use the returned `QuizSubmissionResult` counts and score as authoritative for the just-completed attempt. Preserve a submission snapshot of the module number, submitted choices, and feedback before an asynchronous provider refresh can change the rendered course.

Keep submission-in-progress separate from result-ready so correct/incorrect indicators appear only after a successful server response. Prevent duplicate submissions. If the employee switches modules or courses during a request, attach the response to its original module and avoid changing the new active module.

For reload/revisit, retain the stored score and actual saved answers. Do not recalculate historical grades from a potentially edited current quiz. Missing or conflicting historical details should be represented honestly, not silently corrected.

### 4. Preserve existing learning rules

Keep grading on the backend. Keep the two-thirds pass threshold, video prerequisite, next-module unlocking rules, and failed-attempt rewatch requirement. Present achieved score separately from the pass requirement. Do not change quiz generation prompts or model configuration for these UI defects.

Existing failed submissions return feedback but do not persist selected answers. Hold their review snapshot in the current session until the employee chooses to rewatch. Reload continues the existing replay flow; persisting full failed-attempt history is a separate scope.

### 5. Verify before release

Required checks:

- Backend: 3/3 is 100%; 2/3 is 66.67% and passes; 1/3 fails; incomplete or invalid selections are rejected; varying question counts remain correct.
- Employee UI: all three question results are visible after submission and the next module does not open automatically.
- Review: a 2/3 passed quiz retains the wrong actual selection and distinguishes it from the correct answer, including after revisit/reload.
- Race cases: slow submission, refresh during submission, stale widget progress, repeated clicks, failed network request, and module/course switch during submission.
- Rendering: duplicate option text does not alias selection; no invented selection when history is missing; desktop/mobile review remains readable; labels/icons support keyboard and screen-reader use.
- Lifecycle: continue goes to the expected next module; final-module review appears before finishing; failed-attempt review cannot bypass replay; zero-question modules retain their existing behavior.
- Build and browser-check the Employee frontend. Run the relevant grading, response-parser, progress, and playback-guard tests. An end-to-end browser test must exercise the real playback component with controlled grading responses.
- If persistence or progress endpoints change during implementation, verify those changes against an isolated PostgreSQL schema before approval for deployment.

## Additional confirmed fix: “Draft removed” notification

The Trainer's `frontend/lib/features/document_builder/document_workflow_portal.dart` creates this SnackBar with a ten-second duration and an Undo action but does not specify `persist`. In the configured Flutter 3.44 SDK, SnackBar defaults to `persist = persist ?? action != null`. An Undo action therefore makes this notification persistent despite the duration. This is a confirmed configuration mismatch, not a backend removal failure.

Proposed implementation:

- Set `persist: false` explicitly for the draft-removal SnackBar; keep the existing ten-second duration so trainers have a reasonable opportunity to Undo.
- Add an explicit close control for immediate dismissal.
- Replace an older draft-removal notification when another removal succeeds so messages do not build up in a queue. Keep each Undo action bound to its own draft ID and revision; verify only the latest notification's action remains available.
- Check dismissal on route/tab changes and portal disposal so an outdated Undo prompt does not linger in another workspace.
- Preserve the existing reversible removal and Undo endpoints. Expiry or closing the notification must not permanently delete the draft, documents, or courses.
- Test that the bar disappears after ten seconds plus exit animation without clicking Undo, closes immediately via the close control, restores the correct draft via Undo before expiry, and handles consecutive removals and Undo failures clearly.
- Verify ordinary and accessible-navigation behavior against the pinned SDK. Do not change global accessibility settings to force dismissal. Retain keyboard access to Undo and Close.

This is a Trainer frontend fix; quiz review is an Employee frontend fix. Later deployment must rebuild and verify both frontend images. Keep the current backend image unless an approved implementation change requires a backend update.

## Additional confirmed fix: resume at the first incomplete module

The Employee playback page initializes `_activeModuleIndex = 0` in its state and explicitly resets it to zero when the course changes. `initState` loads answers for that index without selecting an index from saved progress. Reopening the playback view therefore starts at Module 1 even when earlier modules are complete. The dashboard supplies the course's module-progress map, so the initial fix belongs in the Employee frontend rather than a new progress-reset endpoint.

### Resume rules

Use the most recent successfully loaded server progress for the authenticated employee and current course/assignment. Choose the first incomplete module in the course's displayed, published sequence, looking up progress by actual module number rather than list index.

Completion must follow the backend's existing rule:

- Module with a quiz: video watched **and** quiz passed.
- Module without a quiz: video watched.
- A missing module-progress entry means incomplete once a successful progress response has been loaded. A failed fetch does not mean the employee has no progress.

Expected behavior:

| Saved state on reopening | Opening location |
| --- | --- |
| No modules completed | Module 1 in the published sequence |
| Modules 1 and 2 complete; Module 3 untouched | Module 3, video section |
| Module 2 video complete; its quiz not passed or not submitted | Module 2, quiz section, without requiring its completed video again unless a failed quiz reset its watched status |
| Module 2 quiz failed and video-watched status reset | Module 2, video section, retaining the existing rewatch requirement |
| An earlier incomplete module exists despite later completion records | Earliest incomplete module; do not skip the gap |
| All modules complete | Completed-course view with an explicit Review course action; do not silently restart playback or reset progress |
| No published modules | Existing no-modules state, with no index access |

“Resume” in this scope selects the correct module and, when applicable, its pending quiz. Resuming an unfinished video at an exact timestamp requires separately persisted watch-position data and is not promised by this frontend change. Do not bypass the current continuous-watch restrictions.

### Implementation safeguards

1. Add one testable resume-selection helper driven by published modules and saved progress. Use the same completion rule for resume, related module-status labels, and prerequisite checks where they currently diverge; preserve server enforcement.
2. At explicit course entry (dashboard Continue, direct course link, browser reload, or re-entry after closing), obtain fresh progress before choosing the resume location. Show loading and a retryable error if fresh progress cannot be obtained; do not quietly open Module 1 using an empty/stale response. Reuse the existing authenticated progress-loading path and keep previously displayed data intact on fetch failure.
3. Apply automatic resume only once per explicit entry and course/employee identity. Routine websocket/poll/provider updates must not navigate to another module, clear in-progress answers, dismiss the result review, or restart the video. Handle late responses from a previously opened course and logout/employee changes without applying the wrong progress.
4. After a successful quiz submission, use the separate quiz-result review flow in this plan. Do not let resume-selection logic auto-advance to the first incomplete module during that review. Continue remains an explicit action; closing and reopening later may resume at the next incomplete module.
5. Preserve deliberate selection of an earlier unlocked module for review within the current session. Refresh must not override that selection. Avoid an unsolicited autoplay on resume.
6. On a same-course module-list update, preserve selection by a stable module identity, reconcile it against the new list, and check bounds before access. If the active module disappears, select a valid accessible resume target. Do not rely on a stale array index or on module numbers being contiguous.
7. Reuse saved completion, quiz score, attempt count, and actual selections. Opening or resuming a course must perform no progress-reset writes. No schema change or historical progress migration is needed for the initial frontend fix. If investigation reveals missing server progress rather than selection-only failure, report that separately before expanding the implementation.

### Additional release checks

- Resume with 0, 1, 2, and all modules complete; reload, logout/login, next-day re-entry, and a second browser session loading the same saved progress.
- Video watched but quiz pending; failed quiz requiring replay; zero-question modules; missing module-progress entries; gaps in completion and non-contiguous module numbers.
- Slow/failed progress fetch, stale cached data, and out-of-order refresh responses. No silent reset, wrong initial target, or cross-employee progress reuse.
- While reviewing a 2/3 or 3/3 quiz result, background refresh does not advance modules. Explicit Continue advances correctly, and later reopening resumes from the next incomplete module.
- Manual review of an earlier module survives background refresh; active-module removal/reordering never causes an out-of-range error or a jump to a locked module.
- Opening/resuming preserves stored scores, attempts, answers, and completion. Verify no progress mutation requests are sent merely because the course opens.
- Completed-course entry clearly offers review; it does not present an unfinished course or demand another attempt.
- Add selector unit tests and playback/dashboard browser tests with controlled saved-progress responses. Test desktop and mobile against the actual Employee playback component.

## Combined implementation and approval gate

Prepare all three fixes in the clean `codex/document-builder-workflow` implementation worktree, keeping unrelated local changes intact. Share screenshots or a local demo of 100%, 66.67%, and failed-result review, the ten-second draft notification, and reopening a course at Module 3 after two completed modules. Include the targeted verification results for approval before deployment.

No deployment, production progress edits, course regeneration, or score migration is part of this plan. Any later deployment must explicitly rebuild the Employee frontend image; rebuilding only the Trainer frontend will not update this screen.

Do not blanket-correct existing 66.67% scores to 100%. They may be valid 2/3 results. Any score correction requires a separately verified affected attempt and a backed-up, scoped repair.
