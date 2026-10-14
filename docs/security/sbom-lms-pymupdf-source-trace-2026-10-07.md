# PyMuPDF / MuPDF public source trace — 7 October 2026

The recorded PyMuPDF source commit is public, and the embedded 1.29.0 version is consistent with public MuPDF development source from the wheel's build period. Exact compiled-source identity remains open; no advisory is closed and no dependency is replaced.

## Evidence and correction

The earlier query used the old `ArtifexSoftware/PyMuPDF` repository. The correct [PyMuPDF commit](https://github.com/pymupdf/PyMuPDF/commit/e9cdfc9e7fe3260efcc9d28713903f075ab05bce) exists in `pymupdf/PyMuPDF`. Its `setup.py` SHA-256 is `99302528d6dd4bb62dc79bf463a3ce9166139a10d88cceb1a7c1f238f639dce5`, identical to the independently verified PyPI source archive's setup. The release default selects MuPDF 1.28.0, but the build API explicitly permits a different local checkout.

The wheel was uploaded on 29 June 2026 at 09:04:19 UTC. [MuPDF commit baaa3b2](https://github.com/ArtifexSoftware/mupdf/commit/baaa3b237ad85c6afcb23dc3e4b827a3bfb0a0cb) changed the development version on 26 June at 08:52:51 UTC. Its version header matches the published wheel exactly. This explains how public development source can report 1.29.0 before a release tag exists; it does not select an exact compiled revision.

| Check | Result |
| --- | --- |
| PyMuPDF recorded source commit | Public, exact setup matches verified source distribution |
| Wheel MuPDF version header | Exact byte match to public development header |
| Bundled headers compared with public MuPDF revision `39101dd8179599d5b9653e7a33f157c08e5614eb` | 84 of 90 match Git blob identities; the other six are generated C++ headers absent from that tree |
| Published wheel payload check from previous step | All 114 hashed payload files match installed candidate |
| Source-tree target-family path search | No cJSON/librsvg/libsndfile path hits at this level; transitive source/build coverage is incomplete |
| Publication-period Artifex aptest configuration | Public; release test selects a mutable `1.28.x` branch. Context only, not proven to be the wheel's build |
| Public build artifacts for that contextual run | Zero returned; unauthenticated job-log request returns HTTP 403 |
| Exact compiled MuPDF revision / generated bindings / transitive inputs | Open |

The wheel metadata records a local `aptest-git-mupdf` path, with no MuPDF commit hash. Header equivalence and a successful neighboring CI run cannot authenticate compiled machine code. No PyPI build attestation was retrieved in the previous step. The six inherited High assessments therefore remain open. Earlier raw queries and the original enriched SBOM are preserved; `backend.provenance-corrected.cdx.json` adds corrected provenance wording without changing components, hashes, versions or findings.

## Replacement build approach

If exact build inputs cannot be recovered, build a reviewable replacement in isolation:

1. Select a supported PyMuPDF/MuPDF source pair after checking current upstream advisories and the application's PDF extraction requirements. Do not automatically substitute 1.28.0 for the installed development engine.
2. Pin source archive hashes or immutable commits, every MuPDF submodule, toolchain/container digest and Python build dependencies. Reject mutable branches and source downloads without verified hashes. Preserve the source dependency inventory, compiler/configuration records, generated bindings and resulting wheel hashes.
3. Build the wheel with a local pinned MuPDF source directory through `PYMUPDF_SETUP_MUPDF_BUILD`. Test engine/binding versions, dependency linkage, PDF text and image extraction, malformed inputs, document conversion and the real LMS course flow.
4. Review the changed native files, update the native lock, build one backend candidate and scan it with a recorded database. Assess each advisory against its compiled inputs before closing any finding.

This is a prepared approach, not a tested replacement recipe or a claim of a fix. The VM capacity check reports 2.7 GiB free and 99% disk usage. A source build and new image require additional capacity first; no shared image, volume or cache was pruned. PostgreSQL remains deferred. No deployment or restart occurred.

Evidence is under `tmp/security-20261007/pymupdf-source-trace`, with checksum inventory and public API responses. The candidate remains `lms-sbom-backend:candidate-20261007-25`, image `sha256:0c799be7d178d617340cd8dd0edb339a1dbd1180581e434b29a9a4ca7ceeef45`.
