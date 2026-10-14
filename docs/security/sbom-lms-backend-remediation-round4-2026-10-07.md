# LMS backend parser and X library remediation — round 4

Historical candidate 17 snapshot. Current backend results are in the [round-five report](sbom-lms-backend-remediation-round5-2026-10-07.md).

Date: 7 October 2026. Isolated candidate tested; not deployed. PostgreSQL security work remains deferred.

Seven more inherited High package-advisory occurrences are addressed. The remaining inherited backlog is **0 Critical, 7 High, 97 Medium, 195 Low and 20 Unknown**. All 829 inherited rows remain in the register: 510 addressed and 319 open. Of the original 537 Critical/High/Medium occurrences, 433 are addressed and 104 remain open. Counts represent package-advisory occurrences, not unique vulnerabilities.

## Root causes and changes

Updating an OS package alone would leave older parsers embedded in CPython and Pillow. This batch removes that duplication for the reviewed parser paths: CPython's `pyexpat` extension is rebuilt from the same CPython 3.12.14 source against shared Expat 2.8.5; Pillow 12.3.0 is rebuilt from its hash-pinned source against shared TIFF 4.7.2. Its previous private TIFF library is removed from the final filesystem. Both Python and system callers now use the maintained shared parsers. Other native bundles still need separate review.

| Family | Fix | Inherited High occurrences addressed |
| --- | --- | ---: |
| Expat | System library and CPython binding use 2.8.5; malformed UTF-16 surrogate sequences rejected | 1 |
| TIFF | System library and Pillow use 4.7.2; multipage and compressed image handling preserved | 1 |
| ACL | Shared library upgraded to 2.4.0; new no-follow API and existing tar ACL behavior verified | 1 |
| libX11 | Apply exact upstream MR309 key-action bounds check to 1.8.13; rebuild library and XCB companion consistently | 3 |
| libXrender | Apply exact upstream MR19 screen/subpixel bounds check to 0.9.12 | 1 |

Primary references: [Expat advisory](https://security-tracker.debian.org/tracker/CVE-2026-93990), [TIFF advisory](https://security-tracker.debian.org/tracker/CVE-2026-36849), [ACL advisory](https://security-tracker.debian.org/tracker/CVE-2026-54369), [X11 advisory](https://security-tracker.debian.org/tracker/CVE-2026-88806), [Xrender advisory](https://security-tracker.debian.org/tracker/CVE-2026-88807). Their retrieved pages and hashes are preserved. X fixes are pinned merge-request patches, **not new upstream releases**. X11 data remains at its distribution version; the affected executable implementation is patched in the shared library. No library-wide exemption is applied to unrelated advisories.

The package recipe preserves SONAMEs and checks existing versioned ELF exports. X11's XCB companion is rebuilt with the matching exact package dependency. Package metadata records actual source versions and patch provenance. Neither dependencies nor scanner findings are ignored.

Pillow now uses distribution codec libraries instead of its former private libraries. Functional codec support is preserved, but underlying versions change: for example FreeType 2.14.3 → distribution 2.14.2 and WebP 1.6.0 → distribution 1.5.0. Distribution backports and advisories require review; this is not a claim that every codec was upgraded. FreeType CVE-2026-95512 remains open with a listed distribution fix. Expat CVE-2025-66382 also remains open: Expat 2.8.5 does not fix every Expat advisory.

## Candidate and validation

Selected tag: `lms-sbom-backend:candidate-20261007-17`.

Exact image ID: `sha256:0f8a5e8b83e00ce07f1976ab0ea9dba2e1dde6bf85fb4bca8e8659ff6cc0cf0e`.

To reduce build time and preserve application behavior, validation adds the maintenance layer to the exact prior candidate 16. All 147 application/script files match that parent. The repository Dockerfile contains the corresponding full build recipe; **a full repository rebuild has not been validated**. Evidence contains both recipes, source hashes, package metadata, scans and tests.

- Expat upstream test program, 17 TIFF tests, 10 ordinary ACL test groups and one X11 upstream test passed. Xrender `make check` completed without a separate test suite.
- Six ACL privileged/NFS groups are excluded because required device privileges or NFS mounts are unavailable. Initial fixture failures with Rust utilities were diagnosed; ordinary tests passed using their required GNU utilities. No privileged container was introduced.
- Malformed UTF-16 rejection and valid supplementary Unicode passed through Expat and ElementTree. Shared-library linkage, removal of private TIFF, six-library ELF compatibility, package dependency checks and native hashes passed.
- PNG, progressive JPEG, WebP, AVIF, JPEG2000, LZW/deflate TIFF and multipage TIFF round trips passed. Font, color-management, text-layout, XCB and Tk codec features remain available. The new ACL no-follow API rejects a symlink without changing its target; GNU tar preserves ACLs through archive/restore.
- Native LMS PDF/DOCX/PPTX, image, browser slide capture, narration encoding, clip concatenation and fMP4 HLS checks passed offline with synthetic inputs and no live mounts or credentials. The font-request substitution remains a test fixture.
- Affected application tests: **27 passed, one existing slide-layout failure**. The same previously recorded test expects three slides and receives four; it remains a release gate. Initial test-harness missing imports were corrected before the final run.
- Application import and `/health` passed without lifespan. Full PostgreSQL startup, actual Hub authentication and full course workflows remain pending.

## Scanner results and remaining work

Both parent and new candidate were scanned against one frozen Trivy database updated `2026-10-07T00:53:05.111120428Z`, using pinned Trivy 0.75.0.

| Raw Ubuntu findings | Parent 16, refreshed | Candidate 17 |
| --- | ---: | ---: |
| Critical / High | 0 / 0 | 0 / 0 |
| Medium / Low | 28 / 12 | 28 / 12 |
| Total | 40 | 40 |

No raw package-advisory pairs were introduced or removed. The database refresh adds three Medium occurrences to the prior 37 on **both** images: one FreeType and two Poppler advisories. The inherited High fixes rely on reviewed component/patch evidence; their original severity differs from Ubuntu's coverage and ratings. Equal raw totals do not invalidate the verified patches, and zero raw High does not close the seven unresolved inherited High reviews. Four raw matches have reviewed upstream fixes/patches; 36 remain open in the current register. Raw reports remain unsuppressed.

Remaining inherited High reviews: **cJSON (5), librsvg (1), libsndfile (1)**. Distribution paths are absent, but that alone cannot prove absence inside stripped or bundled native code. A bounded screen of 980 native ELF files found no component fingerprints; one embedded wheel SBOM also lists none of those families. Stripped/static code and incomplete manifests prevent treating that screen as definitive absence. These seven rows retain `OPEN_SOURCE_ABSENT_BUNDLE_REVIEW`; no speculative upgrades or false closure were applied. Next work is component provenance for those native bundles, then the remaining Medium families, starting with supported distribution fixes.

Raw CycloneDX contains 406 components; enriched inventory contains 407 including manual FFmpeg provenance and the reviewed parser/X patches. Reference integrity passed; this is not full schema, licence or native-code coverage validation. Archive hashes match preserved Debian source descriptors where available; descriptor signatures were not independently verified. CPython's source hash was computed from its official HTTPS download.

All three live LMS application containers remain healthy on their original image IDs. No database access, service restart, UAT deployment, commit or push occurred. Source-built packages and pinned patches require ongoing maintenance. Full rebuild, existing layout failure, full-stack checks and remaining risk review still block release.

See the [inherited register](sbom-lms-backend-inherited-round4-2026-10-07.csv), [current scanner register](sbom-lms-backend-current-round4-2026-10-07.csv), and [candidate manifest](sbom-lms-candidate-manifest-2026-10-07.json). VM evidence: `/home/karphi/lms-security/evidence/backend-parsers-candidate-20261007-17`; local copy: `tmp/security-20261007/backend-parsers-candidate-20261007-17`.
