# LMS SBOM progress summary

Historical snapshot. See the [6 October remediation update](sbom-lms-remediation-2026-10-06.md) for the refreshed comparisons, completed frontend candidates, further PostgreSQL remediation and open release risks.

As of 5 October 2026, tested security candidates are prepared for the backend and PostgreSQL. Live LMS and UAT deployments are unchanged. Work is on local branch `codex/lms-sbom-remediation`; security changes are not yet committed, pushed, or released.

An SBOM (Software Bill of Materials) is an inventory of the software components and versions in an artifact. Comparing that inventory with vulnerability advisories helps identify affected dependencies, select fixes, and track the result. It also supports licence review and release traceability. An inventory alone does not fix vulnerabilities or verify authentication/business logic.

## What we completed

1. Reviewed the supplied LMS workbook and established a stepwise implementation plan. Kept historical spreadsheet results separate from fresh image scans.
2. Identified running container images and package versions on big-coding. Found deployment drift: running frontend/PostgreSQL versions differed from repository definitions, and frontend image files were unavailable in the local image store. Documented exact running identifiers instead of assuming `main` represented the deployed artifacts.
3. Established fresh backend/PostgreSQL image baselines and OS-only inventories of both running frontends with a digest-pinned Trivy scanner. Saved reports, image identities, and advisory DB metadata outside the application repository on the VM.
4. Updated backend urllib3 to 2.8.0 with regenerated dependency hashes; upgraded installed PCRE2/OpenSSL packages. Added hash-locked pip 26.2.1 for build-time installation and removed build-only pip afterwards to avoid shipping its vulnerable bundled dependencies.
5. Tested PostgreSQL 16.15 from the existing pinned repository definition, then added a derivative Dockerfile with supported PCRE2/OpenSSL distribution updates. Preserved upstream database startup and privilege-switching behavior.
6. Verified backend functions and synthetic database operations in isolated containers. Preserved live data and cleaned up temporary database resources.
7. Assessed the exact gosu binary using official Go vulnerability analysis. All 46 Trivy gosu advisories mapped to Go database entries without affected symbol matches. Kept scanner findings visible and recorded the analysis limits.
8. Exported CycloneDX inventories for the tested backend and PostgreSQL candidates: 500 and 148 detected components. Recorded image-linked evidence and local copies. These are candidate inventories, with coverage/licence-normalization limitations.

## Verified scanner results

| Component | Original findings | Tested candidate findings | Removed | Critical, original → candidate |
| --- | ---: | ---: | ---: | --- |
| Backend | 879 | 829 | 50 | 1 → 1 |
| PostgreSQL | 546 | 342 | 204 | 14 → 2 |
| Trainer frontend, OS only | 22 | Not yet tested | — | 0 → pending |
| Employee frontend, OS only | 22 | Not yet tested | — | 0 → pending |

Backend/PostgreSQL candidates removed 254 package/advisory occurrences in total, with no added advisory matches in comparable scans. These are not counts of distinct exploitable vulnerabilities, and the reductions are not deployed yet. Each frontend still has four high OpenSSL occurrences in its captured OS inventory.

## Validation completed

- 22 existing local tests covering TTS configuration, thumbnail fallback, directory sync, and Langfuse tracing.
- Backend dependency consistency during build; HTTP chunked/gzip handling, HTTPS trust acceptance/rejection, PDF extraction, Chromium rendering, and both system/bundled FFmpeg encoders in offline candidate containers.
- PostgreSQL startup, privilege switching, LMS schema initialization twice, pooled reads/writes, advisory locking, transaction rollback, restart persistence, and custom-format synthetic dump/restore.
- Source hashes, image identities, unchanged advisory DB comparisons, preserved PostgreSQL image startup configuration, and cleanup checks.

These tests do not replace real provider/proxy checks, existing-data migration rehearsal, Hub login, or end-to-end UI/course-generation validation.

## What remains

1. Build/scan/test trainer and employee frontend candidates, including Dart dependency coverage.
2. Finish browser/media binary vulnerability coverage, configuration review, and licence assessment, including PyMuPDF entitlement and unnormalized licence expressions.
3. Assess libxml2 exposure/mitigations and monitor supported fixes. Its critical finding remains in both backend and PostgreSQL. PostgreSQL's additional critical Go-runtime finding has no affected symbol match in the tested gosu binary; it remains in raw reports and requires explicit release risk handling.
4. Run an isolated full-stack test through Hub: trainer/employee login, document upload, course/media generation, assignment, and progress workflows.
5. Rehearse backup/restore with appropriate existing-data safeguards, prepare a rollback procedure, and release the exact tested image artifacts. Generate final image-linked SBOMs, then validate big-coding and UAT deployments.
6. Establish a repeatable release scan/report workflow and regular advisory refresh process. No scheduled automation has been created.

The practical improvements so far are a verified inventory, evidence of deployment drift, fewer reported vulnerable packages in tested candidates, checks against breaking core functions, and traceable evidence for release decisions. Live-system security improvements begin when validated artifacts are deployed.

See `sbom-lms-baseline-2026-10-05.md` for exact hashes, reports, findings, and limits, and `sbom-lms-implementation-plan.md` for the remaining phase exit checks.
