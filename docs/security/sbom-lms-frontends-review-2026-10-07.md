# Trainer and employee frontend security review — 7 October 2026

Both existing remediated candidates were rescanned and browser-tested. Each has **0 Critical, 0 High, 0 Medium and 0 other detected runtime vulnerability occurrences** in the refreshed Trivy report. No additional dependency change was required in this review. This is candidate evidence; the fixes have not been deployed.

| Component | Recorded original OS High / Medium | Refreshed candidate High / Medium | Candidate image ID |
| --- | --- | --- | --- |
| Trainer | 4 / 15 | 0 / 0 | `sha256:c88f10f7f0575b71aebec69a3facb605e41f9dec0243e8bf9535e8a20ec5776d` |
| Employee | 4 / 15 | 0 / 0 | `sha256:1450b4384f5473e8dfa401677da8afbaf5255bd7ace086a35d848e8ad3a7df2d` |

Original counts are the preserved 6 October baseline, not a rescan of the running containers on 7 October. The earlier same-database comparison verified removal of these occurrences. The new scans confirm the candidates remain clear with the 7 October database; they do not constitute a new same-snapshot before/after reduction.

## Fixes already included and verified again

- nginx 1.31.6 / Alpine 3.24 runtime, pinned base digest and distribution package upgrades. Refreshed detected OS: Alpine 3.24.2.
- Immutable Flutter 3.44.0 revision with Dart 3.12.0 and enforced dependency locks, preventing the older build from silently downgrading packages.
- Locally bundled web resources and licensed Roboto font for rendering without external CDN requests.
- Existing capability restrictions and prevention of privilege escalation.

All ten saved Dockerfile, pubspec, dependency-lock and font input hashes match the current local files. The candidates retain the previously verified compiled dependency versions.

## Refreshed verification

Trivy 0.75.0: `aquasec/trivy@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa`.
Both exact image IDs used one advisory database: `UpdatedAt=2026-10-07T00:53:05.111120428Z`. No scanner suppressions were added.

OSV checks queried 57 unique public Dart package/version pairs from both current lockfiles on 7 October; no advisories were returned. SDK packages are separately recorded as coverage gaps rather than treated as clean public-package results.

Disposable containers on an internal network passed nginx configuration, static serving/cache headers, API proxy application headers, synthetic video byte ranges, and Chromium rendering of both Hub access gates. Both produced accessible text, no browser page errors and no external requests. No live database, credentials or application storage was used. The test wrapper's final fixture-copy command referenced an old filename and failed after all assertions and result/screenshot copies passed; the actual scripts were then copied explicitly. This artifact-copy failure is not recorded as a failed application test or a successful wrapper exit.

## Remaining release gates

- Real Hub authentication and complete trainer/employee course workflows.
- Employee browser-platform widget test, previously unresolved.
- Complete Flutter/CanvasKit/native engine advisory provenance, SBOM schema validation and licence review. A zero package scan does not establish complete compiled-engine coverage.
- Release the exact reviewed artifacts, retain rollback images, and verify running identities on big-coding and UAT. No deployment, restart, commit or push was performed during this review. PostgreSQL remains deferred.

VM evidence: `/home/karphi/lms-security/evidence/frontend-review-20261007`.
Local evidence: `tmp/security-20261007/frontend-review-20261007`.
Public-package audit: `tmp/security-20261007/frontend-pub-audit.json`.
Earlier builds, SBOMs, comparisons and input hashes: `tmp/security-20261006/frontend-candidates-20261006-03`.
