# Email status tab: implementation plan

Status: phases 1–3 and the automated part of phase 4 are implemented for the course assignment email. The UAT comparison with IT's message trace is still to do. Demo: https://claude.ai/artifact/UgTimg9evVmSYZkrUBPVLi

## Goal

Give trainers a per-employee view of a course's assignment emails, at **Performance → Emails** in the trainer app, with course activity alongside and a way to resend failed emails.

## What "correct" means here

PhillipAcademy can only know what happened up to the moment the company mail server answered. It cannot know whether an email reached the inbox, later bounced, went to junk, or was read. No amount of code changes that.

So the rule for this screen is: **every label states exactly what the system recorded, and nothing more.** Where the system does not know, the screen says so. It never infers a reason or guesses a time.

## Why the current data is not enough

A screen built only on today's `email_notifications` table would mislead trainers in these cases.

| # | Today's behaviour | False information it would cause | Fix |
|---|---|---|---|
| 1 | `log` mode marks emails `sent` without emailing anyone | "Sent" for an email that never left | Record the delivery mode on each attempt |
| 2 | `with client as smtp` sends `QUIT` on exit. A non-221 reply raises an exception **after** the server already accepted the message | "Failed", then a duplicate email on retry | Treat `send_message` returning as the point of acceptance; ignore errors while closing |
| 3 | `_claim_pending_notifications` marks the whole batch of 25 `sending` at once | "Sending now" for 25 people when one is in progress | Label it "In current send batch" |
| 4 | A crash, or `_mark_sent` failing, after acceptance leaves the row `sending` until the lock expires, then it is retried | Looks in progress, or later looks unsent, when it may have gone | New "Outcome unknown" state, derived from the attempt record |
| 5 | Workers claim `failed` rows while `attempts < EMAIL_MAX_ATTEMPTS`, so raising that setting revives them. Lowering it strands `pending` rows | "Gave up" when it will retry, or "will retry" when it never will | Derive the state from status and attempts against the current limit |
| 6 | `attempts` goes up when a row is claimed, even if it is then cancelled without contacting the server | "1 attempt" when no attempt happened | Count real attempts from a new attempts table |
| 7 | Cancel reasons are not stored | The demo's "Assignment was withdrawn" would be a guess | Store `cancel_reason` at every cancel site |
| 8 | Skips (no email address, not on allowlist, email off, journey-only) only reach the logs, or nothing at all | "No email address" inferred from today's directory, which may differ from then | Record each skip when it happens |
| 9 | Deadline change, reactivation and completion bump `notification_lifecycle`, with no new assignment email | "Sent" that actually refers to an earlier deadline | Compare lifecycles and show a note |
| 10 | Timestamps are naive `datetime.now()`, the containers set no `TZ`, and `dmyHm` shows the raw value | Times wrong by 5h30 | API returns timezone-aware values, converted on the server |
| 11 | No record of when the worker last ran | Emails shown as "Waiting" forever if the worker is off, and the demo's "next round in 3 minutes" is invented | Worker heartbeat; no time estimates |
| 12 | `recipient_email` is fixed at queue time | Showing the employee's current address when the email went to an older one | Display the address on the email row |
| 13 | The stored `subject` is the queue-time version; the sent one is rebuilt in memory | Wrong subject | Do not display the stored subject |

### A related bug to fix first

`_event_is_current` cancels any email whose lifecycle changed. If a trainer **changes the deadline while the queue is draining** (700 emails take about 3 hours), every assignment email not yet sent is cancelled, and those employees are never told about the course. See Decision 1.

## Phase 1: record the truth (backend, one PR)

All database changes are additive, in `schema.py`. No existing row is rewritten or backfilled with guessed values.

**`email_delivery_attempts` (new)**: `attempt_id`, `notification_id` (FK), `started_at`, `finished_at`, `delivery_mode`, `recipient_email`, `result` (`started`, `accepted`, `logged_only`, `rejected`, `error`), `smtp_code`, `smtp_response` (truncated), `initiated_by`.
A row is written as `started` and committed **before** connecting to the mail server. A row left at `started` is the exact signature of an unknown outcome.

**`email_notification_skips` (new)**: `assignment_id`, `notification_lifecycle`, `event_type`, `recipient_role`, `reason` (`missing_email`, `not_allowlisted`, `delivery_disabled`, `journey_only`), `recipient_email_at_time`, `created_at`, unique on the first four. Written in `enqueue_assignment_notifications`, including its early return when email is disabled.

**`email_notifications` (new columns)**: `cancel_reason`, `resent_by`, `resent_at`.

**`email_worker_status` (new, one row)**: `last_cycle_started_at`, `last_cycle_finished_at`, `last_cycle_ok`.

**Send path changes in `email_notifications.py`**
- Replace `with client as smtp` with explicit handling: once `send_message` returns, the result is `accepted`, and errors while closing are logged and ignored.
- Capture `SMTPResponseException.smtp_code` and the reply text.
- Wrap `_mark_sent` so a database error cannot abort the rest of the batch; log `course_email_accepted_not_recorded`.
- Give `_cancel_stale` and both bulk cancels a reason: `assignment_changed`, `not_allowlisted`, `not_applicable`, `certificate_unavailable`, `moved_to_digest`.
- Write the heartbeat around `run_notification_cycle`.
- `_claim_pending_notifications` must not re-claim an **assignment email** whose last attempt is still `started`. It stays "Outcome unknown" until someone resends it, so the system never sends a possible duplicate by itself. Rows claimed but never attempted are definitely unsent and keep being retried automatically. Other email types have no Resend button, so they keep retrying as before.

## Phase 2: one source of truth for status (backend, one PR)

A single pure function, `derive_email_state(...)`, decides every label. The UI and the CSV only display its output; neither re-derives anything.

| Recorded facts | State | Label |
|---|---|---|
| `sent`, last attempt `accepted` | `accepted` | Sent to mail server |
| `sent`, last attempt `logged_only` | `logged_only` | Not emailed (log mode) |
| `sent`, no attempt record | `sent_untracked` | Recorded as sent (before detailed tracking) |
| `pending`, no real attempts | `queued` | Waiting in queue |
| `pending` or `failed`, attempts below limit, has attempts | `retrying` | Failed, will retry |
| `pending` or `failed`, attempts at or above limit | `gave_up` | Failed, gave up |
| `sending`, lock younger than timeout | `in_batch` | In current send batch |
| `sending`, lock expired, no unfinished attempt | `queued` | Waiting in queue (claimed in a batch but never tried) |
| `sending`, lock expired, last attempt still `started` | `unknown` | Outcome unknown |
| `cancelled` with reason | `cancelled` | Cancelled, plus the reason |
| `cancelled`, no reason | `cancelled_untracked` | Cancelled (reason not recorded) |
| No row, skip recorded | `skipped` | Not sent, plus the recorded reason |
| No row, no skip | `no_record` | No email record |
| Anything unrecognised | `unrecognised` | Status unavailable (and logged as an error) |

Notes shown alongside the state:
- Lifecycle differs and the course is not completed: "The assignment changed after this email (new deadline or reactivated). No new assignment email was sent."
- "Failed, will retry" says "not before {`next_attempt_at`}", never "at".

**Endpoints**, all under `/api/trainer/performance/emails`, using the existing `_trainer_scope`, `owner_filter` and `_assignment_scope`:
- `GET ?course_id=…` returns tile counts, one page of rows, delivery status and `generated_at`, all read in **one `REPEATABLE READ` transaction**, so the tiles always add up to the rows.
- `GET /export` returns CSV through the same function.
- `POST /{notification_id}/resend` and `POST /resend-failed?course_id=…`.

The endpoints reject any scope that is not `TrainerPerformanceScope`. There is no `/api/employee/...` equivalent.

**Delivery status banner** (returned by the API, shown above everything):
- `disabled`: "Email delivery is off. Nothing here will be sent."
- `log`: "Log mode. Emails are written to the server log, not sent."
- Test mode: "Test mode. Only allow-listed addresses receive email."
- Heartbeat older than 3 intervals, or last cycle failed: "The email worker last ran at {time}. Queued emails are not moving."

**Course activity** reuses the `_decorated_assignments` SQL and the same started rule as `employee_page`, so numbers always match the rest of Performance. It uses `last_learner_activity_at`, never `last_activity_at`, which system writes also touch. The column is titled "Course activity" and never implies the email was read.

**Timestamps** are converted on the server with `value.astimezone()` from the server's local clock, and returned with an explicit offset.

**Resend rules**
- Only the course owner or an Admin Trainer (`course_authorization`).
- Allowed for `gave_up`, and for `unknown` only after a confirmation warning that the employee may get a duplicate.
- Rejected if the assignment is completed or revoked.
- One conditional `UPDATE … WHERE status = … RETURNING`. Zero rows returns 409 "This email's status changed. Refresh and try again."
- Sets the current `notification_lifecycle` and the employee's **current** email address, resets `attempts`, and records `resent_by` and `resent_at`. Earlier attempts stay in `email_delivery_attempts`.
- Blocked with a clear message if the employee has no valid email address.

## Phase 3: the screen (frontend, one PR)

- Add `{ view: 4, label: 'Emails' }` to `TABS` in `PerformanceReport.tsx`, shown only when `app === 'trainer'`.
- New `EmailsView.tsx` in `packages/shared/src/performance/`. It needs a course selected; until then it shows "Choose a course".
- Server-side paging (50 rows) and search. Tiles count the whole course, regardless of the page.
- Show "Data as of {`generated_at`}". Refresh button, plus polling every 30 seconds while the tab is open.
- If a refresh fails, keep the old data and show "Couldn't refresh. Showing data from {time}."
- Filter "Sent but not started", computed on the server.
- Assign tab shortcut after publishing, using `linkedReport`.

**Changes from the demo, required for accuracy**: "Sending now" becomes "In current send batch"; "Next send round in about 3 minutes" becomes "Last send round: {time}"; new states for Outcome unknown, Not emailed (log mode), and the untracked labels; raw SMTP errors are replaced with plain explanations (below).

**Error text**: known SMTP codes map to plain wording, e.g. 550 → "The mail server says this mailbox doesn't exist." Unknown errors show "The mail server rejected this email (code {n})." Raw replies can contain internal server names, so only Admin Trainers see them.

## Phase 4: prove it

**Automated, required before merge**
- Truth-table test of `derive_email_state` across every combination of status, attempts, lock age, last attempt result, lifecycle and limit, asserting no combination is unhandled.
- Real-Postgres tests, **actually run**, with a local fake SMTP server covering: accept; 421 then accept; 550 until gave up; accept then bad `QUIT` (must be one email, `accepted`); crash between accept and record (`unknown`); log mode; email disabled; allowlist; no email address; deadline changed while queued; concurrent resend (one wins).
- Invariant: tile counts sum to the course's assignment count.
- Parity: Course activity matches the Employees tab for the same employees.
- Access: HOD and Observer tokens get 403; a non-owner trainer can view but not resend.
- Timestamp test with the server clock in UTC and in IST.

The earlier overdue and journey Postgres tests have not been run yet. Run them in the same pass.

**UAT, required before Production**, with a small test group: one good address, one non-existent mailbox, one employee with no address, one not on the allowlist, one journey-only course. Stop the mail server briefly to force retries. Compare each row against the **mail server's message trace** with IT. Every row must match, or it does not ship.

## Rollout order

1. Deploy Phase 1 first. Accurate records only begin from that moment; older rows keep the "before detailed tracking" labels.
2. Deploy Phases 2 and 3 to UAT, and complete Phase 4.
3. Deploy to Production.

## Out of scope for this version

- HOD and trainer digests, and reminder, due-soon, overdue and completed emails. Journey-only courses show "Not sent: journey course" and their journey emails come later.
- Sending a first email to employees with "No email record".
- Bounce detection. Reading bounces from the sender's mailbox would catch delivery failures after acceptance, but needs IT access and is a separate project.
- Open or read tracking, as agreed.

## Decisions (accepted 2026-11-11)

1. **Deadline changed while assignment emails are queued:** still send them (rebuilt with the new deadline), as long as the assignment is active, instead of cancelling.
2. **Label for accepted emails:** "Sent to mail server" rather than plain "Sent".
3. **Email addresses:** full addresses for the course owner and Admin Trainers, masked for other trainers (done on the server, and in the CSV too), since all trainers can see all published courses in Performance.
4. **Resending "Outcome unknown":** never retried automatically; the course owner or an Admin Trainer can resend it, with the duplicate warning. Emails are sent one at a time, so a crash leaves at most one such email.
