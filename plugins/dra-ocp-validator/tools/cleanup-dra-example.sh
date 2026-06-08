#!/bin/bash
# Cleanup script for dra-example-driver and test resources
# Based on: /dra-ocp-validator:cleanup command specification

set -euo pipefail

KUBECONFIG_PATH=$1
REMOVE_DRIVER="${2:-false}"
FORCE="${3:-false}"

export KUBECONFIG=${KUBECONFIG_PATH}

echo "========================================="
echo "DRA OCP Validator - Cleanup"
echo "========================================="
echo ""

# Verify required tools
for cmd in oc kubectl helm; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: Required command not found: $cmd"
        exit 1
    fi
done

#=========================================
# Step 1: Clean up test namespaces
#=========================================
echo "=== Step 1: Clean up test namespaces ==="

TEST_NAMESPACES=$(oc get namespaces -o name 2>/dev/null | grep 'namespace/dra-.*-test' | sed 's|namespace/||' || true)

if [ -z "${TEST_NAMESPACES}" ]; then
    echo "No test namespaces found (pattern: dra-*-test)"
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
# Step 2: Remove dra-example-driver (if requested)
#=========================================
if [ "${REMOVE_DRIVER}" == "true" ] || [ "${REMOVE_DRIVER}" == "--remove-driver" ]; then
    echo "=== Step 2: Remove dra-example-driver ==="
    echo ""
    echo "Uninstalling dra-example-driver..."

    # Check if Helm release exists
    if helm list -n dra-example-driver 2>/dev/null | grep -q dra-example-driver; then
        echo "  Removing Helm release..."
        helm uninstall dra-example-driver -n dra-example-driver || echo "  ⚠ Helm uninstall failed"
        echo "  ✓ Helm release removed"
    else
        echo "  ℹ Helm release not found (may have been installed manually)"
    fi

    # Delete namespace
    if oc get namespace dra-example-driver &>/dev/null; then
        echo "  Deleting namespace dra-example-driver..."
        oc delete namespace dra-example-driver --wait=false
        echo "  ✓ Namespace deletion initiated"
    else
        echo "  ℹ Namespace dra-example-driver not found"
    fi

    echo ""
    echo "Waiting for namespace deletion..."
    timeout 120 bash -c '
    while oc get namespace dra-example-driver &>/dev/null; do
        echo "  Waiting..."
        sleep 5
    done
    ' || echo "  ⚠ Timeout waiting for namespace deletion"

    # Verify cleanup
    echo ""
    echo "Verifying cleanup..."

    if oc get namespace dra-example-driver &>/dev/null; then
        echo "  ⚠ Namespace still exists"
    else
        echo "  ✓ Namespace removed"
    fi

    if oc get deviceclass gpu.example.com &>/dev/null; then
        echo "  ⚠ DeviceClass still exists"
    else
        echo "  ✓ DeviceClass removed"
    fi

    RESOURCESLICES=$(oc get resourceslice -o json 2>/dev/null | grep -c "example.com" || true)
    if [ -n "${RESOURCESLICES}" ] && [ "${RESOURCESLICES}" -gt 0 ] 2>/dev/null; then
        echo "  ⚠ ${RESOURCESLICES} ResourceSlices still exist"
    else
        echo "  ✓ ResourceSlices removed"
    fi
else
    echo "=== Step 2: Preserve dra-example-driver ==="
    echo "Driver installation preserved."
    echo "To remove driver, run with --remove-driver flag"
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

if [ "${REMOVE_DRIVER}" == "true" ] || [ "${REMOVE_DRIVER}" == "--remove-driver" ]; then
    echo "  ✓ dra-example-driver removed"
else
    echo "  ℹ dra-example-driver preserved"
fi
echo ""
