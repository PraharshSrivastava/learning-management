# Employee LMS Dashboard Plan

Branch: `enhance-employee-frontend`

## Scope

This plan covers one screen only: the LMS employee dashboard shown after a user launches the Learning Management System tile from the umbrella application. Course playback, quizzes, profiles, catalog browsing, and full notification history remain out of scope for this phase.

The dashboard should feel like a natural continuation of the umbrella portal: clean white work surfaces, pale gray page background, PhillipCapital blue navigation and actions, Material interaction patterns, and the existing PhillipCapital wordmark. It should still have its own learning-focused hierarchy rather than duplicating the portal dashboard.

## Dashboard Outcome

The first viewport should answer four questions quickly:

1. What learning work is assigned to me and needs attention?
2. How am I progressing overall?
3. What have I already attempted and what was the outcome?
4. Have any new courses been assigned to me?

The page should be useful at desktop widths and remain readable and efficient on tablets and phones.

## Proposed Information Architecture

### App Shell and Left Navigation

- Use a collapsible left navigation rail, matching the hub application's layout and behavior. It is expanded by default on desktop and can collapse to an icon rail through a visible chevron control beside the wordmark.
- Place the PhillipCapital wordmark at the top of the left navigation, with the `Learning Management System` product name visible in the expanded state and available as a tooltip in the collapsed state.
- Show `Dashboard` as the active item. Reserve consistent navigation items for `My Courses`, `Completed`, `Leaderboard`, and `Notifications`; these can be non-navigating placeholders until their internal pages are implemented.
- Keep the left navigation fixed on desktop, and present it as a Material modal drawer on tablet and phone widths. The dashboard content must not be obscured by the drawer.
- Retain a compact top app bar for page context, global actions, the notification bell, and the future profile/account menu. Do not duplicate dashboard navigation in the top bar.
- Show a notification bell as an icon button in the top-right area. It uses a Material badge to show the unread assignment count and changes to a filled/highlighted bell when unread notifications exist.
- Use the umbrella application palette and typography tokens, including the established two-corner PhillipCapital geometry only on key branded surfaces. Standard Material cards remain restrained, with an 8 px radius maximum.

### Header and Learning Summary

- Add a concise welcome heading with the employee name from the authenticated session when available; otherwise use `My learning`.
- Include a short supporting line that calls out the nearest action, such as an overdue or newly assigned course. Do not add generic marketing copy.
- Present a responsive metrics row immediately below the heading:
  - `Assigned` - active courses allocated to the employee.
  - `Attempted` - courses started at least once, including completed courses.
  - `Passed` - completed courses with a passing result.
  - `Pending` - assigned courses not yet started.
  - `In progress` - started but not completed courses.
- Use icon-led metric tiles with one strong numeric value, a short label, and an accessible semantic description. At desktop size, show five evenly sized tiles; collapse to a two-column grid on mobile.

### Assigned Courses

- Make `Assigned to you` the primary course section.
- Place quick filters beside the section title using Material `FilterChip`s: `All`, `Pending`, `In progress`, and `Due soon`. Keep the initial dashboard to these high-value filters rather than adding a full filter panel.
- Show course cards in a responsive grid: three columns on wide desktop, two columns on tablet, one column on phone.
- Every card must contain:
  - a fixed-ratio course thumbnail at the top;
  - course title, clamped to two lines;
  - one-line description, clamped to one line;
  - a status chip such as `New`, `In progress`, `Due soon`, or `Overdue`;
  - learning progress where applicable;
  - one clear action: `Start`, `Continue`, or `Review`.
- Sort by urgency: overdue, due soon, newly assigned, then in-progress. Do not bury required training behind completed content.
- Make the entire card keyboard-focusable and selectable, while keeping the visible action button explicit.

### Attempted Courses

- Add an `Already attempted` section after assigned courses, initially showing the most recent four courses.
- Use the same course-card anatomy for visual consistency, but emphasize outcome and completion date instead of urgency.
- Use Material status chips for `Passed`, `Needs retry`, and `Completed`, without relying on color alone.
- Include a compact `View all` text action; its destination can be left unimplemented or routed to the existing completed view until the dedicated history page is built.
- Show an intentional empty state when the employee has not started any course yet.

### Leaderboard

- Add a compact right-rail panel on desktop, positioned beside the course sections when space permits. Stack it below the course sections on narrower screens.
- Display the top five employees ranked by passed-course count, with rank, name, passed-course total, and the current employee clearly marked when present.
- Keep the visual tone professional: numbered ranks and a simple progress/achievement indicator instead of trophy-heavy decoration.
- Include a loading skeleton and an empty/error state so the panel never looks broken when leaderboard data is unavailable.

### Notifications

- The notification bell should support an unread numeric badge capped at `99+`.
- Clicking it opens a Material menu or anchored panel containing recent learning notifications, beginning with new-course assignments.
- Each notification includes course title, assigned date/time, unread state, and an action to open the relevant course card.
- Opening the panel marks notifications as seen only after the backend contract supports that behavior. Until then, keep visual state local and avoid implying persistence.
- The dashboard must remain usable if notification delivery is temporarily disconnected; show the last known count and a subtle connection/retry state rather than blocking the page.

## Data and Contract Requirements

The current employee course model supplies course and module progress, but this screen needs a small dashboard view model that avoids duplicating status logic across widgets.

- Add or expose `shortDescription`, `thumbnailUrl` (with a local fallback), `assignedAt`, `dueDate`, course progress, and completion/pass result for each course.
- Derive `pending`, `inProgress`, `attempted`, `passed`, `overdue`, and `dueSoon` through one shared status/progress helper.
- Add a dashboard summary contract or locally derive these values from the course list for the first release. A server summary becomes worthwhile when course volumes or reporting rules grow.
- Add a leaderboard endpoint or WebSocket payload returning rank, employee display name, passed-course count, and the current employee's entry if they are outside the top five.
- Add notification data with id, type, title, course id, created time, and read state. Restrict the first release to assignment notifications.
- Confirm authorization rules: users may read only their own courses/notifications; leaderboard names should follow internal privacy policy.

## Component Plan

- `EmployeeDashboardPage`: layout orchestration and responsive breakpoints only.
- `EmployeeLmsShell`: collapsible desktop navigation rail, mobile drawer, top app bar, and dashboard content slot.
- `EmployeeLmsNavigation`: hub-aligned navigation items, active state, collapse control, tooltips, and future routes.
- `EmployeeDashboardHeader`: welcome state and notification trigger.
- `LearningMetricsGrid` and `LearningMetricTile`: the five calculated metrics.
- `DashboardCourseSection`: section title, filter chips, collection state, and optional `View all` action.
- `EmployeeCourseCard`: shared thumbnail, title, description, status, progress, metadata, and action treatment.
- `LeaderboardPanel`: ranking list plus loading, empty, and error states.
- `NotificationMenu`: unread badge, notification list, and course navigation callback.
- `CourseDashboardState` / presentation helper: single source of truth for course statuses, metric counts, ordering, and card labels.

## Visual and Interaction Rules

- Use Material 3 components and `ThemeData` tokens already present in the Flutter app; avoid bespoke controls where Material has a suitable component.
- Use `Image.network` with placeholders, loading treatment, and a local fallback thumbnail. Reserve a stable 16:9 area so images never cause layout shifts.
- Use the existing blue as the primary action color, green for passed/success, amber for due soon/pending attention, and red only for overdue/error. Every status also needs a label and icon/text distinction.
- Keep information dense but breathable: 24 px desktop page padding, 16 px mobile padding, 16 px card spacing, and predictable grid gaps.
- Provide hover, pressed, keyboard-focus, loading, empty, and error states for every interactive surface.
- Do not make the leaderboard or course sections into stacked "cards within cards". Use cards for course items and one contained leaderboard panel; keep page sections as unframed layouts.

## Implementation Sequence

1. Define the dashboard course-status helper and view models, then add unit tests for status and metric calculations.
2. Extend the app theme with Material 3 color, spacing, status-chip, card, navigation, and focus-state tokens. Replace text-only branding with the supplied wordmark asset.
3. Build the hub-aligned LMS shell with its collapsible left navigation rail and mobile drawer, then add the dashboard header, responsive metrics grid, and empty/loading states.
4. Replace the current basic list with responsive assigned and attempted course-card sections, including thumbnail fallbacks and filter chips.
5. Add the notification bell and a locally driven notification menu; connect it to the backend once the notification payload exists.
6. Add the leaderboard panel behind a provider with loading/error handling, then connect the endpoint when available.
7. Run widget tests, `flutter analyze`, and manual visual checks at phone, tablet, and desktop widths.

## First Delivery Milestone

Deliver a polished static-and-live-data dashboard using the existing course feed:

- Branded LMS shell with a collapsible left navigation menu and notification badge UI.
- Five dashboard metrics derived from employee course state.
- Assigned and already-attempted course sections.
- Course cards with 16:9 thumbnail, title, one-line description, status, progress, and action.
- Responsive layout plus loading, empty, and error states.
- A leaderboard panel using clearly isolated sample/provider data until the server endpoint is available.

This delivers the requested dashboard without prematurely designing internal learning pages or requiring backend changes before the UI structure is proven.

## Internal Learning Workspace Plan

### Outcome

Opening a course from the dashboard leads to a focused learning workspace with one clear sequence for every module: watch the video, read the notes, complete the unlocked quiz, then progress to the next module.

### Experience Structure

- Keep the LMS shell visible and replace dashboard content with a course workspace that has a back action, course title, overall progress, and current module context.
- Use a persistent desktop module rail and a Material selector on smaller widths. Each module shows locked, available, video complete, and quiz passed states.
- Place the lesson video first, followed by a concise `Notes` panel and then the quiz. Notes remain readable without competing with the player.
- Show a clear locked quiz state until the video-complete event is recorded. Disable forward scrub controls so the existing full-watch requirement cannot be bypassed.
- Use a compact quiz header with pass mark and answered count. Keep question choices, result feedback, passed state, retry flow, and next-module action in the existing progress contract.

### Data and Safety

- Extend the published module payload with optional `notes`, populated from the existing module text when available; use course description as a fallback for older published courses.
- Preserve existing module progress calls and WebSocket updates for video completion and quiz result submission.
- Keep direct navigation to later modules locked until the previous module quiz has passed.

### Implementation Order

1. Add optional published-module notes parsing/exporting.
2. Connect dashboard card actions to the course workspace with a return action.
3. Refresh the playback layout, course header, module rail, video panel, notes panel, locked-quiz state, and quiz presentation.
4. Disable forward video scrubbing, analyze, and visually check desktop/mobile workflows.
