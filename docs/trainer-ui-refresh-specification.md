# Trainer UI refresh — shared specification

Last updated: 22 October 2026

Dedicated branch: `codex/trainer-ui-refresh`

Starting main release: `b5f8dbc` (PR #32, including the React workflow parity fixes)

Current milestone: Documents design recorded; application implementation pending.

## 1. Purpose and approval record

This is the continuing specification for the Trainer Documents, Blueprint, Courses,
Assign and Performance tabs. Update this same file as each tab is reviewed; do not
replace previously approved requirements with a different design by inference.

The selected Documents design is **Focused desk**, including the subsequent user
corrections: **Your uploaded documents**, no **Edit first** for uploaded files, and
a complete multi-page document preview. The AI entry uses a Gemini-inspired
four-point sparkle with a restrained blue/violet gradient. This is a visual mark;
it does not change the configured AI provider, model, RunPod endpoint or credentials.

| Tab / area                                       | Design status                                               | Implementation status                      |
| ------------------------------------------------ | ----------------------------------------------------------- | ------------------------------------------ |
| Documents landing and uploaded-document preview  | Selected and specified here                                 | Pending                                    |
| Document editor simplification and notifications | Specified here                                              | Pending                                    |
| Blueprint                                        | Next design review; requirements not yet agreed             | Pending design                             |
| Assign                                           | Reserved for later review                                   | Pending design                             |
| Courses                                          | Reserved for later review                                   | Pending design                             |
| Performance / Observer                           | Preserve current behavior; later visual review if requested | No change authorized by this specification |

No application code, generation behavior, backend configuration or deployment is
changed merely by adding this document and its design references.

## 2. Authoritative visual references

- [Focused desk reference source](design/trainer-ui/documents-focused-desk.reference.html).
- [Documents desktop reference](design/trainer-ui/documents-desktop.reference.png).
- [Documents mobile reference](design/trainer-ui/documents-mobile.reference.png).
- [Complete-document last-page reference](design/trainer-ui/documents-pdf-last-page.reference.png).
- [AI sparkle vector reference](design/trainer-ui/ai-sparkle.reference.svg).

The HTML file is a design-only fragment with sample documents and simulated AI
responses. Its host supplies icon rendering and presentation utilities. Do not
serve this fragment as the production Trainer app, copy its sample data into the
database, or substitute its simulated timers for real API state.

**Visual acceptance rule:** implement this layout, wording, spacing, typography,
icon shapes, hierarchy and interaction placement in the React app. Compare the
actual compiled application with these references at the same viewport and theme.
A successful Docker build or an HTTP 200 response alone is not visual acceptance.
Record any intentional deviation in this file before accepting the change.

PDF page content, document counts, file names, timestamps and scores come from
real data and will vary. Their variation must not change the surrounding approved
layout. Native browser PDF toolbar appearance is not an acceptable substitute for
the specified toolbar when exact visual matching is required; see section 8.

## 3. Documents layout: fixed order and wording

The Documents tab opens the workspace directly, with no extra Document Builder
landing page or modal required to reach the two starting choices.

1. Existing PhillipCapital header and navigation: Documents, Blueprint, Courses,
   Assign and Performance. Documents is visibly active.
2. Page heading **Documents**, with a short supporting sentence.
3. Two creation cards in this exact order:
   - **Use existing content** — upload a ready document and open Blueprint.
   - **Generate with AI** — describe the topic and review an AI draft.
4. **Recent drafts**, initially showing the three most recent drafts.
5. **Your uploaded documents**, initially showing the five most recent files.

Remove **Start blank** from the main creation choices. Preserve existing blank-mode
drafts and valid saved links; hiding an entry card must not delete or strand work.
Keep normal manual editing available inside an existing authoring draft.

### Recent drafts

- Show a meaningful title, module count or outline state, and readable edit time.
- Keep **Open** and **Remove**, with accessible names for icon-only actions.
- Retain **View all** / **Show recent** when there are more than three drafts.
- Removal has an Undo opportunity and a dismissible notification. Retain the
  existing ten-second removal-notice duration; do not leave a permanent bottom bar.
- Removing a draft must not remove an uploaded original document or a course.

### Your uploaded documents

The heading must be **Your uploaded documents**, not **Your documents**.

- These are already prepared documents intended for course creation.
- Row actions are **Preview** and **Create course** only.
- Remove **Edit first** from the rows, the uploaded-document preview and this
  ready-document entry flow. AI draft editing remains a separate authoring path.
- Show a consistent file-type icon, readable document name, file type, size and
  readable date. Do not display internal storage prefixes as the main title.
- Show the first **five** most recent files by default, using a stable ordering.
- Show **View all documents (N)** when more than five matching files exist.
- Expanding changes to **Show recent documents**; collapsing returns to five.
- Keep the search field in this section header. Search the complete owned file
  collection before applying the five-row limit, not only the visible five rows.
- Search remains available while the preview is open and in View all mode.
- Handle empty, no-match, loading and fetch-error states without a blank panel.

## 4. Complete uploaded-document preview

Clicking Preview expands **immediately beneath the selected document row**, inside
Your uploaded documents. It must not open a separate preview block after the
entire library, move the user to the bottom of Documents, or open the editor.

Only one file preview is open at a time. The selected row is softly highlighted.
Closing restores the document list and keyboard focus to the appropriate row.
Changing files replaces the current viewer and cancels or ignores stale loads.

The viewer is read-only and opens the **complete document**, not a thumbnail,
first-page screenshot or extracted-text summary. For DOCX/PPTX, use the existing
complete converted-PDF preview while preserving the original uploaded file.

Viewer controls and layout:

- Header: document name and **Read-only preview · Complete document · N pages**.
- Header actions: **Create course** and **Close**. No Edit first action.
- Toolbar: Previous page, editable current-page number, total pages, Next page,
  Zoom out, zoom percentage, Zoom in and Fit width.
- Continuous vertical reading surface; every page must be accessible by scrolling
  and by entering its page number. All pages belong to the same uploaded document.
- Desktop viewport: 530 px high; mobile: 480 px. This deliberate internal scrolling
  is confined to the PDF reader, so a long file does not stretch the whole library.
- Default page 1 and fit-width presentation; supported demo zoom steps are
  75%, 100%, 125%, 150%. Bind real controls to actual rendered-page geometry.
- Page navigation clamps to the valid page range. Disable Previous on page 1 and
  Next on the final page; keep the page counter in sync with scrolling.
- Footer identifies the total available pages and the reading/navigation affordance.
- Show explicit document-loading and document-load-error states. Keep the filename
  and a retry/open-original fallback visible if embedded viewing fails.
- Do not silently reload the open PDF when an authentication media ticket refreshes.
- Preserve document ownership checks, media authorization, original content and
  existing conversion behavior. Do not expose a public storage-file URL.

The reference contains an eight-page sample. Production page count and content
must come from the actual PDF. Large documents may render pages lazily; this must
not limit access to the rest of the file or claim that only loaded pages exist.

## 5. Ready-document course creation

Keep the current, confirmed workflow:

**Your uploaded documents → Create course → outline extraction → Blueprint review
→ Generate Course → videos and quizzes.**

- Use the selected file's server-assigned filename and existing ownership-checked
  generation endpoint through `useGenerateCourse`.
- Go directly to Blueprint without creating an authoring draft or asking for AI
  Builder topic, audience, learning goals or imported-outline approval.
- Show loading while the course outline is extracted and select the returned course.
- Creating/opening the Blueprint must **not automatically start video/quiz
  generation**. That starts when the trainer clicks Generate Course in Blueprint.
- Prevent duplicate requests and show a useful failure message with a recovery path.
- Keep the existing ready-upload shortcut: a successful ready-document upload opens
  Blueprint; failed/cancelled uploads must not create a course.

## 6. AI authoring and editor simplification

Keep Generate with AI's three essential inputs and its existing reviewed workflow:
topic, audience and learning outcomes → outline proposal → approval → draft/editor
or course handoff as already supported. Default module wording remains
**Default — 4 modules**.

The main editor insertion/formatting toolbar exposes only:

**Bold · Italic · Heading · Image**

- Remove Bullet list, Numbered list and Table insertion buttons from the primary
  module editor toolbar, matching the selected demo.
- Do not delete list/table blocks already present in saved or imported content.
  Preserve their data, rendering, source references and downstream PDF/course export.
- Preserve autosave, mark ranges, Undo/restore safeguards, revision checks, sources,
  image layout controls and explicit AI suggestion acceptance from main.
- Keep source/reference/history and other secondary tools available without putting
  every advanced action on the primary toolbar.
- Preserve all supported assistant scopes and clearly separate Original, Suggested,
  the review notice, and Accept/Dismiss actions.
- Removing an uploaded-file Edit first shortcut does not remove editing from AI
  drafts or stop existing drafts from opening through Recent drafts.

## 7. Visual tokens and icon contract

Use scoped product tokens and existing locally bundled Inter font files. Do not
depend on a font CDN, Unicode symbols, emojis or machine-specific icon fonts.
Use consistent vector icons with visible text labels and accessible names.

### Core light appearance

| Token / element                | Required value                                       |
| ------------------------------ | ---------------------------------------------------- |
| Workspace background           | `#f4f6fa`                                            |
| Cards and controls             | `#ffffff`                                            |
| Primary text                   | `#19273e`                                            |
| Secondary text                 | `#5b6980`                                            |
| Borders                        | `#e0e7f0`                                            |
| Soft selected/interactive fill | `#edf3fc`                                            |
| Primary brand/action           | `#153c83`                                            |
| Main heading                   | Inter, 28 px, weight 500                             |
| Section heading                | Inter, 17 px, weight 500                             |
| Body                           | Inter, 14 px, weight 400                             |
| Row titles/actions             | 12 px, weight 500                                    |
| Supporting metadata            | 11–12 px; no smaller                                 |
| Main content                   | Max width 1240 px, centered; desktop padding 30 px   |
| Card corners / control corners | 12 px / 8 px                                         |
| Card gap                       | 16 px; approximately 20–24 px between major sections |
| Creation-card icon container   | 45 × 45 px, 12 px radius                             |
| Normal action/file icons       | 17–22 px, consistent visual stroke                   |
| AI sparkle mark                | 24 px, four points, blue → violet → soft purple      |

Dark-theme equivalents are defined in the committed reference. Preserve contrast,
hierarchy and selected states; do not simply invert the light screenshot.

### Icon choices

| Action / state                   | Reference mark                                       |
| -------------------------------- | ---------------------------------------------------- |
| Use existing content             | Cloud upload                                         |
| Generate with AI / AI generation | Single four-point sparkle; Gemini-inspired treatment |
| Uploaded PDF / document          | File text                                            |
| DOCX                             | File with pen                                        |
| PPTX                             | Presentation                                         |
| Preview                          | Eye                                                  |
| Create course                    | Open book                                            |
| Open draft / draft content       | File with pen                                        |
| Remove                           | Trash                                                |
| Search                           | Magnifying glass                                     |
| Warning / unavailable            | Warning triangle                                     |
| Error                            | Circled exclamation                                  |
| Success / saved                  | Circled check                                        |
| Working                          | Loader with explanatory text                         |

The prototype uses standard Lucide shapes. The AI reference vector is a locally
saved mark, not a remotely loaded Google logo. Its gradient stops are `#4787ff`,
`#8b5cf6`, `#c779df`; its icon-container gradient is `#edf4ff` → `#f0eaff` in light
appearance. Keep the visible label **Generate with AI**; do not label the configured
model Gemini. Preserve the existing PhillipCapital brand identity.

Production icons must be bundled and versioned in the frontend (through a shared
component/local SVG or an approved pinned icon package), with applicable attribution.
Do not copy the prototype's dependency on a host-provided `lucide` global.
For an inline SVG gradient, use a unique ID per component instance (for example,
React `useId`); do not repeat the standalone reference's gradient ID across icons.

## 8. Feasibility review and implementation map

All requested layout, controls and icon changes are feasible in the React frontend.
The existing backend already provides the ready-file handoff and full-document
preview. This design does not require a new server, model or deployment topology.

| Area                                 | Existing code / capability inspected                         | Required change / constraint                                                                                                                                                                                                             |
| ------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Landing, counts, search, row actions | `apps/trainer/src/features/documents/DocumentsWorkspace.tsx` | Two entry cards, uploaded naming, five-file limit, inline preview placement, no uploaded-file editing shortcut                                                                                                                           |
| Full PDF source                      | `PdfViewerCard.tsx`, `previewFileUrl`, `useHasMediaTicket`   | Existing iframe loads the full PDF; reuse authenticated source and conversion, not a first-page image                                                                                                                                    |
| Exact PDF controls                   | Current browser-native iframe toolbar                        | Native toolbars differ by browser. To reproduce the reference toolbar exactly, use app-owned controls with a bundled PDF renderer such as PDF.js; validate worker/CSP/media authorization and dependency packaging before implementation |
| Course handoff                       | `useGenerateCourse.ts`                                       | Preserve existing request, blocking overlay, cache update and Blueprint navigation                                                                                                                                                       |
| Editor tools and assistant           | `FocusedWorkspace.tsx`, `editorParity.tsx`                   | Hide insertion actions without changing stored block/schema support or assistant scope/revision guarantees                                                                                                                               |
| Fonts                                | `packages/shared/src/theme.css` and bundled Inter files      | Reuse local regular/medium faces; scope Documents styling before adopting it on other tabs                                                                                                                                               |
| Existing vector support              | `packages/shared/src/ui/icons/Icon.tsx`, `iconData.ts`       | Replace text glyphs with consistent bundled vectors; add/reuse a dedicated AI mark, keeping accessibility                                                                                                                                |
| Notifications                        | Documents error/state rendering and shared `Toast.tsx`       | Add typed, readable status presentation without changing error semantics or leaking backend details                                                                                                                                      |

The PDF toolbar is the integration item requiring the most care. Feasibility is
established by existing full-PDF access plus a controlled frontend renderer, but
exact real-PDF rendering/worker integration has **not** been implemented or tested
by saving this specification. Do not claim the HTML sample is a working production
PDF.js integration or promise browser-native controls will be pixel-identical.

## 9. Notifications and loading

| State                                   | Appearance                                            | Behavior                                                                                        |
| --------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Saved / success                         | Text `#14694b`, background `#edf8f2`, check icon      | Short, non-blocking; normally dismiss after about 4–5 seconds                                   |
| Draft removed                           | Same success styling, Undo and Dismiss                | Ten-second Undo notice; then disappears                                                         |
| Model unavailable / recoverable warning | Text `#865515`, background `#fff7e9`, warning icon    | Keep work intact; Try again and Dismiss; do not disappear before it can be acted on             |
| Validation / save failure               | Text `#a43441`, background `#fff1f2`, error icon      | Explain the fix or Retry save; retain input/unsaved edits; do not auto-dismiss a data-loss risk |
| Generating / loading                    | Brand-blue text on soft blue, loader plus stage label | Reflect actual queued/running/completed state; no frozen button or silent blank panel           |

Preferred unavailable copy:

> Document model is unavailable
>
> We couldn't reach the AI service. Your work is safe. Try again or continue editing.

Use that copy only when the failure indicates model connectivity/availability.
Authentication, authorization, invalid input and document-conversion errors need
their own correct messages. Do not relabel every failure as a model outage.

Use real server progress when available; otherwise use an indeterminate indicator
with an honest stage name. Do not copy the reference's simulated percentages,
elapsed-time completion or fabricated ETA into production. Do not show All changes
saved until persistence succeeds. Keep a revision conflict actionable.

Color is always paired with icon and text. Use `role=status`/polite announcements
for progress/success and appropriate alerts for errors. Respect reduced motion.

## 10. Responsive and accessibility acceptance

- Match desktop reference at 1080 px viewport width; also inspect 1440 and 1024 px.
- Validate 800, 480, 390 and 320 px widths; no page-level horizontal overflow.
- Creation choices stack on small screens. Row actions wrap beneath metadata.
- Search stays in the uploaded-section header and remains full-width when needed.
- PDF toolbar groups wrap; the reader retains all pages without clipping controls.
- Keyboard users can search, open/close a preview, navigate pages, zoom, open drafts,
  remove/undo and create a Blueprint. Keep focus visible and restore it on close.
- Provide a readable fallback/open-original action when embedded PDF viewing is
  unavailable on a supported browser. Do not make mobile depend on a desktop plugin.
- Long filenames wrap safely or expose their full title accessibly. Dates are human
  readable. Empty/loading/error states preserve the page structure.

## 11. Implementation and post-deployment acceptance checklist

These boxes remain unchecked until the real application is implemented and verified.

The design reference itself was checked in Chrome on 22 October: renamed library,
five-row limit, full-collection search, no uploaded-file Edit first, all eight sample
pages, last-page navigation, zoom/Fit width, inline preview, responsive fit and
Blueprint handoff passed with no runtime errors. The AI mark has one four-point
shape and three gradient stops. These are prototype checks, not production PDF or
model acceptance results.

- [ ] React Documents landing matches the committed desktop/mobile references.
- [ ] Local vector icons load without network fonts, emojis or missing glyphs.
- [ ] AI sparkle shape/gradient matches the saved vector and is consistent in AI actions.
- [ ] Only two entry cards; existing authoring drafts still reopen correctly.
- [ ] Uploaded section has the exact heading and no Edit first shortcut.
- [ ] Five files initially; View all/Show recent and complete-library search work together.
- [ ] PDF preview opens beneath the clicked row and closes without a bottom-page jump.
- [ ] A real multi-page PDF can reach its last page by scrolling and page number.
- [ ] Real DOCX/PPTX converted previews expose every page and preserve originals.
- [ ] Page count, zoom, Fit width, loading, error and authorization behavior are tested.
- [ ] Auth refresh does not unexpectedly reload or swap the selected document.
- [ ] Create course opens Blueprint and does not start videos/quizzes before confirmation.
- [ ] Main editor has Bold/Italic/Heading/Image; existing list/table content is retained.
- [ ] Autosave, revisions, sources and all assistant scopes pass regression checks.
- [ ] Model-unavailable, validation, save-failure, progress and timed notices are verified.
- [ ] Relevant component/interaction tests, types, lint and production builds pass.
- [ ] Desktop/mobile browser acceptance uses the compiled app, not the sample HTML.
- [ ] Deployed HTML and JS/CSS hashes match the intended built images at the public URLs.
- [ ] Self-hosted fonts, icon assets and any PDF worker load correctly under `/lms/trainer/`.
- [ ] Hard-refresh/cache behavior is verified against the actual deployed screen.
- [ ] Existing same-Compose, tagged-image, backup/rollback deployment is retained.

Public acceptance uses the established Trainer URL and its normal authentication.
Do not introduce a new deployment port, localhost-only replacement or pilot service
as part of this visual refresh. Keep backend/database/AI configuration unchanged
unless a separately documented implementation requirement is approved.

## 12. Extending this file for the next tabs

Next: **Blueprint**. Add its approved layout, actions, workflow boundaries, states,
icons, responsive rules, references, feasibility notes and acceptance checks below.
Then do the same for Assign and any remaining tabs.

For each approved change, record the date, affected requirement, reference version
and implementation status. Shared tokens/icons should stay consistent; a later tab
must not silently change Documents wording or restore removed entry/actions.

### Blueprint — pending design review

No new Blueprint UI has been finalized. Preserve current course outline extraction,
module review, save/reset behavior and explicit Generate Course step while its
design is discussed. Do not implement a guessed redesign from this placeholder.

### Assign — pending design review

No new Assign UI has been finalized. Preserve current assignment, role, observer,
deadline, lifecycle and notification behavior while reviewing presentation later.

### Change log

| Date        | Decision                                                                                                       |
| ----------- | -------------------------------------------------------------------------------------------------------------- |
| 22 Oct 2026 | Selected Focused desk over side-by-side and library-first alternatives                                         |
| 22 Oct 2026 | Renamed uploaded library; removed uploaded-file Edit first; required full-document inline preview              |
| 22 Oct 2026 | Confirmed uploaded-file Create course opens Blueprint; videos/quizzes start only on its Generate Course action |
| 22 Oct 2026 | Created dedicated branch and continuing specification; added Gemini-inspired AI sparkle reference              |
