# Backend Medium remediation, round 6 — 7 October 2026

**Verified result: 17 inherited Medium occurrences addressed by code backports, plus two verified nscd component-absence assessments. The inherited Medium backlog is 59 → 40. Six High remain open; zero inherited Critical remain. The full Medium backlog is not resolved.**

All 829 inherited rows are preserved: 568 addressed and 261 open (6 High, 40 Medium, 195 Low, 20 Unknown). Counts are package/advisory occurrences, not unique CVEs. Closures include applicability evidence as well as code changes; do not call all 568 software patches.

| Source family | Newly addressed inherited Medium occurrences | Change |
| --- | ---: | --- |
| GnuPG | 7 | Fail-closed truncation guard in both gpg and gpgv; existing Ubuntu patches retained |
| ALSA | 4 | Upstream ctlparse bound fix and narrow pre-allocation binding checks |
| Poppler | 4 | Four accepted upstream bounds/bitmap/overflow backports; SONAME 156 and every vendor export retained |
| CUPS | 1 | Accepted fixed-width UTF-32 type fix on exact Ubuntu source |
| GStreamer | 1 | Fixed 1.28.7 RTSP parser length handling backported to 1.28.2 |
| glibc / nscd | 2 | Required nscd service/package/executable absent; no glibc upgrade claimed |

Selected candidate: `lms-sbom-backend:candidate-20261007-24`.
Image ID: `sha256:8a7cf064b26ead5b381d7a1ebf478a010780e1d42739df4c3c476e8d6659ed04`.

Raw current severity: `{'MEDIUM': 27, 'LOW': 12}`. After explicit patch/component assessments, current open severity is `{'MEDIUM': 15, 'LOW': 12}`. This raw current scan and the inherited historical register track different sets. Both remain visible; no Trivy ignores or suppression rules were added. Parent21 and candidate24 use byte-identical database metadata and the same pinned Trivy 0.75.0 image. See the [current register](sbom-lms-backend-current-round6-2026-10-07.csv) and [inherited register](sbom-lms-backend-inherited-round6-2026-10-07.csv).

## Verification

- Both old GnuPG verifiers accepted forged synthetic cleartext signatures. Both patched verifiers reject all 12 boundary-input cases and accept valid normal/form-feed signatures; binary detached-signature control passes. Keys were generated offline in disposable containers and removed. The operator guard also rejects legitimate cleartext lines reaching the existing truncation limit; no upstream release fix is claimed.
- The same RTSP fixture crashes parent21 with exit 139 and passes six malformed/valid Digest and Basic cases on candidate24.
- Actual ALSA entry points reject negative, out-of-range and sparse bindings. Long ctlparse inputs do not crash; this is not an ASAN proof. The pinned upstream source change supplies the bound fix.
- CUPS guard-page regression and Unicode conversions pass. Fixed-width UTF-32 parameters intentionally change element width; retained SONAME/exports alone are not universal caller compatibility. Printing/hardware callers were not tested.
- All replaced shared-library SONAMEs and vendor exports are retained; apt dependencies and dpkg audit pass. Poppler's five optimization-dependent vendor C++ object/typeinfo exports were retained using real matching-compiler objects, without stubs or weakening the export check.
- Parser, font/image codec, PKCS#11 path/GnuTLS initialization and actual DOCX/PPTX/PDF, browser capture, narration, clip concatenation and fMP4 HLS checks pass. Exact upstream Poppler exploit corpus was not available; accepted patch identity, build/ABI checks and document behavior were verified.
- Affected application suite: 27 passed, one known slide-layout failure (expects three slides, gets four), previously reproduced on the parent. Import and /health pass without lifespan/database startup. All 102 recorded parent application file hashes match.
- Raw/enriched CycloneDX documents were parsed and reference-checked; enriched inventory contains 407 components. Full schema/licence validation remains pending.
- All 68 synchronized VM evidence files match their local SHA-256 checksums.

The earlier approval-review usage-limit interruption stopped the subsequent status check. Validation was resumed through normal approval. Its initial setup retry stopped on an inaccessible working directory before tests; the wrapper now sets an accessible working directory. SBOM export initially failed because the restricted scanner container could not write into the evidence owner's directory; export was completed using that owner's UID, and the wrapper was corrected. Passed checks and the completed scan were preserved. Failed builds and their diagnostics remain evidence, not successful validations.

## Remaining Medium backlog

| Group | Medium occurrences | Why still open |
| --- | ---: | --- |
| GCC historical source/caller mapping | 12 | Current GCC source name/version alone does not prove old compiled/header code fixed |
| glibc, excluding absent nscd | 8 | Four advisories require a coherent supported update or carefully tested vendor-source backports |
| cJSON, libsndfile, GDK Pixbuf, libusb, JPEG XL | 11 | Original OS components absent; unidentified static/private copies remain a coverage gap |
| Poppler, OpenJPEG, tar, Expat, GLib, zlib | 9 | No accepted fix or conflicting/incomplete vendor evidence for these specific advisories |

The [remaining-family register](sbom-lms-backend-remaining-round6-2026-10-07.csv) retains exact advisories and next actions. For example, current primary records still mark [Poppler 93311](https://security-tracker.debian.org/tracker/CVE-2026-93311), [Poppler 93653](https://security-tracker.debian.org/tracker/CVE-2026-93653), [Expat 66382](https://security-tracker.debian.org/tracker/CVE-2025-66382) and [GLib 86469](https://security-tracker.debian.org/tracker/CVE-2026-86469) unfixed. These are not cleared by the unrelated patches in this batch.

## Release limits and evidence

All four live containers are healthy. Image identities differ from the round5 snapshot: `True`; the backend and frontend identities changed outside this candidate-validation sequence, while PostgreSQL retains its recorded identity. A read-only live backend check shows Debian 13.7 and the older GnuPG/ALSA/CUPS/GStreamer packages, so these native candidate fixes are not deployed. No deployment, restart, commit, push or PostgreSQL operation was performed by this work. Do not apply this candidate's scan totals to the changed live images. This is an incremental candidate; a full current-checkout build, full-stack startup, real Hub/course workflows, rollback preparation and release remain open gates. Source archives/patches are hash pinned, but source-signature authentication and full native provenance are not universally complete. Custom maintenance packages require ongoing operator support.

VM evidence: `/home/karphi/lms-security/evidence/backend-medium-candidate-20261007-24`.
Local evidence: `tmp/security-20261007/backend-medium-candidate-20261007-24`.
Pinned advisory index: 49 downloaded records at Canonical commit `4c7a64a3ea1d4a49de81b7adf3247e7bce76d822`. Patch/source notes: [native maintenance README](../../backend/security/README.md).
