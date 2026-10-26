# Video Generator integration plan

Branch: `feature/video-generator-integration` (from `main` @ `e0ba810`)
External service: https://github.com/PraharshSrivastava/Video-Generator (studied at `eadf893`, 2026-10-21)

## Key finding

The Video Generator already exposes an LMS API, so we don't have to wait for one. Its full contract is in
`docs/lms-integration-guide.md` in that repo. It accepts the same per-module body we proposed:
`request_id, course_id, blueprint_revision, course_name, course_objective, target_audience, language, module{module_id, module_number, title, source_text}`.

We adapt our client to **their** contract instead of asking for ours:

| What | Our draft | Their actual API |
|---|---|---|
| Submit | `POST /api/v1/video-jobs` | `POST /api/v1/animation-requests` (202 new, 200 replay, 409 body mismatch, 422, 429) |
| Status | `GET /video-jobs/{job_id}` | `GET /animation-requests/{id}` |
| Download | `GET .../video` | `GET .../{id}/video` (MP4) and `GET .../{id}/captions` (SRT); both 409 until done |
| Extras | — | `POST .../{id}/retry` (resume from checkpoint), `DELETE .../{id}` (cleanup) |
| Job id field | `job_id` | `id` |
| States | queued/running/completed/failed | queued/processing/succeeded/failed/needs_attention |
| Auth | Bearer key | HMAC-SHA256: `X-VG-Timestamp`, `X-VG-Nonce`, `X-VG-Signature` over `METHOD\nPATH\nQUERY\nTS\nNONCE\nsha256(body)`; 300 s skew, single-use nonce |

Output: H.264/AAC MP4, 1920x1080 at 30 fps with `+faststart`, plus SRT captions and a sha256 in the status.

## How it plugs into the LMS

The current pipeline in `backend/app/generation/runtime.py` (`run_full_course_generation`) runs these stages:

```
wave 1 (parallel): thumbnail, quiz, notes, slides
then: html -> scripts -> tts -> video -> publish
```

In the new **external** mode it becomes:

```
wave 1 (parallel): thumbnail, quiz, notes        (slides dropped)
then: external_video -> publish                  (html, scripts, tts, local video dropped)
```

`external_video` does this for each module, up to N at a time:
1. Submit the module to `POST /animation-requests` with a deterministic `request_id`
   (`{course_id}:{module_number}:{hash(title+source_text)}`), so restarts replay instead of duplicating.
2. Save `{request_id, external_id, status, stage, progress}` in the module's `metadata_json`.
3. Poll `GET /animation-requests/{id}` every `poll_after`/15–30 s, with a 60-minute ceiling per module.
4. On `succeeded`: download the MP4 to `storage/generated/videos/course_<id>/module_<n>.mp4` and verify sha256 and size.
   Write the file atomically, run `generate_hls_playlist`, and set `video_path`.
5. Subtitles: when the service has captions on (`INTEGRATION_CAPTIONS=true`), it **burns them into the video**.
   So the LMS adds no soft captions of its own (that would show them twice), removes any old `.vtt`/`.captions.json` sidecars, and keeps the SRT only as a transcript (`module_<n>.srt`).
   Then it calls `DELETE` on the remote run.
6. On `failed` with `retryable`: call `/retry`. On `needs_attention`, or a failure we can't retry: fail the stage with a clear error.

Selected by a setting: `VIDEO_GENERATION_MODE = local | external` (default `local`), so the old path keeps working.

## Work breakdown (LMS side)

| # | Area | Change | Main files |
|---|---|---|---|
| 1 | Settings | `VIDEO_GENERATION_MODE`, `VIDEO_SERVICE_BASE_URL`, `VIDEO_SERVICE_HMAC_SECRET`, `VIDEO_SERVICE_MAX_CONCURRENCY` (≤4), poll interval and timeout; production checks | `backend/app/core/settings.py`, `.env.example` |
| 2 | Client | `VideoServiceClient`: HMAC signing, submit, status, download video/captions, retry, delete; 429 `Retry-After` backoff; errors raised as `ProviderError` | new `backend/app/generation/video_service.py` |
| 3 | Pipeline stage | `generate_videos_via_service(course_id)` (submit → poll → download → HLS → `video_path`) | same file, `backend/app/generation/video.py` (reuse HLS helper) |
| 4 | Orchestration | Branch on mode in `run_full_course_generation`: skip slides, html, scripts and tts in external mode | `backend/app/generation/runtime.py` |
| 5 | Readiness | `missing_generation_outputs` checks only the outputs the mode needs; publish checks are unchanged (they already only need `video_path`, thumbnail, quiz) | `runtime.py` |
| 6 | Module metadata | Add `video_service` to `MODULE_METADATA_FIELDS` | `backend/app/repositories/courses.py` |
| 7 | Captions | SRT → VTT and `captions.json` adapter; skip the forced-alignment path in external mode | `backend/app/generation/captions.py` |
| 8 | Single-module regen | `modules/{n}/generate-video` uses the service in external mode | `backend/app/services/generation.py` |
| 9 | Trainer UI (React) | Show per-module external status and progress; hide the slide transcript in external mode | `apps/trainer/src/features/training/*`, `apps/trainer/src/features/courses/useFullCourseGeneration.ts`, `packages/shared/src/models/course.ts` |
| 10 | Tests | Client signing (match their reference `sign()`), stage flow with a fake service, readiness rules per mode | `backend/tests/` |

No DB migration is needed: the state lives in `course_modules.metadata_json`.

## Models the Video Generator needs (LMS animation path)

All are remote OpenAPI-compatible endpoints on the Video Generator side; nothing runs on the LMS host.

| Purpose | Default model | Video Generator env |
|---|---|---|
| Storyboard / scene planning, and vision review of generated artwork | `qwen3.6-35b` (must accept images) | `CONTENT_LLM_ENDPOINT`, `ANIMATION_LLM_MODEL`, `PIPELINE_VISION_MODEL` |
| Scene artwork | `qwen-image-2.1` | `CONTENT_IMAGE_ENDPOINT`, `ANIMATION_IMAGE_MODEL` |
| Narration | `qwen3-tts`, voice `ryan` | `CONTENT_TTS_ENDPOINT` / `ANIMATION_TTS_ENDPOINT`, `ANIMATION_TTS_MODEL`, `ANIMATION_TTS_VOICE` (or `INTEGRATION_VOICE`) |

Not needed for LMS videos: `gemma-4-e4b` (studio dialogue scripts), Docling (document upload), LatentSync lip-sync, Veo (paid, requires manual artwork review, never auto-approved).

## Implementation status (2026-10-26)

Done:
- Settings and validation (`VIDEO_GENERATION_MODE` and the `VIDEO_SERVICE_*` settings).
- `VideoServiceClient`, signed with HMAC and tested against the service's reference `sign()`.
- External video stage, with resume, 429 back-off, remote retry, checksum checks, HLS packaging and remote cleanup.
- Readiness checks that depend on the video mode.
- Background job endpoints: `POST /api/courses/{id}/modules/{n}/video-jobs` and `POST /api/courses/{id}/generation-jobs/continue`.
- `GET /api/generation/config`.
- Per-module `video_service` progress in `ModuleResponse`.
- Trainer UI (React, `apps/trainer`):
  - inline module progress, plus Regenerate and Retry buttons
  - video progress in the full-course overlay
  - the slide transcript hidden in external mode
  - Continue runs in the background for checkpoints other than the blueprint

Not yet done:
- Not yet run against the real Video Generator: we still need its URL and HMAC secret.

## Open questions for the Video Generator owner

1. **Network:** their `/api/v1` is bound to `127.0.0.1` in `infra/onprem/compose.yaml`. Will the services share one host, or will they expose it over TLS to our backend?
2. **Secret:** they need to issue `INTEGRATION_HMAC_SECRET` (32+ chars) and a tenant/client id for us.
3. **Language:** English only for now. Is that OK for our courses?
4. **Capacity:** 4 active jobs by default, several minutes per module, and the LLM, image and TTS inference endpoints are shared. Agree on limits.
5. **Images:** `source_text` contains `[IMAGE: id]` markers. Should we strip them, or will they accept images later?
6. **Text limits:** source_text must be 50–100,000 chars. Modules under 50 chars need a fallback.
7. **Branding:** voice, template and logo are fixed per tenant (`INTEGRATION_*`), not per request. Is that acceptable?
8. **Webhooks:** none; we poll.
