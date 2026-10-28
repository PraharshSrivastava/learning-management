# Video captions: setup, validation, and backfill

## Current state

The branch contains the corporate player, verified-caption asset pipeline, generation integration, local alignment worker, and selected-module backfill command. Caption controls are unavailable for a video until a valid caption asset is present. The configured alignment command defaults to `[]`, so no captions are produced until the aligner is configured. Captions never use estimated timings. Historical videos are captioned only through the explicit backfill below.

The configured speech URL, `http://35.238.33.238:8081`, was checked read-only on 9 October 2026. Its `/openapi.json` identifies **Docling Serve 1.29.0**, exposes document conversion routes, and does not list `/v1/audio/speech` or word alignment. Repository defaults and `.env` point to that same address. No production settings were changed. Existing videos can play independently of this service, but new speech generation needs the actual speech endpoint.

## Alignment runtime

The optional worker uses [Qwen3-ForcedAligner](https://github.com/QwenLM/Qwen3-ASR), aligning a known transcript against final speed-adjusted WAV audio. It does not transcribe guessed text or divide an audio duration by word count. The worker API follows the [official alignment example](https://github.com/QwenLM/Qwen3-ASR/blob/main/examples/example_qwen3_forced_aligner.py). The separate [qwen-asr 0.0.6 package](https://pypi.org/project/qwen-asr/0.0.6/) is pinned in `backend/requirements-caption-aligner.txt`; its ML dependencies are deliberately excluded from the API's existing requirements and lockfile.

Prepare an isolated worker environment on the generation host, install the optional requirements, and place reviewed Qwen3-ForcedAligner-0.6B weights in a local directory. Lock the worker's transitive packages and validate resource usage before production. The worker refuses a missing model directory and sets offline model loading: there is no implicit weight download or audio upload during course generation. The first version aligns English narration, per slide, with a 600-second worker timeout. The upstream model supports audio up to five minutes per alignment input; longer slides must be split and validated before enabling this path.

Example Linux backend environment, with paths adjusted to the actual installation:

```dotenv
CAPTION_ALIGN_COMMAND=["/opt/caption-venv/bin/python","/app/scripts/align_captions_qwen.py"]
CAPTION_ALIGN_MODEL_PATH=/opt/models/Qwen3-ForcedAligner-0.6B
CAPTION_ALIGN_DEVICE=cpu
```

Use `cuda:0` only where the isolated worker has a compatible GPU stack. All command/model paths must exist inside the backend's runtime namespace. Docker Compose passes these variables but does not install the optional worker or mount weights automatically. Provisioning the worker in a production container is a separate release prerequisite, not a change already deployed by this branch.

`CAPTION_ALIGN_COMMAND` is a JSON argv list executed without a shell. Custom compatible workers receive `request.json` and `result.json` as their final arguments. The backend sends one request per module: `items` (a list of `audio`, an absolute local path, and `text`, the normalized spoken transcript) and `language` (`English`). The result must contain `results`, one entry per item in order, each with a complete ordered `words` list of `text`, `start`, and `end` in seconds. The bundled worker also still accepts the older single-slide request (`audio`, `text`, `language` → `words`). Validation rejects missing words, nonfinite/negative/overlapping intervals, wrong tokens, or audio-bound violations.

Measured on 27 October 2026 (WSL, CPU, `CAPTION_ALIGN_THREADS=4`): the model loads in about 14 s, alignment runs at about 0.08× real time, and a 3-minute module takes about 30 s in total. Peak memory is about 6 GB per run, released when the worker exits. Runs are serial, so memory does not add up across modules.

## Assets and provenance

New narration records `.narration.json` with normalized transcript and final WAV hashes. TTS cache reuse requires that proof, preventing audio from an old script being silently reused. Narration synthesis uses an audio asset lock. Newly rendered videos record `.source.json` with narration hashes and measured encoded slide durations only when the narration proof matches. Video rendering and backfill share a per-module `.media.lock`. Video publication is atomic, and caption metadata is published after the caption file. Regeneration/replaced narration invalidates the source fingerprint; failures remain visible in generation logs without breaking video playback.

Each successful caption run produces `module_N.vtt` and `module_N.captions.json` beside the MP4. Media authorization maps exactly these two files to their MP4's course; `.source.json`, `.narration.json`, `.srt`, and lock files are never served. The client validates version, cue count, final duration, the MP4's size/Last-Modified headers, and the caption file's SHA-256 before enabling CC. VTT URLs contain a content fingerprint; metadata and headers are fetched without caching. CORS exposes the necessary video headers. Caption integrity works on both HTTP and HTTPS deployments.

Treat video/sidecar replacement as one release operation. Do not manually copy caption metadata from another video. A hard-killed generation job can leave `.media.lock`; remove it only after confirming no render or backfill process is active for that module.

## Existing videos

Backfill is dry-run by default, runs one module at a time, and is limited to an explicit course (optionally one module). It refuses to run when `VIDEO_GENERATION_MODE=external`, and it always skips Video Generator videos (a `video_service` run record or an `.srt` transcript), because those already show burned-in subtitles.

```bash
python backend/scripts/backfill_video_captions.py --course-id COURSE_ID              # dry run, all modules
python backend/scripts/backfill_video_captions.py --course-id COURSE_ID --module 2   # dry run, one module
python backend/scripts/backfill_video_captions.py --course-id COURSE_ID --apply      # write captions
```

Each module prints one JSON line: `dry_run`, `generated`, `skipped_valid_captions`, `skipped_video_generator`, `skipped_no_video`, or `unavailable` with a reason. The exit status is nonzero when any module is `unavailable`.

- **Videos with render-time provenance** (`.source.json`) use the provenance-checked path above.
- **Older videos without provenance** (`method: forced-alignment-legacy`) are captioned from the MP4's own soundtrack:
  1. The pause between slides is solved from the video length and the slide WAV lengths. It must be between 0 and 3 seconds.
  2. Each slide WAV's loudness pattern, followed by its silent pause, is matched against the soundtrack within 0.6 s of where it should start. Encoding shifts each clip by a few hundredths of a second, so the matched position is used rather than the arithmetic one.
  3. Each matched piece of soundtrack is aligned with the slide's current script.
- The legacy path refuses a module when:
  - the narration does not add up to the video length;
  - a slide's narration does not match the soundtrack (`Slide N narration does not match…`);
  - most aligned words collapse to zero length, which means the script no longer matches the speech.
- **Known limitation:** if a script was edited after rendering but the edit still aligns plausibly, the captions show the edited text. Spot-check one module per course after a backfill.

A valid existing caption asset is skipped idempotently. No production course backfill has been run.

## Validation commands

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_captions.py backend/tests/test_video_hls.py --basetemp=tmp/captions/pytest -q
node --test frontend/test/caption_player_test.cjs
node frontend/test/caption_player_browser_test.cjs
```

The browser test requires Playwright; optionally set `CHROME_PATH` to an installed Chrome executable and `PLAYER_SCREENSHOT` to a local output PNG path. It uses isolated fixtures, not live employee data. Run `flutter build web --release --no-pub --no-web-resources-cdn` for both apps with pinned Flutter 3.44.0, and the employee `linear_playback_guard_test.dart`. A local employee `.env` containing `API_BASE_URL=` was added solely to satisfy its declared build asset; deployment still supplies its normal environment.

Before rollout, configure the real speech endpoint and alignment runtime; validate real audio near the start/middle/end of a multi-slide video, at every speed, including acronyms, financial text, long narration, and transition pauses. Then validate native HLS, MP4 fallback, fullscreen, quiz unlocking, and actual app-level behavior with selected courses. Automated fixture tests are not a claim that live alignment accuracy has been verified.
