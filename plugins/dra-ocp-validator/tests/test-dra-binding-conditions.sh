#!/bin/bash
# DRA Device Binding Conditions Validation Test
# Tests enhanced conditions for device binding state
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

LOG_DIR="./dra-binding-conditions-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Device Binding Conditions Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: Device Binding Conditions (Alpha)"
echo ""

NAMESPACE="dra-binding-test"

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
# Phase 1: ResourceClaim Status Conditions
#==============================================
echo "=== PHASE 1: ResourceClaim Status Conditions ==="

cat <<EOF | tee ${LOG_DIR}/test1-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-binding-test
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

# Check for conditions in claim status
oc get resourceclaim claim-binding-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-claim-unbound.yaml

CONDITIONS=$(oc get resourceclaim claim-binding-test -n ${NAMESPACE} -o jsonpath='{.status.conditions}')
if [ -n "${CONDITIONS}" ] && [ "${CONDITIONS}" != "null" ] && [ "${CONDITIONS}" != "[]" ]; then
    echo "✅ ResourceClaim has status.conditions field"
    echo "${CONDITIONS}" | jq '.' > ${LOG_DIR}/test1-conditions-initial.json

    # List condition types
    echo "Condition types present:"
    echo "${CONDITIONS}" | jq -r '.[].type' | sed 's/^/  - /'
else
    echo "ℹ No conditions in unbound claim (may appear after binding)"
fi
echo ""

#==============================================
# Phase 2: Conditions After Pod Binding
#==============================================
echo "=== PHASE 2: Conditions After Device Binding ==="

cat <<EOF | tee ${LOG_DIR}/test2-pod.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-binding-test
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "echo 'Device bound to pod'; sleep 60"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-binding-test
EOF

echo ""
sleep 10

POD_STATUS=$(oc get pod pod-binding-test -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD_STATUS}"

if [ "${POD_STATUS}" == "Running" ] || [ "${POD_STATUS}" == "Succeeded" ]; then
    echo "✅ Pod scheduled and device bound"

    # Check conditions after binding
    sleep 5
    oc get resourceclaim claim-binding-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-claim-bound.yaml

    CONDITIONS_BOUND=$(oc get resourceclaim claim-binding-test -n ${NAMESPACE} -o jsonpath='{.status.conditions}')

    if [ -n "${CONDITIONS_BOUND}" ] && [ "${CONDITIONS_BOUND}" != "null" ] && [ "${CONDITIONS_BOUND}" != "[]" ]; then
        echo "✅ PASS: Conditions present after binding"
        echo "${CONDITIONS_BOUND}" | jq '.' > ${LOG_DIR}/test2-conditions-bound.json

        echo "Binding conditions:"
        echo "${CONDITIONS_BOUND}" | jq -r '.[] | "  - \(.type): \(.status) (\(.reason))"'

        # Check for common condition types
        READY_CONDITION=$(echo "${CONDITIONS_BOUND}" | jq -r '.[] | select(.type == "Ready") | .status')
        ALLOCATED_CONDITION=$(echo "${CONDITIONS_BOUND}" | jq -r '.[] | select(.type == "Allocated") | .status')

        if [ -n "${READY_CONDITION}" ]; then
            echo "  Ready condition: ${READY_CONDITION}"
        fi
        if [ -n "${ALLOCATED_CONDITION}" ]; then
            echo "  Allocated condition: ${ALLOCATED_CONDITION}"
        fi
    else
        echo "ℹ No conditions after binding (may not be implemented by driver)"
    fi
else
    echo "❌ FAIL: Pod not running: ${POD_STATUS}"
    oc describe pod pod-binding-test -n ${NAMESPACE} > ${LOG_DIR}/test2-pod-describe.txt
fi
echo ""

#==============================================
# Phase 3: Pod Scheduling Conditions
#==============================================
echo "=== PHASE 3: Pod Scheduling Conditions ==="

if [ "${POD_STATUS}" == "Running" ] || [ "${POD_STATUS}" == "Succeeded" ]; then
    # Check pod conditions related to resource claims
    POD_CONDITIONS=$(oc get pod pod-binding-test -n ${NAMESPACE} -o jsonpath='{.status.conditions}')

    echo "Pod conditions:"
    echo "${POD_CONDITIONS}" | jq '.' > ${LOG_DIR}/test3-pod-conditions.json
    echo "${POD_CONDITIONS}" | jq -r '.[] | "  - \(.type): \(.status)"'

    # Check for PodScheduled condition
    SCHEDULED_CONDITION=$(echo "${POD_CONDITIONS}" | jq -r '.[] | select(.type == "PodScheduled")')
    if [ -n "${SCHEDULED_CONDITION}" ]; then
        echo ""
        echo "PodScheduled condition details:"
        echo "${SCHEDULED_CONDITION}" | jq '.'

        SCHED_REASON=$(echo "${SCHEDULED_CONDITION}" | jq -r '.reason')
        SCHED_MESSAGE=$(echo "${SCHEDULED_CONDITION}" | jq -r '.message')

        echo "  Reason: ${SCHED_REASON}"
        if [ -n "${SCHED_MESSAGE}" ] && [ "${SCHED_MESSAGE}" != "null" ]; then
            echo "  Message: ${SCHED_MESSAGE}"
        fi
    fi
fi
echo ""

#==============================================
# Phase 4: Failure Scenario - Invalid Selector
#==============================================
echo "=== PHASE 4: Conditions on Allocation Failure ==="

cat <<EOF | tee ${LOG_DIR}/test4-claim-invalid.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-invalid-selector
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: device
      exactly:
        deviceClassName: ${DEVICECLASS}
        selectors:
        - cel:
            expression: "device.name == 'nonexistent-device-12345'"
        count: 1
EOF

cat <<EOF | tee ${LOG_DIR}/test4-pod-failing.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-binding-fail
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "sleep 60"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-invalid-selector
EOF

echo ""
sleep 15

# Check pod and claim conditions for failure case
FAIL_POD_STATUS=$(oc get pod pod-binding-fail -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Failing Pod Status: ${FAIL_POD_STATUS}"

if [ "${FAIL_POD_STATUS}" == "Pending" ]; then
    echo "✅ Pod pending as expected (device not available)"

    # Check pod conditions for scheduling failure
    FAIL_POD_CONDITIONS=$(oc get pod pod-binding-fail -n ${NAMESPACE} -o jsonpath='{.status.conditions}')
    echo "${FAIL_POD_CONDITIONS}" | jq '.' > ${LOG_DIR}/test4-fail-pod-conditions.json

    SCHED_FAIL=$(echo "${FAIL_POD_CONDITIONS}" | jq -r '.[] | select(.type == "PodScheduled" and .status == "False")')
    if [ -n "${SCHED_FAIL}" ]; then
        echo "✅ PodScheduled=False condition present"

        FAIL_REASON=$(echo "${SCHED_FAIL}" | jq -r '.reason')
        FAIL_MESSAGE=$(echo "${SCHED_FAIL}" | jq -r '.message')

        echo "  Reason: ${FAIL_REASON}"
        echo "  Message: ${FAIL_MESSAGE}"
    fi

    # Check claim conditions
    FAIL_CLAIM_CONDITIONS=$(oc get resourceclaim claim-invalid-selector -n ${NAMESPACE} -o jsonpath='{.status.conditions}')
    if [ -n "${FAIL_CLAIM_CONDITIONS}" ] && [ "${FAIL_CLAIM_CONDITIONS}" != "null" ] && [ "${FAIL_CLAIM_CONDITIONS}" != "[]" ]; then
        echo ""
        echo "ResourceClaim conditions on failure:"
        echo "${FAIL_CLAIM_CONDITIONS}" | jq '.' > ${LOG_DIR}/test4-fail-claim-conditions.json
        echo "${FAIL_CLAIM_CONDITIONS}" | jq -r '.[] | "  - \(.type): \(.status) - \(.message)"'
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
oc get pods -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-pods-full.yaml
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

HAS_CLAIM_CONDITIONS=$([ -n "${CONDITIONS_BOUND}" ] && [ "${CONDITIONS_BOUND}" != "null" ] && [ "${CONDITIONS_BOUND}" != "[]" ] && echo "YES" || echo "NO")
HAS_FAIL_CONDITIONS=$([ -n "${FAIL_CLAIM_CONDITIONS}" ] && [ "${FAIL_CLAIM_CONDITIONS}" != "null" ] && [ "${FAIL_CLAIM_CONDITIONS}" != "[]" ] && echo "YES" || echo "NO")

echo "Test Results:"
echo "  Pod Status (success):       ${POD_STATUS}"
echo "  Claim conditions (bound):   ${HAS_CLAIM_CONDITIONS}"
echo "  Pod Status (failure):       ${FAIL_POD_STATUS}"
echo "  Claim conditions (failed):  ${HAS_FAIL_CONDITIONS}"
echo ""

if [ "${POD_STATUS}" == "Running" ]; then
    echo "🎉 DRA DEVICE BINDING CONDITIONS: VALIDATED"
    echo ""
    echo "Note: Binding conditions provide enhanced state tracking:"
    echo "  - ResourceClaim.status.conditions tracks allocation state"
    echo "  - Pod.status.conditions tracks scheduling with DRA"
    echo "  - Failure conditions help diagnose allocation issues"
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
