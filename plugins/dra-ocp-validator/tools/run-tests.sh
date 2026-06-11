#!/usr/bin/env bash
# DRA OCP Validator - Test runner (assumes setup already done)
# Runs DRA feature tests on a cluster with prerequisites already installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "${SCRIPT_DIR}")"

# Source common utilities
if [ -f "${SCRIPT_DIR}/common.sh" ]; then
    source "${SCRIPT_DIR}/common.sh"
fi

# Parse arguments
KUBECONFIG_PATH=""
FEATURES="all"
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --features)
      FEATURES="${2}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2}"
      shift 2
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
  OUTPUT_DIR="./dra-test-$(date +%Y%m%d-%H%M%S)"
fi

mkdir -p "${OUTPUT_DIR}"

echo "========================================="
echo "DRA OCP Validator - Test Suite"
echo "========================================="
echo ""

# Step 1: Verify cluster access
echo "=== Step 1: Cluster verification ==="

if ! validate_cluster_connectivity "true"; then
  exit 1
fi

# Extract cluster info
OCP_VERSION=$(oc version -o json | jq -r '.openshiftVersion // "unknown"')
K8S_VERSION=$(oc version -o json | jq -r '.serverVersion.gitVersion // "unknown"')

echo "✓ Cluster accessible (OCP ${OCP_VERSION}, K8s ${K8S_VERSION})"
echo ""

# Step 2: Verify DRA driver is installed
echo "=== Step 2: DRA driver verification ==="

DEVICECLASS_COUNT=$(oc get deviceclass --no-headers 2>/dev/null | wc -l || echo "0")
RESOURCESLICE_COUNT=$(oc get resourceslice --no-headers 2>/dev/null | wc -l || echo "0")

if [ "${DEVICECLASS_COUNT}" -eq 0 ]; then
  echo "❌ ERROR: No DeviceClass found - DRA driver not installed"
  echo ""
  echo "Please run setup first:"
  echo "  /dra-ocp-validator:setup ${KUBECONFIG_PATH}"
  exit 1
fi

DEVICECLASS_NAME=$(oc get deviceclass -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

echo "✓ DRA driver ready (DeviceClass: ${DEVICECLASS_NAME}, ResourceSlices: ${RESOURCESLICE_COUNT})"
echo ""

# Step 3: Detect available features based on K8s version
echo "=== Step 3: Feature detection ==="

# Source the feature metadata helper first
METADATA_HELPER="${SCRIPT_DIR}/feature-metadata.sh"
if [ ! -f "${METADATA_HELPER}" ]; then
  echo "❌ ERROR: feature-metadata.sh not found at ${METADATA_HELPER}"
  exit 1
fi
source "${METADATA_HELPER}"

K8S_MINOR=$(echo "${K8S_VERSION}" | sed -E 's/v1\.([0-9]+)\..*/\1/')
K8S_VERSION_NORMALIZED="1.${K8S_MINOR}"

# Use metadata system to discover available features
# Note: is_feature_available expects minor version number only (e.g., "35")
# get_feature_graduation expects full version (e.g., "1.35")
AVAILABLE_FEATURES=()
for feature in $(list_all_features); do
  if is_feature_available "${feature}" "${K8S_MINOR}" 2>/dev/null; then
    AVAILABLE_FEATURES+=("${feature}")
  fi
done

echo "Available features on K8s ${K8S_VERSION}: ${AVAILABLE_FEATURES[*]}"
echo ""

# Parse features to test
TEST_FEATURES=()
ALPHA_FEATURES_REQUESTED=()

if [ "${FEATURES}" = "all" ]; then
  # Default: Only test Beta + GA features (exclude Alpha)
  echo "Default mode: Testing Beta and GA features only"
  for feature in "${AVAILABLE_FEATURES[@]}"; do
    graduation=$(get_feature_graduation "${feature}" "${K8S_VERSION_NORMALIZED}")
    if [ "${graduation}" != "alpha" ]; then
      TEST_FEATURES+=("${feature}")
    fi
  done
else
  # User specified features - check for Alpha features
  IFS=',' read -ra REQUESTED_FEATURES <<< "${FEATURES}"
  for feature in "${REQUESTED_FEATURES[@]}"; do
    if [[ " ${AVAILABLE_FEATURES[@]} " =~ " ${feature} " ]]; then
      graduation=$(get_feature_graduation "${feature}" "${K8S_VERSION_NORMALIZED}")
      if [ "${graduation}" = "alpha" ]; then
        ALPHA_FEATURES_REQUESTED+=("${feature}")
      else
        TEST_FEATURES+=("${feature}")
      fi
    else
      echo "⚠ Feature '${feature}' not available on K8s ${K8S_VERSION} - skipping"
    fi
  done
fi

# Error out if Alpha features requested
if [ ${#ALPHA_FEATURES_REQUESTED[@]} -gt 0 ]; then
  echo ""
  echo "❌ ERROR: Alpha features requested but not enabled"
  echo ""
  echo "The following Alpha features require feature gate enablement:"
  for feature in "${ALPHA_FEATURES_REQUESTED[@]}"; do
    gate_name=$(get_feature_gate "${feature}")
    echo "  - ${feature} → requires '${gate_name}' feature gate"
  done
  echo ""
  echo "⚠️  IMPORTANT: OpenShift only allows ONE featureset at a time:"
  echo "  - TechPreviewNoUpgrade (for officially supported tech preview features)"
  echo "  - CustomNoUpgrade (for upstream Alpha features not in downstream)"
  echo ""
  echo "You cannot enable features from different featuresets simultaneously."
  echo ""
  echo "To enable Alpha features, you must:"
  echo "  1. Determine which featureset each feature requires"
  echo "  2. Choose features from the SAME featureset"
  echo "  3. Enable the feature gate(s) manually via:"
  echo ""
  echo "     For TechPreviewNoUpgrade (e.g., DRAPartitionableDevices):"
  echo "       oc patch featuregate cluster --type=merge \\"
  echo "         -p '{\"spec\":{\"featureSet\":\"TechPreviewNoUpgrade\"}}'"
  echo ""
  echo "     For CustomNoUpgrade (e.g., DRADeviceTaints, DRAConsumableCapacity):"
  echo "       oc patch featuregate cluster --type=merge \\"
  echo "         -p '{\"spec\":{\"customNoUpgrade\":{\"enabled\":[\"<GATE_NAME>\"]}}}'"
  echo ""
  echo "  4. Re-run setup if driver configuration is needed:"
  echo "       /dra-ocp-validator:setup ${KUBECONFIG_PATH} [--enable-dynamic-mig]"
  echo ""
  echo "  5. Re-run tests with the same --features flag"
  echo ""
  exit 1
fi

echo "Features to test: ${TEST_FEATURES[*]}"
echo ""

# Step 3.5: Check feature prerequisites and filter out features that can't run
echo "=== Step 3.5: Checking feature prerequisites ==="

RUNNABLE_FEATURES=()
SKIPPED_FEATURES=()

for feature in "${TEST_FEATURES[@]}"; do
  SKIP_REASON=""

  # Use metadata-driven prerequisite checking if available
  if declare -f get_feature_gate > /dev/null 2>&1; then
    # Get K8s version for graduation detection
    K8S_VERSION_FULL=$(echo "${K8S_VERSION}" | sed -E 's/v(1\.[0-9]+)\..*/\1/')

    # Check feature gate status based on graduation level
    GATE_STATUS=$(check_feature_gate_status "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null || echo "error")

    case "${GATE_STATUS}" in
      enabled|ga_always_enabled|no_gate_required)
        # Feature gate satisfied, check additional prerequisites
        case "${feature}" in
          partitionable)
            # Check if driver has partition support via dual-check:
            # Primary: SharedCounters (KEP-4815 partitionable devices)
            # Fallback: Driver-specific partition configuration
            #   - NVIDIA: DynamicMIG feature gate + MIG devices present
            #   - Example: gpuPartitions > 0

            # Check for SharedCounters
            SLICES_WITH_COUNTERS=$(oc get resourceslice -o json 2>/dev/null | \
              jq -r '.items[] | select(.spec.sharedCounters != null) | .metadata.name' | wc -l || echo "0")

            PARTITION_CONFIGURED=false

            # Detect driver type and check partition configuration
            if helm list -n nvidia-dra-driver 2>/dev/null | grep -q nvidia-dra-driver; then
              # NVIDIA driver - check DynamicMIG feature gate
              DYNAMIC_MIG_VALUE=$(helm get values nvidia-dra-driver -n nvidia-dra-driver -o json 2>/dev/null | \
                jq -r '.featureGates.DynamicMIG // false')
              MIG_DEVICES=$(oc get resourceslice -o json 2>/dev/null | \
                jq -r '.items[].spec.devices[]? | select(.name | contains("mig")) | .name' | wc -l || echo "0")

              if [ "${DYNAMIC_MIG_VALUE}" = "true" ] && [ "${MIG_DEVICES}" -gt 0 ]; then
                PARTITION_CONFIGURED=true
                echo "  ℹ ${feature}: NVIDIA DynamicMIG enabled, ${MIG_DEVICES} MIG devices detected"
              fi
            elif helm list -n dra-example-driver 2>/dev/null | grep -q dra-example-driver; then
              # Example driver - check gpuPartitions value
              GPU_PARTITIONS=$(helm get values dra-example-driver -n dra-example-driver -o json 2>/dev/null | \
                jq -r '.kubeletPlugin.gpuPartitions // 0')

              if [ "${GPU_PARTITIONS}" -gt 0 ]; then
                PARTITION_CONFIGURED=true
                echo "  ℹ ${feature}: Example driver gpuPartitions=${GPU_PARTITIONS}"
              fi
            fi

            # Determine if partition support is available
            if [ "${SLICES_WITH_COUNTERS}" -eq 0 ]; then
              # SharedCounters not present - check fallback indicators
              if [ "${PARTITION_CONFIGURED}" = true ]; then
                # Driver partition config detected - consider it configured
                echo "  ℹ Note: SharedCounters not populated in ResourceSlice (may populate after first claim)"
              else
                GRADUATION=$(get_feature_graduation "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null || echo "unknown")
                SKIP_REASON="Driver does not have partition support (${GRADUATION} feature, use --enable-dynamic-mig during setup)"
              fi
            fi
            ;;
        esac
        ;;

      not_enabled:alpha)
        GATE_NAME=$(get_feature_gate "${feature}")
        SKIP_REASON="${GATE_NAME} feature gate not enabled (Alpha feature - requires explicit enablement)"
        ;;

      not_enabled:beta)
        GATE_NAME=$(get_feature_gate "${feature}")
        SKIP_REASON="${GATE_NAME} feature gate not enabled (Beta feature - use --enable-dynamic-mig during setup)"
        ;;

      feature_unavailable)
        SKIP_REASON="Feature not available in K8s ${K8S_VERSION}"
        ;;

      error)
        # Metadata helper error, fall back to legacy checks
        SKIP_REASON=""
        ;;
    esac
  fi

  if [ -n "${SKIP_REASON}" ]; then
    SKIPPED_FEATURES+=("${feature}")
    echo "  ⚠ ${feature}: Prerequisites not met - ${SKIP_REASON}"
  else
    RUNNABLE_FEATURES+=("${feature}")
  fi
done

echo ""

# Update TEST_FEATURES to only include runnable features
TEST_FEATURES=("${RUNNABLE_FEATURES[@]}")

# Step 4: Run feature tests
echo "=== Step 4: Running tests ==="
echo ""

PASSED=0
FAILED=0
SKIPPED=0
PASSED_FEATURES=()
FAILED_FEATURES=()

for feature in "${TEST_FEATURES[@]}"; do
  # Get test script path and feature name from metadata
  TEST_SCRIPT=$(get_test_script "${feature}" 2>/dev/null || echo "")
  TEST_NAME=$(get_feature_name "${feature}" 2>/dev/null || echo "${feature}")

  if [ -z "${TEST_SCRIPT}" ] || [ ! -f "${TEST_SCRIPT}" ]; then
    echo "  ⚠ ${TEST_NAME}: SKIP (test not found: ${TEST_SCRIPT})"
    ((SKIPPED++))
    continue
  fi

  echo "Testing: ${TEST_NAME}..."

  TEST_OUTPUT="${OUTPUT_DIR}/${feature}-test.log"

  if "${TEST_SCRIPT}" "${KUBECONFIG_PATH}" > "${TEST_OUTPUT}" 2>&1; then
    echo "  ✅ ${TEST_NAME}: PASS"
    PASSED=$((PASSED + 1))
    PASSED_FEATURES+=("${feature}")
  else
    EXIT_CODE=$?
    echo "  ❌ ${TEST_NAME}: FAIL (exit code: ${EXIT_CODE})"
    echo "     See: ${TEST_OUTPUT}"
    FAILED=$((FAILED + 1))
    FAILED_FEATURES+=("${feature}")
  fi
done

echo ""

# Step 5: Collect artifacts
echo "=== Step 5: Collecting artifacts ==="

"${SCRIPT_DIR}/collect-artifacts.sh" "${KUBECONFIG_PATH}" "${OUTPUT_DIR}"

echo "✓ Artifacts collected: ${OUTPUT_DIR}/"
echo ""

# Summary
echo "========================================="
echo "Testing Complete!"
echo "========================================="
echo ""
echo "Results:"
echo "  ✅ Passed:  ${PASSED}"
echo "  ❌ Failed:  ${FAILED}"
echo "  ⚠ Skipped: ${SKIPPED} (prerequisite checks) + ${#SKIPPED_FEATURES[@]} (feature gates)"
echo ""

# List passed features
if [ ${#PASSED_FEATURES[@]} -gt 0 ]; then
  echo "Passed (${#PASSED_FEATURES[@]}):"
  for feature in "${PASSED_FEATURES[@]}"; do
    FEATURE_NAME=$(get_feature_name "${feature}" 2>/dev/null || echo "${feature}")
    echo "  ✅ ${feature} - ${FEATURE_NAME}"
  done
  echo ""
fi

# List failed features
if [ ${#FAILED_FEATURES[@]} -gt 0 ]; then
  echo "Failed (${#FAILED_FEATURES[@]}):"
  for feature in "${FAILED_FEATURES[@]}"; do
    FEATURE_NAME=$(get_feature_name "${feature}" 2>/dev/null || echo "${feature}")
    echo "  ❌ ${feature} - ${FEATURE_NAME}"
  done
  echo ""
fi

# List skipped features with reasons
if [ "${#SKIPPED_FEATURES[@]}" -gt 0 ]; then
  echo "Skipped (${#SKIPPED_FEATURES[@]}) - Prerequisites not met:"
  for feature in "${SKIPPED_FEATURES[@]}"; do
    FEATURE_NAME=$(get_feature_name "${feature}" 2>/dev/null || echo "${feature}")
    echo "  ⚠ ${feature} - ${FEATURE_NAME}"
  done
  echo ""
fi

echo "Total: $((PASSED + FAILED + SKIPPED + ${#SKIPPED_FEATURES[@]})) features processed"
echo ""

if [ "${FAILED}" -gt 0 ]; then
  echo "⚠ Some tests failed - see logs in ${OUTPUT_DIR}/"
  echo ""
  echo "For detailed failure analysis, check:"
  for feature in "${FAILED_FEATURES[@]}"; do
    LOG_FILE=$(find "${OUTPUT_DIR}" -name "*${feature}*test.log" -o -name "*${feature}*output.log" 2>/dev/null | head -1)
    if [ -n "${LOG_FILE}" ]; then
      echo "  • ${feature}: ${LOG_FILE}"
    fi
  done
  echo ""
  exit 1
else
  echo "✓ All tests passed or skipped with valid reasons"
  echo ""
  echo "Next steps:"
  echo "  1. Review artifacts: ${OUTPUT_DIR}/"
  echo "  2. Clean up: /dra-ocp-validator:cleanup ${KUBECONFIG_PATH}"
  exit 0
fi
