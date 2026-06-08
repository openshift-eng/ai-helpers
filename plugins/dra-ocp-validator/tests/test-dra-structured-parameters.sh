#!/bin/bash
# DRA Structured Parameters Validation Test
# Tests structured parameter support for device allocation (KEP-4831)
# GA in K8s 1.34+

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

LOG_DIR="./dra-structured-params-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Structured Parameters Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: Structured Parameters (GA - KEP-4831)"
echo ""

NAMESPACE="dra-structured-params-test"

#==============================================
# Phase 0: Prerequisites
#==============================================
echo "=== PHASE 0: Prerequisites ==="
oc version | tee ${LOG_DIR}/00-version.txt
oc get nodes -o wide | tee ${LOG_DIR}/01-nodes.txt
oc get deviceclass | tee ${LOG_DIR}/02-deviceclass.txt

# Get DeviceClass to verify structured parameters support
DEVICECLASS=$(oc get deviceclass -o jsonpath='{.items[0].metadata.name}')
echo "DeviceClass: ${DEVICECLASS}" | tee -a ${LOG_DIR}/02-deviceclass.txt

# Check if structured parameters API is available (v1)
API_VERSION=$(oc api-resources --api-group=resource.k8s.io -o name | grep -E '^deviceclasses\.resource\.k8s\.io$' || echo "not found")
if [ "${API_VERSION}" == "not found" ]; then
    echo "❌ FAIL: resource.k8s.io/v1 API not available"
    exit 1
fi
echo "✓ resource.k8s.io/v1 API available"

# Verify DeviceClass has structured parameters format
oc get deviceclass ${DEVICECLASS} -o yaml | tee ${LOG_DIR}/02-deviceclass-full.yaml
echo ""

oc create namespace ${NAMESPACE}
echo "✓ Namespace created"
echo ""

#==============================================
# Phase 1: Basic Structured Parameters Request
#==============================================
echo "=== PHASE 1: Basic Structured Parameters ==="

cat <<EOF | tee ${LOG_DIR}/test1-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-structured-basic
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: device
      exactly:
        deviceClassName: ${DEVICECLASS}
        count: 1
EOF

echo ""
sleep 5

# Check claim was created with structured parameters API
CLAIM_API=$(oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o jsonpath='{.apiVersion}')
echo "ResourceClaim API Version: ${CLAIM_API}"

if echo "${CLAIM_API}" | grep -q "resource.k8s.io/v1"; then
    echo "✅ PASS: ResourceClaim created with v1 API (structured parameters)"
else
    echo "⚠ WARNING: ResourceClaim not using v1 API: ${CLAIM_API}"
fi

oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-claim-created.yaml

# Verify structured format in spec.devices
HAS_DEVICES=$(oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o jsonpath='{.spec.devices}' | grep -q "requests" && echo "yes" || echo "no")
if [ "${HAS_DEVICES}" == "yes" ]; then
    echo "✅ PASS: Claim uses spec.devices.requests (structured format)"
    oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o jsonpath='{.spec.devices}' | jq '.' > ${LOG_DIR}/test1-devices-spec.json
else
    echo "❌ FAIL: Claim missing spec.devices.requests"
fi
echo ""

#==============================================
# Phase 2: Structured Parameters with Selectors
#==============================================
echo "=== PHASE 2: Structured Parameters with CEL Selectors ==="

cat <<EOF | tee ${LOG_DIR}/test2-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-structured-selector
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: selected-device
      exactly:
        deviceClassName: ${DEVICECLASS}
        selectors:
        - cel:
            expression: "device.driver == '${DEVICECLASS}'"
        count: 1
EOF

echo ""
sleep 5

# Verify selector was accepted
SELECTOR=$(oc get resourceclaim claim-structured-selector -n ${NAMESPACE} -o jsonpath='{.spec.devices.requests[0].exactly.selectors[0].cel.expression}')
echo "CEL Selector: ${SELECTOR}"

if [ -n "${SELECTOR}" ]; then
    echo "✅ PASS: CEL selector preserved in ResourceClaim"
    oc get resourceclaim claim-structured-selector -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-claim-with-selector.yaml
else
    echo "❌ FAIL: CEL selector missing or rejected"
fi
echo ""

#==============================================
# Phase 3: Pod with Structured Parameters Claim
#==============================================
echo "=== PHASE 3: Pod Using Structured Parameters Claim ==="

cat <<EOF | tee ${LOG_DIR}/test3-pod.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-structured-claim
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "echo 'Using structured parameters device'; sleep 30"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-structured-basic
EOF

echo ""
sleep 10

POD_STATUS=$(oc get pod pod-structured-claim -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD_STATUS}"

if [ "${POD_STATUS}" == "Running" ] || [ "${POD_STATUS}" == "Succeeded" ]; then
    echo "✅ PASS: Pod scheduled with structured parameters claim"

    # Check allocation
    sleep 5
    ALLOCATION=$(oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o jsonpath='{.status.allocation}')
    if [ -n "${ALLOCATION}" ]; then
        echo "✅ Allocation present in claim status"
        oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o jsonpath='{.status.allocation}' | jq '.' > ${LOG_DIR}/test3-allocation.json

        # Verify allocation uses structured format (devices.results)
        HAS_RESULTS=$(oc get resourceclaim claim-structured-basic -n ${NAMESPACE} -o jsonpath='{.status.allocation.devices.results}' | grep -q "\[" && echo "yes" || echo "no")
        if [ "${HAS_RESULTS}" == "yes" ]; then
            echo "✅ PASS: Allocation uses structured format (devices.results)"
        fi
    else
        echo "⚠ WARNING: No allocation in claim status"
    fi

    oc logs pod-structured-claim -n ${NAMESPACE} | tee ${LOG_DIR}/test3-pod-logs.txt
else
    echo "❌ FAIL: Pod not running: ${POD_STATUS}"
    oc describe pod pod-structured-claim -n ${NAMESPACE} > ${LOG_DIR}/test3-pod-describe.txt
fi
echo ""

#==============================================
# Phase 4: DeviceClass Validation
#==============================================
echo "=== PHASE 4: DeviceClass Structured Format ==="

# Verify DeviceClass uses structured selectors
DEVICECLASS_SELECTORS=$(oc get deviceclass ${DEVICECLASS} -o jsonpath='{.spec.selectors}')
if [ -n "${DEVICECLASS_SELECTORS}" ]; then
    echo "✅ DeviceClass has spec.selectors (structured format)"
    oc get deviceclass ${DEVICECLASS} -o jsonpath='{.spec.selectors}' | jq '.' > ${LOG_DIR}/test4-deviceclass-selectors.json

    # Check for CEL selector
    HAS_CEL=$(echo "${DEVICECLASS_SELECTORS}" | grep -q "cel" && echo "yes" || echo "no")
    if [ "${HAS_CEL}" == "yes" ]; then
        echo "✅ DeviceClass uses CEL selectors"
    fi
else
    echo "⚠ WARNING: DeviceClass missing spec.selectors"
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
echo "  API Version:              ${CLAIM_API}"
echo "  Structured spec.devices:  ${HAS_DEVICES}"
echo "  CEL Selector Support:     $([ -n "${SELECTOR}" ] && echo 'YES' || echo 'NO')"
echo "  Pod Status:               ${POD_STATUS}"
echo "  Allocation Format:        ${HAS_RESULTS:-unknown}"
echo ""

if [ "${HAS_DEVICES}" == "yes" ] && [ "${POD_STATUS}" == "Running" ]; then
    echo "🎉 DRA STRUCTURED PARAMETERS: VALIDATED"
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
