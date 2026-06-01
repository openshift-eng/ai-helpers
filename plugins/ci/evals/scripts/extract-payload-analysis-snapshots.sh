#!/bin/bash
# Fetch payload-analysis snapshot data for eval runs.
#
# Clones historical-payload-data repo and makes snapshots available
# at .work/eval-payload-snapshots/<tag>/
#
# Usage: ./plugins/ci/evals/scripts/extract-payload-analysis-snapshots.sh
# Or:    SNAPSHOT_DIR=$(./plugins/ci/evals/scripts/extract-payload-analysis-snapshots.sh 5.0.0-0.nightly-2026-05-30-072431)

set -euo pipefail

REPO_URL="https://github.com/stbenjam/historical-payload-data.git"
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
BASE_DIR="$REPO_ROOT/.work/eval-payload-snapshots"

tag="${1:-}"

if [[ -d "$BASE_DIR/.git" ]]; then
    echo "Snapshot repo already cloned at $BASE_DIR" >&2
    git -C "$BASE_DIR" pull --ff-only >&2 2>/dev/null || true
else
    echo "Cloning snapshot data from $REPO_URL..." >&2
    git clone --depth 1 "$REPO_URL" "$BASE_DIR" >&2
fi

if [[ -n "$tag" ]]; then
    if [[ -d "$BASE_DIR/$tag" ]]; then
        echo "$BASE_DIR/$tag"
    else
        echo "Snapshot not found for tag: $tag" >&2
        exit 1
    fi
else
    echo "$BASE_DIR"
fi
