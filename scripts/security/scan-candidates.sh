#!/usr/bin/env bash
# Scan exact local image IDs once against a shared advisory snapshot. No builds or deployments.
set -euo pipefail
: "${REPORT_DIR:?Set a new report directory}"
: "${CACHE_DIR:?Set a scanner cache directory}"
: "${SCANNER_IMAGE:?Set the verified scanner image digest}"
case "$SCANNER_IMAGE" in *@sha256:*) ;; *) echo 'Use a digest-pinned scanner image' >&2; exit 2 ;; esac
if [ "$#" -eq 0 ]; then echo 'Pass one or more local candidate image references' >&2; exit 2; fi
if [ -e "$REPORT_DIR" ]; then echo 'Report directory already exists; preserve it and choose a new run directory' >&2; exit 2; fi
# Resolve tags before starting so a later retag cannot change the scanned artifact.
images=()
for reference in "$@"; do images+=("$(docker image inspect "$reference" --format '{{.Id}}')"); done
mkdir -p "$REPORT_DIR" "$CACHE_DIR"
exec 9>"$CACHE_DIR/.lms-scan.lock"
flock 9
printf '%s\n' "$SCANNER_IMAGE" > "$REPORT_DIR/scanner-image.txt"
docker run --rm --cpus=2 --memory=3g -v "$CACHE_DIR:/root/.cache" \
    "$SCANNER_IMAGE" image --download-db-only > "$REPORT_DIR/db-download.log" 2>&1
index=0
for reference in "$@"; do
    image="${images[$index]}"
    index=$((index + 1))
    label=$(printf '%s' "$reference" | tr -c 'a-zA-Z0-9._-' '_')
    prefix="$index-$label"
    printf '%s\n' "$reference" "$image" > "$REPORT_DIR/$prefix-image.txt"
    docker run --rm --cpus=2 --memory=3g \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$CACHE_DIR:/root/.cache" -v "$REPORT_DIR:/reports" \
        "$SCANNER_IMAGE" image --image-src docker --scanners vuln --skip-db-update \
        --timeout 15m --format json --output "/reports/$prefix.json" "$image" \
        > "$REPORT_DIR/$prefix-scan.log" 2>&1
    echo "Scanned $reference ($image)"
done
cp "$CACHE_DIR/trivy/db/metadata.json" "$REPORT_DIR/vulnerability-db-metadata.json"
