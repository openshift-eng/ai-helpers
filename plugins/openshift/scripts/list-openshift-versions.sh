#!/usr/bin/env bash
# list-openshift-versions.sh - List available OpenShift versions from mirror
# Usage: ./list-openshift-versions.sh [--count N] [--format json|text]

set -euo pipefail

# Default values
COUNT=5
FORMAT="text"
MIRROR_URL="https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --count)
            COUNT="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --help|-h)
            cat <<EOF
Usage: $0 [options]

List available OpenShift versions from the official mirror.

Options:
  --count N         Number of versions to return (default: 5)
  --format FORMAT   Output format: json or text (default: text)
  --help, -h        Show this help message

Examples:
  # List top 5 versions (text)
  $0

  # List top 10 versions
  $0 --count 10

  # Output as JSON
  $0 --format json

  # Get specific version for scripting
  $0 --count 1 --format text

Output formats:
  text: One version per line (e.g., "4.20", "4.19")
  json: JSON array (e.g., ["4.20", "4.19", "4.18"])
EOF
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            echo "Use --help for usage information" >&2
            exit 1
            ;;
    esac
done

# Fetch versions from mirror
VERSIONS=$(curl -sL "$MIRROR_URL" | \
    grep -oE 'href="latest-[^"]*/"' | \
    sed 's/href="latest-//g' | \
    sed 's/\/"//g' | \
    sort -V -r | \
    head -n "$COUNT")

# Check if any versions were found
if [ -z "$VERSIONS" ]; then
    echo "Error: Failed to fetch OpenShift versions from mirror" >&2
    exit 1
fi

# Output in requested format
if [ "$FORMAT" = "json" ]; then
    # Convert to JSON array
    echo "$VERSIONS" | jq -R -s -c 'split("\n") | map(select(length > 0))'
else
    # Text output (one per line)
    echo "$VERSIONS"
fi
