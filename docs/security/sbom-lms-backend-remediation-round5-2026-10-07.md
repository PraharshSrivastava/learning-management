# Backend SBOM remediation, round 5 — 7 October 2026

**Verified result:** one of the seven inherited High occurrences and 38 of the 97 inherited Medium occurrences are addressed. **Six High and 59 Medium remain unresolved.** All 829 tracked inherited rows are retained: 549 addressed, 280 open (6 High, 59 Medium, 195 Low, 20 Unknown; 0 Critical). Counts are package-advisory occurrences, not unique CVEs. This does not claim that all requested findings are fixed.

| Register | Before | Selected candidate | Change |
| --- | ---: | ---: | ---: |
| Inherited High | 7 | 6 | 1 verified architecture exclusion |
| Inherited Medium | 97 | 59 | 38 fixes/applicability verifications |
| Raw detected Critical / High | 0 / 0 | 0 / 0 | No new detected priority findings |
| Raw detected Medium / Low | 28 / 12 | 27 / 12 | 1 Medium scanner occurrence removed |

Raw 39 occurrences include eight previously/now verified patch or component-absence assessments, leaving **19 Medium and 12 Low current vendor matches open**. Raw scan totals and the inherited register measure different sets. Database updated `2026-10-07T00:53:05.111120428Z`; parent 17 and candidate 21 used the same pinned Trivy 0.75.0 and byte-identical database metadata. The parent scan was reused after that identity check. No scanner ignores or suppression rules were added.

## What changed

| Work | Inherited Medium occurrences | Evidence |
| --- | ---: | --- |
| X11 and XInput upstream bounds-check patches | 16 | Pinned MR310/MR23 patches, same SONAME/exports, upstream tests and headless browser/document checks |
| FreeType supported Ubuntu security update | 1 | 2.14.2+dfsg-1ubuntu0.2, matching the listed fix; shared Pillow/font checks |
| Expat allocation-overflow backport | 1 | Commit 69edbec with SIZE_MAX regression test; system/Python shared linkage preserved |
| p11-kit upstream 0.26.5 | 2 | Same shared-library ABI, 1078 upstream subtests pass/3 skip/0 fail; Ubuntu PKCS#11 paths explicitly preserved |
| Existing TIFF 4.7.2 and CUPS 2.4.16 fixes verified | 3 | Specific upstream fixed-version evidence, not additional package upgrades |
| Avahi daemon/core, ACL tools and ALSA topology absent | 15 | Twelve Avahi rows concern daemon/simple-protocol or core/browse code; only client/common libraries ship. Recursive setfacl/chacl tools and separate libatopology decoder are absent |

The single High closure is **CVE-2026-16554**, whose [CERT Polska advisory](https://cert.pl/en/posts/2026/07/CVE-2026-16554/) identifies a 32-bit size_t overflow. Runtime size_t is 64-bit and 1308 inventoried ELF files are 64-bit. No cJSON patch/upgrade is claimed.

The other six High rows are cJSON 29036/67215/67216/87933, librsvg 96889 and libsndfile 37555 (CVE-2026 identifiers). Their original OS packages/shared libraries are absent; the whole-runtime dynamic dependency audit found no references and FFmpeg's librsvg decoder is disabled. A build guard prevents these components returning. **These rows stay open because stripped/static/private copies are not fully attributable.** Fingerprint absence or a missing scanner match is insufficient to close that gap.

Zlib 85091 stays open: Canonical records this exact Ubuntu version under investigation and notes contradictory affected-range/reproducer evidence. The initially proposed version-based closure was rejected. GStreamer 85150 must be reviewed as RTSP Digest parsing: fresh primary evidence does not support a volume-plugin exclusion. No speculative zlib/GStreamer patch or applicability closure was made.

## Verification and limits

Selected tag: `lms-sbom-backend:candidate-20261007-21`.

Image ID: `sha256:602027e10b4d031e80d63c22ef1445ce706c0bcea57a281af981619da8f8aa21`.

Native parser, font/image codec, ACL, DOCX/PPTX/PDF, browser capture, narration, clip concatenation and fMP4 HLS checks passed offline. The affected application suite has 27 passes and the same known slide-layout failure as the parent. Application import and /health passed without lifespan/database startup. 102 application Python/shell hashes match parent 17. Shared-library exports, SONAMEs, apt dependencies and dpkg audit passed. PKCS#11 hardware and real TLS endpoints were not exercised. Three p11-kit upstream subtests were skipped by its suite; no hardware coverage is claimed.

Source archives and patches are SHA-256 pinned. Debian source-descriptor/release signatures were not independently authenticated. Custom maintenance packages remain operator-supported. Raw CycloneDX 406 components and enriched 407 components were parsed and reference-checked; full schema/licence validation remains pending. Full repository rebuild, the known layout failure, real Hub/course flows and full-stack startup remain release gates. Candidate checks inherit the unchanged parent application; they do not verify a fresh full checkout build.

Live backend, trainer frontend, employee frontend and PostgreSQL retain their original image IDs and healthy state. **No commit, push, deployment, restart or PostgreSQL fix was performed.** VM disk availability was 16 GiB at the capacity check; no shared cache/image/volume pruning was performed.

## Remaining priority work by family

The [remaining-family register](sbom-lms-backend-remaining-round 5-2026-10-07.csv) records all 65 remaining priority occurrences and concrete next actions. Some need supported updates/backports; others have no accepted fix, conflicting vendor evidence or missing native provenance. These are not all 97 independent code bugs and cannot safely be cleared through one blind upgrade.

| Source family | High | Medium |
| --- | ---: | ---: |
| cjson | 4 | 1 |
| libsndfile | 1 | 3 |
| librsvg | 1 | 0 |
| gcc-14 | 0 | 12 |
| glibc | 0 | 10 |
| gnupg2 | 0 | 7 |
| poppler | 0 | 6 |
| alsa-lib | 0 | 4 |
| gdk-pixbuf | 0 | 4 |
| libusb-1.0 | 0 | 2 |
| openjpeg2 | 0 | 2 |
| tar | 0 | 2 |
| cups | 0 | 1 |
| expat | 0 | 1 |
| glib2.0 | 0 | 1 |
| gst-plugins-base1.0 | 0 | 1 |
| jpeg-xl | 0 | 1 |
| zlib | 0 | 1 |

Backend remains the active scope; trainer/employee frontend work follows it. PostgreSQL stays deferred by the user. See the [inherited register](sbom-lms-backend-inherited-round 5-2026-10-07.csv), [current vendor register](sbom-lms-backend-current-round 5-2026-10-07.csv), and [candidate manifest](sbom-lms-candidate-manifest-2026-10-07.json).

VM evidence: `/home/karphi/lms-security/evidence/backend-medium-candidate-20261007-21`. Local evidence: `tmp/security-20261007/backend-medium-candidate-20261007-21`. All 65 downloaded evidence-file hashes were verified before report generation. The final reproduction script corrects the baseline-path substitution that stopped the consolidated wrapper before scanning; the checks had passed, and the final scan/SBOM/reconciliation then ran explicitly against the verified baseline/database.
