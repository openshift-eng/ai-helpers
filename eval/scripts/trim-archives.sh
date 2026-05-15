#!/bin/bash
# Trims eval archives by removing large files the skill never reads,
# while preserving directory structure for realistic gcloud storage ls output.
#
# Usage:
#   ./trim-archives.sh [--archives-dir <path>] [--dry-run]
#
# The skill only reads specific files (junit XML, build-log.txt, finished.json,
# prowjob.json). This script removes the heavy artifacts (audit logs, metrics,
# prometheus tars, e2e event dumps, etc.) that the skill never touches, while
# keeping empty directories so that `gcloud storage ls` navigation still looks
# realistic.
#
# Safe to run multiple times (idempotent).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVES_DIR="${SCRIPT_DIR}/../../archives"
DRY_RUN=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Trim eval archives by removing large files the skill never reads.

Options:
  --archives-dir <path>  Path to archives directory (default: ../../archives relative to script)
  --dry-run              Show what would be removed without removing
  -h, --help             Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --archives-dir)
            ARCHIVES_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            ;;
    esac
done

ARCHIVES_DIR="$(cd "$ARCHIVES_DIR" && pwd)"

if [[ ! -d "$ARCHIVES_DIR" ]]; then
    echo "Error: archives directory not found: $ARCHIVES_DIR" >&2
    exit 1
fi

human_size() {
    local bytes=$1
    if (( bytes >= 1073741824 )); then
        printf "%.1f GB" "$(echo "scale=1; $bytes / 1073741824" | bc)"
    elif (( bytes >= 1048576 )); then
        printf "%.1f MB" "$(echo "scale=1; $bytes / 1048576" | bc)"
    elif (( bytes >= 1024 )); then
        printf "%.1f KB" "$(echo "scale=1; $bytes / 1024" | bc)"
    else
        printf "%d B" "$bytes"
    fi
}

dir_size_bytes() {
    du -sb "$1" 2>/dev/null | cut -f1
}

# Remove contents of a directory but keep the directory itself (preserves
# structure for gcloud storage ls). Creates a .trimmed marker so repeated
# runs can skip already-emptied dirs.
remove_dir_contents() {
    local dir="$1"
    [[ -d "$dir" ]] || return 0

    # Already trimmed on a previous run
    if [[ -f "$dir/.trimmed" ]] && [[ $(find "$dir" -maxdepth 1 -not -name '.trimmed' -not -path "$dir" | wc -l) -eq 0 ]]; then
        return 0
    fi

    local size
    size=$(dir_size_bytes "$dir")
    if (( size == 0 )); then
        return 0
    fi

    if $DRY_RUN; then
        echo "  [dry-run] would remove contents of $dir ($(human_size "$size"))"
    else
        find "$dir" -mindepth 1 -not -name '.trimmed' -delete 2>/dev/null || true
        touch "$dir/.trimmed"
    fi
    REMOVED_BYTES=$((REMOVED_BYTES + size))
}

# Remove files matching a glob pattern under a base directory.
remove_matching_files() {
    local base_dir="$1"
    local pattern="$2"
    [[ -d "$base_dir" ]] || return 0

    while IFS= read -r -d '' file; do
        local size
        size=$(stat --printf='%s' "$file" 2>/dev/null || echo 0)
        if $DRY_RUN; then
            echo "  [dry-run] would remove $file ($(human_size "$size"))"
        else
            rm -f "$file"
        fi
        REMOVED_BYTES=$((REMOVED_BYTES + size))
    done < <(find "$base_dir" -name "$pattern" -type f -print0 2>/dev/null)
}

# Remove any individual file larger than a threshold.
remove_large_files() {
    local base_dir="$1"
    local max_bytes="$2"

    while IFS= read -r -d '' file; do
        local size
        size=$(stat --printf='%s' "$file" 2>/dev/null || echo 0)
        if (( size > max_bytes )); then
            if $DRY_RUN; then
                echo "  [dry-run] would remove large file $file ($(human_size "$size"))"
            else
                rm -f "$file"
            fi
            REMOVED_BYTES=$((REMOVED_BYTES + size))
        fi
    done < <(find "$base_dir" -type f -print0 2>/dev/null)
}

TOTAL_SAVED=0

# Iterate over each archive directory (skip tarballs)
for archive in "$ARCHIVES_DIR"/*/; do
    [[ -d "$archive" ]] || continue
    archive_name="$(basename "$archive")"

    BEFORE_BYTES=$(dir_size_bytes "$archive")
    REMOVED_BYTES=0

    echo "Processing: $archive_name"

    # --- Directories to empty (keep dir, remove contents) ---

    # gather-extra/artifacts/audit_logs/ — 106 GB total, never read
    while IFS= read -r -d '' dir; do
        remove_dir_contents "$dir"
    done < <(find "$archive" -type d -path '*/gather-extra/artifacts/audit_logs' -print0 2>/dev/null)

    # gather-extra/artifacts/metrics/ — 27 GB total (prometheus tars), never read
    while IFS= read -r -d '' dir; do
        remove_dir_contents "$dir"
    done < <(find "$archive" -type d -path '*/gather-extra/artifacts/metrics' -print0 2>/dev/null)

    # observers-resource-watch/ — 9 GB total, never read
    while IFS= read -r -d '' dir; do
        remove_dir_contents "$dir"
    done < <(find "$archive" -type d -name 'observers-resource-watch' -print0 2>/dev/null)

    # gather-network/ — 1.7 GB total, never read
    while IFS= read -r -d '' dir; do
        remove_dir_contents "$dir"
    done < <(find "$archive" -type d -name 'gather-network' -print0 2>/dev/null)

    # gather-extra/artifacts/inspect/ — 6 GB total, never read
    while IFS= read -r -d '' dir; do
        remove_dir_contents "$dir"
    done < <(find "$archive" -type d -path '*/gather-extra/artifacts/inspect' -print0 2>/dev/null)

    # --- Specific large files ---

    # gather-audit-logs/artifacts/audit-logs.tar — 7 GB total
    remove_matching_files "$archive" "audit-logs.tar"

    # openshift-e2e-test e2e-events*.json — 10 GB total
    remove_matching_files "$archive" "e2e-events*.json"

    # openshift-e2e-test events_used_for_junits*.json
    remove_matching_files "$archive" "events_used_for_junits*.json"

    # openshift-e2e-test extension_test_result* — 2.7 GB total
    remove_matching_files "$archive" "extension_test_result*"

    # --- Catch-all: any remaining file > 200 MB ---
    remove_large_files "$archive" $((200 * 1048576))

    AFTER_BYTES=$(( BEFORE_BYTES - REMOVED_BYTES ))
    if (( AFTER_BYTES < 0 )); then
        AFTER_BYTES=0
    fi

    if (( REMOVED_BYTES > 0 )); then
        echo "  Before: $(human_size "$BEFORE_BYTES")  After: $(human_size "$AFTER_BYTES")  Saved: $(human_size "$REMOVED_BYTES")"
    else
        echo "  Nothing to trim"
    fi

    TOTAL_SAVED=$((TOTAL_SAVED + REMOVED_BYTES))
done

echo ""
if $DRY_RUN; then
    echo "Dry run complete. Would save: $(human_size "$TOTAL_SAVED")"
else
    echo "Done. Total space saved: $(human_size "$TOTAL_SAVED")"
fi
