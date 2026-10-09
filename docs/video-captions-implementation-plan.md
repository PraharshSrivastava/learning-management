# Video captions implementation plan

Date: 9 October 2026
Branch: `codex/video-captions-plan`
Status: Feature code implemented; live alignment/runtime validation and rollout remain pending. See `video-captions-operations.md` for setup and verification.

## Objective and approved design

Add synchronized narration captions to trainer and employee video playback using the corporate design reviewed in this chat. Keep all slide content visible by rendering captions beneath the video, inside its rounded player card.

- Charcoal options menu with white text, consistent icons, subtle dividers, and restrained rounding.
- Retain the three-dot control; add `Captions (CC)` to its menu.
- Include a visible CC shortcut for immediate on/off, as shown in the latest reviewed preview. Keep the shortcut configurable during implementation if the final preference is menu-only.
- Caption settings contain an enable switch and Small, Medium, and Large choices. Show the selected choice with a checkmark and navy background.
- Use 14 px / 16 px / 20 px for Small / Medium / Large; Medium is the initial default.
- Default captions off on first use. Remember the viewer's enable preference and size locally; a missing caption asset never changes the saved preference.
- Captions on: compact charcoal strip, centered white text, no heading or tab. Preserve the full video aspect ratio; grow the card and move Module notes down.
- Captions off: remove the strip and its spacing completely. Restore the existing page geometry, with the new control styling.
- Caption text wraps naturally; split long cues during generation and let the strip grow when required by Large size or mobile width. Do not truncate speech.
- Keep the strip height stable during gaps within a video when captions are enabled; clear its text during silence. Turning captions off collapses it completely.
- Fullscreen includes video, controls, options menu, and caption strip together. Fit the slide image into the remaining space without cropping.

## Current implementation findings

Both apps use `lib/core/video/hls_video_player.dart`, which creates an HTML `VideoElement` with browser controls and supports native HLS, hls.js, and MP4 fallback. The browser's built-in three-dot menu cannot supply our custom layout and size settings; replace the controls while retaining the media element and HLS playback implementation.

The employee player additionally uses `linear_playback_guard.dart` to restrict forward seeking and validate completion. Custom controls, keyboard shortcuts, and caption lookup must use the allowed media position and preserve this guard. CC actions must never count as watched progress or unlock a quiz.

`backend/app/generation/tts.py` synthesizes WAV narration from each slide's `script`, normalizes the text, and adjusts audio speed. Its current request consumes audio bytes and does not store word timestamps. `backend/app/generation/video.py` encodes each slide with narration plus a transition pause, concatenates clips, and packages HLS. Valid existing videos are currently skipped by generation.

Video assets already have a static mount. Keep caption sidecars beside the MP4, outside the HLS directory that packaging replaces. Existing MP4-only courses must continue to play.

## Architecture and asset contract

Use WebVTT for timed captions and a small metadata sidecar for versioning and validation:

```text
assets/videos/course_<course_id>/module_<number>.mp4
assets/videos/course_<course_id>/module_<number>.vtt
assets/videos/course_<course_id>/module_<number>.captions.json
assets/videos/course_<course_id>/module_<number>_hls/master.m3u8
```

Derive sidecar URLs from the canonical video URL in each app's `AppConstants`. Use URI-aware path replacement so query strings, absolute URLs, and proxy prefixes remain valid. Unsupported video URLs have no derived caption URL. This first version does not need a database migration or new course model field.

The metadata includes schema version, language, alignment method/version, cue count, final video duration, generation version/fingerprint, and hashes of the rendered video and relevant script/audio inputs. Use generation fingerprints in caption asset URLs to avoid serving cached captions after regeneration. Confirm metadata matches the currently served video generation; mismatched or incomplete assets are unavailable, not guessed.

Load the caption asset with the same permitted origin/proxy rules as video assets. Check actual content and metadata, not just HTTP HEAD success. Missing, malformed, or stale captions must not block media playback. Disable CC with a short accessible `Captions unavailable` explanation and show no strip. Do not silently display unsynchronized narration.

Render captions as plain text, never as HTML. Keep the timed cue model and lookup independently testable. Determine the active cue from the actual media time using start-inclusive/end-exclusive intervals; clear the cue outside intervals. Retain cues across speed changes and refresh after seeks, source changes, and pause/resume. Do not enable a second native overlay track alongside the custom strip.

## Phase 1 — Establish accurate caption timing

1. Add a caption generation module, proposed `backend/app/generation/captions.py`, with a typed internal cue representation and WebVTT serializer.
2. Verify whether the deployed TTS service can return usable word timestamps. Do not assume support from the current audio-only integration. If supported, capture timestamps and account for the final applied audio speed.
3. Otherwise align the known narration transcript to the final, speed-adjusted WAV using a validated forced-alignment service/runtime. Evaluate accuracy, supported language, deployment resources, licensing, dependency impact, and latency before choosing the integration. Keep external audio transfer within the existing approved infrastructure.
4. Align against the normalized text actually spoken by TTS. Retain a mapping to readable caption text where normalization changes numbers or abbreviations.
5. Group aligned words into short readable cues at phrase boundaries. Target at most two lines at Medium on desktop, without excessive flashes or dense paragraphs. Validate cue text, monotonic times, positive intervals, and audio bounds.
6. Measure the actual encoded clip durations for slide offsets, including frame rounding and transition silence. Keep each slide's cues within its audible narration and offset by the previous clips' durations. Verify against the final concatenated MP4 duration.
7. Write validated sidecars through temporary files and atomic replacement. Prevent simultaneous backfill and regeneration for the same module; publish metadata last and reject fingerprint mismatches.

Deliverable: representative modules with accurate cues checked against real audio, including numbers, pauses, long sentences, and the last slide. **Do not substitute word-count interpolation as production synchronization.** The alignment provider is the principal implementation dependency to resolve in this phase.

## Phase 2 — Integrate generation and existing videos

1. Integrate caption generation into both single-module and full-course video generation paths after rendering/packaging succeeds.
2. When a valid video is skipped, independently check whether its caption sidecars are valid. Generate missing captions when the matching narration assets exist; do not rerender a valid video just to add captions.
3. Invalidate caption fingerprints whenever slides, scripts, audio, or video are regenerated. Never serve old cues with a new video.
4. Add a backfill command with dry-run and explicit course/module selection, bounded concurrency, idempotent processing, and per-module results. Check source fingerprints before and after processing.
5. If a historical video cannot be verified against its narration assets, report it as requiring regeneration. Preserve the video and publish no captions for it.
6. Log caption success, unavailable reasons, and generation failure distinctly. Caption failure leaves working video playback available and is visible in generation/backfill diagnostics; it must not silently count as successful caption generation.
7. Confirm static MIME type, proxy/CORS behavior, and cache invalidation for VTT/metadata. Sidecars follow the existing video access model; caption availability must not expose additional course data.

## Phase 3 — Build the corporate player

1. Keep the existing `VideoElement`, HLS attachment, fallback, and completion callbacks. Replace browser controls with controls inside the same HTML platform-view container as video and captions, avoiding Flutter/HTML stacking issues for overlays and menus.
2. Provide play/pause, elapsed/duration display, accessible seek slider, mute/volume, fullscreen, and three-dot options. Preserve playback-speed functionality and existing download actions. Do not expose forward-skip shortcuts that bypass employee restrictions.
3. Implement charcoal main and caption submenus, back navigation, selected-size checkmarks, and the visible CC shortcut. Close on outside click and Escape; reflect enabled state in the shortcut and menu summary.
4. Implement keyboard interaction, focus return, labeled controls, selected states, focus-visible styling, and usable touch targets. Ensure video/menu shortcuts do not fire while interacting with form controls.
5. Persist only caption preferences using namespaced browser storage keys with safe fallback if storage is unavailable. Playback state and cue text are not persisted.
6. Drive all UI state from media events. Display buffering and media errors, handle a zero/unknown duration safely, and avoid stale asynchronous loads during rapid module changes.
7. Fullscreen the complete container. Handle entry/exit events and request rejection; preserve captions, current time, preferences, and playback guards. Pause and clean up old media instances, listeners, and HLS objects on replacement/disposal.
8. Keep the two apps' player behavior consistent, while retaining the employee guard integration. Use matching code/contracts and parity checks initially; do not expand this feature into an unrelated monorepo packaging migration.

## Phase 4 — Integrate all playback surfaces

Update these callers in both apps:

- `frontend/lib/features/training/training_portal.dart`
- `frontend/lib/features/generation/video_portal.dart`
- `employee_frontend/lib/features/training/training_portal.dart`
- `employee_frontend/lib/features/generation/video_portal.dart`
- `employee_frontend/lib/features/learning/course_playback_page.dart`

The employee learning page currently wraps the entire player in a 16:9 `AspectRatio`; move that ratio to the video region so captions add height below it. Trainer playback also uses fixed-height or expanded containers: ensure those constraints reserve room or allow scrolling rather than compressing/cropping captions. Keep notes below the whole player and sidebars aligned with their existing layout.

Inspect the older `ModuleVideoPlayer` classes before editing; consolidate only if they are active callers. Apply changes through the HLS player used by the actual training and generation screens.

## Phase 5 — Verification and release readiness

### Automated checks

- Backend: cue validation, text normalization mapping, WebVTT escaping/Unicode, silent gaps, rounding at slide boundaries, final cue bounds, regeneration invalidation, skipped-video caption generation, backfill dry-run/idempotency, partial failure, and concurrent-generation mismatch rejection.
- Frontends: cue lookup at boundaries, seek/speed changes, missing/malformed caption assets, preference restoration, three font sizes, complete collapse when off, source-switch races, and parity between apps.
- Employee playback: retain existing `linear_playback_guard_test.dart` coverage and add meaningful regressions proving custom seeks/shortcuts and completion callbacks cannot bypass the guard.
- Run focused backend tests and existing video HLS tests; run Flutter analysis, focused tests, and web builds for both apps. Broaden checks only for affected areas or failures.

### Browser and visual checks

- Match the approved trainer design: charcoal menu, navy selected row/checkmark, aligned icons, correct caption strip, notes placement, and unchanged slide visibility.
- Exercise CC shortcut and three-dot path; Small/Medium/Large; first-use default and restored preferences; captions unavailable; silent gaps; pause/resume; and module switching.
- Verify at desktop and 320/390 px mobile widths with long narration and Large text. Text and menus must fit without clipping or horizontal scrolling.
- Verify HLS and MP4 fallback, actual media synchronization near the start/middle/end of a multi-slide lesson, and every available playback speed.
- Verify fullscreen captions, menu placement, Escape, and return to normal layout in Chrome and Edge; validate native-HLS behavior in a supported browser/environment where available.
- Verify keyboard/focus navigation and screen-reader labels without continuously announcing every cue as an interrupting live region.
- Verify watching completion, quiz unlocking, completed-video replay, trainer download behavior, and no duplicate completion requests.

## Acceptance criteria

1. Caption controls are available from the three-dot menu, with the reviewed corporate appearance and optional direct CC shortcut.
2. Medium defaults to 16 px; Small and Large are visibly different and retained as preferences.
3. Caption text follows audible narration through seeking and speed changes. Representative browser QA targets approximately 250 ms phrase-boundary accuracy; disclose and fix material mismatches before enabling that asset.
4. Slides are never obscured by captions. Turning captions off removes the entire strip and spacing.
5. Fullscreen keeps captions and controls together without cropping slides.
6. Missing/stale captions never break video playback or show mismatched text.
7. Existing courses remain usable; supported backfill adds captions without rerendering verified matching videos.
8. Learner playback restrictions and completion/quiz behavior remain intact.
9. Both frontend apps build and relevant backend/frontend regression checks pass.

## Delivery sequence and boundaries

Implement timing/assets first, then player controls, caller layouts, backfill tooling, and verification. Enable captions on representative generated modules before undertaking a selected historical-course backfill. Deploy assets and frontends together after validation; old videos without caption assets remain playable.

The user subsequently authorized implementation on 9 October 2026. Feature code has been added on this branch; production deployment and historical-course backfill have not been performed. The branch was created from the current `codex/lms-sbom-remediation` checkout; pre-existing local changes remain in the working tree and must be kept separate from caption commits. Verify the intended integration base before opening a feature PR so unrelated remediation history is not accidentally included.
