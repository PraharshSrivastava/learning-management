# Video captions: setup, validation, and backfill

## Current state

The branch contains the corporate player, verified-caption asset pipeline, generation integration, local alignment worker, and selected-module backfill command. Caption controls are unavailable for a video until a valid caption asset is present. The configured alignment command defaults to `[]`, so this checkout does not fabricate timings or enable captions for historical videos.

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

`CAPTION_ALIGN_COMMAND` is a JSON argv list executed without a shell. Custom compatible workers receive `request.json` and `result.json` as their final arguments. The request contains `audio` (absolute local path), `text` (normalized spoken transcript), and `language` (`English`). The result must contain a complete ordered `words` list with `text`, `start`, and `end` in seconds. Validation rejects missing words, nonfinite/nonpositive/overlapping intervals, wrong tokens, or audio-bound violations.

## Assets and provenance

New narration records `.narration.json` with normalized transcript and final WAV hashes. TTS cache reuse requires that proof, preventing audio from an old script being silently reused. Narration synthesis uses an audio asset lock. Newly rendered videos record `.source.json` with narration hashes and measured encoded slide durations only when the narration proof matches. Video rendering and backfill share a per-module `.media.lock`. Video publication is atomic, and caption metadata is published after the caption file. Regeneration/replaced narration invalidates the source fingerprint; failures remain visible in generation logs without breaking video playback.

Each successful caption run produces `module_N.vtt` and `module_N.captions.json` beside the MP4. The client validates version, cue count, final duration, the MP4's size/Last-Modified headers, and the caption file's SHA-256 before enabling CC. VTT URLs contain a content fingerprint; metadata and headers are fetched without caching. CORS exposes the necessary video headers. Caption integrity works on both HTTP and HTTPS deployments.

Treat video/sidecar replacement as one release operation. Do not manually copy caption metadata from another video. A hard-killed generation job can leave `.media.lock`; remove it only after confirming no render or backfill process is active for that module.

## Existing videos

Backfill is dry-run by default and limited to an explicit course/module:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/backfill_video_captions.py --course-id COURSE_ID --module 2
backend/.venv/Scripts/python.exe backend/scripts/backfill_video_captions.py --course-id COURSE_ID --module 2 --apply
```

Use the backend Python equivalent on Linux. A historical MP4 without render-time provenance reports `requires_video_regeneration`; matching text filenames alone do not prove the audio belongs to that video. Regenerate selected narration and then the module video through the normal authorized workflow to establish provenance. Existing WAV files without narration proof are regenerated on an explicitly requested TTS generation run. Do not mass-regenerate published courses as part of a caption dry-run.

The command returns a nonzero exit status on unavailable/mismatched sources. A valid existing caption asset is skipped idempotently. No production course backfill or video regeneration has been run during this implementation.

## Validation commands

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_captions.py backend/tests/test_video_hls.py --basetemp=tmp/captions/pytest -q
node --test frontend/test/caption_player_test.cjs
node frontend/test/caption_player_browser_test.cjs
```

The browser test requires Playwright; optionally set `CHROME_PATH` to an installed Chrome executable and `PLAYER_SCREENSHOT` to a local output PNG path. It uses isolated fixtures, not live employee data. Run `flutter build web --release --no-pub --no-web-resources-cdn` for both apps with pinned Flutter 3.44.0, and the employee `linear_playback_guard_test.dart`. A local employee `.env` containing `API_BASE_URL=` was added solely to satisfy its declared build asset; deployment still supplies its normal environment.

Before rollout, configure the real speech endpoint and alignment runtime; validate real audio near the start/middle/end of a multi-slide video, at every speed, including acronyms, financial text, long narration, and transition pauses. Then validate native HLS, MP4 fallback, fullscreen, quiz unlocking, and actual app-level behavior with selected courses. Automated fixture tests are not a claim that live alignment accuracy has been verified.
