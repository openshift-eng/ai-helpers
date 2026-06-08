#!/bin/bash
set -euo pipefail

# Parse arguments
KUBECONFIG_PATH="${1:-}"
DETAILED="${2:-false}"

# Get the plugin root directory (parent of tools/)
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source common utilities
COMMON_LIB="${PLUGIN_ROOT}/tools/common.sh"
if [ ! -f "${COMMON_LIB}" ]; then
  echo "ERROR: common.sh not found at ${COMMON_LIB}"
  exit 1
fi
source "${COMMON_LIB}"

# Validate kubeconfig
if [ -z "${KUBECONFIG_PATH}" ]; then
    echo "ERROR: Missing required argument: kubeconfig-path"
    echo "Usage: $0 <kubeconfig-path> [--detailed]"
    exit 1
fi

KUBECONFIG_PATH="${KUBECONFIG_PATH/#\~/$HOME}"
if [ ! -f "${KUBECONFIG_PATH}" ]; then
    echo "ERROR: Kubeconfig not found: ${KUBECONFIG_PATH}"
    exit 1
fi

export KUBECONFIG="${KUBECONFIG_PATH}"

# Check for --detailed flag
if [ "${2:-}" == "--detailed" ]; then
    DETAILED="true"
fi

# Source the metadata helper
METADATA_HELPER="${PLUGIN_ROOT}/tools/feature-metadata.sh"
if [ ! -f "${METADATA_HELPER}" ]; then
    echo "ERROR: feature-metadata.sh not found at ${METADATA_HELPER}"
    exit 1
fi
source "${METADATA_HELPER}"

# Get cluster version
echo "=========================================="
echo "DRA Features - Cluster Analysis"
echo "=========================================="
echo ""

# Check cluster connectivity (non-required for offline mode)
CLUSTER_ONLINE=false
if validate_cluster_connectivity "false"; then
    CLUSTER_ONLINE=true
fi

# Get cluster version info if online
if [ "${CLUSTER_ONLINE}" == "true" ]; then
    VERSION_JSON=$(oc version -o json 2>/dev/null)
    OCP_VERSION=$(echo "${VERSION_JSON}" | jq -r '.openshiftVersion // "unknown"')
    K8S_VERSION=$(echo "${VERSION_JSON}" | jq -r '.serverVersion.gitVersion // "unknown"')
    K8S_VERSION_FULL=$(echo "${K8S_VERSION}" | sed -E 's/v(1\.[0-9]+)\..*/\1/')
    K8S_MINOR=$(echo "${K8S_VERSION}" | sed -E 's/v1\.([0-9]+)\..*/\1/')

    echo "Cluster: OCP ${OCP_VERSION}, Kubernetes ${K8S_VERSION}"
    echo ""

    # Check if DRA driver is installed
    DEVICECLASS_COUNT=$(oc get deviceclass --no-headers 2>/dev/null | wc -l || echo "0")
    if [ "${DEVICECLASS_COUNT}" -gt 0 ]; then
        DRIVER_NAME=$(oc get deviceclass -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        echo "DRA Driver: ✓ Installed (${DRIVER_NAME})"
    else
        echo "DRA Driver: ✗ Not installed"
    fi
else
    echo "Cluster: ⚠ Offline (cluster unavailable)"
    echo "Mode: Displaying feature metadata only"
    K8S_MINOR="36"  # Default to latest supported version for offline mode
    K8S_VERSION_FULL="1.36"  # Default for offline mode
    K8S_VERSION="v1.36.0"  # Default for offline mode
    echo ""
fi

echo ""
echo "=========================================="
echo "Available DRA Features"
echo "=========================================="
echo ""

# Get all features
FEATURES=$(list_all_features)

# Header for table
printf "%-20s %-12s %-10s %-15s %-30s\n" "FEATURE" "GRADUATION" "MIN K8S" "GATE STATUS" "DESCRIPTION"
printf "%-20s %-12s %-10s %-15s %-30s\n" "-------" "----------" "-------" "-----------" "-----------"

# Iterate through features
for feature in ${FEATURES}; do
    # Get feature metadata
    FEATURE_NAME=$(get_feature_name "${feature}" 2>/dev/null || echo "Unknown")
    DESCRIPTION=$(get_feature_description "${feature}" 2>/dev/null || echo "")
    MIN_VERSION=$(get_min_k8s_version "${feature}" 2>/dev/null || echo "N/A")

    # Check if feature is available on this cluster
    if is_feature_available "${feature}" "${K8S_MINOR}" 2>/dev/null; then
        # Get graduation level for current K8s version
        GRADUATION=$(get_feature_graduation "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null || echo "unavailable")

        # Check feature gate status
        GATE_STATUS=$(check_feature_gate_status "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null || echo "unknown")

        case "${GATE_STATUS}" in
            enabled)
                GATE_DISPLAY="✓ Enabled"
                ;;
            ga_always_enabled)
                GATE_DISPLAY="✓ GA (always)"
                ;;
            no_gate_required)
                GATE_DISPLAY="N/A"
                ;;
            not_enabled:alpha)
                GATE_DISPLAY="✗ Not enabled"
                ;;
            not_enabled:beta)
                GATE_DISPLAY="⚠ Check needed"
                ;;
            feature_unavailable)
                GATE_DISPLAY="N/A (old K8s)"
                ;;
            *)
                GATE_DISPLAY="Unknown"
                ;;
        esac

        # Color code graduation level
        case "${GRADUATION}" in
            alpha)
                GRAD_DISPLAY="Alpha"
                ;;
            beta)
                GRAD_DISPLAY="Beta"
                ;;
            ga)
                GRAD_DISPLAY="GA"
                ;;
            *)
                GRAD_DISPLAY="${GRADUATION}"
                ;;
        esac
    else
        GRAD_DISPLAY="N/A"
        GATE_DISPLAY="N/A (K8s < ${MIN_VERSION})"
    fi

    # Truncate description for table view
    DESC_SHORT=$(echo "${DESCRIPTION}" | cut -c1-30)
    if [ ${#DESCRIPTION} -gt 30 ]; then
        DESC_SHORT="${DESC_SHORT}..."
    fi

    printf "%-20s %-12s %-10s %-15s %-30s\n" \
        "${feature}" "${GRAD_DISPLAY}" "${MIN_VERSION}" "${GATE_DISPLAY}" "${DESC_SHORT}"
done

echo ""

# Detailed view
if [ "${DETAILED}" == "true" ]; then
    echo "=========================================="
    echo "Detailed Feature Information"
    echo "=========================================="
    echo ""

    for feature in ${FEATURES}; do
        # Check if available
        if ! is_feature_available "${feature}" "${K8S_MINOR}" 2>/dev/null; then
            continue
        fi

        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Feature: ${feature}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        FEATURE_NAME=$(get_feature_name "${feature}" 2>/dev/null)
        DESCRIPTION=$(get_feature_description "${feature}" 2>/dev/null)
        MIN_VERSION=$(get_min_k8s_version "${feature}" 2>/dev/null)
        GRADUATION=$(get_feature_graduation "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null)

        echo "Name:        ${FEATURE_NAME}"
        echo "Description: ${DESCRIPTION}"
        echo "Min K8s:     ${MIN_VERSION}"
        echo "Graduation:  ${GRADUATION} (on K8s ${K8S_VERSION_FULL})"

        # Feature gate info
        GATE_NAME=$(get_feature_gate "${feature}" 2>/dev/null)
        if [ "${GATE_NAME}" != "null" ] && [ -n "${GATE_NAME}" ]; then
            echo "Feature Gate: ${GATE_NAME}"

            GATE_STATUS=$(check_feature_gate_status "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null || true)
            case "${GATE_STATUS}" in
                enabled)
                    echo "Gate Status:  ✓ Enabled in cluster"
                    ;;
                not_enabled:alpha)
                    echo "Gate Status:  ✗ Not enabled (Alpha - requires enablement)"
                    echo ""
                    echo "To enable:"
                    ENABLE_CMD=$(get_enablement_command "${feature}" 2>/dev/null | sed 's/^/  /')
                    echo "${ENABLE_CMD}"
                    ;;
                not_enabled:beta)
                    echo "Gate Status:  ⚠ Not enabled (Beta - may need CustomNoUpgrade)"
                    echo ""
                    echo "To enable:"
                    ENABLE_CMD=$(get_enablement_command "${feature}" 2>/dev/null | sed 's/^/  /')
                    echo "${ENABLE_CMD}"
                    ;;
                ga_always_enabled)
                    echo "Gate Status:  ✓ Always enabled (GA)"
                    ;;
            esac
        else
            echo "Feature Gate: None (Beta by default)"
        fi

        # Setup flags
        SETUP_FLAGS=$(get_setup_flags "${feature}" 2>/dev/null)
        if [ -n "${SETUP_FLAGS}" ]; then
            echo "Setup Flags:  ${SETUP_FLAGS}"
        fi

        # Test script
        TEST_SCRIPT=$(get_test_script "${feature}" 2>/dev/null)
        if [ -n "${TEST_SCRIPT}" ]; then
            TEST_BASENAME=$(basename "${TEST_SCRIPT}")
            echo "Test Script:  ${TEST_BASENAME}"
        fi

        echo ""
    done
fi

echo "=========================================="
echo "Summary"
echo "=========================================="

# Count features by graduation level
ALPHA_COUNT=0
BETA_COUNT=0
GA_COUNT=0
UNAVAILABLE_COUNT=0

for feature in ${FEATURES}; do
    if is_feature_available "${feature}" "${K8S_MINOR}" 2>/dev/null; then
        GRADUATION=$(get_feature_graduation "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null)
        case "${GRADUATION}" in
            alpha) ALPHA_COUNT=$((ALPHA_COUNT + 1)) ;;
            beta) BETA_COUNT=$((BETA_COUNT + 1)) ;;
            ga) GA_COUNT=$((GA_COUNT + 1)) ;;
        esac
    else
        UNAVAILABLE_COUNT=$((UNAVAILABLE_COUNT + 1))
    fi
done

echo "Features available on K8s ${K8S_VERSION}:"
echo "  Alpha: ${ALPHA_COUNT}"
echo "  Beta:  ${BETA_COUNT}"
echo "  GA:    ${GA_COUNT}"
if [ ${UNAVAILABLE_COUNT} -gt 0 ]; then
    echo "  Unavailable (K8s too old): ${UNAVAILABLE_COUNT}"
fi

echo ""
echo "Commands:"
echo "  • View detailed info:  /dra-ocp-validator:list-features ${KUBECONFIG_PATH} --detailed"
echo "  • Setup DRA driver:    /dra-ocp-validator:setup ${KUBECONFIG_PATH}"
echo "  • Run tests:           /dra-ocp-validator:test ${KUBECONFIG_PATH}"

exit 0
