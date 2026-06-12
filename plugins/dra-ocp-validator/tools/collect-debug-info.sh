#!/usr/bin/env bash
# Shared debug collection function for DRA tests
# Usage: source this file and call collect_test_debug_info <log_dir> <namespace> [pod_name]

collect_test_debug_info() {
    local LOG_DIR="${1}"
    local NAMESPACE="${2}"
    local POD_NAME="${3:-}"

    if [ -z "${LOG_DIR}" ] || [ -z "${NAMESPACE}" ]; then
        echo "⚠ collect_test_debug_info: Missing required arguments"
        return 1
    fi

    mkdir -p "${LOG_DIR}/debug"

    echo ""
    echo "=== Collecting Debug Information ==="

    # 1. Events (most important for debugging scheduling failures)
    echo "  → Events in namespace ${NAMESPACE}..."
    oc get events -n "${NAMESPACE}" --sort-by='.lastTimestamp' \
        > "${LOG_DIR}/debug/events.txt" 2>/dev/null || true

    # Also get cluster-wide events related to DRA
    oc get events -A --sort-by='.lastTimestamp' | grep -i "dra\|resource.*claim\|device" \
        > "${LOG_DIR}/debug/events-cluster-dra.txt" 2>/dev/null || true

    # 2. ResourceClaims status
    echo "  → ResourceClaims in namespace ${NAMESPACE}..."
    oc get resourceclaim -n "${NAMESPACE}" -o yaml \
        > "${LOG_DIR}/debug/resourceclaims-full.yaml" 2>/dev/null || true

    oc get resourceclaim -n "${NAMESPACE}" -o json | \
        jq '.items[] | {name: .metadata.name, allocated: .status.allocation.devices.results, conditions: .status.conditions}' \
        > "${LOG_DIR}/debug/resourceclaims-status.json" 2>/dev/null || true

    # 3. Pod logs (if pod name provided)
    if [ -n "${POD_NAME}" ]; then
        echo "  → Pod logs for ${POD_NAME}..."
        oc logs -n "${NAMESPACE}" "${POD_NAME}" --all-containers=true \
            > "${LOG_DIR}/debug/pod-${POD_NAME}-logs.txt" 2>/dev/null || echo "Pod not found or no logs" > "${LOG_DIR}/debug/pod-${POD_NAME}-logs.txt"

        oc logs -n "${NAMESPACE}" "${POD_NAME}" --previous --all-containers=true \
            > "${LOG_DIR}/debug/pod-${POD_NAME}-logs-previous.txt" 2>/dev/null || true
    fi

    # 4. All pods in namespace
    echo "  → All pods in namespace ${NAMESPACE}..."
    oc get pods -n "${NAMESPACE}" -o wide \
        > "${LOG_DIR}/debug/pods.txt" 2>/dev/null || true

    oc get pods -n "${NAMESPACE}" -o json | \
        jq '.items[] | {name: .metadata.name, phase: .status.phase, conditions: .status.conditions, resourceClaimStatuses: .status.resourceClaimStatuses}' \
        > "${LOG_DIR}/debug/pods-status.json" 2>/dev/null || true

    # 5. Pod descriptions (contains scheduling failures)
    for pod in $(oc get pods -n "${NAMESPACE}" -o name 2>/dev/null); do
        POD_SHORT=$(basename "$pod")
        oc describe -n "${NAMESPACE}" "$pod" \
            > "${LOG_DIR}/debug/describe-${POD_SHORT}.txt" 2>/dev/null || true
    done

    # 6. DRA driver logs (from driver namespace)
    echo "  → DRA driver logs..."

    # NVIDIA driver
    if oc get namespace nvidia-dra-driver &>/dev/null; then
        oc logs -n nvidia-dra-driver -l app=nvidia-dra-driver --tail=500 --timestamps \
            > "${LOG_DIR}/debug/nvidia-dra-driver-logs.txt" 2>/dev/null || true
    fi

    # Example driver
    if oc get namespace dra-example-driver &>/dev/null; then
        oc logs -n dra-example-driver -l app=dra-example-driver --tail=500 --timestamps \
            > "${LOG_DIR}/debug/dra-example-driver-logs.txt" 2>/dev/null || true
    fi

    # 7. Current ResourceSlice state
    echo "  → ResourceSlice state..."
    oc get resourceslice -o yaml > "${LOG_DIR}/debug/resourceslice-current.yaml" 2>/dev/null || true

    # 8. Scheduler logs (if accessible)
    echo "  → Scheduler logs..."
    oc logs -n openshift-kube-scheduler -l app=openshift-kube-scheduler --tail=200 --timestamps \
        > "${LOG_DIR}/debug/scheduler-logs.txt" 2>/dev/null || true

    # 9. Create a quick summary
    cat > "${LOG_DIR}/debug/README.txt" <<EOF
==============================================
Debug Information Summary
==============================================

This directory contains debugging artifacts collected at: $(date)

Key Files:
----------
1. events.txt                    - Namespace events (check for scheduling/allocation failures)
2. events-cluster-dra.txt        - Cluster-wide DRA-related events
3. resourceclaims-full.yaml      - Complete ResourceClaim state
4. resourceclaims-status.json    - Allocation status and conditions (easier to read)
5. pods-status.json              - Pod status and resourceClaimStatuses
6. describe-*.txt                - Pod descriptions (scheduling decisions)
7. *-driver-logs.txt             - DRA driver logs
8. scheduler-logs.txt            - Scheduler logs (allocation decisions)

What to Check First:
-------------------
1. events.txt - Look for "FailedScheduling", "FailedAllocation", errors
2. resourceclaims-status.json - Check if claims are allocated
3. pods-status.json - Check resourceClaimStatuses field
4. describe-pod-*.txt - Check "Events:" section for scheduling failures
5. Driver logs - Check for allocation errors

Common Issues:
-------------
- "No devices available" → Check ResourceSlice capacity
- "AdminAccess forbidden" → Check namespace labels
- "Pending" pods → Check events.txt for scheduling failures
- Empty resourceClaimStatuses → Claim not allocated to pod

EOF

    echo "✓ Debug info collected in ${LOG_DIR}/debug/"
    echo ""
}

# Export the function so tests can use it
export -f collect_test_debug_info 2>/dev/null || true
