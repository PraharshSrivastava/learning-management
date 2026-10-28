# Video captions: setup, validation, and backfill

## Current state

The branch contains the corporate player, verified-caption asset pipeline, generation integration, local alignment worker, and selected-module backfill command. Caption controls are unavailable for a video until a valid caption asset is present. With the default settings (`CAPTION_TIMING=auto`, `CAPTION_ALIGN_COMMAND=[]`), locally rendered videos get **narration-timed** captions, so no aligner is needed. Historical videos are captioned only through the explicit backfill below.

## Caption timing

`CAPTION_TIMING` picks how cues are timed:

| Value | Behaviour |
|---|---|
| `auto` (default) | Forced alignment when `CAPTION_ALIGN_COMMAND` is set; otherwise narration timing. If alignment fails for a module, narration timing is used instead |
| `narration` | Always narration timing |
| `aligned` | Forced alignment only; captions fail, as before, when the aligner is not configured or fails |
| `off` | No captions are written (status `skipped_captions_off`); videos are unaffected |

Both methods write the same `.vtt` and `.captions.json`, and the player validates them the same way. The metadata `method` records which one was used: `forced-alignment` / `forced-alignment-legacy`, or `narration-timing` / `narration-timing-legacy`. The player does not read `method`.

**Forced alignment** times every word with the local aligner described below.

**Narration timing** uses the Video Generator's method, with no ML:
1. Slide spans are exact. Slide *n* starts at the sum of the earlier measured clip lengths (`clip_durations` in `.source.json`), and its speech lasts its narration WAV's length. The transition pause after it gets no cue.
2. Silence at each edge of the slide WAV is trimmed. Speech is any 10 ms frame louder than 3% (about −30 dB) of the slide's own 95th-percentile loudness, and each cue starts 50 ms before the first sound and ends 50 ms after the last. If no speech is detected, the whole WAV is used.
3. Cues are built from the **written** script (so AML and FIU-IND appear as written). They break at `.`, `!`, `?` and `;`, but not after "Mr.", "Mrs.", "Ms.", "Dr.", "e.g.", "i.e." or "vs.". Longer phrases are split evenly, preferring a comma or colon, to at most 78 characters and two 42-character lines. A cue never ends on a weak word such as "the", "of" or "and" (also when it has an opening bracket or quote, as in "(the"), and a single word is not left on its own where avoidable.
4. Speech time follows **spoken** length: "FIU-IND" counts as "eff eye you India". If the spoken mapping fails, written length is used.
5. Pause anchors: pauses of at least 0.25 s inside the WAV (frames below 10% of the speech level, about −20 dB) are paired, in order and one each, with phrase ends: sentence ends, commas and colons. Each pause is predicted from the previous pinned phrase end at the slide's own speaking rate, so estimates do not drift across a long slide. A pair must lie within ±1.5 s of the prediction, and is scored by its error relative to the length of the stretch. A phrase end left without a pause, or a pause left without a phrase end, costs a penalty; sentence ends cost the most, because they nearly always pause. Commas therefore claim their own pauses, and a sentence end cannot take a comma's pause.
6. Each pinned phrase ends where its pause starts, and the next begins where the pause ends. Between pins, time is shared by spoken length. Every cue lasts at least 0.8 s where the time allows, and cues never overlap.

**Measured accuracy** (28 October 2026, 23 real narrated slides from two courses, 177 cues, compared with the forced aligner's word times): both cue edges are within 0.25 s for 91.5% of cues, within 0.5 s for 100%, and within 1.0 s for 100%. The median edge error is 0.03 s and the largest is 0.40 s. Individual words are not timed.

**Script checks.** Newly rendered videos prove by hash that each slide's script produced its narration (`.narration.json`, `.source.json`). Older videos have no such proof, so on the legacy path each slide's script must fit its narration length: spoken characters per second of trimmed speech must be between 8 and 28. Real narration measured 13.9–18.6. Slides with fewer than 40 spoken characters and under 3 s of speech are too short to judge. A failing slide refuses the module with `Slide N script does not match its narration length; regenerate narration`. An edit that changes a slide's length by less than about 1.5×, either way, is not detected; the captions then show the current script.

**Fallback in `auto`.** When the aligner is configured but alignment fails for a module (worker error, timeout, bad output, or a transcript it cannot handle), the failure is logged as `caption_alignment_failed` and the module is narration-timed instead. When narration captions already exist and the failed run was an upgrade, they are kept unchanged (status `kept_narration_captions`). A script that does not match its audio (most aligned words collapse to zero length, or the length check above fails) is never a reason to fall back: the module is refused. Explicit `aligned` mode never falls back.

**Upgrading to aligned captions.** Valid captions are normally skipped. When an aligner is configured (`auto` with a command, or `aligned`), captions whose `method` is a narration-timing method are regenerated with forced alignment, both by the backfill and when a course's videos are regenerated. Aligned captions are never replaced by narration timing; in `narration` mode, any valid captions are kept.

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

Each module prints one JSON line: `dry_run`, `generated`, `skipped_valid_captions`, `kept_narration_captions`, `skipped_video_generator`, `skipped_no_video`, `skipped_captions_off`, or `unavailable` with a reason. The exit status is nonzero when any module is `unavailable`. `method` is the method of the captions on disk after the run (or the one that would be used, in a dry run). A dry run also reports `existing_method` (the valid captions already on disk, or `null`) and `would_upgrade` (whether `--apply` would replace narration-timed captions with aligned ones).

- **Videos with render-time provenance** (`.source.json`) use the provenance-checked path above.
- **Older videos without provenance** (`method: forced-alignment-legacy` or `narration-timing-legacy`) are captioned from the MP4's own soundtrack. This works with or without an aligner:
  1. The pause between slides is solved from the video length and the slide WAV lengths. It must be between 0 and 3 seconds.
  2. Each slide WAV's loudness pattern, followed by its silent pause, is matched against the soundtrack within 0.6 s of where it should start. Encoding shifts each clip by a few hundredths of a second, so the matched position is used rather than the arithmetic one.
  3. Each matched piece of soundtrack is either aligned with the slide's current script, or narration-timed from that piece (edge trimming and sentence anchors as above), starting at the matched slide start.
- The legacy path refuses a module when:
  - the narration does not add up to the video length;
  - a slide's narration does not match the soundtrack (`Slide N narration does not match…`);
  - with an aligner, most aligned words collapse to zero length, which means the script no longer matches the speech;
  - with narration timing, a slide's script does not fit its narration length (see *Script checks*).
- To upgrade narration-timed captions once an aligner is installed, configure it and run the backfill again with `--apply`.
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
