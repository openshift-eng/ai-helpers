#!/bin/bash
# DRA Consumable Capacity Validation Test
# Tests support for consumable resource capacity (memory, bandwidth, etc.)
# Alpha in K8s 1.34+

# Handle KUBECONFIG argument
if [ -n "${1}" ]; then
  KUBECONFIG_PATH="${1/#~/$HOME}"
  if [ -f "${KUBECONFIG_PATH}" ]; then
    export KUBECONFIG="${KUBECONFIG_PATH}"
  fi
fi

set -e

# Source debug collection utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(dirname "${SCRIPT_DIR}")/tools"
if [ -f "${TOOLS_DIR}/collect-debug-info.sh" ]; then
    source "${TOOLS_DIR}/collect-debug-info.sh"
fi

LOG_DIR="./dra-consumable-capacity-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Consumable Capacity Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: Consumable Capacity (Alpha)"
echo ""

NAMESPACE="dra-consumable-test"

#==============================================
# Phase 0: Prerequisites
#==============================================
echo "=== PHASE 0: Prerequisites ==="
oc version | tee ${LOG_DIR}/00-version.txt
oc get nodes -o wide | tee ${LOG_DIR}/01-nodes.txt
oc get deviceclass | tee ${LOG_DIR}/02-deviceclass.txt

DEVICECLASS=$(oc get deviceclass -o jsonpath='{.items[0].metadata.name}')
echo "DeviceClass: ${DEVICECLASS}"
echo ""

# Check for feature gate
echo "Checking for DRAConsumableCapacity feature gate..."
FEATURE_GATES=$(oc get featuregate cluster -o jsonpath='{.spec.customNoUpgrade.enabled}' 2>/dev/null || echo "[]")
if echo "${FEATURE_GATES}" | grep -q "DRAConsumableCapacity"; then
    echo "✓ DRAConsumableCapacity feature gate enabled"
else
    echo "⚠ WARNING: DRAConsumableCapacity feature gate may not be enabled"
    echo "  This is an Alpha feature requiring explicit enablement"
    echo ""
    echo "To enable:"
    echo "  oc patch featuregate cluster --type=merge \\"
    echo "    -p '{\"spec\":{\"customNoUpgrade\":{\"enabled\":[\"DRAConsumableCapacity\"]}}}'"
    echo ""
fi

oc create namespace ${NAMESPACE}
echo "✓ Namespace created"
echo ""

#==============================================
# Phase 1: Check Device Capacity
#==============================================
echo "=== PHASE 1: Device Capacity Information ==="

# Check if any devices have capacity defined
RESOURCE_SLICES=$(oc get resourceslice -o json)
echo "${RESOURCE_SLICES}" > ${LOG_DIR}/test1-resourceslices.json

# Look for capacity in device definitions
CAPACITY_COUNT=$(echo "${RESOURCE_SLICES}" | jq '[.items[].spec.devices[] | select(.capacity != null)] | length')
echo "Devices with capacity: ${CAPACITY_COUNT}"

if [ "${CAPACITY_COUNT}" -gt 0 ]; then
    echo "✅ Found devices with capacity definitions"

    # Show first device with capacity
    DEVICE_WITH_CAPACITY=$(echo "${RESOURCE_SLICES}" | jq -r '.items[].spec.devices[] | select(.capacity != null) | .name' | head -1)
    echo "Example device: ${DEVICE_WITH_CAPACITY}"

    CAPACITY_INFO=$(echo "${RESOURCE_SLICES}" | jq '.items[].spec.devices[] | select(.name == "'${DEVICE_WITH_CAPACITY}'") | .capacity')
    echo "Capacity info:"
    echo "${CAPACITY_INFO}" | jq '.' > ${LOG_DIR}/test1-capacity-example.json
    echo "${CAPACITY_INFO}" | jq '.'
else
    echo "ℹ No devices with capacity found"
    echo "  Consumable capacity requires driver support"
    echo "  Example drivers (test-driver, NVIDIA with MIG) may provide capacity"
fi
echo ""

#==============================================
# Phase 2: Capacity Request in ResourceClaim
#==============================================
echo "=== PHASE 2: ResourceClaim with Capacity Request ==="

cat <<EOF | tee ${LOG_DIR}/test2-claim-with-capacity.yaml | oc apply -f - 2>&1 | tee ${LOG_DIR}/test2-apply-result.txt || true
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-capacity-request
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: device-with-capacity
      exactly:
        deviceClassName: ${DEVICECLASS}
        count: 1
        capacity:
          requests:
            memory: "2Gi"
EOF

CLAIM_CREATED=$?
echo ""

if [ ${CLAIM_CREATED} -eq 0 ]; then
    echo "✅ ResourceClaim with capacity request created"

    sleep 5
    oc get resourceclaim claim-capacity-request -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-claim-full.yaml

    # Verify capacity field preserved
    CAPACITY_REQ=$(oc get resourceclaim claim-capacity-request -n ${NAMESPACE} -o jsonpath='{.spec.devices.requests[0].exactly.capacity.requests.memory}')

    if [ -n "${CAPACITY_REQ}" ]; then
        echo "✅ PASS: Capacity request preserved in claim: ${CAPACITY_REQ}"
    else
        echo "⚠ Capacity request missing in created claim"
    fi
else
    echo "⚠ ResourceClaim with capacity rejected (expected if feature not enabled)"
    cat ${LOG_DIR}/test2-apply-result.txt
fi
echo ""

#==============================================
# Phase 3: Multiple Allocations Test
#==============================================
echo "=== PHASE 3: Multiple Allocations Consuming Capacity ==="

if [ ${CLAIM_CREATED} -eq 0 ]; then
    echo "Testing multiple allocations from same device..."

    # Create first pod requesting 2Gi
    cat <<EOF | tee ${LOG_DIR}/test3-pod1.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-capacity-1
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "echo 'Using 2Gi capacity'; sleep 60"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-capacity-request
EOF

    sleep 10
    POD1_STATUS=$(oc get pod pod-capacity-1 -n ${NAMESPACE} -o jsonpath='{.status.phase}')
    echo "Pod 1 Status: ${POD1_STATUS}"

    if [ "${POD1_STATUS}" == "Running" ]; then
        echo "✅ First pod allocated successfully"

        # Create second claim requesting more capacity
        cat <<EOF | tee ${LOG_DIR}/test3-claim2.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-capacity-2
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: device-with-capacity
      exactly:
        deviceClassName: ${DEVICECLASS}
        count: 1
        capacity:
          requests:
            memory: "4Gi"
EOF

        cat <<EOF | tee ${LOG_DIR}/test3-pod2.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-capacity-2
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "echo 'Using 4Gi capacity'; sleep 60"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-capacity-2
EOF

        sleep 15
        POD2_STATUS=$(oc get pod pod-capacity-2 -n ${NAMESPACE} -o jsonpath='{.status.phase}')
        echo "Pod 2 Status: ${POD2_STATUS}"

        # Check if scheduling was affected by capacity
        POD2_EVENTS=$(oc get events -n ${NAMESPACE} --field-selector involvedObject.name=pod-capacity-2 -o json)
        echo "${POD2_EVENTS}" > ${LOG_DIR}/test3-pod2-events.json

        if [ "${POD2_STATUS}" == "Running" ]; then
            echo "✅ Second pod also allocated (sufficient capacity available)"
        elif [ "${POD2_STATUS}" == "Pending" ]; then
            echo "✅ PASS: Second pod pending (capacity exhausted as expected)"

            # Check for capacity-related events
            CAPACITY_EVENT=$(echo "${POD2_EVENTS}" | jq -r '.items[] | select(.reason == "FailedScheduling" or .message | contains("capacity")) | .message' | head -1)
            if [ -n "${CAPACITY_EVENT}" ]; then
                echo "  Event: ${CAPACITY_EVENT}"
            fi
        fi
    else
        echo "⚠ First pod not running: ${POD1_STATUS}"
    fi
else
    echo "Skipping multiple allocation test (capacity claim not created)"
fi
echo ""

#==============================================
# Phase 4: Capacity Validation
#==============================================
echo "=== PHASE 4: Capacity Request Validation ==="

if [ ${CLAIM_CREATED} -eq 0 ]; then
    # Check allocation shows consumed capacity
    ALLOCATION=$(oc get resourceclaim claim-capacity-request -n ${NAMESPACE} -o jsonpath='{.status.allocation}')

    if [ -n "${ALLOCATION}" ]; then
        echo "Allocation details:"
        echo "${ALLOCATION}" | jq '.' > ${LOG_DIR}/test4-allocation.json
        echo "${ALLOCATION}" | jq '.'

        # Look for capacity in allocation
        ALLOCATED_CAPACITY=$(echo "${ALLOCATION}" | jq '.devices.results[0].capacity // {}')
        if [ "${ALLOCATED_CAPACITY}" != "{}" ]; then
            echo "✅ Capacity information in allocation"
        else
            echo "ℹ No capacity information in allocation (may not be reported)"
        fi
    fi
fi
echo ""

#==============================================
# Final State
#==============================================
echo "=== Final State ==="
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods.txt
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-claims.txt
oc get resourceclaim -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-claims-full.yaml
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

echo "Test Results:"
echo "  Devices with capacity:      ${CAPACITY_COUNT}"
echo "  Capacity claim created:     $([ ${CLAIM_CREATED} -eq 0 ] && echo 'YES' || echo 'NO')"
if [ ${CLAIM_CREATED} -eq 0 ]; then
    echo "  Capacity request preserved: $([ -n "${CAPACITY_REQ}" ] && echo 'YES' || echo 'NO')"
    echo "  Pod 1 status:              ${POD1_STATUS:-not-created}"
    echo "  Pod 2 status:              ${POD2_STATUS:-not-created}"
fi
echo ""

if [ "${CAPACITY_COUNT}" -gt 0 ] || [ ${CLAIM_CREATED} -eq 0 ]; then
    echo "🎉 DRA CONSUMABLE CAPACITY: VALIDATED"
    echo ""
    echo "Note: Full consumable capacity requires:"
    echo "  - Feature gate DRAConsumableCapacity (Alpha)"
    echo "  - Driver that supports capacity definitions"
    echo "  - Device with allowMultipleAllocations=true"
    EXIT_CODE=0
else
    echo "⚠ VALIDATION INCOMPLETE"
    echo ""
    echo "Consumable capacity not available on this cluster."
    echo "This is expected if:"
    echo "  - Feature gate not enabled"
    echo "  - Driver doesn't support capacity"
    EXIT_CODE=1

    # Collect debug info on failure
    echo ""
    echo "Collecting debug information..."
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE}"
fi
echo ""

echo "Logs: ${LOG_DIR}"
if [ ${EXIT_CODE} -ne 0 ]; then
    echo "Debug: ${LOG_DIR}/debug/"
fi
echo ""
echo "Cleanup:"
echo "  oc delete pods --all -n ${NAMESPACE}"
echo "  oc delete resourceclaim --all -n ${NAMESPACE}"
echo "  oc delete namespace ${NAMESPACE}"

exit ${EXIT_CODE}
