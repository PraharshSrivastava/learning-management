# Backend Priority 1 review — 7 October 2026

**Six inherited High findings remain open: cJSON four, librsvg one and libsndfile one. No affected private copy was confirmed and no advisory closure or software patch is claimed in this review.** The work adds native artifact attribution, a build-time identity guard, two previously unrecorded PDF engine components and a tested candidate. The inherited register remains 568 addressed / 261 open: 6 High, 40 Medium, 195 Low and 20 Unknown; zero inherited Critical.

Candidate25: `sha256:0c799be7d178d617340cd8dd0edb339a1dbd1180581e434b29a9a4ca7ceeef45`. Parent24: `sha256:8a7cf064b26ead5b381d7a1ebf478a010780e1d42739df4c3c476e8d6659ed04`. Both are isolated candidates, not deployed release evidence.

## What was verified

- 1,316 native files: 1,308 ELF files and eight static archives, in `/usr`, `/opt`, `/ms-playwright`, application code and scripts. Application storage, live mounts, `/proc` and credentials were excluded. No target-family fingerprint matches or inventory errors; no forbidden dynamic dependencies. All existing installed native RECORD/md5sum comparisons matched. Installed metadata checks are not independent authentication.
- Attribution: 1,155 files have dpkg owners, 55 Python distribution owners, 82 are copied/custom CPython runtime files, nine operator FFmpeg artifacts, 14 Playwright downloads and one unowned Ubuntu base helper (`/usr/bin/pebble`). An owner or assigned origin is not complete source/build provenance.
- All 1,316 native SHA-256 identities and 102 recorded application files are identical between parent24 and candidate25. Earlier patch/regression assessments therefore remain applicable to these unchanged files; previous application-suite results were not rerun or represented as new passes.
- The new identity guard records 69 Python/browser native artifacts. It rejects changed, missing and added native files. Four guard control cases and three synthetic archive fingerprint controls pass. The existing component-removal guard still verifies absent cJSON/rsvg/sndfile OS libraries and disabled FFmpeg librsvg decoding.
- Candidate25 document conversion, PDF extraction, browser capture, narration, concatenation, HLS, CPython library resolution, application import and /health checks pass. Health excludes lifespan/database startup; real Hub/course flows and the known slide-layout failure remain release gates.
- Pinned Trivy 0.75.0, byte-identical 7 October database metadata: raw 27 Medium / 12 Low, zero detected Critical/High; zero added or removed matches compared with parent24. Current evidence-based register remains 15 Medium / 12 Low open. This does not clear the six historical bundled-code High reviews.
- Raw CycloneDX 406 components preserved. Separate enriched inventory 409 components: prior native/FFmpeg annotations plus runtime-reported MuPDF 1.29.0 and PDFium 153.0.7999.0, with actual library hashes and dependency links. Reference checks pass; full schema/licence validation and engine advisory coverage remain open.

## Why High closure is still blocked

The original affected OS libraries are absent. Negative names/symbols/strings alone cannot establish absence of stripped, statically linked, renamed or runtime-loaded copies. Source dependency listings for Chromium 153.0.8010.12, Node 24.21.0 and the PDFium7999 branch contain no target-family names at the reviewed level, but do not prove complete transitive compiled contents. Branch/release listings are not binary build attestations. Proprietary browser components also lack complete public source provenance.

The exact installed PyMuPDF wheel reports PyMuPDF 1.28.0 with MuPDF 1.29.0. **Correction:** the earlier PyMuPDF commit query used the old `ArtifexSoftware/PyMuPDF` repository. Its recorded commit `e9cdfc9e7fe3260efcc9d28713903f075ab05bce` is public in `pymupdf/PyMuPDF`, and its setup matches the verified PyPI source distribution byte for byte. MuPDF's public development branch bumped its version to 1.29.0 on 26 June, before the wheel publication; its version header matches the wheel exactly. Eighty-four bundled headers match public MuPDF revision `39101dd8179599d5b9653e7a33f157c08e5614eb`; six generated headers have no corresponding source-tree entries. This is consistent with a development checkout, but does not authenticate the exact compiled engine revision or dependencies. The stable 1.28.0 source declaration and missing 1.29.0 release tag alone do not establish that source is unavailable. See the [source trace](sbom-lms-pymupdf-source-trace-2026-10-07.md).

Primary advisory review: [cJSON compare](https://security-tracker.debian.org/tracker/CVE-2026-67216), [cJSON merge patch](https://security-tracker.debian.org/tracker/CVE-2026-87933), [libsndfile disclosure](https://www.openwall.com/lists/oss-security/2026/04/30/7), [librsvg upstream fixes](https://gnome.pages.gitlab.gnome.org/librsvg/devel-docs/security.html). A supported librsvg fix does not repair an unidentified or absent private copy; installing these libraries solely to upgrade them would reintroduce unnecessary code.

## Concrete remaining actions

Follow-up: [exact PyMuPDF artifact verification](sbom-lms-pymupdf-origin-2026-10-07.md) confirms all 114 hashed payload files match the published PyPI wheel, including all five native files. The exact PyPI provenance endpoint has no available attestation. Artifact identity is verified; matching compiled-source/dependency provenance is still open.

1. Obtain or independently establish matching source/dependency/build evidence for exact downloaded artifacts, starting with the PyMuPDF embedded-version mismatch. Review transitive build inputs, not just top-level names. Record unchanged OS/native ownership separately from compiled-source authentication.
2. If matching evidence remains unavailable, prepare a source-controlled replacement build of the affected document/browser dependency on an independently reviewable, supported source revision. Check its advisories first; do not silently downgrade MuPDF to match a source archive. The latest VM capacity check has only 2.7 GiB free (99% used); larger source builds need capacity planning. No shared cache/image/volume pruning was performed.
3. Where an affected copy is identified, rebuild/replace the owning artifact once per family and run parser/document/browser/media and ABI tests. Close only the specific advisories supported by that evidence. Otherwise retain the coverage gap and owner/action in the register.
4. Rebuild the full current checkout, refresh the native identity lock after reviewing any changed artifacts, validate the full stack and real Hub workflows, and prepare exact-image release/rollback evidence. The guard baseline is not an automatic CVE acceptance and does not close any High finding.

## Scope and evidence

No deployment, restart, commit, push, PostgreSQL fix, frontend change or scanner suppression was performed. Live images were not rescanned by this batch. Source changes add the guard and lock to the final backend Dockerfile; only the matching small incremental layer was built, so full-checkout reproducibility is still pending.

The first guard build failed on Windows-generated directory separators. Scope was corrected to POSIX roots and includes the rebuilt Pillow/lxml files; positive candidate and negative controls then passed. Initial local controls stopped on a temporary-directory permission before assertions; they passed after using the writable workspace. The validation wrapper completed behavior checks then stopped on an incorrect database metadata path; export/scan completed separately after correcting the path. Failed attempts are retained and are not recorded as passes.

VM evidence: `/home/karphi/lms-security/evidence/backend-priority1-20261007`.
Local evidence: `tmp/security-20261007/backend-priority1-20261007`; source-query/download evidence under `tmp/security-20261007/priority1/sources`.

See [native attribution](sbom-lms-backend-native-attribution-2026-10-07.csv), [inherited assessments](sbom-lms-backend-inherited-priority1-2026-10-07.csv) and [current register](sbom-lms-backend-current-priority1-2026-10-07.csv). The six High rows retain their open assessments; this review makes the evidence gap more specific rather than changing the count.
