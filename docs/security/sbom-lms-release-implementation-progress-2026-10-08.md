# Combined release execution progress — 8 October 2026

- Baseline confirmed: GitHub main and big-coding checkout e5c42da include the Performance/Observer changes through 7402617. Running app/database image IDs and deployment overlay hashes are recorded separately.
- Original dirty SBOM checkout preserved. Snapshot ZIP SHA-256: 8cd5841d205641f7e1042d167b6540279e1ae92f1518b6bfd77f47f428c29a08.
- Integrated on isolated branch codex/lms-sbom-release, build-source commit 767d262. Compose retains both trusted edge configuration and security restrictions. Application feature source and Nginx templates have zero diff from e5c42da.
- Failed PDF source replacement excluded; PostgreSQL remediation deferred. No live service restart or UAT deployment performed.
- Local backend suite: 329 passed, 60 opt-in tests skipped, one pre-existing landscape slide assertion failure. Both the failing test and its implementation are unchanged from main.
- Disposable VM database tests: 41 passed. Seeded only lms_performance_demo with synthetic data; Performance SQL parity suite: 15 passed. These validate feature code with the test image dependencies, not the unfinished maintained backend runtime.
- Trainer tests on pinned Flutter SDK: 36 passed on both export attempts. Employee native-platform tests expose the existing browser-only import gap; browser-platform validation is in progress.
- Both final frontend image identities have fresh Trivy scans with zero detected findings. Their CycloneDX 1.7 SBOMs validate against the official schema; each records 71 components, 70 with licence metadata. This OS/container inventory does not establish complete compiled Flutter/engine coverage.
- Fresh OSV audit of 57 hosted Dart package versions found no listed advisories. Flutter/SDK entries remain a separate coverage gap.
- Four Nginx/shared-route regression tests passed against the combined templates. Employee Chrome widget validation did not reach assertions: DDC modules fail ERR_INSUFFICIENT_RESOURCES at both nofile 1024 and 65536, and after one cached reload. The disposable browser tests were stopped and the harness gap recorded; compiled UI acceptance remains required. No runtime application changes were made for this test harness issue.
- Maintained backend compilation, its fresh scan/native smoke tests, and full candidate-runtime/Hub/UAT acceptance remain pending. Historical backend security counts are not recertified by this integration.
- UAT execution method confirmed: the user will run the supplied commands and share outputs. Read-only preflight collects deployment identities and topology before exact rollout/rollback commands are finalized.

## Canonical source export

The first Windows Git archive exported text with CRLF and was unsuitable for pinned Linux patches/scripts. Its source/evidence are retained under source-crlf and release-767d262-crlf on the VM; its attempted backend build was cancelled. Do not use that archive for release.

Export using explicit Git configuration:

```bash
git -c core.autocrlf=false -c core.eol=lf archive --format=tar.gz --output=release-source.tar.gz 767d262
```

Accepted archive SHA-256: d208d1f98f529b4c134d0745f220418999e5dfb27bdc88712884a06185879c3e. Shell and patch archive bytes were checked against Git blobs, and the VM verified the archive checksum before extraction. Added LF attributes protect future shell/security-input checkouts; this infrastructure policy does not alter feature code.

## Remaining gates

Finish the maintained backend build and review any native identity drift; generate final SBOMs/scans, retain residual coverage gaps, run native/media smoke tests and the real Hub workflow checks, evaluate the existing slide-layout test failure, then prepare the reviewed release/rollback bundle before UAT promotion. Candidate tests use dedicated data/storage and preserve the live database and edge aliases.

## UAT preflight received

UAT is pcilailabuat, 10.204.6.139, with an offline deployment directory at /root/lms/lms_1_10_26/learning-management-offline-amd64-20261001. It has no Git checkout. Project learning-management uses docker-compose.yml plus observability.yml; three app containers currently use 20261001 tags. Root filesystem has 361G free. Exact image identities, mount/network topology and database host/name are requested. Transfer tested image archives rather than invoking git pull or rebuilding on UAT. Do not substitute the VM database/edge configuration.

Feature startup migration review against the October 1 source identifies additive learning_events/last_learner_activity_at/access metadata changes. Startup invokes init_db, not recreate_db. Existing UAT source identity is unrecorded so compatibility and database backup/restore readiness must be checked against its actual state; image rollback alone does not restore data.

## Updated responsibility for UAT

The user superseded the manual-command plan: DevOps will get the merged Git main code, build Docker images on their PC and deploy them to UAT. No more UAT command execution is requested from the user. Codex will provide the validated integration and DevOps handoff. Separately rebuilt DevOps artifacts require their own recorded identities, scans and runtime acceptance; main-commit equivalence does not guarantee image equivalence. See sbom-lms-devops-handoff-2026-10-08.md (draft until remaining gates pass).

## Compiled frontend runtime smoke

Four checks passed on the exact trainer/employee candidate IDs: each direct route and its shared /lms route rendered the expected unauthenticated Hub gate. Playwright intercepted only API calls with a synthetic unauthenticated Hub response; no real Hub login was performed. There were zero JavaScript exceptions and zero external asset requests. Trainer and employee screenshots were inspected and show the correct gate. The test network/containers were removed automatically; no live mounts or aliases were used. Evidence archive SHA-256: 37688142cde95dffe05b7d62ba108f885beb9840c63854f35f975ea9cb069b6d. The legacy Chrome widget harness gap remains open; these four smoke cases do not replace its assertions or real Hub workflow acceptance.

## Confirmed UAT topology

Follow-up user output records the previous UAT images in sbom-lms-uat-baseline-2026-10-08.json. Existing runtime users match the candidate UID 10001 backend and UID 101 frontends. DATABASE_URL host is 172.30.0.2:5432, database lms, external to the LMS project. Storage mounts and all five backend networks are recorded. DevOps owns confirming that database's owner/backup and preserving the existing observability/network configuration. No further UAT commands are requested from the user.

## Native identity rebuild issue

The full backend build reached its final guard, which rejected exactly seven source-built lxml binaries. The other 62 reference identities matched. A cache-only diagnostic printed the unchanged guard rejection; a separate pre-guard diagnostic image is retained solely for review, not release. The final guard now binds the seven lxml outputs to a manifest generated from the hash-enforced source wheel build (lxml 6.1.3, source SHA-256 45222d94ddd511536f3b2f7d9deae3b2339b4ce0f075f1ca25703b07cad9dd21). The manifest records wheel/native output hashes, Python/compiler/XML/XSLT versions and build packages. It must match the exact approved version/source and original seven-file set; the other 62 files keep their historical exact-hash checks. New/missing/modified files remain rejected. All six inherited High coverage reviews remain open. Twelve focused tests passed, including source/version tampering, changed outputs, extra/missing evidence and unsafe wheel paths. Updated guarded candidate rebuild/native validation/scanning remain pending; the old failed build is preserved.

## Guarded combined backend build

Build-source commit 9f2695172dae768a3e1f0a285cfeaba3ef5ba662, canonical source archive SHA-256 7e6398783bf7a5d9e50ae104e1aeaff4dcdf745380f9aea5071f17e43de97ed1. Frontend build inputs have zero diff from 767d262, so the already scanned/tested frontend images are reused with their original source identity. The backend final native guard passed: 62 reference identities plus seven approved-source lxml outputs. Some native stages missed cache and were rebuilt; no claim of a completely cached rebuild is made. Final image export/loading, raw scan/SBOM, native/media checks and maintained-runtime SQL/startup checks are pending. The draft DevOps handoff is recorded; GitHub repository access for the planned PR was checked read-only, and no PR/merge/deployment has occurred.


## Final guarded candidate verification

The maintained backend image build completed: sha256:79a2e619cfd6f90729bfedded267dd8ce89e3b396eab8dc1a9e8f8f944930097. All four native/media smoke suites passed. Final-runtime access/database tests passed 41/41, then Performance SQL parity passed 15/15. Production-config startup passed on the isolated synthetic database. Backend CycloneDX 1.7 schema passed (406 components; 328 with licence metadata). Raw findings are 0 Critical, 0 High, 27 Medium, 12 Low on the shared recorded October 7 database snapshot downloaded October 8; exact package/version/advisory/severity multiset matches the previous assessment. Frontend zero-detection scans and SBOM schema passes remain valid for their unchanged exact images. Six inherited High coverage reviews remain open; no automatic closure or risk acceptance. Evidence archive SHA-256: 52f78eb9d9fc0d7135dcd507e9c3dd17ecb3aba192bdc24b793eeb74191a0448.

Remaining owner gates: draft PR review and merge, real authenticated Hub workflow acceptance, the known slide assertion/browser harness gaps, residual-risk disposition, license attribution review, and DevOps build/scan/acceptance of separately rebuilt images before UAT rollout. PostgreSQL remains deferred. No live service was restarted.
