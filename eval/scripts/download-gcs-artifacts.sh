#!/bin/bash
# Download all artifacts for a GCS prefix using rclone (no auth needed).
# Usage: download-gcs-artifacts.sh <gcs-prefix> <dest-dir>
#
# Example:
#   ./download-gcs-artifacts.sh \
#     "logs/periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn-techpreview/2034916736909709312" \
#     "./archive/test-platform-results"

set -euo pipefail

BUCKET="test-platform-results"
PREFIX="${1%/}"
DEST="$2"

mkdir -p "$DEST/$PREFIX"
rclone copy ":gcs:$BUCKET/$PREFIX" "$DEST/$PREFIX" \
    --transfers "${RCLONE_TRANSFERS:-16}" \
    --checkers "${RCLONE_CHECKERS:-8}" \
    --no-traverse \
    -q

count=$(find "$DEST/$PREFIX" -type f | wc -l)
size=$(du -sh "$DEST/$PREFIX" | cut -f1)
echo "Done: $PREFIX ($count files, $size)"
