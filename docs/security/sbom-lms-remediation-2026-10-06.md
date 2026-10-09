# LMS SBOM remediation — 6 October 2026

Historical first-round snapshot. The backend selection and current risk status are superseded by [the native remediation report](sbom-lms-backend-remediation-round2-2026-10-06.md). Preserve the comparable results below as evidence for the earlier Debian candidate; do not substitute the new Ubuntu counts into this table.

Current scope: backend and both frontends. PostgreSQL security fixes are deferred by the user's latest instruction. Its completed candidate/evidence is preserved separately and excluded from active totals and deployment scope. The new PostgreSQL Compose hardening setting was removed; its deployment image reference was never changed.

Security candidates were built and tested in isolated containers on big-coding. These changes have not been deployed, committed, pushed, or applied to UAT. The live LMS image identities remain those recorded in the original baseline. This report continues the [5 October summary](sbom-lms-progress-summary-2026-10-05.md).

## Comparable results

The same Trivy 0.75.0 scanner and 6 October advisory snapshot were used for both columns. Database UpdatedAt: `2026-10-06T01:08:27.80517672Z`; DownloadedAt: `2026-10-06T04:26:58.756905245Z`. Original 5 October counts must not be substituted into this comparison.

| Component | Refreshed previous candidate / running OS baseline | New candidate | Removed occurrences |
| --- | ---: | ---: | ---: |
| Backend | 943 | 829 | 114 |
| Trainer frontend | 22 | 0 | 22 |
| Employee frontend | 22 | 0 | 22 |
| Active scope total | 987 | 829 | 158 |

No new advisory occurrences appeared in these comparisons. The 158 removed active-scope occurrences comprise 8 High, 30 Medium, 4 Low and 116 Unknown. The backend refresh added 114 Unknown LibreOffice matches to the unchanged previous candidate; upgrading LibreOffice removed those matches. That is why the refreshed backend starting count is 943 rather than the earlier 829. The Playwright/browser update did not change the raw image finding count.

Remaining in active scope: backend 1 Critical / 230 High / 306 Medium, plus 272 Low and 20 Unknown. These are package/advisory occurrences, not distinct exploitable defects. Both frontend image scans report zero matches in their detected runtime packages; Flutter/Dart/browser engine coverage requires separate evidence. Deferred PostgreSQL results are excluded.

## Changes prepared

- Backend: supported LibreOffice update to the fixed Debian revision; use `/usr/bin/ffmpeg` throughout the application instead of the older wheel-bundled executable, and remove that bundled executable. Upgrade hash-locked Playwright 1.61.0 to 1.63.0 and its downloaded Chromium from 149.0.7827.55 to 153.0.8010.12; only Playwright changed in this last dependency resolution. Preserve document conversion, HLS packaging, and narration speed adjustment. Earlier urllib3, PCRE2/OpenSSL and build-only pip remediation remains included. Browser versions are separately inventoried because the Trivy image report does not establish complete downloaded-browser advisory coverage; the upgrade is not assigned a speculative CVE reduction.
- Deferred PostgreSQL work, completed before the scope change: immutable upstream gosu 1.19 was rebuilt with Go 1.26.6 and x/sys 0.44.0. The isolated candidate removed 46 matches (342 to 296). Its Dockerfile and evidence are retained for later review; Compose does not select it and it is excluded from the current release scope.
- Both frontends: build with immutable Flutter 3.44.0 / Dart 3.12.0, matching existing dependency locks. Enforce the lockfile rather than silently resolving older package versions. The old 3.24.5 build had downgraded 22 packages despite a copied lockfile suggesting otherwise. Use the pinned nginx 1.31.6 / Alpine 3.24 runtime; bundle web resources and the licensed Roboto fallback font for offline rendering.
- Container definitions: disable privilege escalation and drop all capabilities for backend and both frontends. PostgreSQL Compose settings are unchanged. These restrictions reduce privilege exposure; they do not close unfixed findings.
- Automation: resolve exact image IDs, download advisory data once per batch, serialize cache access, group findings by shared source family, and compare saved JSON reports. See [security tooling](../../scripts/security/README.md).

## Validation and its limits

- Backend isolated smoke checks passed: HTTP chunked/gzip, trusted/untrusted HTTPS, PDF extraction, Chromium rendering, actual DOCX/PPTX conversion, FFmpeg audio/video encoding, actual HLS packaging and TTS speed adjustment. Effective capabilities were empty and NoNewPrivs was enabled. Dependency consistency was checked during the image build.
- Deferred PostgreSQL evidence only: isolated synthetic schema, transaction, backup/restore, restart and gosu checks passed before the scope change. No live database files were mounted. No further PostgreSQL remediation or deployment is being performed.
- Both frontend candidates passed nginx configuration, cache headers, API proxy app headers, synthetic video range serving, and actual browser rendering of the Hub access gates. There were no external requests or browser page errors. Screenshots were retained. This does not validate real Hub login or the complete course workflow.
- Locked public Dart dependencies: 57 unique package/version pairs queried against OSV, with no reported advisories. SDK packages and engine/native binary coverage remain explicit gaps. Compiled dependency versions were checked against the locks. Trainer native test passed; six employee native tests passed, but its widget test cannot load browser-only HLS imports natively. A browser-platform attempt stalled while loading and was stopped after eight minutes. This test is unresolved, not passed.
- Active-scope CycloneDX inventories were exported from exact candidate reports: backend 500 components and each frontend 71. The earlier PostgreSQL inventory is preserved separately. Counts reflect detected components, not complete coverage of every downloaded or compiled binary. Exported JSON was parsed; full CycloneDX schema/licence normalization was not performed.

## Remaining risks and release work

All remaining active-scope reported occurrences are Debian packages with no populated FixedVersion in this advisory snapshot. They remain open, with no ignore rules or blanket risk acceptance. Backend work is grouped into 71 source families. The [residual family register](sbom-lms-residual-families-2026-10-06.csv) preserves priorities and owner/action fields; PostgreSQL groups remain in separate deferred evidence.

The top release concern is `CVE-2026-6653` in libxml2, reported Critical in the backend (also present in the separately deferred database evidence). Debian's [advisory](https://security-tracker.debian.org/tracker/CVE-2026-6653) still lists the Trixie package as vulnerable; no supported Trixie/backports fix was found. Debian's lower impact assessment does not erase the scanner severity. Upstream's fix changes parser internals across several files; an untested cross-version ABI patch was not applied. Next decision: a vendor-supported fix, maintained backport, or tested replacement architecture plus a documented assessment of XML/document exposure. Container restrictions are supplementary mitigation.

The FFmpeg source family contributes 279 backend occurrences (144 High, 126 Medium, 9 Low). The application needs document/media dependencies. The [Debian source tracker](https://security-tracker.debian.org/tracker/source-package/ffmpeg) lists unresolved stable issues; no supported Trixie-backports replacement was found. Upgrading the previously selected wheel executable to the maintained system executable improves actual processing, but does not eliminate these OS matches. Assess document/media input exposure and supported replacement/backport options by family rather than attempting 279 individual package changes.

Next release steps: resolve or explicitly review the remaining Critical/High release risks; validate real Hub login and trainer/employee course flows with the finalized candidates in an isolated full stack; prepare immutable backend/frontend release image references and rollback instructions; deploy only those reviewed artifacts, preserving the database deployment; re-check running image IDs and scan evidence on big-coding and UAT. The current Compose PostgreSQL reference still points to upstream, so it does not automatically select the custom candidate Dockerfile. No deployment result is implied by this report.

## Evidence

Raw reports, DB metadata, build inputs/logs, tests, inventories and comparisons are preserved on the VM under `/home/karphi/lms-security/evidence/`, with local copies in ignored `tmp/security-20261006/`. Final candidate folders: `backend-candidate-20261006-05`, `postgres-candidate-20261006-03`, and `frontend-candidates-20261006-03`; superseded/failed attempts remain identifiable. Candidate image identifiers are recorded in each folder and the [candidate manifest](sbom-lms-candidate-manifest-2026-10-06.json). No production credentials or live data are part of these synthetic test reports.
