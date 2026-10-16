# Video captions implementation progress

Branch: `codex/video-captions-plan`
Updated: 9 October 2026

## Implemented

1. **Caption pipeline:** local forced-alignment worker contract and Qwen adapter, readable text mapping for TTS normalization/acronyms/financial expressions, cue grouping, validated WebVTT, and content fingerprints. No estimated word-count timing.
2. **Video integration:** measured encoded-slide offsets, atomic MP4 publication, narration provenance hashes, module locking, generation for new/verified skipped videos, and explicit dry-run backfill. Unknown historical provenance requires selected video regeneration.
3. **Corporate player:** custom HTML controls within the existing HLS platform view, charcoal three-dot menu, direct CC shortcut, Small/Medium/Large at 14/16/20 px, saved preferences, fullscreen, buffering/error messages, plain-text captions, and complete strip removal when off.
4. **App integration:** identical player assets in both apps, responsive player height in training and employee learning, existing generation previews using the same player, and synchronous seek constraints through the employee playback guard. Source requests reject stale asynchronous results.
5. **Configuration:** validated alignment argv/model/device settings, Compose environment plumbing, sample disabled configuration, isolated optional worker requirements, CORS video-header exposure, and operator documentation.

## Verification completed

- 14 focused backend tests passed: captions, source matching, narration cache invalidation, idempotency, locking, financial text, configuration validation, and existing HLS packaging.
- 4 Node tests passed: URL derivation, cue boundaries/silence, malformed captions, and HTTP-compatible SHA-256 integrity including Unicode.
- Chrome browser fixture checks passed: all three font sizes, CC off/on and full collapse, constrained seeking, silence, fullscreen entry/exit, 390 px mobile fit, stale-asset rejection, and disposal. The tested screenshots are fixture player views, not live course screenshots.
- All 4 existing employee linear playback guard tests passed.
- Both Flutter web release builds passed with pinned Flutter 3.44.0 and locked dependencies. The player JavaScript asset is included in each build. WebAssembly compatibility warnings reflect the existing `dart:html`/JS-interoperability implementation; the supported JavaScript web builds succeed.
- Targeted Dart analysis reported no errors; web-library/deprecation informational findings remain in the existing browser-based architecture.
- Focused Ruff checks passed and changed backend Python modules were compiled successfully.

## Still required before enabling real captions

- Provision and validate the isolated alignment runtime and local model weights. The optional Qwen worker has not been exercised with the actual model in this environment; fixture tests validate the asset/control pipeline, not acoustic accuracy.
- Identify/fix the real speech-service address. The configured port 8081 exposes Docling Serve's document-conversion schema. The configured model gateway's model listing also returned 401 during a read-only check, so it did not provide a usable alternative speech/alignment route.
- Verify real multi-slide audio synchronization, resource usage and worker latency, actual HLS/MP4 playback in the apps, native HLS where supported, quiz completion flow, and selected historical-course regeneration/backfill.
- Lock/review the isolated worker's transitive ML dependencies and provision its paths/model volume in the generation environment before deploying it.

Until valid assets exist, CC stays unavailable and videos continue to play. `CAPTION_ALIGN_COMMAND=[]` remains the default. No production speech calls, deployment, bulk regeneration, or production backfill were performed. Unrelated pre-existing security/remediation changes remain separate and untouched by this feature work.
