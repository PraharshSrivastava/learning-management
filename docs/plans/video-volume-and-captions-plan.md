# Video volume carry-over and captions for existing courses: implementation plan

Branch: `fix/video-volume-captions` (from `origin/main` at `0d27855`, after PR #41).
Scope: the React apps (`apps/employee`, `apps/trainer`, `packages/shared`) and the FastAPI backend.
The Flutter directories are out of scope.

## Part 1: Volume carries from video to video

### Required behaviour

- The learner sets a volume (for example 70%) on any module video. Every following video in the course starts at that volume, through to the last one.
- If the learner changes the volume on a later video (for example to 40%), that becomes the volume from then on. The most recent change always wins.
- Mute follows the same rule. A video muted on one module starts muted on the next, until the learner unmutes it.
- The setting survives a page reload and a return visit in the same browser.
- If the browser blocks storage (for example some private windows), the setting still carries between modules for the rest of the visit.
- Default for a viewer with no saved setting: full volume, not muted (unchanged).

### Cause

Both `CoursePlayback.tsx` (employee) and `TrainingView.tsx` (trainer preview) render the shared `HlsVideoPlayer`. When the module changes, the player creates a new `<video>` element, and a new element always starts at volume 1. No code saved or restored the learner's choice.

### Change (implemented, not committed)

File: `packages/shared/src/video/captionPlayer.js`, the control bar used by both apps.

1. Save on every change. A `volumechange` listener on the video stores `{ volume, muted }`. It covers the slider, the mute button, and any other way the volume changes.
2. Two places hold the setting:
   - `localStorage` key `lms.video-volume.v1`, which survives reloads. Every read and write is wrapped in try/catch.
   - An in-memory copy for the current page, used when storage is unavailable.
3. Restore on create. Each new player applies the saved volume (only if it is between 0 and 1) and mute state before playback starts.
4. Because every change overwrites the saved value, the latest volume is always the one carried forward.

No change is needed in `CoursePlayback.tsx` or `TrainingView.tsx`.

### Tests

File: `packages/shared/src/video/HlsVideoPlayer.test.tsx`

| Test | Status |
| --- | --- |
| Set 35% and mute → next module starts at 35% and muted → after reload still 35% and muted, and storage holds the value | Done |
| Storage blocked → 60% still carries to the next module | Done |
| **Chain:** 70% on module 1 → module 2 starts at 70% → change to 40% on module 2 → modules 3 and 4 start at 40% → unmute and set 80% → module 5 starts at 80%, unmuted | To add |
| Invalid stored value (for example `{"volume": 7}` or broken JSON) → falls back to full volume without error | To add |

### Verification

- `corepack pnpm test`, `corepack pnpm lint`, typecheck (root `tsc` plus each package).
- Manual demo in the employee app: play module 1, set 70%, move to module 2 (starts at 70%), change to 40%, move to module 3 (starts at 40%), then reload the page (still 40%). Repeat once in the trainer preview.

## Part 2: Captions for courses already uploaded

Applies only when the external Video Generator is **off**. When it is on, its videos have subtitles burned in, and `_remove_stale_captions` deliberately deletes caption files. That path is not touched.

### Why captions do not show today

The caption pipeline from PR #34 is on `main`: alignment, caption-file output, and the player's CC button. Three gaps stop captions from appearing.

1. **The player cannot download caption files.** `asset_courses()` in `backend/app/services/media_access.py` only links a requested file to a course when it is the MP4, a thumbnail, or a file under `_hls/`. Requests for `module_N.vtt` and `module_N.captions.json` match no course, so they get "not found". The fix was written in `9be9576` on `codex/video-captions-plan`, but that branch was never merged.
2. **No caption files are produced.** `CAPTION_ALIGN_COMMAND` is not set in `.env`, so every render logs `captions_unavailable` and skips captions.
3. **Older videos are refused.** Videos rendered before PR #34 have no `.narration.json` or `.source.json` record of the audio and script they were built from. `backfill_video_captions.py` therefore returns `requires_video_regeneration` for them.

### Step 2.1: Let the player download caption files (backend bug fix)

- In `asset_courses()`, for paths under `/assets/videos/` ending in `.vtt` or `.captions.json`, look up the course of the matching `.mp4` instead.
- Only these two suffixes are mapped, so internal files (`.source.json`, `.narration.json`, `.srt`, `.media.lock`) stay inaccessible.
- Tests (Postgres, `LMS_ACCESS_POSTGRES_TESTS=true`):
  - An assigned employee, or the owning trainer, can fetch the `.vtt` and `.captions.json` of a module video.
  - An unassigned employee gets "not found".
  - `.source.json` and `.srt` are still refused.
- Check that the frontend nginx `X-Accel-Redirect` location for videos also serves `.vtt` and `.json` with the correct content types (the `docker/` nginx config).

### Step 2.2: Configure the aligner where captions are generated

Add to the generation host's environment, and to `.env.example` as commented examples:

```dotenv
CAPTION_ALIGN_COMMAND=["/home/<user>/caption-aligner/bin/python","/app/scripts/align_captions_qwen.py"]
CAPTION_ALIGN_MODEL_PATH=/home/<user>/models/Qwen3-ForcedAligner-0.6B
CAPTION_ALIGN_DEVICE=cpu
```

New module videos rendered locally then get captions automatically (the existing `_generate_captions_if_available`). There are no code changes in this step. Update the operations section of `docs/video-captions-operations.md`.

### Step 2.3: Backfill captions for older videos

Extend `backend/scripts/backfill_video_captions.py` with a legacy mode for videos that have no source record. The logic goes in `backend/app/generation/captions.py` as `generate_legacy_module_captions(video, slides)`.

For each selected module:

1. **Guards.** Skip, with a reason, when:
   - the Video Generator is enabled (`uses_external_video_service()`);
   - the video was made by the generator (`.srt` present or a generator run record on the module);
   - valid captions already exist;
   - a slide has no script or no saved WAV.
   Take the existing per-module `.media.lock`.
2. **Use the video's own sound.** Extract the MP4's audio track to a temporary 16 kHz mono WAV with the bundled `imageio_ffmpeg`. Captions then follow exactly what learners hear, even if a WAV was replaced later.
3. **Work out slide boundaries.** Each slide clip is its narration padded with the transition pause, so:
   - clip *i* = length of `slide_i.wav` + pause;
   - pause = (video length − total WAV length) ÷ number of slides.
   - Accept only if the pause is between 0 and 3 s and the boundaries add up to the video length to within 0.25 s. Otherwise report `boundaries_mismatch` and leave the module alone.
   Solving for the pause covers courses rendered with a different pause setting.
4. **Align.** Cut the extracted audio at those boundaries and align each piece with its slide's current script, reusing `display_words`, `group_cues` and the existing word-timing checks.
   - Change the worker (`align_captions_qwen.py`) and `align_slide` to accept a list of slides in one call. The model then loads once per module instead of once per slide.
   - The current single-request format keeps working.
5. **Sanity check.** Reject the module if most words get zero-length or identical timings. That is a sign the script no longer matches the spoken audio.
6. **Write files.** Use the existing writers to produce `module_N.vtt` first, then `module_N.captions.json`, with `"method": "forced-alignment-legacy"`. The player already accepts this format, so there are no frontend changes.

Command line:

```bash
python backend/scripts/backfill_video_captions.py --course-id COURSE_ID              # dry run, all modules
python backend/scripts/backfill_video_captions.py --course-id COURSE_ID --module 2   # dry run, one module
python backend/scripts/backfill_video_captions.py --course-id COURSE_ID --apply      # write captions
```

The command prints one JSON line per module: `generated`, `skipped_*`, `boundaries_mismatch` or `unavailable` with a reason. It runs one module at a time. The exit status is non-zero if any module fails.

Tests (`backend/tests/test_captions.py`; fake aligner command and fixture WAV/MP4 from the existing helpers):

- A legacy module with matching WAVs produces a valid `.vtt` and `.captions.json` that pass the player's own checks: fingerprint, cue count, duration.
- Boundaries that don't add up → `boundaries_mismatch`, and no files are written.
- Video Generator enabled → refused. Video with `.srt` → skipped.
- Existing valid captions → `skipped_valid_captions`.
- The batch worker loads the model once for N slides.
- The single-request worker format still works.

### Cost (measured 27 Oct 2026, WSL, Qwen3-ForcedAligner-0.6B, CPU)

Real module: 9 slides, 180 s of narration.

| Item | Measured |
| --- | --- |
| Model load | about 14 s, once per module with the batch worker |
| Alignment, 4 threads | about 15 s for 180 s of audio (about 0.08× real time) |
| Total per 3-minute module | **about 30 s** (batch) vs about 2–3 min (one process per slide, today) |
| Peak memory | about 6 GB |
| Model files on disk | 1.8 GB |

Example: a 4-module course of about 12 minutes takes about 2 minutes. Audio extraction with ffmpeg adds a few seconds per module.

Dependencies: needs the separate caption-aligner environment (`qwen-asr`, torch, model files), which is not in the API image. It is already installed in WSL at `~/caption-aligner` and `~/models/`. On a server, the backfill must run on a host with that environment and access to `backend/storage/generated`.

### Known limitation

If a slide's script was edited after its video was rendered, without re-rendering, the captions show the edited text. Boundary and timing checks catch added or removed slides and re-recorded audio, but not a text-only edit. The trainer should spot-check one module per course after the backfill.

## Order of work and checks

1. Part 1 tests to add (chain and invalid value). Part 1 code is done.
2. Step 2.1 sidecar authorization with Postgres tests.
3. Step 2.3 legacy backfill, batch worker, and tests.
4. Step 2.2 configuration and operations doc update.
5. Checks:
   - `corepack pnpm test`, `corepack pnpm lint`, typecheck.
   - Backend in WSL: `LMS_ACCESS_POSTGRES_TESTS=true ~/lj-venv/bin/python -m pytest` against the socket at `/tmp`, port 55439.
6. Demo:
   - Volume chain across modules and after a reload.
   - Dry run, then `--apply` on one older course (`course_4c0e8db1…` or a demo course).
   - The CC button turns on in the employee player and shows aligned captions.
7. Commit only when asked.
