#!/usr/bin/env bash
# Build the evidence package for a release and act as the release gate.
#
# For each local image: CycloneDX SBOM, unfiltered Trivy vulnerability report, the
# notice files shipped in the image, and an SBOM copy with supplier names and the
# bundled browser. Also copies the build definitions and scanner settings.
# Exits 1 when any image has a Critical or High vulnerability that has a fix.
#
# Usage:
#   REPORT_DIR=/new/dir CACHE_DIR=/trivy/cache SCANNER_IMAGE=aquasec/trivy@sha256:... \
#     scripts/security/release-evidence.sh BACKEND_IMAGE TRAINER_IMAGE EMPLOYEE_IMAGE
set -euo pipefail
: "${REPORT_DIR:?Set a new report directory}"
: "${CACHE_DIR:?Set a scanner cache directory}"
: "${SCANNER_IMAGE:?Set the digest-pinned scanner image}"
case "$SCANNER_IMAGE" in *@sha256:*) ;; *) echo 'Use a digest-pinned scanner image' >&2; exit 2 ;; esac
if [ "$#" -eq 0 ]; then echo 'Pass one or more local image references' >&2; exit 2; fi
if [ -e "$REPORT_DIR" ]; then echo 'Report directory already exists; choose a new one' >&2; exit 2; fi
repo="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$REPORT_DIR/build-definitions" "$REPORT_DIR/scanner-settings" "$CACHE_DIR"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd)"

cp "$repo/backend/Dockerfile" "$REPORT_DIR/build-definitions/backend.Dockerfile"
cp "$repo/deploy/web.Dockerfile" "$repo/docker-compose.yml" "$REPORT_DIR/build-definitions/"
# Every scanner setting that hides or accepts a finding. Trivy runs with none.
cp "$repo/.bandit" "$repo/.hadolint.yaml" "$REPORT_DIR/scanner-settings/"
printf '%s\n' "$SCANNER_IMAGE" > "$REPORT_DIR/scanner-image.txt"

trivy() {
    docker run --rm --cpus=2 --memory=3g \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$CACHE_DIR:/root/.cache" -v "$REPORT_DIR:/reports" \
        "$SCANNER_IMAGE" "$@"
}
trivy image --download-db-only > "$REPORT_DIR/db-download.log" 2>&1

for reference in "$@"; do
    image="$(docker image inspect "$reference" --format '{{.Id}}')"
    label="$(printf '%s' "$reference" | tr -c 'a-zA-Z0-9._-' '_')"
    printf '%s\n%s\n' "$reference" "$image" > "$REPORT_DIR/$label-image.txt"
    trivy image --image-src docker --skip-db-update --timeout 15m \
        --format cyclonedx --output "/reports/$label.raw.cdx.json" "$image" > "$REPORT_DIR/$label-sbom.log" 2>&1
    trivy image --image-src docker --skip-db-update --timeout 15m --scanners vuln \
        --format json --output "/reports/$label.vulnerabilities.json" "$image" > "$REPORT_DIR/$label-scan.log" 2>&1

    # Notice files are copied out of a stopped container; nothing in the image runs.
    container="$(docker create "$image")"
    mkdir -p "$REPORT_DIR/$label-notices"
    docker cp "$container:/usr/share/lms-security/notices/." "$REPORT_DIR/$label-notices/" 2>/dev/null || true
    docker cp "$container:/usr/share/licenses/lms/." "$REPORT_DIR/$label-notices/" 2>/dev/null || true
    docker rm "$container" > /dev/null

    extra=()
    [ -f "$REPORT_DIR/$label-notices/third-party-inventory.json" ] \
        && extra+=(--inventory "$REPORT_DIR/$label-notices/third-party-inventory.json")
    [ -f "$REPORT_DIR/$label-notices/third-party-licenses.json" ] \
        && extra+=(--npm-licences "$REPORT_DIR/$label-notices/third-party-licenses.json")
    python3 "$repo/scripts/security/finish_sbom.py" \
        "$REPORT_DIR/$label.raw.cdx.json" "$REPORT_DIR/$label.cdx.json" "${extra[@]}"
done
cp "$CACHE_DIR/trivy/db/metadata.json" "$REPORT_DIR/vulnerability-db-metadata.json"

# Release gate: a Critical or High finding with a published fix blocks the release.
python3 - "$REPORT_DIR" <<'EOF'
import collections, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
blocking = 0
lines = []
for report in sorted(root.glob('*.vulnerabilities.json')):
    counts = collections.Counter()
    fixable = []
    for result in json.loads(report.read_text()).get('Results') or []:
        for item in result.get('Vulnerabilities') or []:
            counts[item['Severity']] += 1
            if item['Severity'] in ('CRITICAL', 'HIGH') and item.get('FixedVersion'):
                fixable.append(f"  {item['Severity']} {item['PkgName']} {item['InstalledVersion']}"
                               f" -> {item['FixedVersion']} {item['VulnerabilityID']}")
    lines.append(f"{report.name}: {dict(counts) or 'no vulnerabilities'}; blocking {len(fixable)}")
    lines += sorted(set(fixable))
    blocking += len(fixable)
lines.append('GATE: ' + ('FAIL' if blocking else 'PASS'))
(root / 'gate-summary.txt').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
sys.exit(1 if blocking else 0)
EOF
