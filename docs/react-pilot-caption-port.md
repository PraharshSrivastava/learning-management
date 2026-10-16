# React pilot and caption player

The isolated Document Builder pilot now builds `APP=trainer` with the repository-root
`deploy/web.Dockerfile`. It no longer patches or builds a Flutter Dockerfile. Run the
existing `scripts/document-builder-pilot.sh prepare [provider-env-file]` and `start`
commands from a separate checkout named `lms-document-builder-pilot`.

Preparation creates an ignored `.env.pilot` and an ignored
`tmp/document-builder-pilot/trainer.nginx.conf`. The generated nginx template preserves
main's authorization proxy and internal-only video location, mapping its file delivery
to the isolated storage volume. The pilot remains bound to loopback ports 16969 and
13060, uses its own Compose project, database and storage, and seeds only its synthetic
trainer identity. React already supports the same development-only trainer selection;
production authentication has not been relaxed. The pilot flag must never be copied
to the production environment. Existing pilot configuration and credentials are retained
when preparation is rerun.

The shared React `HlsVideoPlayer` bundles the established caption controls as
`captionPlayer.js`, with a typed module boundary in `captionPlayer.d.ts`. This preserves
the controls, keyboard support, full-player fullscreen, caption preferences/font sizes,
playback speed, and caption rail. It does not add a second native-controls toolbar.
React owns the containing element; the imperative player owns and disposes its video,
listeners, observer, abort controller and controls when the source changes or unmounts.
HLS/progressive fallback, media-ticket renewal, and the existing linear playback guard
remain in `HlsVideoPlayer.tsx`.

Caption metadata and VTT URLs derive from the MP4 URL, retaining the public mount and
media ticket. Every sidecar request uses the current renewed ticket. Captions remain
disabled unless metadata version, source file size/mtime, VTT SHA-256, cue count, cue
ordering, and video duration all match. The SHA-256 implementation also works on HTTP
deployments without SubtleCrypto. Existing videos still require valid generated caption
sidecars; this frontend port neither generates nor backfills them.

Focused verification: `vitest run packages/shared/src/video`, shared TypeScript check,
and video-directory ESLint. Tests cover ticket renewal, stale/corrupt captions,
caption controls and timeline parsing, source replacement/cleanup, and linear playback.
Docker build/start requires a Docker runtime and provider configuration; no live pilot
or production deployment is implied by these local checks.
