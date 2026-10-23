# Trainer UI refresh — shared specification

Last updated: 23 October 2026

Dedicated branch: `codex/trainer-ui-refresh`

Starting main release: `b5f8dbc` (PR #32, including the React workflow parity fixes)

Current milestone: Documents and Blueprint implemented and locally verified;
awaiting review on big-coding. Assign remains planned and its application interface
is unchanged in this release.

## 1. Purpose and approval record

This is the continuing specification for the Trainer Documents, Blueprint, Courses,
Assign and Performance tabs. Update this same file as each tab is reviewed; do not
replace previously approved requirements with a different design by inference.

The selected Documents design is **Focused desk**, including the subsequent user
corrections: **Your uploaded documents**, no **Edit first** for uploaded files, and
a complete multi-page document preview. The approved icon treatment is the subsequent
Smart document proposal: navy document outline, blue wand and restrained violet
accent for Generate with AI; document/upload for existing content; red PDF file
marks and navy document marks for drafts. This supersedes the earlier standalone
Gemini-inspired sparkle. These are visual marks;
they do not change the configured AI provider, model, RunPod endpoint or credentials.

| Tab / area                                       | Design status                                                                                           | Implementation status                      |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| Documents landing and uploaded-document preview  | Selected and specified here                                                                             | Implemented; VM acceptance pending         |
| Document editor simplification and notifications | Specified here                                                                                          | Implemented; VM acceptance pending         |
| Blueprint                                        | Refined desk interactive design approved                                                                | Implemented; VM acceptance pending         |
| Assign                                           | Focused assignment with left course list and top actions approved; employee-picker correction specified | Implemented; VM acceptance pending         |
| Courses                                          | Reserved for later review                                                                               | Pending design                             |
| Performance / Observer                           | Preserve current behavior; later visual review if requested                                             | No change authorized by this specification |

The current implementation milestone changes Documents and Blueprint React code,
including the bundled PDF reader and Blueprint-only lifecycle-action presentation.
No backend/model configuration, Assign application interface or deployment topology
is changed. VM deployment/acceptance remains pending.

### Blueprint implementation verification — 23 October 2026

- Refined desk implemented with scoped Inter, white working surfaces, highlighted
  course sidebar, existing availability and My Courses/All Courses controls. Title
  search is available within the owned Blueprint course list; eligibility is unchanged.
- Single permitted lifecycle actions show directly; zero actions hide and multiple
  actions retain their menu. Default behavior in Assign/other callers is unchanged.
  Ownership, impact/revision checks, typed DELETE confirmation and Enable handoff remain.
- Course details, module cards and source-image review expand/collapse. Existing module
  fields, quiz counts, content, keyboard/drag reorder and video download are retained.
- Source-image captions and mappings remain read-only, matching the current API.
  The demo's editable image-assignment fields are not implemented as unsupported
  server writes. Mapping badges now show current module positions after reordering.
- Saved/unsaved status reflects actual editor state. Course changes, reset and module
  removal protect pending work; server refresh cannot silently overwrite dirty edits.
- Existing save-before-new-generation, checkpoint resume and failure handling are
  preserved. No model/provider or generation endpoint is replaced by a UI simulation.
- Combined validation: 455 React tests passed, workspace TypeScript and ESLint passed,
  production Trainer build passed. Compiled browser fixtures verified Blueprint save
  payloads, dirty navigation, authenticated image loading, typed-delete cancellation,
  save-before-generation/failure and 390/320px layouts without runtime errors.
- Rechecked Documents against the combined build, including full eight-page PDF
  rendering and navigation. Live model/video generation and VM asset delivery still
  require acceptance on big-coding.
- [Compiled Blueprint desktop](design/trainer-ui/blueprint-implemented.desktop.png).
- [Compiled Blueprint mobile](design/trainer-ui/blueprint-implemented.mobile.png).

### Uniform trainer frame — 23 October 2026

User direction: the same layout and fonts on every tab. `apps/trainer/src/shell/desk.css`
now gives Documents, Blueprint, Courses, Assign and Performance one frame: Inter only,
`#f4f6fa` background, 24/32 px page padding and one course-sidebar width
(`clamp(272px, 22vw, 360px)`). Page titles are 28 px and section and sidebar titles are
17 px, all medium weight. Intentional deviations from earlier sections: Documents is
full width instead of a centered 1240 px column; Courses uses the Blueprint desk and course
list; the shared Performance report sits in the trainer frame with Inter (its content and
the employee app are unchanged). Verified on big-coding at 1600 px: all tabs start at the
same position, use only Inter, and the three course sidebars are 352 px wide.

### Assign implementation verification — 23 October 2026

- Focused assignment layout: Blueprint-style course sidebar with search; header card with
  the top toolbar (Save Rule, Refresh, direct lifecycle action, paper-plane publish button).
  No bottom action bar. Two columns from 1280 px: Target employees above Assignment
  preview; Completion deadline above Performance observers. Single column below.
- Add employees opens a searchable multi-select picker with no group step. Picks are kept
  in the first plain employee-id include group (never a saved group), so the rule format and
  backend contract are unchanged. Exclusions use the same picker. Department, mailing list,
  joined-days and saved groups remain under a collapsible filter section; filter groups no
  longer offer their own employee picker, and existing employee ids in them stay removable.
- Lifecycle control shows Disable/Delete directly and never a second Enable: the publish
  button is Enable for disabled courses and keeps its preview/confirmation flow.
- Save Rule, publish confirmation, observer Save/Apply, deadlines, conflict reload and
  inert-while-busy behavior are unchanged. 468 React tests passed; types and lint clean.
- Checked on big-coding (`trainer-ui-7e71952`) with real courses, read-only: layout at
  1440/1080/375 px with no horizontal overflow, picker search/selection/cancel, existing
  department rule loaded intact, single Enable on a disabled course. Publishing was not
  exercised. The design reference still shows the superseded department selector.

### VM review fixes — 23 October 2026

- Recent drafts imported from an uploaded document (entry mode `existing` with a source
  document) open that document's course in Blueprint, or create it through Create course
  when none exists. Only AI-generated and pasted-notes drafts open the document editor.
- PDF preview failed on the VM for every file: nginx served the PDF.js module worker
  (`.mjs`) as `application/octet-stream`, which browsers refuse to run. The trainer nginx
  now serves `.mjs` as JavaScript.
- The Document Builder AI (outline, modules and assistant) uses `DOCUMENT_BUILDER_MODEL`
  `qwen3.6-35b` through LiteLLM with `DOCUMENT_BUILDER_ENABLE_THINKING=false`; otherwise
  Qwen returns reasoning only. Course/video/quiz generation keeps `LLM_MODEL_NAME`.

User steering after the Documents milestone authorized Blueprint implementation
before the combined VM review. Stop before implementing Assign.

### Documents implementation verification — 23 October 2026

- Scoped Inter styling, two creation cards, bundled Smart document/upload/PDF/draft
  icons, recent drafts, removal/Undo, uploaded-file search/five-row limit/View all,
  inline full-PDF reader and simplified editor tools are implemented.
- PDF.js worker, character maps, fonts and image-decoding assets are bundled under
  `static/`; the renderer loads on demand and preserves protected media access.
- Local validation: 443 React tests passed; workspace TypeScript and ESLint passed;
  production Trainer build passed. Existing jsdom scroll/act diagnostic warnings
  do not represent production browser failures.
- Compiled-app browser acceptance used synthetic authenticated API data and a real
  eight-page PDF. Verified default five rows, search beyond those rows, View all,
  recent three drafts with Undo, actual worker/canvas rendering through page eight,
  one PDF fetch, scoped Inter, and 390/320px layouts with no runtime errors.
- This does not establish live RunPod/model health, DOCX/PPTX conversion health or
  VM deployment correctness. Test real upload, AI outline/editor, PDF images and
  Blueprint handoff on big-coding before approving the next tab's implementation.
- The initial Documents milestone paused for review. The user's subsequent
  instruction authorized Blueprint in the same branch before VM testing; Assign
  remains outside the implemented release.

## 2. Authoritative visual references

- [Focused desk reference source](design/trainer-ui/documents-focused-desk.reference.html).
- [Documents desktop reference](design/trainer-ui/documents-desktop.reference.png).
- [Documents mobile reference](design/trainer-ui/documents-mobile.reference.png).
- [Complete-document last-page reference](design/trainer-ui/documents-pdf-last-page.reference.png).
- [Earlier AI sparkle vector reference — superseded](design/trainer-ui/ai-sparkle.reference.svg).

Compiled Documents milestone references (23 October; synthetic API fixtures,
actual React build and real eight-page PDF):

- [Implemented desktop](design/trainer-ui/documents-implemented.desktop.png).
- [Implemented mobile](design/trainer-ui/documents-implemented.mobile.png).
- [Implemented last-page PDF preview](design/trainer-ui/documents-implemented.pdf-last-page.png).

These supersede the earlier prototype icons. The production mark source is
`apps/trainer/src/features/documents/DocumentsIcon.tsx`; Inter and scoped styling
are in `DocumentsStyles.css`. Compare VM appearance to these compiled references,
allowing real filenames/counts/content to vary. VM visual acceptance is still pending.

The Smart document image proposal approved on 22 October supersedes icon shapes
in the earlier HTML/screenshots only. Its reference is
`design/trainer-ui/documents-smart-document.approved.png`. Preserve the agreed
layout and workflow. The small comparison inset in that proposal is not part of
the application. Recreate the approved icons as bundled crisp vectors, then update
the executable reference and desktop/mobile screenshots before implementation
acceptance; do not treat a generated bitmap as a production UI icon sheet.

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
| AI Smart document mark         | 24 px, navy document, blue wand, violet accent       |

Dark-theme equivalents are defined in the committed reference. Preserve contrast,
hierarchy and selected states; do not simply invert the light screenshot.

### Icon choices

| Action / state                   | Reference mark                                           |
| -------------------------------- | -------------------------------------------------------- |
| Use existing content             | Navy document outline with upload arrow                  |
| Generate with AI / AI generation | Smart document: document outline and wand, violet accent |
| Uploaded PDF                     | Red outlined file with PDF label                         |
| Other uploaded document          | Appropriate document-type mark                           |
| DOCX                             | File with pen                                            |
| PPTX                             | Presentation                                             |
| Preview                          | Eye                                                      |
| Create course                    | Open book                                                |
| Open draft / draft content       | Navy document outline with short text lines              |
| Remove                           | Trash                                                    |
| Search                           | Magnifying glass                                         |
| Warning / unavailable            | Warning triangle                                         |
| Error                            | Circled exclamation                                      |
| Success / saved                  | Circled check                                            |
| Working                          | Loader with explanatory text                             |

The earlier prototype uses standard Lucide shapes; its standalone AI sparkle is
superseded. Follow the approved Smart document image for the four entry/file icon
families. Use pale blue backing for upload, pale lavender for AI, and restrained
neutral backing for file/draft marks. Keep the visible label **Generate with AI**.
Preserve the configured model and existing PhillipCapital brand identity.

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

The PDF toolbar required controlled worker and asset integration. Real-PDF
rendering/worker integration is now implemented and locally browser-verified in
React. The earlier HTML sample remains a design reference, not the production
PDF.js reader. Validate the compiled worker and fonts again on the VM.

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
- [ ] Approved Smart document, upload-document, red PDF and navy draft icons match the new proposal at actual UI size; updated executable references supersede the old sparkle.
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

Next: **Assign**. Record its selected layout, workflow boundaries and acceptance
checks below; Blueprint Refined desk has been approved. Continue with other tabs
in this same specification.

For each approved change, record the date, affected requirement, reference version
and implementation status. Shared tokens/icons should stay consistent; a later tab
must not silently change Documents wording or restore removed entry/actions.

### Blueprint — Refined desk approved

The user approved Option A and its interactive Refined desk demo on 22 October.
Implement the familiar course sidebar and expandable module workspace. Preserve
current course outline extraction, module review, save/reset behavior and the
explicit Generate Course step. Option B is not selected.

Requested changes recorded on 22 October:

- Replace the generic Actions dropdown with the actual labeled action when exactly
  one action is available. Current code permits Disable, Enable and Delete depending
  on lifecycle/ownership; more than one may be available. Keep multiple choices
  accessible, hide the control when none are available, and retain all ownership,
  in-progress blocking, impact checks and confirmation behavior. Enable retains its
  existing Assign handoff. Do not equate Enable with Generate course.
- Improve corporate presentation, spacing, hierarchy, module review and loading/error
  clarity consistently with Documents, following the approved Refined desk demo.
- Demos compare A: Refined desk (familiar course sidebar and expandable module cards)
  with B: Module workspace (course picker and module navigation beside one editor).
  Refined desk is now selected; neither design permits removal of existing fields
  or generation controls.
- Preserve save validation and generation/resume semantics; never show fake progress
  percentages or silently discard unsaved edits when switching courses/modules.

Reference priority:

- [Approved interactive Refined desk source](design/trainer-ui/blueprint-refined-desk.reference.html).
- The source contains sample courses, local saves and simulated generation; port
  layout and interaction placement into React, not its mock store or timers.
- Retain title, difficulty, language, description, learning goals and audience.
- Modules use expandable cards with persistent title, quiz question count and module
  content. Preserve existing image references, video downloads and all supported
  module configuration; do not replace module content with invented backend fields.
- Provide Add module, reorder and confirmed removal; removed modules must not leave
  invalid image references. Retain Reset to saved blueprint with discard confirmation.
- Source images are a separate expandable section with image, caption and assigned
  module. Unassigned images have an explicit label; current ownership and asset
  access rules remain enforced.
- Save and Generate remain visually separate. Reflect real saved/dirty state; protect
  edits when switching courses. Match existing generation/save behavior, validation,
  failure/resume and completed states rather than adopting the demo's simplified logic.
- Use a white working surface, subtle borders, navy primary Generate action, quieter
  Save/Reset controls and restrained red destructive controls. Use consistent bundled
  vector icons and accessible action labels. Keep direct lifecycle actions conditional.
- Reflow sidebar and fields on mobile; no hidden essential actions or page overflow.
- Verify direct Delete/Disable/Enable, confirmation/cancellation, no-action/multiple-action
  states, module editing/order/removal, image mapping, dirty/save/reset, course switching,
  generation failures/resume and mobile/keyboard operation against the compiled app.

Earlier illustrative references:

- [A — Refined desk](design/trainer-ui/blueprint-a-refined-desk.proposal.png).
- [B — Module workspace](design/trainer-ui/blueprint-b-module-workspace.proposal.png).

These generated images communicate hierarchy and layout, not final data contracts.
Before freezing the selected reference, map every existing Blueprint field and
image-assignment control to its destination; labels such as Key learning points
must not imply a new backend field. Preserve existing question-count and module
configuration controls even if omitted in these illustrative images. Do not add
module-only Reset semantics from proposal B without defining them. Preserve the
existing PhillipCapital wordmark and navigation; incidental generated brand or
navigation decoration is not approved. Saved indicators must reflect real state.

### Assign — Focused assignment approved with corrections

The selected Assign layout is Focused assignment with the course list on the left,
distinct aligned panels and the top action toolbar. On 23 October the user rejected
the bottom action-bar proposal and explicitly required the current individual
employee-selection workflow. These corrections override conflicting demo details.
Preserve current assignment, role, observer, deadline, lifecycle and notification
behavior. Requirements:

#### Approved layout and action placement

- Keep all assignable courses in the left course panel, with the selected course
  clearly highlighted and its lifecycle/module metadata readable. This is the
  existing Assignable Courses collection, not an expansion of eligibility or access.
- In the main workspace, show a course heading and **top** action toolbar containing
  Save rule, Refresh, the state-appropriate assignment button and any independent
  permitted lifecycle action. Keep the paper-plane icon on assignment publication.
- Do not implement a bottom/sticky assignment bar or duplicate assignment controls
  at the bottom. The user's final choice supersedes the earlier sticky-bar suggestion.
- Use two aligned content columns on sufficiently wide screens: Target employees
  above Assignment preview on the left; Completion deadline above Performance
  observers on the right. Separate sections with white surfaces, consistent borders,
  headings/icons and spacing. Use the shared restrained corporate tokens; avoid
  unnecessary decorative colors. Stack panels and course navigation on narrow screens.
- Keep the observers panel distinct and its Save/Apply actions local to that panel.

#### Employee selection: preserve the current workflow

- The Target employees action must be **Add employees**, opening the existing
  searchable individual employee picker/multi-selection flow. It must not open a
  department-only selector or require a group before an individual can be selected.
- Show selected employees with clear names and remove controls. Preserve current
  employee identity, deduplication, inclusion/exclusion and All active employees
  semantics. Match counts must come from the existing preview API.
- Retain supported attribute filters, saved groups and group logic where currently
  available; these are supplementary capabilities, not a replacement for Add employees.
  Reuse existing picker and rule mapping rather than introducing a parallel data model.
- The sample Add group button and department-only dialog in earlier demos are not
  approved for the Target employees entry. Map the new entry through the existing
  EmployeePickerDialog and existing AssignmentGroup/employee-ID structures without
  changing backend contracts. Internal grouping must not become an extra user step.
- Preserve current individual-employee exclusion selection as well.

#### Workflow, icons and state requirements

- Use the shared direct lifecycle-action rule: one permitted action renders its own
  label; no actions means no control; multiple permitted actions remain accessible.
  Preserve lifecycle revision checks, ownership, confirmations and impact previews.
- The assignment publish button already has a state-specific purpose: active courses
  use Update Assignments, drafts use Publish & Assign, disabled courses use Enable.
  Do not duplicate Enable in a second header action. In Assign, route that single
  primary Enable through the existing preview/confirmation/publish callback.
- Use a recognizable paper-plane/send vector for Update Assignments and Publish &
  Assign. Use consistent save, refresh, users, user-plus, shield/eye, calendar, search,
  remove and warning icons with visible labels or accessible names. Keep touch targets
  usable; do not replace them with emoji or remotely loaded assets.
- Match Documents/Blueprint with a readable course sidebar, white workspace, restrained
  navy primary action, subtle borders and clear section hierarchy. Keep lifecycle
  controls distinct from assignment publication and keep destructive controls quiet.
- Keep Target employees, include groups, exclusions and supported saved-group/filter
  semantics. Preview matching and assigned employees with search and pagination.
- Keep both relative deadlines and fixed dates, validated through existing range rules;
  fixed-date copy must retain Asia/Kolkata end-of-day semantics.
- Save Rule stores configuration; publication/Update Assignments applies employee
  access. Keep these meanings distinct. Refresh must not silently discard drafts.
- Observers remain performance-only and are not enrolled as learners. Keep observer
  scope selection, permission restrictions, Save Observers and Apply Observers separate
  from employee assignment. Apply stays blocked when observer selections are dirty
  or the course is not published/assigned. Do not merge save/apply APIs for visual simplicity.
- The publish confirmation refreshes the employee preview and shows the actual matched
  employee count, deadline, removal impact and progress-retention note. Stale previews
  and learner/observer conflicts remain blocking. Never invent employee counts in production.
- Keep loading/error/retry and revision-conflict reload behavior, preserve pending edits,
  block duplicate publication and ignore stale replies after changing course/user.
- Proposed reference: [Assign — Refined desk](design/trainer-ui/assign-refined-desk.proposal.png).
  Earlier image proposal; the final sidebar/top-toolbar reference and corrections
  above take precedence.

Selected layout reference:

- [Focused assignment with left course panel and top actions](design/trainer-ui/assign-focused-sidebar.reference.html).
- This interactive reference contains simulated saves/publication, sample employee
  data and a simplified department selector. Use it for layout; implement the Add
  employees correction above using the real current workflow. Update the executable
  reference and screenshots to include that picker before final visual acceptance.
- The bottom-actions demo is rejected and must not be used as an implementation reference.

Implementation acceptance:

- Verify direct lifecycle controls across eligible course states; no duplicate Enable.
- Verify Add employees can select/search/remove one or multiple individual employees
  without creating a group first; exercise existing saved groups and attribute filters.
- Verify inclusions, individual exclusions, All active employees, preview search,
  pagination and matched counts continue to use existing rule semantics and APIs.
- Verify top Save rule versus publication, confirmation counts/deadline/impact,
  lifecycle revision conflicts, preserved progress and duplicate-request protection.
- Verify independent observer selection, scope, permissions, save/apply and conflict
  blocking; employee publication must not silently apply observer edits.
- Verify relative/fixed deadlines, Asia/Kolkata date copy, loading/error/retry,
  unsaved-edit protection, course/user switching and narrow-screen/keyboard access.
- Compare compiled React screens against the selected layout and explicit corrections;
  no application deployment is authorized merely by recording this specification.

Further Assign alternatives for review (not selected):

- [Comparison image](design/trainer-ui/assign-alternatives.proposal.png).
- [Interactive comparison source](design/trainer-ui/assign-comparison.proposal.html).
- **Focused assignment:** horizontal course picker, employee selection and preview
  together, deadline beside them, observers in an expandable lower section.
- **Review desk:** course sidebar, Employees/Deadline/Observers tabs and a compact
  assignment review summary alongside the active section.
- These previews use sample employees and locally computed counts. The source, not
  incidental generated image details, defines the interactions being demonstrated.
  Preserve the existing wordmark/nav; image-board brand changes are not approved.
  All-active mode must hide/ignore inclusion groups while exclusions still apply.
- Demo date and numeric limits are illustrative; production must retain its existing
  server validation and date range. No proposal permits replacing supported group
  criteria or observer scopes with only the sample department dropdowns.
- Saving employee rules does not enroll learners; applying observer access does not
  publish employee assignments. Review actual counts and deadline before publication.
  Keep production conflict checks, observer permissions and duplicate-action guards.

### Change log

| Date        | Decision                                                                                                                                      |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 22 Oct 2026 | Selected Focused desk over side-by-side and library-first alternatives                                                                        |
| 22 Oct 2026 | Renamed uploaded library; removed uploaded-file Edit first; required full-document inline preview                                             |
| 22 Oct 2026 | Confirmed uploaded-file Create course opens Blueprint; videos/quizzes start only on its Generate Course action                                |
| 22 Oct 2026 | Created dedicated branch and continuing specification; added Gemini-inspired AI sparkle reference                                             |
| 22 Oct 2026 | Approved Smart document AI, upload-document, red PDF and navy draft icons from subsequent image proposal; old sparkle superseded              |
| 22 Oct 2026 | Recorded Blueprint direct single-action requirement and requested corporate layout demos; layout selection pending                            |
| 22 Oct 2026 | Approved Blueprint Option A Refined desk interactive demo; recorded workflow and visual acceptance requirements                               |
| 22 Oct 2026 | Started Assign review: direct lifecycle actions, paper-plane assignment icon, corporate layout; existing employee/observer semantics retained |
| 23 Oct 2026 | Selected Assign Focused assignment with left course list and distinct panels; retained top actions and rejected bottom action bar             |
| 23 Oct 2026 | Required Add employees with existing individual selection workflow; department-only Add group demo is superseded                              |
