# Video Engine toggle: implementation plan

Status: implemented on `feat/video-engine-toggle`, branched from `main` at `2e312a5`.
Planned against `2f49de3`; the one commit between them (PhillipAcademy naming) does not touch
this work.

## 1. Goal

A trainer chooses, per course, how module videos are made:

- **Video Engine on**: module videos come from the external Video Generator API.
- **Video Engine off ("standard generation")**: the LMS makes slides, scripts, narration and
  the video itself, as before.

The LMS recommends a setting from the source document, sets it as the default, and shows an
amber notice when the trainer picks the setting it doesn't recommend.

| Source document | Default | Notice shown when the trainer… |
| --- | --- | --- |
| No meaningful images (example: trainer Neha CCC document) | On | turns Video Engine off |
| One or more meaningful images or screenshots (example: PhillipX CRM user guide) | Off | turns Video Engine on |

The Video Generator does not use document images, so a course with screenshots loses them
when Video Engine is on. This is why the second notice recommends standard generation.

## 2. Decisions

| Topic | Decision |
| --- | --- |
| Where the toggle lives | Blueprint tab toolbar, between "Save Changes" and "Generate Course" |
| Scope | One setting per course |
| Image threshold | One meaningful image is enough to recommend standard generation |
| What counts as an image | Images the LMS would put in the course, minus decorative ones (logos, headers, footers, icons). See section 4 |
| Changing after creation | Allowed whenever no generation is running. See section 6 |
| Notice | Inline amber notice under the toolbar, not blocking, auto-hides after reading time |
| Courses tab | Read-only "Video Engine" or "Standard" badge for the course |
| Rollout | On by default after deployment, with no `.env` change. `VIDEO_ENGINE_TOGGLE_ENABLED` (default `true`) exists only as an emergency off switch |
| Who decides | The trainer, per course. No developer or `.env` change is needed to use either flow |

Two refinements to what was discussed earlier:

1. **Switching after videos exist.** After a full generation the Generate button reads
   "Already Generated" and is disabled, so there is no "regenerate" action to point the
   trainer to. Instead the toggle stays usable, and when the course already has generated
   content a confirm dialog explains that switching clears it. This is the same reset the
   LMS already applies when the trainer edits the blueprint (`CourseService._invalidate_generated_content`).
2. **Document Builder documents.** No special case. Builder documents can contain images
   (`lms.document-builder.images.yml`), so they follow the same image check: text-only
   builder documents default to On, and builder documents with images default to Off.

## 3. How it works today (verified in code)

- The engine is one global setting: `VIDEO_GENERATION_MODE=local|external`
  (`backend/app/core/settings.py:126`). Production has used `external` since 2026-10-29
  (`docs/video-generator-operations.md`).
- `uses_external_video_service()` (`backend/app/generation/runtime.py:343`) reads that setting.
  It is used in `missing_generation_outputs`, `run_module_video_generation` and
  `run_full_course_generation` (3 call sites).
- `backend/scripts/backfill_video_captions.py:28` also reads the global setting.
- Captions already decide per module (`video_service.run_id` or a `.srt` file in
  `captions.py`), so they need no change.
- `GET /api/generation/config` returns `video_generation_mode`. The trainer app reads it in
  `videoMode.ts` (`useVideoGenerationMode`), used by `TrainingView.tsx:87` and
  `useFullCourseGeneration.ts:156`.
- Course-level extra fields are stored in `courses.metadata_json` through
  `COURSE_METADATA_FIELDS` (`backend/app/repositories/courses.py:15`). Adding fields there
  needs **no database migration**, and `patch_generated_course_fields` already handles them.
- Image extraction at outline time:
  - PDF: `extract_images_from_pdf` (`blueprint.py:608`) keeps every embedded image, with no
    size or repetition filter. Each record has `page`, `bbox`, `width`, `height`, and an
    `image_id` containing the PDF `xref`.
  - DOCX: `extract_docx_blueprint_source` (`documents/docx.py`) keeps every body image, with
    pixel `width` and `height`. If native DOCX extraction fails, it falls back to the PDF path.
  - PPTX: images are deliberately ignored (`run_pptx_blueprint_extraction` returns
    `images=[]`), so standard generation never shows PPTX images either.
- `CourseUpdateRequest` (`schemas/course.py`) and `CourseService.update_course` handle
  blueprint edits and reset generated content when the blueprint changes.

## 4. Image detection

### 4.1 Classifying each image

Add a `decorative: bool` flag to each extracted image record. Slide behaviour does not
change; the flag is used only for the recommendation.

PDF, in `extract_images_from_pdf` (where `page.rect` is available):

- **Small**: the image's box covers less than 1.5% of the page area, or either side is under
  40 pt.
- **Header or footer**: the box sits entirely in the top 8% or bottom 8% of the page.
- **Repeated**: the same `xref` appears on at least 3 pages and on at least 50% of pages
  (logos and letterheads). This needs a first pass over all pages before classifying.

DOCX, in `extract_docx_blueprint_source`:

- **Small**: pixel width or height under 64.
- **Repeated**: the same image bytes (SHA-256) appear 3 or more times.

PPTX: the pipeline uses no images, so the count is always 0 and the recommendation is
always On. This is correct, because standard generation would not show PPTX images either.
Note this in the trainer help text for PPTX uploads.

### 4.2 Recommendation

New module `backend/app/generation/video_engine.py`:

```python
def meaningful_image_count(course: dict) -> int
    # Unique image_ids across course["images"] and every module["images"],
    # counting records where decorative is not True.

def recommended_video_engine(course: dict) -> bool
    # True when meaningful_image_count(course) == 0.

def video_engine_available() -> bool
    # True when VIDEO_SERVICE_BASE_URL is set and VIDEO_SERVICE_HMAC_SECRET has 32+ characters.

def course_uses_video_engine(course: dict) -> bool
    # 1. course["video_engine"] if it is a bool.
    # 2. Older course: True if any module has video_service.run_id,
    #    False if any module has a video_path without one.
    # 3. Otherwise settings.video_generation_mode == "external".
```

Older courses have no `decorative` flags, so all their images count. This can only push an
older course toward "Off" as the recommendation; it never changes the engine an older
course already uses (step 2 and 3 above).

### 4.3 Storing it

At the end of `generate_course_outline` (`blueprint.py:1205`), when the toggle is enabled
(the default):

```python
count = meaningful_image_count(outline)
outline["video_engine_recommendation"] = {"recommended": count == 0, "image_count": count}
outline["video_engine"] = (count == 0) and video_engine_available()
```

Add `video_engine` and `video_engine_recommendation` to `COURSE_METADATA_FIELDS`.

Two more paths, found while building:

- **Document Builder courses** are created in `document_builder/workflow_export.py` without
  `generate_course_outline`, so that export calls `apply_outline_recommendation` too.
  Builder images are placed deliberately, so each one counts.
- **Blueprint re-extraction** (continuing a failed blueprint) rebuilds the outline for an
  existing course. It keeps a choice the trainer already made instead of resetting it to
  the recommendation.

Only if someone sets `VIDEO_ENGINE_TOGGLE_ENABLED=false` (emergency off switch) is neither
field written, and every new course then resolves to the global setting, as before this
feature.

## 5. Backend changes

### 5.1 Settings (`backend/app/core/settings.py`)

- Add `video_engine_toggle_enabled: bool = True` (env `VIDEO_ENGINE_TOGGLE_ENABLED`), and
  read it in the `.env` loader next to `VIDEO_GENERATION_MODE` (around line 468), defaulting
  to `true` when the variable is absent. Existing `.env` files need no change: deploying the
  build turns the toggle on.
- Keep `video_generation_mode`. It now means only "engine for older courses that have no
  stored choice". Leave the current value as it is.
- Keep the existing startup check that `external` mode needs the URL and secret. Video
  Engine stays available as long as `VIDEO_SERVICE_BASE_URL` and `VIDEO_SERVICE_HMAC_SECRET`
  remain set, as they already are in production.
- In the production check (line 343), require `TTS_ENDPOINT` whenever the toggle is enabled,
  not only in `local` mode, because any course can use standard generation. `TTS_ENDPOINT`
  already has a built-in default, so this adds no `.env` step.
- Document the variable in `.env.example` as commented out, with a note that it is an
  emergency off switch and is not needed for normal use.

### 5.2 Runtime (`backend/app/generation/runtime.py`)

- Change `uses_external_video_service()` to `uses_external_video_service(course: dict)`,
  calling `course_uses_video_engine(course)`.
- `missing_generation_outputs(course)`: pass `course`.
- `run_module_video_generation(course_id, module_number)`: load the course first, then decide.
- `run_full_course_generation`: decide from `load_course()` at the start of the run.
- Guard: if the course resolves to Video Engine but `video_engine_available()` is False,
  raise `PipelineStageError("video", "Video Engine isn't available on this server. Turn
  Video Engine off on the Blueprint tab and generate again.")` before any work starts.
- `backend/scripts/backfill_video_captions.py`: replace the global check with
  `course_uses_video_engine(course)` after the course is loaded.

### 5.3 Course API

`backend/app/schemas/course.py`:

- `CourseUpdateRequest`: add `video_engine: bool | None = None`.
- `CourseResponse`: add `video_engine: bool | None = None`,
  `video_engine_recommended: bool | None = None`, `meaningful_image_count: int | None = None`.
  `CourseInspectionResponse` inherits them.

`backend/app/services/courses.py`, in `update_course`, when `video_engine` is in the payload
and differs from the stored value:

1. The toggle flag is off: `ConflictError("Video Engine selection is not enabled.")`.
2. Turning it on while `video_engine_available()` is False:
   `DomainValidationError("Video Engine isn't available on this server.")` (HTTP 400).
3. Store the new value. If any module has generated content (quiz, notes, slides,
   `video_path`, `video_service`) or the course has a thumbnail, call
   `_invalidate_generated_content`.
4. Always save an engine change with `release_generation_worker=True`. `save_course`
   (`repositories/courses.py:305`) then locks the course's `course_generation_status` row and
   raises `ConflictError` while a full-course or module-video job is pending or running. This
   is the existing, race-safe guard used for blueprint edits, so no new running check is
   needed. Catch that error in `update_course` and re-raise it with the message
   "Wait for the current generation to finish before switching engines."

When the course is returned (`get_course`, `generate_outline`, `update_course`), fill
`video_engine` with `course_uses_video_engine(course)`, plus `video_engine_recommended` and
`meaningful_image_count` (from the stored recommendation, or computed for older courses).

Editing rights follow the blueprint: the same owner and archived checks in `update_course`
apply, and read-only viewers (`can_manage: false`) cannot change it.

### 5.4 Generation config (`backend/app/api/generation.py`, `schemas/generation`)

`GET /api/generation/config` returns:

```json
{
  "video_generation_mode": "external",
  "video_engine_toggle_enabled": true,
  "video_engine_available": true
}
```

## 6. Trainer frontend changes

### 6.1 Shared models (`packages/shared/src/models`)

- `course.ts`: parse `video_engine`, `video_engine_recommended`, `meaningful_image_count` into
  `videoEngine: boolean | null`, `videoEngineRecommended: boolean | null`,
  `meaningfulImageCount: number | null`.
- `generation.ts`: add `parseGenerationConfig` returning
  `{ defaultMode, toggleEnabled, videoEngineAvailable }`. Keep `parseVideoGenerationMode`
  working for an older backend that doesn't send the new fields (treated as toggle off,
  because that backend can't store the choice).

### 6.2 Engine per course (`apps/trainer/src/features/training/videoMode.ts`)

- `useGenerationConfig()` replaces `useVideoGenerationMode()`.
- `courseVideoMode(course, config)`: `'external'` when `course.videoEngine === true`,
  `'local'` when `false`, otherwise `config.defaultMode`.
- `TrainingView.tsx:87`: use `courseVideoMode(course, config)`.
- `useFullCourseGeneration.ts:156`: load the running course in all cases and pick the overlay
  text from that course's mode, not the global one.

### 6.3 Switch component

- Move `Switch` from `apps/trainer/src/features/assignments/controls.tsx` to
  `packages/shared/src/ui/Switch.tsx`. Add `size: 'default' | 'compact'`:
  - `default`: the current 52×32 Material switch (Assign tab unchanged).
  - `compact`: 40×24 track, 18 px knob, so it sits inside a 36 px toolbar control.
- Re-export it from `assignments/controls.tsx` so Assign tab imports stay as they are.

### 6.4 Blueprint toggle (`apps/trainer/src/features/courses/VideoEngineToggle.tsx`)

Shown whenever `config.toggleEnabled` is true, which is the default. Placed in the Blueprint toolbar
(`CourseDetailsView.tsx`, `.blueprint-toolbar`) between "Save Changes" and "Generate Course".

Look:

- A 36 px high bordered control matching the Reset and Save buttons: `rounded-lg`,
  `border-slate-200`, white background, `px-3`, `gap-2`.
- Contents: 16 px `ondemand_video_outlined` icon in `text-primary-blue`, the label "Video Engine" in
  `text-sm` (14 px DM Sans, the toolbar's size), then the compact switch.
- On: `bg-primary-blue` (#00317A, the same blue as Generate Course). Off: the existing grey.
- The whole control is the click target, with `role="switch"`, `aria-checked`, focus ring
  `outline-brand-blue-light`, and Space or Enter to toggle.

Helper line, under the toolbar on the right, `text-xs text-slate-500` (the existing helper
style):

- "Recommended: On · no images in the source document"
- "Recommended: Off · 6 screenshots in the source document" (uses `meaningfulImageCount`;
  "1 screenshot" for one)

When the current setting differs from the recommendation, the helper line gets a small amber
dot (`accent-orange`) before it. This stays after the notice has gone.

Disabled states (with a `Tooltip` explaining why):

- Generation running: "Wait for generation to finish to switch engines."
- Video Engine unavailable: switch stays off, "Video Engine isn't available on this server."
- The Blueprint editor only opens the trainer's own courses, and `update_course` checks
  ownership, so there is no separate read-only state.
- A blueprint save or engine change is in progress.

Saving:

- Each change is sent straight away as `PUT /api/courses/{id}` with `{ "video_engine": value }`
  (new `useUpdateVideoEngine` mutation), and the returned course is stored.
- The engine is not part of the blueprint draft, so it never marks the blueprint as having
  unsaved changes. The editor already keeps unsaved edits when the stored course changes
  (`CourseDetailsView.tsx:126-139`).
- Generate Course saves the blueprint first with `blueprintPayload`, which does not include
  `video_engine`, so it cannot overwrite the engine.

Confirm dialog, when the course already has generated content (any module video, quiz or
notes, or a thumbnail). Uses the shared `Dialog`:

- Title: "Switch video engine?"
- Body: "This course's generated videos, quizzes, notes and thumbnail will be cleared.
  Generate the course again to rebuild them with the selected engine."
- Buttons: "Cancel" and "Switch engine".

### 6.5 Advisory notice (`apps/trainer/src/features/courses/VideoEngineNotice.tsx`)

When it appears: only right after the trainer changes the toggle to the setting that is not
recommended. Never on page load.

Placement: full width, directly under the Blueprint toolbar, above the helper line, inside
the header. Not the bottom toast: that is far from the control, and any later toast would
replace it.

Look, using existing theme tokens (`packages/shared/src/theme.css`):

- Background `accent-light-orange` (#FFF6D8), 4 px left border `accent-orange` (#D59A00),
  no rounded corners on the bordered side.
- 20 px `warning_amber_rounded` icon in `accent-orange`.
- Title "Not recommended for this document", `text-sm font-semibold text-text-black`.
- Body text `text-sm leading-[1.55] text-text-black`. Text stays dark because amber text on a
  light amber background is too hard to read.
- 18 px close button (×), `aria-label="Dismiss"`.
- A 3 px `accent-orange` bar along the bottom that shrinks as time runs out.
- `role="status"` and `aria-live="polite"`, so screen readers announce it.

Wording:

- Video Engine turned **off** for a document with no images:
  > Video Engine is recommended for this course. As the source document contains no images or
  > screenshots, Video Engine will deliver smoother, more visually engaging animations for
  > your learners.
- Video Engine turned **on** for a document with images:
  > This document contains images and screenshots that support learner understanding. Video
  > Engine does not include document images in its videos, so standard course generation is
  > recommended to retain these visuals.

Timing:

- Duration = max(8 s, words ÷ 200 × 60 s + 4 s). Both messages are about 30 words, so about
  13 s each. Compute it from the text, so edited wording keeps a fair reading time.
- The timer pauses while the pointer is over the notice or keyboard focus is inside it, and
  resumes on leave.
- Hides at once when the trainer switches back to the recommended setting, clicks ×, or
  presses Escape while focus is in the notice.
- A new non-recommended change restarts the timer.
- Exit: 300 ms fade. With `prefers-reduced-motion`, no fade and no bar animation; the timer
  still runs.

### 6.6 Courses tab

- Header badge with the shared `Chip`: "Video Engine" or "Standard", read-only.
- The module video panel text (`TrainingView.tsx:371`) follows the course's engine.

## 7. Tests

Backend (`backend/tests`):

- `test_video_engine.py` (new):
  - PDF with only a repeated logo: count 0, recommended On.
  - PDF with one screenshot: count 1, recommended Off.
  - Small icons and header or footer images are decorative.
  - DOCX with a repeated small image: decorative. DOCX with one screenshot: count 1.
  - PPTX: count 0.
  - `course_uses_video_engine`: stored value, legacy inference, global default.
- Settings: the toggle is enabled when `VIDEO_ENGINE_TOGGLE_ENABLED` is absent, and disabled
  only when it is set to `false`.
- Outline creation stores both fields by default, and neither when the toggle is disabled.
- `update_course`: running full-course or module job → 409 with the engine message; Video
  Engine unavailable → 400; flag off → 409;
  switching with generated content clears it; switching with none keeps the blueprint.
- `runtime`: each of the 3 call sites follows the course, not the global setting; Video
  Engine unavailable fails the run with the clear message.
- Generation config returns the two new fields.
- Update `test_video_service.py` for the new `uses_external_video_service(course)` signature.

Frontend (`vitest`):

- Shared model parsing of the new fields and the config, including an older backend.
- `VideoEngineToggle`: hidden with the flag off; default state from the course; each disabled
  state; confirm dialog only when content exists; PUT body.
- `VideoEngineNotice`: shows only on a non-recommended change; correct text for each case;
  hides after the computed time (fake timers); pause on hover and focus; hides on switching
  back, × and Escape.
- Update `TrainingView.test.tsx`, `useFullCourseGeneration.test.tsx` and `models.test.ts`
  for per-course mode.
- Assign tab tests still pass after moving `Switch`.

## 8. Rollout

The toggle is live as soon as the build is deployed. No `.env` change is made on any server.

1. Deploy to UAT and run the acceptance checks below.
2. **Before deploying to production, confirm that standard generation works there.** This is
   the only developer step, and it is done once. Production has run only Video Engine since
   2026-10-29, so the TTS service, slide rendering and video assembly may not have been used
   there since. Before the production deploy, run one short test course through standard
   generation on the production backend (current build, `VIDEO_GENERATION_MODE=local` for
   that one test only, then put the value back), or in a UAT that uses the same TTS service.
   If anything fails, fix it before deploying, because trainers will be able to turn Video
   Engine off from day one.
3. Deploy to production. Trainers can choose either flow per course straight away. Existing
   courses keep the engine they were made with.
4. Update `docs/video-generator-operations.md`: the engine is now chosen per course by the
   trainer, `VIDEO_GENERATION_MODE` only covers older courses, and
   `VIDEO_ENGINE_TOGGLE_ENABLED=false` is the emergency off switch.

## 9. Acceptance checks

1. Upload the trainer Neha CCC document and create the course. Blueprint shows Video Engine
   on, "Recommended: On · no images in the source document".
2. Turn it off: the amber notice with the first wording appears, stays about 13 s, pauses on
   hover, then fades. The helper line keeps the amber dot.
3. Upload the PhillipX CRM user guide and create the course. Video Engine is off, and the
   helper line shows the screenshot count.
4. Turn it on: the second wording appears with the same behaviour.
5. Generate each course. The CCC course's videos come from the Video Generator (module
   `video_service` present). The CRM course's videos are made by the LMS, with screenshots in
   the slides.
6. On a generated course, switch the engine: the confirm dialog appears; after confirming,
   Generate Course is enabled again and the regenerated videos use the new engine.
7. While generation runs, the toggle is disabled with its tooltip.
8. The Courses tab badge matches the Blueprint setting.
9. With no `VIDEO_ENGINE_TOGGLE_ENABLED` line in `.env`, the toggle is shown and works.
10. With `VIDEO_ENGINE_TOGGLE_ENABLED=false` (emergency off switch), the trainer app looks and
    behaves exactly as before this feature.

Image check results on the two sample documents (run on 2026-11-04 with the new detection):

| Document | Images extracted | Decorative | Meaningful | Default |
| --- | --- | --- | --- | --- |
| trainer Neha CCC document | 0 | 0 | 0 | Video Engine on |
| PhillipX CRM Web Application User Guide | 28 | 0 | 28 | Video Engine off |

## 10. Out of scope

- Leaving decorative images out of standard-generation slides. The new flag makes this easy
  later, but it changes existing course output, so it is a separate change.
- Choosing the engine per module.
- Using document images inside the Video Generator.
