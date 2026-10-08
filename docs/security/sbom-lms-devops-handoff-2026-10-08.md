# LMS SBOM release handoff for DevOps

Status: preparation in progress; maintained backend build/validation and compiled UI acceptance are still pending. This is not a declaration that UAT is ready for deployment.

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

Current combined-source results: 329 backend unit passes with one pre-existing slide-layout assertion mismatch; 41 synthetic PostgreSQL feature checks plus 15 Performance SQL parity checks; four Nginx/shared-route tests; 36 trainer Flutter tests. Employee native tests have 13 passes plus a browser-only import gap. Chrome widget tests stalled in the DDC harness with module-resource errors; they are not passes. Real compiled UI acceptance must resolve the release impact of these gaps. The fresh trainer/employee candidate container scans detected zero findings; this does not establish complete compiled Flutter/engine vulnerability coverage.

## UAT settings to preserve

User-provided preflight identifies host pcilailabuat (10.204.6.139), offline directory /root/lms/lms_1_10_26/learning-management-offline-amd64-20261001, project learning-management, docker-compose.yml plus observability.yml. Current app images have 20261001 tags and ports backend 127.0.0.1:3060, trainer 6969, employee 6970. No bundled LMS database container was listed; DevOps must identify and preserve the actual database connection.

Preserve the UAT environment, observability overlay, storage paths, networks, Hub secret/cookies/app keys, directory settings and SMTP settings. Do not replace them with VM settings. New frontend images run as UID 101 and backend as UID 10001; verify existing mount access without weakening permissions globally. Preserve trusted edge settings only for the actual UAT topology. Recreate only backend, frontend and employee_frontend; do not bring up or replace a PostgreSQL service.

Record exact previous image IDs and effective configuration before replacing services. Retain recoverable image archives/tags. Confirm a database backup and restore procedure before first candidate startup: the combined feature code adds learning events/access metadata and a learner-activity column. Startup uses init_db, not the explicit recreate_db operation. Existing UAT source identity is not recorded, so do not assume migration compatibility solely from its image tag. Rolling back images cannot undo database writes.

After transferring/loading images, verify the destination IDs against the DevOps manifest. Use a scoped Compose image overlay with the existing UAT files/project and recreate only the three app services, with no build/pull and no dependency recreation. The concrete overlay and rollback commands must use the deployment's verified identities/settings; they are not finalized in this draft.

## Acceptance and completion evidence

Check real Hub trainer/employee launch, shared/direct routes, forwarded scheme/cookies, private media authorization, cross-trainer course visibility, reporting permissions, Performance values, assignment/Observer separation, search/pagination, deadline behavior, PDF/document conversion, slides/audio/video/HLS, progress and safe notification previews. Use controlled test identities/data; external email requires the intended recipients.

Complete the handoff with build logs, Git commit, build values, final image IDs, scanner/database metadata, raw scans, validated SBOMs, smoke/feature/UI results, residual-risk dispositions and rollback readiness. A successful image build or Git main pull alone is insufficient evidence of a verified UAT release.
