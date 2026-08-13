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
BASE_DIR="${HISTORICAL_PAYLOAD_DATA_DIR:-$REPO_ROOT/.work/eval-payload-snapshots}"

tag="${1:-}"

if [[ -n "${HISTORICAL_PAYLOAD_DATA_DIR:-}" ]]; then
    if [[ ! -d "$BASE_DIR" ]]; then
        echo "Historical payload data directory not found: $BASE_DIR" >&2
        exit 1
    fi
elif [[ -d "$BASE_DIR/.git" ]]; then
    echo "Snapshot repo already cloned at $BASE_DIR" >&2
    git -C "$BASE_DIR" pull --ff-only >&2 2>/dev/null || true
else
    echo "Cloning snapshot data from $REPO_URL..." >&2
    git clone --depth 1 "$REPO_URL" "$BASE_DIR" >&2
fi

if [[ -n "$tag" ]]; then
    tag_dir="$BASE_DIR/$tag"
    if [[ ! -d "$tag_dir" ]]; then
        echo "Snapshot not found for tag: $tag" >&2
        exit 1
    fi

    if [[ -f "$tag_dir/summary.json" ]]; then
        echo "$tag_dir"
        exit 0
    fi

    mapfile -t summaries < <(find "$tag_dir" -mindepth 2 -maxdepth 4 \
        -type f -name summary.json -print | sort)
    if [[ ${#summaries[@]} -eq 1 ]]; then
        dirname "${summaries[0]}"
    elif [[ ${#summaries[@]} -eq 0 ]]; then
        echo "Snapshot has no summary.json: $tag_dir" >&2
        exit 1
    else
        echo "Snapshot is ambiguous; multiple summary.json files found under $tag_dir:" >&2
        printf '  %s\n' "${summaries[@]}" >&2
        exit 1
    fi
else
    echo "$BASE_DIR"
fi
