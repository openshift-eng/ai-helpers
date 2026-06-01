#!/bin/bash
# Extract payload-analysis snapshot archives for eval runs.
# Usage: eval "$(./plugins/ci/evals/scripts/extract-payload-analysis-snapshots.sh)"
# Or:    export EVAL_SNAPSHOT_DIR=$(./plugins/ci/evals/scripts/extract-payload-analysis-snapshots.sh 5.0.0-0.nightly-2026-05-30-072431)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SNAPSHOTS_DIR="$SCRIPT_DIR/../snapshots/payload-analysis"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
BASE_DIR="$REPO_ROOT/.work/eval-payload-snapshots"

if [[ ! -d "$SNAPSHOTS_DIR" ]]; then
    echo "No snapshots directory at $SNAPSHOTS_DIR" >&2
    exit 1
fi

tag="${1:-}"

for archive in "$SNAPSHOTS_DIR"/*.tar.gz; do
    [[ -f "$archive" ]] || continue
    name="$(basename "$archive" .tar.gz)"

    if [[ -n "$tag" && "$name" != "$tag" ]]; then
        continue
    fi

    dest="$BASE_DIR/$name"
    if [[ -d "$dest" ]] && find "$dest" -name summary.json -print -quit 2>/dev/null | grep -q .; then
        echo "Already extracted: $dest" >&2
    else
        mkdir -p "$dest"
        tar xzf "$archive" -C "$dest"
        echo "Extracted: $dest" >&2
    fi

    if [[ -n "$tag" ]]; then
        echo "$dest"
        exit 0
    fi
done

if [[ -n "$tag" ]]; then
    echo "Snapshot archive not found for tag: $tag" >&2
    exit 1
fi

echo "$BASE_DIR"
