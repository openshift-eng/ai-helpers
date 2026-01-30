#!/bin/bash

set -euo pipefail

# ci:pr-retest - Find and retest failed e2e CI jobs and payload jobs on a PR
# This is a wrapper that calls both e2e-retest and payload-retest
# Usage: ./pr-retest.sh [repo] <pr-number>

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call e2e-retest
echo "========================================="
echo "E2E JOBS ANALYSIS"
echo "========================================="
echo ""

bash "${SCRIPT_DIR}/../e2e-retest/e2e-retest.sh" "$@"

echo ""
echo ""
echo "========================================="
echo "PAYLOAD JOBS ANALYSIS"
echo "========================================="
echo ""

# Call payload-retest
bash "${SCRIPT_DIR}/../payload-retest/payload-retest.sh" "$@"
