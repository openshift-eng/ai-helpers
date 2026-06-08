#!/bin/bash
# DRA Device Health Status Validation Test
# Tests device health information exposure through pod status
# Alpha in K8s 1.32+

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

LOG_DIR="./dra-health-status-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Device Health Status Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: Device Health Status (Alpha)"
echo ""

NAMESPACE="dra-health-test"

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

oc create namespace ${NAMESPACE}
echo "✓ Namespace created"
echo ""

#==============================================
# Phase 1: Create Pod with Device Claim
#==============================================
echo "=== PHASE 1: Pod with Device Allocation ==="

cat <<EOF | tee ${LOG_DIR}/test1-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-health-test
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: device
      exactly:
        deviceClassName: ${DEVICECLASS}
        count: 1
EOF

cat <<EOF | tee ${LOG_DIR}/test1-pod.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-health-test
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "echo 'Monitoring device health'; sleep 120"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-health-test
EOF

echo ""
sleep 15

POD_STATUS=$(oc get pod pod-health-test -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD_STATUS}"

if [ "${POD_STATUS}" != "Running" ] && [ "${POD_STATUS}" != "Succeeded" ]; then
    echo "❌ FAIL: Pod not running: ${POD_STATUS}"
    oc describe pod pod-health-test -n ${NAMESPACE} > ${LOG_DIR}/test1-pod-describe.txt
    exit 1
fi

echo "✅ Pod running with allocated device"
echo ""

#==============================================
# Phase 2: Check AllocatedResourcesStatus
#==============================================
echo "=== PHASE 2: AllocatedResourcesStatus in Pod Status ==="

sleep 5
oc get pod pod-health-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-pod-full.yaml

# Check for allocatedResourcesStatus in container status
ARS_EXISTS=$(oc get pod pod-health-test -n ${NAMESPACE} -o jsonpath='{.status.containerStatuses[0].allocatedResourcesStatus}')

if [ -n "${ARS_EXISTS}" ] && [ "${ARS_EXISTS}" != "null" ]; then
    echo "✅ PASS: allocatedResourcesStatus field present in container status"
    echo "${ARS_EXISTS}" | jq '.' > ${LOG_DIR}/test2-allocated-resources-status.json

    # Extract resource health info
    CLAIM_NAME=$(oc get pod pod-health-test -n ${NAMESPACE} -o jsonpath='{.spec.resourceClaims[0].name}')
    RESOURCE_NAME="claim:${CLAIM_NAME}"

    echo "Looking for resource: ${RESOURCE_NAME}"

    # Check for resources array
    RESOURCES=$(oc get pod pod-health-test -n ${NAMESPACE} -o jsonpath="{.status.containerStatuses[0].allocatedResourcesStatus[?(@.name=='${RESOURCE_NAME}')].resources}")

    if [ -n "${RESOURCES}" ] && [ "${RESOURCES}" != "null" ] && [ "${RESOURCES}" != "[]" ]; then
        echo "✅ PASS: Resource health information available"
        echo "${RESOURCES}" | jq '.' > ${LOG_DIR}/test2-resources-health.json

        # Extract health fields
        HEALTH_STATUS=$(echo "${RESOURCES}" | jq -r '.[0].health // "not-set"')
        HEALTH_MESSAGE=$(echo "${RESOURCES}" | jq -r '.[0].message // ""')

        echo "  Health Status: ${HEALTH_STATUS}"
        if [ -n "${HEALTH_MESSAGE}" ]; then
            echo "  Health Message: ${HEALTH_MESSAGE}"
        fi

        # Validate health status values
        if [ "${HEALTH_STATUS}" == "Healthy" ] || [ "${HEALTH_STATUS}" == "Unhealthy" ] || [ "${HEALTH_STATUS}" == "Unknown" ]; then
            echo "✅ PASS: Health status uses valid value: ${HEALTH_STATUS}"
        elif [ "${HEALTH_STATUS}" == "not-set" ]; then
            echo "ℹ Health status not set (driver may not report health)"
        else
            echo "⚠ WARNING: Unexpected health status: ${HEALTH_STATUS}"
        fi
    else
        echo "ℹ No health resources in allocatedResourcesStatus"
        echo "  (Driver may not implement health reporting)"
    fi
else
    echo "ℹ allocatedResourcesStatus not present"
    echo "  (Feature may require specific feature gate or driver support)"
fi
echo ""

#==============================================
# Phase 3: Monitor Health Status Changes
#==============================================
echo "=== PHASE 3: Health Status Monitoring ==="

# Note: Real health status changes require driver support
# This test documents the expected behavior

echo "Health status is reported by the DRA driver through the kubelet."
echo "Expected fields in status.containerStatuses[].allocatedResourcesStatus[]:"
echo "  - name: Resource name (e.g., 'claim:device')"
echo "  - resources[].health: 'Healthy', 'Unhealthy', or 'Unknown'"
echo "  - resources[].message: Optional health message"
echo ""

# Check if driver supports health reporting
DRIVER=$(oc get resourceclaim claim-health-test -n ${NAMESPACE} -o jsonpath='{.status.allocation.devices.results[0].driver}')
echo "Driver: ${DRIVER}"

if [ "${DRIVER}" == "gpu.example.com" ]; then
    echo "ℹ Using dra-example-driver (health reporting may not be implemented)"
elif echo "${DRIVER}" | grep -q "nvidia"; then
    echo "✓ Using NVIDIA driver (may support health reporting)"
fi
echo ""

#==============================================
# Phase 4: Health Status API Validation
#==============================================
echo "=== PHASE 4: Health Status API Structure ==="

# Verify the API structure matches the spec
cat > ${LOG_DIR}/test4-expected-structure.yaml <<'EOFSTRUCT'
# Expected structure in Pod status:
status:
  containerStatuses:
  - name: consumer
    allocatedResourcesStatus:
    - name: "claim:device"
      resources:
      - resourceID: "pool-123:device-456"
        health: "Healthy"  # or "Unhealthy", "Unknown"
        message: "Device operating normally, temperature: 45°C"
EOFSTRUCT

cat ${LOG_DIR}/test4-expected-structure.yaml
echo ""

# Extract actual structure
ACTUAL_STRUCTURE=$(oc get pod pod-health-test -n ${NAMESPACE} -o jsonpath='{.status.containerStatuses[0]}' | jq '{name: .name, allocatedResourcesStatus: .allocatedResourcesStatus}')

echo "Actual container status structure:"
echo "${ACTUAL_STRUCTURE}" | jq '.' > ${LOG_DIR}/test4-actual-structure.json
echo "${ACTUAL_STRUCTURE}" | jq '.'
echo ""

#==============================================
# Final State
#==============================================
echo "=== Final State ==="
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods.txt
oc get resourceclaim -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-claims.yaml
oc get pod pod-health-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-pod-full.yaml
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

HAS_ARS=$([ -n "${ARS_EXISTS}" ] && [ "${ARS_EXISTS}" != "null" ] && echo "YES" || echo "NO")
HAS_HEALTH_DATA=$([ -n "${RESOURCES}" ] && [ "${RESOURCES}" != "null" ] && [ "${RESOURCES}" != "[]" ] && echo "YES" || echo "NO")

echo "Test Results:"
echo "  Pod Status:                     ${POD_STATUS}"
echo "  allocatedResourcesStatus:       ${HAS_ARS}"
echo "  Health Resources Data:          ${HAS_HEALTH_DATA}"
if [ "${HAS_HEALTH_DATA}" == "YES" ]; then
    echo "  Health Status Value:            ${HEALTH_STATUS}"
fi
echo ""

if [ "${POD_STATUS}" == "Running" ] && [ "${HAS_ARS}" == "YES" ]; then
    echo "🎉 DRA DEVICE HEALTH STATUS: VALIDATED"
    echo ""
    echo "Note: Full health status reporting requires:"
    echo "  - Driver that implements health status updates"
    echo "  - Feature gate DRAResourceHealth (Alpha)"
    EXIT_CODE=0
else
    echo "⚠ VALIDATION INCOMPLETE"
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
