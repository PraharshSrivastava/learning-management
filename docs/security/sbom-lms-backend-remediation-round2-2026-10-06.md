# LMS backend native remediation — 6 October 2026

Historical round-two record. The selected candidate and current backlog are now in [round three](sbom-lms-backend-remediation-round3-2026-10-06.md); the results below are preserved as originally assessed.

State: isolated candidate tested; **not deployed**. PostgreSQL remains deferred. This supersedes the backend candidate selection in the [first remediation snapshot](sbom-lms-remediation-2026-10-06.md); its historical counts remain valid for that earlier artifact.

## Changes and purpose

The previous backend candidate had 829 reported package/advisory occurrences: 1 Critical, 230 High, 306 Medium, 272 Low and 20 Unknown. Its saved scan did not list available fixes. We grouped the shared native libraries, checked upstream evidence and tested one coherent replacement build instead of attempting hundreds of unrelated package changes.

The replacement uses pinned Ubuntu 26.04 runtime libraries and the existing pinned CPython 3.12.14 installation. Debian OS shared libraries are not copied into Ubuntu. This change was needed to preserve the newer XML library interface used by LibreOffice; replacing Debian's older XML interface directly would break compatibility.

| Component | Verified candidate | Purpose |
| --- | --- | --- |
| System libxml2 and lxml's XML dependency | libxml2 2.15.4; source-built lxml 6.1.3 | Address the critical XML issue and other reviewed XML advisories, including the separately bundled older wheel library |
| FFmpeg and ffprobe | 9.0.2, restricted build | Address reviewed upstream media fixes; retain LMS PNG/WAV → H.264/AAC MP4 → concatenation/HLS |
| DVD subtitle and MPEG-PS support | Disabled; configuration, archive symbols and installed decoder list checked | Exclude the code associated with CVE-2026-6385, which lacks an upstream version fix |
| PCRE2 | 10.49 with JIT and compatible exports | Preserve previous regex fixes and the reviewed upstream fix thresholds |
| libpng | 1.6.59 | Prevent the new base from reintroducing CVE-2026-46675; the exact source archive announcement confirms this fix |
| Standard file utilities | Ubuntu's GNU coreutils replacement | Remove unnecessary rust-coreutils and its 20 reported Medium occurrences while retaining normal utilities |
| Python, HTTP client and browser | CPython 3.12.14, urllib3 2.8.0, Chromium 153.0.8010.12 | Retain the earlier batch's tested dependency updates; pip and the older imageio FFmpeg executable stay removed from runtime |

Native source archives have SHA-256 verification in the Dockerfile. FFmpeg's archive was additionally checked against the upstream signing key before its hash was selected. The XML, PCRE2 and PNG builds run upstream tests and retain compatible exported symbols; missing symbols stop the build. Candidate smoke checks load the actual installed libraries. Licences and configuration evidence are retained.

## Results and accounting

Final image identity, report hashes and counts are recorded in the [candidate manifest](sbom-lms-candidate-manifest-2026-10-06.json). Detailed inherited assessments are in [the occurrence register](sbom-lms-backend-inherited-round2-2026-10-06.csv).

The final raw scan reports **0 Critical, 0 High, 24 Medium and 14 Low** occurrences. It uses the same pinned Trivy 0.75.0 and frozen database snapshot as the previous backend candidate. However, the OS changed from Debian to Ubuntu: vendor coverage and severity can differ. **829 → 38 is not a verified count of fixes.** The comparison tool now rejects cross-OS-family package comparisons.

We instead retained all 829 inherited occurrences and reconciled them with official Ubuntu VEX and preserved upstream evidence. Unknown, missing, under-investigation and absent-source/bundled-code cases stay open. A vendor “not affected” result is accepted only for the exact installed source version with a code-absence justification. Different statuses remain distinguishable from version fixes.

| Original priority | Original occurrences | Addressed with recorded evidence | Still open for review |
| --- | ---: | ---: | ---: |
| Critical | 1 | 1 | 0 |
| High | 230 | 169 | 61 |
| Medium | 306 | 209 | 97 |

The original priority backlog therefore has **379 addressed occurrences and 158 still open**. These counts include version fixes, verified code exclusion and applicable vendor not-affected evidence; they are not all software patches. The full inherited register also retains Low and Unknown occurrences. New raw Medium findings are a separate view and must not be added to inherited counts without deduplicating source/advisory identities.

Across all 829 inherited occurrences, the recorded dispositions are 282 upstream version fixes, 9 verified code exclusions, 126 vendor-confirmed fixed versions, and 39 exact-version vendor not-affected assessments: **456 addressed**. The **373 open** occurrences comprise 61 High, 97 Medium, 195 Low and 20 Unknown. The stricter exact-version rule intentionally retains uncertainties after changing a custom library. The preserved VEX batch covers 330 CVE IDs (320 downloaded, 10 missing); five non-CVE identifiers remain unqueried/open. Its commit is `a3f40224dd201a816b4725891b70d22f7809225f`.

Two raw Medium PCRE2 matches remain in the unsuppressed scanner report despite verified 10.49 and upstream fix evidence. The other 22 raw Medium occurrences need further patch/applicability review. No ignore file was added. Do not describe vendor under-investigation findings or absent package names as resolved.

The [current raw-finding register](sbom-lms-backend-current-round2-2026-10-06.csv) preserves all 38 matches with separate assessment fields. A check against the earlier batch's 41 removed OS occurrences confirms 39 OpenSSL occurrences through vendor fixed-version evidence and the upstream PCRE2/PNG fixes separately. Earlier urllib3 and installed-pip fixes remain verified by the final runtime checks.

The inherited High review starts with util-linux (36 occurrences), gnupg2 (7), cJSON (5, absent source needing bundled-code review), and the remaining document/X libraries. Ubuntu VEX does not establish their closure. Supported updates, isolated package removal or precise code/exposure evidence must be verified before changing their assessment. No vendor fix in a scan is a triage state, not an acceptance decision.

## Validation and limits

- The final candidate passes trusted/untrusted TLS, chunked gzip HTTP, PDF creation/extraction, headless Chromium rendering, DOCX/PPTX conversion with embedded images, narration speed changes, and the actual LMS slide capture → video encoding → concatenation → fMP4 HLS pipeline.
- Every CPython native extension resolves its shared libraries. Runtime libxml2, PCRE2 and libpng versions are asserted. Old FFmpeg shared libraries and wheel executable are absent. Non-root execution, no-new-privileges and empty effective capabilities are checked.
- The selected regression batch has **44 passed and 1 failed**. `test_splits_third_landscape_image_to_separate_slide` expects three slides but receives four; the same failure was reproduced on the earlier candidate. It remains an explicit release blocker. The application behavior and its test were not modified to make this batch pass.
- Tests run in disposable, resource-limited containers with networking disabled and no live storage or database mounts. A test fixture substitutes empty CSS for Google's external font request; this does not prove backend product-wide offline font support or real Hub authentication.
- The previously tested trainer and employee frontend candidates remain selected, each with zero detected runtime image matches. Their Flutter/native SDK coverage and unfinished widget/real Hub workflow checks remain documented in the first snapshot.
- Full Hub login, real course generation/playback and UAT validation remain pending. PostgreSQL was neither remediated nor tested in this batch. Live services were not restarted.

## Evidence and maintenance

VM evidence: `/home/karphi/lms-security/evidence/backend-patched-candidate-20261006-15`. Local evidence copy: ignored `tmp/security-20261006/backend-patched-candidate-20261006-15`. The manifest links the raw report, database snapshot, native inventory, source/input hashes and selected image ID. The complete application and script context is hash-checked against the local source.

The final evidence check verified 147 application/script context files and byte-identical Dockerfile/dependency-lock inputs. Final VM verification found all three live LMS application containers running healthy on their original image IDs. Root storage has 28 GiB free (90% used); no shared images, caches or volumes were pruned.

`backend.raw.cdx.json` is the unchanged scanner-generated SBOM. `backend.enriched.cdx.json` separately adds manually inventoried FFmpeg and identifies operator-built XML/PCRE2/PNG packages. Their automatic Ubuntu package classification does not make them official Ubuntu binaries. The enriched file is parsed and reference-checked; this is not full CycloneDX schema validation or complete native binary/advisory coverage.

The custom packages and restricted FFmpeg build require an explicit maintainer, upstream advisory monitoring, retained source/recipe/licences and repeatable compatibility checks. Only Linux amd64 was tested. Base digest and Python dependency hashes are pinned, but mutable APT repositories, browser downloads and build-isolation tooling prevent a claim of bit-for-bit reproducibility. Additional media formats require a deliberate build/configuration change and relevant tests.

The critical XML fix, native media updates and PNG regression fix are concrete candidate changes. Remaining inherited risks, the pre-existing test failure, full-stack validation and controlled deployment/rollback must be handled before reporting the deployed LMS as remediated. Findings close in each deployed environment only after verifying its running image identity.

## Primary evidence

- [libxml2 critical advisory and fix information](https://security-tracker.debian.org/tracker/CVE-2026-6653)
- [FFmpeg source-package advisory tracker](https://security-tracker.debian.org/tracker/source-package/ffmpeg) and [unfixed DVD subtitle issue](https://security-tracker.debian.org/tracker/CVE-2026-6385)
- [PCRE2 security support lifecycle](https://www.pcre2.org/project/support-lifecycle/) and [CVE-2026-103111](https://security-tracker.debian.org/tracker/CVE-2026-103111)
- [libpng 1.6.59 announcement](https://github.com/pnggroup/libpng/blob/v1.6.59/ANNOUNCE) and [CVE-2026-46675 tracker](https://security-tracker.debian.org/tracker/CVE-2026-46675)
- [Ubuntu VEX interpretation](https://documentation.ubuntu.com/security/security-updates/vex/)
- [Ubuntu GNU coreutils replacement instructions](https://ubuntu.com/server/docs/reference/other-tools/sudo-rs/)
