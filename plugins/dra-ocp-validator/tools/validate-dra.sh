#!/usr/bin/env bash
# DRA OCP Validator - Full validation workflow
# Orchestrates setup, testing, and reporting for comprehensive DRA validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common utilities
if [ -f "${SCRIPT_DIR}/common.sh" ]; then
    source "${SCRIPT_DIR}/common.sh"
fi

# Parse arguments
KUBECONFIG_PATH=""
SETUP_ARGS=()
TEST_ARGS=()
SKIP_INSTALL=false
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --skip-install)
      SKIP_INSTALL=true
      shift
      ;;
    --output-dir)
      OUTPUT_DIR="${2}"
      TEST_ARGS+=("${1}" "${2}")
      shift 2
      ;;
    --features)
      TEST_ARGS+=("${1}" "${2}")
      shift 2
      ;;
    --driver|--enable-dynamic-mig|--driver-version|--skip-nfd)
      SETUP_ARGS+=("${1}")
      if [[ "${1}" == "--driver" || "${1}" == "--driver-version" ]]; then
        SETUP_ARGS+=("${2}")
        shift
      fi
      shift
      ;;
    *)
      if [ -z "${KUBECONFIG_PATH}" ]; then
        KUBECONFIG_PATH="${1}"
      else
        echo "ERROR: Unknown argument: ${1}"
        exit 1
      fi
      shift
      ;;
  esac
done

# Validate required arguments
if [ -z "${KUBECONFIG_PATH}" ]; then
  echo "ERROR: Missing required argument: kubeconfig-path"
  echo "Usage: $0 <kubeconfig-path> [options]"
  exit 1
fi

# Expand tilde
KUBECONFIG_PATH="${KUBECONFIG_PATH/#\~/$HOME}"

# Validate kubeconfig exists
if [ ! -f "${KUBECONFIG_PATH}" ]; then
  echo "ERROR: Kubeconfig not found: ${KUBECONFIG_PATH}"
  exit 1
fi

export KUBECONFIG="${KUBECONFIG_PATH}"

# Set output directory
if [ -z "${OUTPUT_DIR}" ]; then
  OUTPUT_DIR="./dra-validation-$(date +%Y%m%d-%H%M%S)"
fi

mkdir -p "${OUTPUT_DIR}"

echo "========================================="
echo "DRA OCP Validator - Full Validation"
echo "========================================="
echo ""

# Step 1: Verify cluster access
echo "=== Step 1: Cluster verification ==="

if ! validate_cluster_connectivity "true"; then
  exit 1
fi

OCP_VERSION=$(oc version -o json | jq -r '.openshiftVersion // "unknown"')
K8S_VERSION=$(oc version -o json | jq -r '.serverVersion.gitVersion // "unknown"')
echo "✓ Cluster accessible (OCP ${OCP_VERSION}, K8s ${K8S_VERSION})"
echo ""

# Step 2: Setup (unless skipped)
if [ "${SKIP_INSTALL}" = false ]; then
  echo "=== Step 2: Installing DRA stack ==="
  "${SCRIPT_DIR}/setup-dra.sh" "${KUBECONFIG_PATH}" "${SETUP_ARGS[@]}" | tee "${OUTPUT_DIR}/setup.log"
  echo ""
else
  echo "=== Step 2: Skipped (--skip-install) ==="
  echo ""
fi

# Step 3: Run tests (delegates to run-tests.sh)
echo "=== Step 3: Running tests ==="
if "${SCRIPT_DIR}/run-tests.sh" "${KUBECONFIG_PATH}" --output-dir "${OUTPUT_DIR}" "${TEST_ARGS[@]}"; then
  TEST_EXIT=0
else
  TEST_EXIT=$?
fi
echo ""

# Step 4: Create tarball
echo "=== Step 4: Packaging results ==="
TARBALL="${OUTPUT_DIR}.tar.gz"
tar -czf "${TARBALL}" -C "$(dirname "${OUTPUT_DIR}")" "$(basename "${OUTPUT_DIR}")"
TARBALL_SIZE=$(du -h "${TARBALL}" | cut -f1)
echo "✓ Tarball created: ${TARBALL} (${TARBALL_SIZE})"
echo ""

# Summary
echo "========================================="
echo "Validation Complete!"
echo "========================================="
echo ""

if [ "${TEST_EXIT}" -ne 0 ]; then
  echo "⚠ Some tests failed - see logs in ${OUTPUT_DIR}/"
  exit 1
else
  echo "✓ All tests passed or skipped with valid reasons"
  echo ""
  echo "Next steps:"
  echo "  1. Review: ${OUTPUT_DIR}/"
  echo "  2. Cleanup: /dra-ocp-validator:cleanup ${KUBECONFIG_PATH}"
  exit 0
fi
