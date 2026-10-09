# LMS SBOM release handoff for DevOps

Status: combined candidate build, scan/SBOM, native/media, maintained-runtime database tests and synthetic production startup are complete. Real Hub workflow acceptance and residual-risk review remain pending. Four compiled frontend startup/gating smoke cases passed with synthetic Hub responses. This is not a declaration that UAT is ready for deployment.

## Agreed release workflow

Integrate the reviewed SBOM changes into Git main together with the latest feature code. DevOps checks out the resulting main commit on their PC, builds Linux amd64 Docker images, validates those new artifacts, and transfers/deploys them to UAT. No direct UAT execution by Codex is required. Changes are currently on codex/lms-sbom-release; they have not been merged into main.

The integration base is e5c42dae92de314f13ee87e25b055b5360e18b20. Build-source commit 767d262 preserves feature source and Nginx templates exactly from that main revision. PostgreSQL security remediation and the failed experimental PDF replacement are excluded.

## Required build settings

Run these commands in a Linux shell (including WSL if the build PC is Windows), inside the reviewed checkout. Record the actual merged commit. Shell scripts/security patches must retain LF bytes; the repository attributes specify this. The backend target must be maintained-priority-runtime: intermediate runtime stages omit later remediation.

```bash
set -euo pipefail
revision=$(git rev-parse HEAD)
release="sbom-${revision:0:12}"
mkdir -p "release-evidence/$release"
git status --short
git rev-parse HEAD > "release-evidence/$release/source-commit.txt"
# Use the UAT-approved API build values. Empty means same-origin routing.
trainer_api_base=''
employee_api_base=''
docker build --platform linux/amd64 --target maintained-priority-runtime \
  --label "org.opencontainers.image.revision=$revision" \
  -t "learning-management-backend:$release" backend \
  > "release-evidence/$release/backend-build.log" 2>&1
docker build --platform linux/amd64 --build-arg "API_BASE_URL=$trainer_api_base" \
  --label "org.opencontainers.image.revision=$revision" \
  -t "learning-management-frontend:$release" frontend \
  > "release-evidence/$release/trainer-build.log" 2>&1
docker build --platform linux/amd64 --build-arg "API_BASE_URL=$employee_api_base" \
  --label "org.opencontainers.image.revision=$revision" \
  -t "learning-management-employee-frontend:$release" employee_frontend \
  > "release-evidence/$release/employee-build.log" 2>&1
for image in "learning-management-backend:$release" \
  "learning-management-frontend:$release" "learning-management-employee-frontend:$release"; do
  docker image inspect --format '{{.Id}} {{.Architecture}} {{.Os}} {{json .RepoTags}}' "$image"
done > "release-evidence/$release/image-identities.txt"
```

Native identity checks must pass. If the backend guard reports changed or new native files, investigate the exact inputs, provenance and regression results. Do not delete/skip the guard or automatically replace its hashes to make a build pass.

Build inputs are partly pinned, but apt/apk updates and source-built wheels can differ with build date/environment. Matching source commits and tags do not prove matching image bytes. Codex's candidate results therefore do not certify a separately rebuilt DevOps image.

## Validate the DevOps artifacts

Record a digest-pinned Trivy scanner and its database metadata, scan all three final image IDs against one database snapshot, and generate CycloneDX SBOMs. The repository scan script resolves image IDs before scanning and preserves raw output:

```bash
export SCANNER_IMAGE='aquasec/trivy@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa'
export REPORT_DIR="$PWD/release-evidence/$release/scans"
export CACHE_DIR="$PWD/release-evidence/scanner-cache"
bash scripts/security/scan-candidates.sh \
  "learning-management-backend:$release" \
  "learning-management-frontend:$release" \
  "learning-management-employee-frontend:$release"
```

Generate/validate SBOMs, review new findings and retain native attribution/provenance. Scanner success/exit zero does not mean zero findings. Run the four backend native/parser/medium/backlog smoke scripts in the final backend image using a read-only scripts mount, network none, cap_drop ALL and no-new-privileges. Repeat feature/runtime checks and compiled frontend acceptance on those artifacts. Keep raw findings separate from supported patch/affectedness assessments. Six inherited High bundled-code coverage reviews are still open; no automatic risk acceptance is recorded.

Current combined-source results: 329 backend unit passes with one pre-existing slide-layout assertion mismatch; 41 synthetic PostgreSQL feature checks plus 15 Performance SQL parity checks; four Nginx/shared-route tests; 36 trainer Flutter tests. Employee native tests have 13 passes plus a browser-only import gap. Chrome widget tests stalled in the DDC harness with module-resource errors; they are not passes. Four exact-image compiled startup/access-gate checks passed (trainer/employee direct/shared routes), with zero JavaScript errors and zero external asset requests. They used synthetic Hub responses; real Hub workflow acceptance must still resolve the release impact of the remaining gaps. The fresh trainer/employee candidate container scans detected zero findings; this does not establish complete compiled Flutter/engine vulnerability coverage.

## UAT settings to preserve

User-provided preflight identifies host pcilailabuat (10.204.6.139), offline directory /root/lms/lms_1_10_26/learning-management-offline-amd64-20261001, project learning-management, docker-compose.yml plus observability.yml. Current app images have 20261001 tags and ports backend 127.0.0.1:3060, trainer 6969, employee 6970. The LMS database connection is 172.30.0.2:5432/lms, external to this Compose project; DevOps must confirm its owner/backup and preserve the connection.

Preserve the UAT environment, observability overlay, storage paths, networks, Hub secret/cookies/app keys, directory settings and SMTP settings. Do not replace them with VM settings. New frontend images run as UID 101 and backend as UID 10001; verify existing mount access without weakening permissions globally. Preserve trusted edge settings only for the actual UAT topology. Recreate only backend, frontend and employee_frontend; do not bring up or replace a PostgreSQL service.

Record exact previous image IDs and effective configuration before replacing services. Retain recoverable image archives/tags. Confirm a database backup and restore procedure before first candidate startup: the combined feature code adds learning events/access metadata and a learner-activity column. Startup uses init_db, not the explicit recreate_db operation. Existing UAT source identity is not recorded, so do not assume migration compatibility solely from its image tag. Rolling back images cannot undo database writes.

After transferring/loading images, verify the destination IDs against the DevOps manifest. Use a scoped Compose image overlay with the existing UAT files/project and recreate only the three app services, with no build/pull and no dependency recreation. The concrete overlay and rollback commands must use the deployment's verified identities/settings; they are not finalized in this draft.

## Acceptance and completion evidence

Check real Hub trainer/employee launch, shared/direct routes, forwarded scheme/cookies, private media authorization, cross-trainer course visibility, reporting permissions, Performance values, assignment/Observer separation, search/pagination, deadline behavior, PDF/document conversion, slides/audio/video/HLS, progress and safe notification previews. Use controlled test identities/data; external email requires the intended recipients.

Complete the handoff with build logs, Git commit, build values, final image IDs, scanner/database metadata, raw scans, validated SBOMs, smoke/feature/UI results, residual-risk dispositions and rollback readiness. A successful image build or Git main pull alone is insufficient evidence of a verified UAT release.

## Confirmed UAT baseline (refresh before deployment)

The targeted user-run inspection recorded these current image IDs:

| Service | Current image ID | Runtime user |
| --- | --- | --- |
| backend | sha256:a112df637acd59771ea5f794d0370d5789d6614de31483c1346e72f521c8ebe4 | 10001:10001 |
| frontend | sha256:36a28c1401dd2dcf8ee020b41b3fec214a8efea41fe2e32bbccfb236f88a9458 | 101 |
| employee_frontend | sha256:17ee77349090a9aaae34690e977350cbe77b372ce0b909de246c262bdb9d3b1e | 101 |

Backend storage is /opt/lms/storage -> /app/storage. Both frontend mounts are /opt/lms/storage/generated/videos -> /srv/lms/videos and read-only in Compose. Frontends use learning-management_default. Backend uses that network plus 11-hub-app_default, hub-app_default, ai-observability and learning-management_learning-management. Preserve these existing settings rather than introducing VM onprem-edge aliases.

DATABASE_URL points to host 172.30.0.2, port 5432, database lms. The database owner/container has not been identified; confirm connectivity/backup with that owner before rollout and preserve the connection. Current image source-revision labels are unrecorded. See sbom-lms-uat-baseline-2026-10-08.json. These recorded October 8 identities must be rechecked immediately before deployment; a later release may have changed them.

A release image overlay should change only the three app image references plus the intended cap_drop ALL/no-new-privileges settings, retaining the original deployment files. With a validated overlay and rollback record in place, the scoped command shape is:

```bash
docker compose -p learning-management \
  -f docker-compose.yml -f observability.yml -f security-release.images.yml \
  up -d --no-deps --no-build --pull never backend frontend employee_frontend
```

Do not run this draft command until the actual image overlay, build/scan acceptance and database recovery readiness are complete. To revert app images, use the captured rollback overlay with the same original files/project and scoped services; treat any data/schema recovery as a separate reviewed operation.

## Source-build guard review

The original combined backend guard rejected seven locally compiled lxml files while the other 62 reference files matched. Replacing historical hashes on every machine would not provide a repeatable build policy. The reviewed update records the hash-enforced lxml 6.1.3 source wheel outputs and requires the exact approved source/version/seven-file set; all other reference files remain exact and additional native files fail. Twelve tamper/manifest tests passed, and the complete 9f26951 backend build passed this final guard. Final image export, scanner/SBOM schema validation, all four native smoke suites, 41 access/database tests, 15 Performance parity tests and synthetic production-config startup passed. Real authenticated Hub workflow acceptance remains pending. This changes build verification, not the status of the six inherited High coverage reviews.

## Final combined candidate evidence

Backend source 9f2695172dae768a3e1f0a285cfeaba3ef5ba662 produced image sha256:79a2e619cfd6f90729bfedded267dd8ce89e3b396eab8dc1a9e8f8f944930097. Trainer image is sha256:0d9f86c72818a6a7025e9c3f796db2381d6dcc8178763a48ffa0123576016573; employee image is sha256:8f352d64d842557ea91d6a363d445b17b4b4782166e28a1a30c707e6e43e4a13. Their inputs are unchanged from the earlier 767d262 frontend build.

Against the shared recorded Trivy database snapshot (UpdatedAt 2026-10-07T07:38:55Z, downloaded October 8 07:04 UTC), backend raw results are 0 Critical, 0 High, 27 Medium and 12 Low; both frontend raw scans have zero findings. This is a consistent comparison snapshot, not a claim that its database is the latest at deployment. The exact backend package/version/advisory/severity multiset matches the prior 39-row assessment. Existing assessment evidence still requires review for the final artifact; no finding is closed merely by matching counts. Six inherited High bundled-code coverage reviews remain open independently of scanner counts.

All three CycloneDX 1.7 SBOM schemas pass. Backend contains 406 components, 328 with license metadata; each frontend contains 71 components, 70 with license metadata. Missing license metadata requires attribution review before distribution. Final backend evidence archive SHA-256 is 52f78eb9d9fc0d7135dcd507e9c3dd17ecb3aba192bdc24b793eeb74191a0448. Four native/media suites passed. The 56 database feature checks were repeated on the final maintained runtime, and production-config startup passed against an isolated synthetic database. No live service or UAT deployment was changed.