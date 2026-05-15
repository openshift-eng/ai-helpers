#!/bin/bash
# compress-archives.sh — compress/decompress payload archive directories as .tar.gz
#
# Default mode: finds uncompressed directories in the archives dir, creates
# {tag}.tar.gz alongside each, then removes the directory.
#
# Decompress mode (--decompress): finds .tar.gz files without a corresponding
# directory and extracts them.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCHIVES_DIR="${SCRIPT_DIR}/../../archives"
KEEP=false
DECOMPRESS=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Compress or decompress payload archive directories.

Options:
  --archives-dir DIR   Archive root directory (default: ../../archives relative to script)
  --keep               Preserve uncompressed directories after compression
  --decompress         Extract .tar.gz files that lack a corresponding directory
  -h, --help           Show this help message

Default mode compresses uncompressed directories into .tar.gz files.
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --archives-dir)
            ARCHIVES_DIR="$2"
            shift 2
            ;;
        --keep)
            KEEP=true
            shift
            ;;
        --decompress)
            DECOMPRESS=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

ARCHIVES_DIR="$(cd "$ARCHIVES_DIR" 2>/dev/null && pwd)" || {
    echo "ERROR: archives directory does not exist: $ARCHIVES_DIR" >&2
    exit 1
}

human_size() {
    local bytes="$1"
    if command -v numfmt &>/dev/null; then
        numfmt --to=iec --suffix=B "$bytes"
    else
        echo "${bytes} bytes"
    fi
}

dir_size() {
    du -sb "$1" 2>/dev/null | cut -f1
}

file_size() {
    stat --format='%s' "$1" 2>/dev/null || stat -f '%z' "$1" 2>/dev/null
}

if $DECOMPRESS; then
    echo "=== Decompressing archives in $ARCHIVES_DIR ==="
    found=0
    for tarball in "$ARCHIVES_DIR"/*.tar.gz; do
        [[ -f "$tarball" ]] || continue
        tag="$(basename "$tarball" .tar.gz)"
        target_dir="$ARCHIVES_DIR/$tag"

        if [[ -d "$target_dir" ]]; then
            echo "SKIP: $tag (directory already exists)"
            continue
        fi

        found=$((found + 1))
        compressed_size="$(file_size "$tarball")"
        echo -n "Extracting $tag ($(human_size "$compressed_size"))... "
        tar xzf "$tarball" -C "$ARCHIVES_DIR"
        extracted_size="$(dir_size "$target_dir")"
        echo "done ($(human_size "$extracted_size"))"
    done

    if [[ $found -eq 0 ]]; then
        echo "Nothing to decompress."
    fi
    exit 0
fi

# Default mode: compress
echo "=== Compressing archives in $ARCHIVES_DIR ==="
found=0
for dir in "$ARCHIVES_DIR"/*/; do
    [[ -d "$dir" ]] || continue
    tag="$(basename "$dir")"
    tarball="$ARCHIVES_DIR/$tag.tar.gz"

    if [[ -f "$tarball" ]]; then
        echo "SKIP: $tag (tar.gz already exists)"
        continue
    fi

    found=$((found + 1))
    before_size="$(dir_size "$dir")"
    echo -n "Compressing $tag ($(human_size "$before_size"))... "
    tar czf "$tarball" -C "$ARCHIVES_DIR" "$tag"
    after_size="$(file_size "$tarball")"
    echo "done ($(human_size "$before_size") -> $(human_size "$after_size"))"

    if ! $KEEP; then
        rm -rf "$dir"
        echo "  Removed uncompressed directory"
    fi
done

if [[ $found -eq 0 ]]; then
    echo "Nothing to compress."
fi
