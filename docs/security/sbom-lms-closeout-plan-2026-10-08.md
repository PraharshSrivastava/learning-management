# LMS SBOM closeout status and release plan — 8 October 2026

Recommendation: proceed with release preparation and controlled big-coding validation. A zero-finding target is not required to prepare a release. UAT release remains conditional on tested artifacts, assessed residual risks and the organization's required approvals. No blanket risk acceptance or release approval has been made.

## Verified counts

These are package/advisory occurrences, not distinct vulnerabilities. The reviewed evidence is dated 7 October; this is not a fresh 8 October runtime scan.

| Component / register | Tracked baseline | Addressed or removed | Remaining |
| --- | ---: | ---: | ---: |
| Backend inherited register | 829 | 568 | 261 |
| Trainer frontend OS inventory | 22 | 22 | 0 detected in tested runtime candidate |
| Employee frontend OS inventory | 22 | 22 | 0 detected in tested runtime candidate |
| Active tracked scope | 873 | 612 | 261 |

Backend addressed breakdown: **1 Critical, 224 High, 266 Medium and 77 Low**. Of the 568 addressed entries, 491 have version/security patch evidence, nine exclude vulnerable code, 28 have verified component removal/absence, and 40 have exact-version/architecture not-affected evidence. The 40 remaining Medium entries cover 13 source families; review these in batches.

Backend's 261 open entries are **0 Critical, 6 High, 40 Medium, 195 Low and 20 Unknown**. The six High entries are unresolved native/bundled-code coverage reviews for cJSON (four), librsvg (one) and libsndfile (one). An affected private copy has not been confirmed; lack of a detected fingerprint is not conclusive absence evidence.

The backend originally scanned at 879 occurrences. An early comparable stage removed 50 (879 → 829). Later database refreshes added and removed records, including 114 LibreOffice Unknown matches in an intermediate snapshot. The 568 count is reconciled against the retained 829-row register; do not present one grand subtraction across database snapshots or describe every addressed row as a software patch. Closures also include verified component removal and exact-version applicability evidence.

The current backend raw scan is a different view: **27 Medium and 12 Low, no detected Critical/High**. Its explicit assessment leaves **15 Medium and 12 Low open**. Do not add this total to the inherited 261, or use it to erase the six historical coverage reviews. Both views must stay in the release evidence.

PostgreSQL remains deferred by instruction. Earlier scans went 546 → 342 → 296; the last preserved candidate has 1 Critical, 61 High, 103 Medium, 125 Low and 6 Unknown. It is excluded from the active total and has not been selected for release. Deployment scope must explicitly state this database exception; a frontend/backend closeout is not a whole-platform security clearance.

## Latest PDF source work

Reviewed and hash-pinned PyMuPDF 1.28.2 and MuPDF 1.28.5. The MuPDF archive contains 8,013 files: 1,427 main-tree files match the pinned public revision, 6,559 bundled dependency files match their pinned submodule trees, and 27 curl Windows solution files match after CRLF normalization. An optional nested FreeType dlg gitlink is recorded separately and is absent from the archive.

Commit-level OSV review identified two FreeType issues and one zlib issue. Three exact upstream patches apply with source preimage hashes and zero fuzz. This is source-change evidence, not three additional closures. The zlib upstream patch text names CVE-2026-85091; the consulted CVE-2026-76844 record also references that same fix. Preserve this advisory mapping distinction.

The isolated build failed during generated PyMuPDF wrapper compilation (`PyString_FromString` not declared). PDF compatibility and the prepared FreeType sanitizer regression have not run. No successful wheel or accepted replacement backend candidate exists. Build recipes, tool locks, patches and failure logs are preserved. The local failed-build evidence archive matches VM SHA-256 `ae639a95dcc0e0f84d38e7707bc163bb9789e660c4b4529dd4654158bb68da6e`; its applied-patch manifest contains three entries and its final exit code is 1. The previous VM action interruption was an automatic approval-review usage-limit failure, not a finding that the action was unsafe; the resumed read-only status check succeeded normally.

The disk cleanup removed the earlier isolated backend, trainer and employee candidate images (confirmed by exact image-ID queries on 8 October). Do not rely on a historical tag being available. The current VM has about 80 GiB free. Source changes remain uncommitted; this SBOM work has not deployed or restarted application/database services.

## Release decision

Proceed now with preparation, residual-risk review and isolated functional testing. Do not wait indefinitely for all Low/Medium findings or every provenance uncertainty to disappear.

A release blocker is a confirmed exploitable issue on a reachable LMS path with unacceptable impact, a failed essential workflow, or an unmet organizational release policy. Check known exploitation, reachability, authentication requirements, uploaded-document handling and existing controls before prioritizing. Unknown coverage is uncertainty that needs an owner and disposition, not an automatic safe/not-affected conclusion.

For a deferrable finding, record the exact release artifact, package/CVE, applicability evidence, exposure, mitigation, owner, approving authority and review/expiry date. Use a draft 30-day review interval for High coverage gaps and 90 days for lower-risk backlog entries only if the responsible owner accepts those intervals. Risk acceptance does not convert an open finding into a fixed finding. The generated residual review CSV has **PENDING; NOT_ACCEPTED** decisions throughout.

This approach follows risk-based prioritization and mitigation principles in [NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final) and [CISA's SSVC guide](https://www.cisa.gov/sites/default/files/publications/cisa-ssvc-guide%20508c.pdf). These references are guidance; they do not approve this LMS release or override company policy.

## Operations plan

| Step | Work | Completion evidence |
| --- | --- | --- |
| 1. Freeze and triage | Select the release scope; reconcile inherited/current records; group residual issues by source family; decide whether the optional PDF source build belongs in this release. Avoid more broad custom rebuilds unless they address a confirmed release blocker. | Reviewed risk register, owned actions and dated exceptions where required; PostgreSQL explicitly deferred |
| 2. Rebuild final artifacts | Build the full maintained backend and both frontends from a recorded commit and reviewed source inputs. If the PDF source change is included, resolve its wrapper build and pass compatibility/patch regressions first. Review native lock changes; preserve rollback artifacts. | Successful complete builds, exact image digests, source hashes, dependency locks and build logs |
| 3. Scan and package evidence | Scan final image digests using the same recorded database; refresh SBOMs; validate schema and licence data; record compiled/native coverage limits. Check all raw Critical/High matches and inherited High reviews. | Final image-linked SBOMs, raw scans, explicit assessments and no silent suppressions |
| 4. Validate on big-coding | Run isolated full-stack checks with synthetic data, then real Hub trainer/employee login, course creation/assignment, PDF/image extraction, slides, video/audio, HLS playback and SMTP behavior. Resolve the known slide-layout mismatch and browser widget-test gap or document a justified non-blocking disposition. | Passed essential user workflows, logs/screenshots and regression results; no unresolved essential failure |
| 5. Review and release to UAT | Prepare a focused PR/release bundle. Obtain any required residual-risk and UAT deployment decisions. Transfer/promote the tested images to 10.204.6.139 and verify their digests; a separate rebuild after `git pull main` must not be assumed identical. Keep PostgreSQL deployment unchanged in this scoped release. | Recorded release decision, deployment/rollback instructions, matched running digests and UAT smoke results |
| 6. Maintain after release | Set up scan checks for releases and a weekly review, prevent new unacceptable Critical/High findings, review exception expiry and remediate lower-priority families in batches. Schedule automations only when explicitly requested. | Maintained SBOM, owned backlog and completed recurring review records |

The next practical operation is Step 1: finalize the residual-risk register and release scope, then build one final reviewed set of images. This replaces an open-ended zero-finding chase with measurable release gates.
