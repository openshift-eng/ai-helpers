#!/bin/bash
# Cleanup script for DRA drivers (NVIDIA or example) and test resources
# Auto-detects installed driver type

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common utilities
if [ -f "${SCRIPT_DIR}/common.sh" ]; then
    source "${SCRIPT_DIR}/common.sh"
fi

KUBECONFIG_PATH=$1
# Default: full cleanup (remove everything)
REMOVE_DRIVER="true"
REMOVE_OPERATOR="true"
FORCE="false"

# Parse flags from all arguments after kubeconfig
shift  # Remove kubeconfig path
for arg in "$@"; do
    case "$arg" in
        --keep-driver) REMOVE_DRIVER="false" ;;
        --keep-operator) REMOVE_OPERATOR="false" ;;
        --force) FORCE="true" ;;
    esac
done

export KUBECONFIG=${KUBECONFIG_PATH}

echo "========================================="
echo "DRA OCP Validator - Cleanup"
echo "========================================="
echo ""

# Verify required tools
for cmd in oc kubectl; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: Required command not found: $cmd"
        exit 1
    fi
done

# Verify cluster connectivity
if ! validate_cluster_connectivity "true"; then
  exit 1
fi

#=========================================
# Step 1: Clean up test namespaces
#=========================================
echo "=== Step 1: Clean up test namespaces ==="

TEST_NAMESPACES=$(oc get namespaces -o name 2>/dev/null | \
    grep 'namespace/dra-' | \
    grep -v 'namespace/dra-example-driver' | \
    grep -v 'namespace/dra-nvidia-driver' | \
    sed 's|namespace/||' || true)

if [ -z "${TEST_NAMESPACES}" ]; then
    echo "No test namespaces found"
else
    echo "Found test namespaces:"
    echo "${TEST_NAMESPACES}" | sed 's/^/  - /'
    echo ""

    echo "Deleting test namespaces..."
    for ns in ${TEST_NAMESPACES}; do
        oc delete namespace ${ns} --wait=false 2>/dev/null && echo "  ✓ ${ns} deleted" || echo "  ⚠ ${ns} failed to delete"
    done
fi

echo ""

#=========================================
# Step 2: Detect and remove DRA driver (if requested)
#=========================================
if [ "${REMOVE_DRIVER}" == "true" ] || [ "${REMOVE_DRIVER}" == "--remove-driver" ]; then
    echo "=== Step 2: Detect and remove DRA driver ==="
    echo ""

    # Detect which driver is installed with multi-layer verification
    DRIVER_TYPE="none"
    DRIVER_NAMESPACE=""
    DRIVER_RELEASE=""

    # Cache helm list results if helm is available
    HELM_AVAILABLE=false
    HELM_NVIDIA_LIST=""
    HELM_EXAMPLE_LIST=""
    if command -v helm &>/dev/null; then
        HELM_AVAILABLE=true
        HELM_NVIDIA_LIST=$(helm list -n nvidia-dra-driver 2>/dev/null || true)
        HELM_EXAMPLE_LIST=$(helm list -n dra-example-driver 2>/dev/null || true)
    fi

    # Function: Detect NVIDIA DRA driver (namespace + at least one confirming resource)
    detect_nvidia_driver() {
        # Layer 1: Check namespace exists
        if ! oc get namespace nvidia-dra-driver &>/dev/null; then
            return 1
        fi

        # Layer 2: Confirm with deeper checks (any one proves it's real)
        # Check Helm release (using cached result)
        if [ "${HELM_AVAILABLE}" == "true" ] && echo "${HELM_NVIDIA_LIST}" | grep -q nvidia-dra-driver; then
            return 0
        fi

        # Check DeviceClass with NVIDIA pattern
        if oc get deviceclass 2>/dev/null | grep -q 'nvidia.com/'; then
            return 0
        fi

        # Check DaemonSet in namespace
        if oc get daemonset -n nvidia-dra-driver 2>/dev/null | grep -q nvidia-dra; then
            return 0
        fi

        # Check for driver pods
        if oc get pods -n nvidia-dra-driver --no-headers 2>/dev/null | grep -q nvidia-dra; then
            return 0
        fi

        # Namespace exists but no confirming resources
        echo "  ⚠ Found nvidia-dra-driver namespace but no driver resources - skipping"
        return 1
    }

    # Function: Detect example DRA driver (namespace + at least one confirming resource)
    detect_example_driver() {
        # Layer 1: Check namespace exists
        if ! oc get namespace dra-example-driver &>/dev/null; then
            return 1
        fi

        # Layer 2: Confirm with deeper checks (any one proves it's real)
        # Check Helm release (using cached result)
        if [ "${HELM_AVAILABLE}" == "true" ] && echo "${HELM_EXAMPLE_LIST}" | grep -q dra-example-driver; then
            return 0
        fi

        # Check DeviceClass with example pattern
        if oc get deviceclass 2>/dev/null | grep -qE '(example.com/|dra.example.com/)'; then
            return 0
        fi

        # Check Deployment in namespace
        if oc get deployment -n dra-example-driver 2>/dev/null | grep -q dra-example-driver; then
            return 0
        fi

        # Check for controller pods
        if oc get pods -n dra-example-driver --no-headers 2>/dev/null | grep -q example; then
            return 0
        fi

        # Namespace exists but no confirming resources
        echo "  ⚠ Found dra-example-driver namespace but no driver resources - skipping"
        return 1
    }

    # Detect drivers with robust checks
    if detect_example_driver; then
        DRIVER_TYPE="example"
        DRIVER_NAMESPACE="dra-example-driver"
        DRIVER_RELEASE="dra-example-driver"
        echo "Detected: dra-example-driver (verified)"
    fi

    if detect_nvidia_driver; then
        DRIVER_TYPE="nvidia"
        DRIVER_NAMESPACE="nvidia-dra-driver"
        DRIVER_RELEASE="nvidia-dra-driver"
        echo "Detected: NVIDIA DRA driver (verified)"
    fi

    # Check for GPU operator (NVIDIA) - multi-layer verification
    if oc get namespace nvidia-gpu-operator &>/dev/null; then
        # Verify with ClusterPolicy or Subscription
        if oc get clusterpolicy 2>/dev/null | grep -q cluster-policy || \
           oc get subscription -n nvidia-gpu-operator 2>/dev/null | grep -q gpu-operator; then
            if [ "${DRIVER_TYPE}" == "none" ]; then
                DRIVER_TYPE="nvidia-operator"
            fi
            echo "Detected: NVIDIA GPU Operator (verified)"
        else
            echo "  ⚠ Found nvidia-gpu-operator namespace but no operator resources - skipping"
        fi
    fi

    if [ "${DRIVER_TYPE}" == "none" ]; then
        echo "ℹ No DRA driver installation detected"
        echo ""
        echo "Checked namespaces:"
        echo "  - dra-example-driver (not found or no resources)"
        echo "  - nvidia-dra-driver (not found or no resources)"
        echo "  - nvidia-gpu-operator (not found or no resources)"
    else
        echo ""
        echo "Driver type: ${DRIVER_TYPE}"
        echo "Namespace: ${DRIVER_NAMESPACE}"
        echo ""
        echo "Uninstalling ${DRIVER_TYPE} driver..."
        echo ""

        # Helper functions
        uninstall_helm_if_exists() {
            local release="$1" namespace="$2" cached_list="$3"
            if [ "${HELM_AVAILABLE}" == "true" ] && echo "${cached_list}" | grep -q "${release}"; then
                echo "  Removing Helm release..."
                helm uninstall "${release}" -n "${namespace}" || echo "  ⚠ Helm uninstall failed"
                echo "  ✓ Helm release removed"
            else
                echo "  ℹ Helm release not found"
            fi
        }

        delete_namespace_if_exists() {
            local ns="$1"
            if oc get namespace "${ns}" &>/dev/null; then
                echo "  Deleting namespace ${ns}..."
                oc delete namespace "${ns}" --wait=false
                echo "  ✓ Namespace deletion initiated"
            fi
        }

        # Remove driver based on type
        case "${DRIVER_TYPE}" in
            example)
                echo "Uninstalling dra-example-driver..."
                uninstall_helm_if_exists "${DRIVER_RELEASE}" "${DRIVER_NAMESPACE}" "${HELM_EXAMPLE_LIST}"
                delete_namespace_if_exists "${DRIVER_NAMESPACE}"
                ;;

            nvidia)
                echo "Uninstalling NVIDIA DRA driver..."

                # Clean up SCC permissions (ClusterRoleBindings)
                echo "  Cleaning up SCC permissions..."
                for crb in \
                  nvidia-dra-privileged-nvidia-dra-driver-gpu-service-account-controller \
                  nvidia-dra-privileged-nvidia-dra-driver-gpu-service-account-kubeletplugin \
                  nvidia-dra-privileged-compute-domain-daemon-service-account; do
                  oc delete clusterrolebinding "$crb" --ignore-not-found=true 2>/dev/null && \
                    echo "    Deleted ClusterRoleBinding: $crb" || true
                done

                uninstall_helm_if_exists "nvidia-dra-driver" "${DRIVER_NAMESPACE}" "${HELM_NVIDIA_LIST}"
                delete_namespace_if_exists "${DRIVER_NAMESPACE}"

                # Note about GPU operator
                if [ "${REMOVE_OPERATOR}" != "true" ]; then
                    if oc get namespace nvidia-gpu-operator &>/dev/null; then
                        echo ""
                        echo "  ℹ GPU Operator is still installed"
                        echo "  To remove GPU operator, run cleanup without --keep-operator flag"
                    fi
                fi
                ;;

            nvidia-operator)
                echo "Uninstalling NVIDIA GPU Operator (OLM-based)..."

                # Delete ClusterPolicy first
                if oc get clusterpolicy gpu-cluster-policy &>/dev/null; then
                    echo "  Deleting ClusterPolicy..."
                    oc delete clusterpolicy gpu-cluster-policy --ignore-not-found=true
                    echo "  ✓ ClusterPolicy deleted"
                fi

                # Delete subscription
                if oc get subscription gpu-operator-certified -n nvidia-gpu-operator &>/dev/null; then
                    echo "  Deleting GPU Operator subscription..."
                    oc delete subscription gpu-operator-certified -n nvidia-gpu-operator
                    echo "  ✓ Subscription deleted"
                fi

                # Delete CSV
                CSV_NAME=$(oc get csv -n nvidia-gpu-operator -l operators.coreos.com/gpu-operator-certified.nvidia-gpu-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
                if [ -n "${CSV_NAME}" ]; then
                    echo "  Deleting CSV: ${CSV_NAME}..."
                    oc delete csv "${CSV_NAME}" -n nvidia-gpu-operator
                    echo "  ✓ CSV deleted"
                fi

                # Delete namespace
                if oc get namespace nvidia-gpu-operator &>/dev/null; then
                    echo "  Deleting namespace nvidia-gpu-operator..."
                    oc delete namespace nvidia-gpu-operator --wait=false
                    echo "  ✓ Namespace deletion initiated"
                fi
                ;;
        esac

        echo ""
        echo "Waiting for namespace deletion..."
        oc wait --for=delete namespace/${DRIVER_NAMESPACE} --timeout=120s 2>/dev/null || echo "  ⚠ Timeout waiting for namespace deletion"

        # Verify cleanup
        echo ""
        echo "Verifying cleanup..."

        if oc get namespace ${DRIVER_NAMESPACE} &>/dev/null 2>&1; then
            echo "  ⚠ Namespace ${DRIVER_NAMESPACE} still exists"
        else
            echo "  ✓ Namespace removed"
        fi

        # Check for DeviceClass removal
        DEVICECLASS_COUNT=$(oc get deviceclass --no-headers 2>/dev/null | wc -l)
        if [ "${DEVICECLASS_COUNT}" -gt 0 ]; then
            echo "  ⚠ ${DEVICECLASS_COUNT} DeviceClass(es) still exist"
            oc get deviceclass -o name
        else
            echo "  ✓ DeviceClasses removed"
        fi

        # Check for ResourceSlice removal (filter by driver to avoid false warnings)
        if [ "${DRIVER_TYPE}" == "example" ]; then
            DRIVER_RESOURCESLICES=$(oc get resourceslice -o json 2>/dev/null | jq -r '.items[] | select(.spec.driver == "gpu.example.com") | .metadata.name' | wc -l)
        elif [ "${DRIVER_TYPE}" == "nvidia" ]; then
            DRIVER_RESOURCESLICES=$(oc get resourceslice -o json 2>/dev/null | jq -r '.items[] | select(.spec.driver == "nvidia.com/gpu" or .spec.driver == "mig.nvidia.com") | .metadata.name' | wc -l)
        else
            DRIVER_RESOURCESLICES=0
        fi

        if [ "${DRIVER_RESOURCESLICES}" -gt 0 ]; then
            echo "  ℹ ${DRIVER_RESOURCESLICES} ${DRIVER_TYPE} driver ResourceSlice(s) still being garbage collected"
        else
            echo "  ✓ Driver ResourceSlices removed"
        fi
    fi
else
    echo "=== Step 2: Preserve DRA driver ==="
    echo "Driver installation preserved (--keep-driver specified)."
fi

echo ""

#=========================================
# Step 3: Remove GPU Operator (if requested and applicable)
#=========================================
if [ "${REMOVE_OPERATOR}" == "true" ]; then
    echo "=== Step 3: Remove GPU Operator ==="
    echo ""

    # Check if NVIDIA GPU operator is installed
    if oc get namespace nvidia-gpu-operator &>/dev/null; then
        echo "Detected: NVIDIA GPU Operator (namespace: nvidia-gpu-operator)"
        echo ""
        echo "Uninstalling NVIDIA GPU Operator (OLM-based)..."

        # Delete ClusterPolicy first
        if oc get clusterpolicy gpu-cluster-policy &>/dev/null; then
            echo "  Deleting ClusterPolicy..."
            oc delete clusterpolicy gpu-cluster-policy --ignore-not-found=true
            echo "  ✓ ClusterPolicy deleted"
        fi

        # Delete subscription
        if oc get subscription gpu-operator-certified -n nvidia-gpu-operator &>/dev/null; then
            echo "  Deleting GPU Operator subscription..."
            oc delete subscription gpu-operator-certified -n nvidia-gpu-operator
            echo "  ✓ Subscription deleted"
        fi

        # Delete CSV
        CSV_NAME=$(oc get csv -n nvidia-gpu-operator -l operators.coreos.com/gpu-operator-certified.nvidia-gpu-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
        if [ -n "${CSV_NAME}" ]; then
            echo "  Deleting CSV: ${CSV_NAME}..."
            oc delete csv "${CSV_NAME}" -n nvidia-gpu-operator
            echo "  ✓ CSV deleted"
        fi

        # Delete namespace
        if oc get namespace nvidia-gpu-operator &>/dev/null; then
            echo "  Deleting namespace nvidia-gpu-operator..."
            oc delete namespace nvidia-gpu-operator --wait=false
            echo "  ✓ Namespace deletion initiated"
        fi

        echo ""
        echo "Waiting for GPU operator namespace deletion..."
        oc wait --for=delete namespace/nvidia-gpu-operator --timeout=120s 2>/dev/null || echo "  ⚠ Timeout waiting for namespace deletion"

        echo ""
        echo "  ✓ GPU operator removed"
    else
        echo "ℹ No GPU operator installation detected (checked nvidia-gpu-operator namespace)"
    fi
else
    echo "=== Step 3: Preserve GPU Operator ==="
    echo "GPU operator preserved (--keep-operator specified)."
fi

echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo "Summary:"
if [ -n "${TEST_NAMESPACES}" ]; then
    echo "  ✓ Test namespaces cleaned up"
else
    echo "  ℹ No test namespaces found"
fi

if [ "${REMOVE_DRIVER}" == "true" ]; then
    if [ "${DRIVER_TYPE}" != "none" ]; then
        echo "  ✓ ${DRIVER_TYPE} driver removed"
    else
        echo "  ℹ No driver found to remove"
    fi
else
    echo "  ℹ DRA driver preserved (--keep-driver)"
fi

if [ "${REMOVE_OPERATOR}" == "true" ]; then
    if oc get namespace nvidia-gpu-operator &>/dev/null 2>&1; then
        echo "  ⚠ GPU operator namespace still exists"
    else
        echo "  ✓ GPU operator removed"
    fi
else
    echo "  ℹ GPU operator preserved (--keep-operator)"
fi
echo ""
