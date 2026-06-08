#!/bin/bash
# DRA ResourceClaim Status Validation Test
# Tests enhanced status reporting for ResourceClaim objects (KEP-4817)
# Beta in K8s 1.33+

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

LOG_DIR="./dra-claim-status-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA ResourceClaim Status Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: ResourceClaim Status (Beta - KEP-4817)"
echo ""

NAMESPACE="dra-claim-status-test"

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
# Phase 1: Basic ResourceClaim Status Fields
#==============================================
echo "=== PHASE 1: ResourceClaim Status Fields ==="

cat <<EOF | tee ${LOG_DIR}/test1-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-status-test
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

# Check initial status
oc get resourceclaim claim-status-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-claim-initial.yaml

# Verify status structure
STATUS=$(oc get resourceclaim claim-status-test -n ${NAMESPACE} -o jsonpath='{.status}')
if [ -n "${STATUS}" ]; then
    echo "✅ ResourceClaim has status field"
    echo "${STATUS}" | jq '.' > ${LOG_DIR}/test1-status-initial.json
else
    echo "⚠ ResourceClaim status empty (claim not allocated yet)"
fi
echo ""

#==============================================
# Phase 2: Status with Pod Allocation
#==============================================
echo "=== PHASE 2: Status After Pod Allocation ==="

cat <<EOF | tee ${LOG_DIR}/test2-pod.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-claim-status
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: consumer
    image: registry.access.redhat.com/ubi8/ubi-minimal:latest
    command: ["sh", "-c", "echo 'Testing claim status'; sleep 60"]
    resources:
      claims:
      - name: device
  resourceClaims:
  - name: device
    resourceClaimName: claim-status-test
EOF

echo ""
sleep 10

# Wait for pod to be scheduled
POD_STATUS=$(oc get pod pod-claim-status -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD_STATUS}"

if [ "${POD_STATUS}" == "Running" ] || [ "${POD_STATUS}" == "Succeeded" ]; then
    echo "✅ Pod scheduled successfully"

    # Check allocation status
    sleep 5
    ALLOCATION=$(oc get resourceclaim claim-status-test -n ${NAMESPACE} -o jsonpath='{.status.allocation}')

    if [ -n "${ALLOCATION}" ]; then
        echo "✅ PASS: status.allocation populated"
        echo "${ALLOCATION}" | jq '.' > ${LOG_DIR}/test2-allocation.json

        # Check allocation.devices.results
        RESULTS=$(oc get resourceclaim claim-status-test -n ${NAMESPACE} -o jsonpath='{.status.allocation.devices.results}')
        if [ -n "${RESULTS}" ] && [ "${RESULTS}" != "null" ]; then
            echo "✅ PASS: status.allocation.devices.results present"
            echo "${RESULTS}" | jq '.' > ${LOG_DIR}/test2-results.json

            # Extract allocated device info
            REQUEST_NAME=$(echo "${RESULTS}" | jq -r '.[0].request')
            DRIVER=$(echo "${RESULTS}" | jq -r '.[0].driver')
            POOL=$(echo "${RESULTS}" | jq -r '.[0].pool')
            DEVICE=$(echo "${RESULTS}" | jq -r '.[0].device')

            echo "  Request: ${REQUEST_NAME}"
            echo "  Driver: ${DRIVER}"
            echo "  Pool: ${POOL}"
            echo "  Device: ${DEVICE}"
        else
            echo "❌ FAIL: status.allocation.devices.results missing"
        fi
    else
        echo "❌ FAIL: status.allocation missing"
    fi

    # Check reserved status
    RESERVED=$(oc get resourceclaim claim-status-test -n ${NAMESPACE} -o jsonpath='{.status.reserved}')
    if [ "${RESERVED}" == "true" ]; then
        echo "✅ PASS: status.reserved=true (claim is in use)"
    else
        echo "⚠ WARNING: status.reserved not true"
    fi
else
    echo "❌ FAIL: Pod not running: ${POD_STATUS}"
    oc describe pod pod-claim-status -n ${NAMESPACE} > ${LOG_DIR}/test2-pod-describe.txt
fi
echo ""

#==============================================
# Phase 3: Status RBAC Testing
#==============================================
echo "=== PHASE 3: Status Subresource RBAC ==="

# Create ServiceAccount for status updates
SA_NAME="claim-status-updater-sa"
ROLE_NAME="claim-status-updater-role"
BINDING_NAME="claim-status-updater-binding"

cat <<EOF | oc apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${SA_NAME}
  namespace: ${NAMESPACE}
EOF

# Create Role with status subresource permissions
cat <<EOF | tee ${LOG_DIR}/test3-role.yaml | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ${ROLE_NAME}
rules:
- apiGroups: ["resource.k8s.io"]
  resources: ["resourceclaims/status"]
  verbs: ["get", "update", "patch"]
- apiGroups: ["resource.k8s.io"]
  resources: ["resourceclaims"]
  verbs: ["get", "list"]
EOF

cat <<EOF | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: ${BINDING_NAME}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: ${ROLE_NAME}
subjects:
- kind: ServiceAccount
  name: ${SA_NAME}
  namespace: ${NAMESPACE}
EOF

echo "✓ RBAC configured for status updates"

# Test that status subresource exists
TOKEN=$(oc create token ${SA_NAME} -n ${NAMESPACE} --duration=10m)
API_SERVER=$(oc whoami --show-server)

# Try to get status subresource
RESPONSE=$(curl -k -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  "${API_SERVER}/apis/resource.k8s.io/v1/namespaces/${NAMESPACE}/resourceclaims/claim-status-test/status")

echo "Status subresource GET response: ${RESPONSE}"

if [ "${RESPONSE}" == "200" ]; then
    echo "✅ PASS: resourceclaims/status subresource accessible"
else
    echo "⚠ WARNING: Status subresource returned ${RESPONSE}"
fi
echo ""

#==============================================
# Phase 4: Status Conditions
#==============================================
echo "=== PHASE 4: Status Conditions ==="

oc get resourceclaim claim-status-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test4-claim-full.yaml

# Check for conditions in status
CONDITIONS=$(oc get resourceclaim claim-status-test -n ${NAMESPACE} -o jsonpath='{.status.conditions}')
if [ -n "${CONDITIONS}" ] && [ "${CONDITIONS}" != "null" ]; then
    echo "✅ status.conditions field present"
    echo "${CONDITIONS}" | jq '.' > ${LOG_DIR}/test4-conditions.json

    # List condition types
    CONDITION_TYPES=$(echo "${CONDITIONS}" | jq -r '.[].type')
    echo "Condition types:"
    echo "${CONDITION_TYPES}" | sed 's/^/  - /'
else
    echo "ℹ No conditions in status (may be normal for simple allocation)"
fi
echo ""

#==============================================
# Final State
#==============================================
echo "=== Final State ==="
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods.txt
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-claims.txt
oc get resourceclaim claim-status-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-claim-final.yaml
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

HAS_ALLOCATION=$([ -n "${ALLOCATION}" ] && echo "YES" || echo "NO")
HAS_RESULTS=$([ -n "${RESULTS}" ] && [ "${RESULTS}" != "null" ] && echo "YES" || echo "NO")
RBAC_OK=$([ "${RESPONSE}" == "200" ] && echo "YES" || echo "NO")

echo "Test Results:"
echo "  Pod Status:              ${POD_STATUS}"
echo "  status.allocation:       ${HAS_ALLOCATION}"
echo "  status.allocation.devices.results: ${HAS_RESULTS}"
echo "  status.reserved:         ${RESERVED:-unknown}"
echo "  Status subresource:      ${RBAC_OK}"
echo ""

if [ "${POD_STATUS}" == "Running" ] && [ "${HAS_ALLOCATION}" == "YES" ] && [ "${HAS_RESULTS}" == "YES" ]; then
    echo "🎉 DRA RESOURCECLAIM STATUS: VALIDATED"
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
echo "  oc delete clusterrolebinding ${BINDING_NAME}"
echo "  oc delete clusterrole ${ROLE_NAME}"
echo "  oc delete pods --all -n ${NAMESPACE}"
echo "  oc delete resourceclaim --all -n ${NAMESPACE}"
echo "  oc delete namespace ${NAMESPACE}"

exit ${EXIT_CODE}
