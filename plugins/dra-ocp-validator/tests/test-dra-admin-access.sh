#!/bin/bash
# DRA Admin Access Validation Test (Fixed)
# Tests namespace-level device access control

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

LOG_DIR="./dra-admin-access-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Admin Access Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: DRA Admin Access (Beta)"
echo ""

#==============================================
# Phase 0: Prerequisites
#==============================================
echo "=== PHASE 0: Prerequisites ===" 
oc version | tee ${LOG_DIR}/00-version.txt
oc get nodes -o wide | tee ${LOG_DIR}/01-nodes.txt
oc get deviceclass | tee ${LOG_DIR}/02-deviceclass.txt
echo ""

#==============================================
# Phase 1: Unauthorized Namespace
#==============================================
echo "=== PHASE 1: Unauthorized Namespace ==="
NAMESPACE_UNAUTH="dra-no-admin"

oc create namespace ${NAMESPACE_UNAUTH}
echo "Created namespace without admin-access label"
echo ""

echo "--- Attempting ResourceClaim with adminAccess=true ---"
cat <<EOF | tee ${LOG_DIR}/test1-claim.yaml | oc apply -f - 2>&1 | tee ${LOG_DIR}/test1-result.txt || true
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-admin-test
  namespace: ${NAMESPACE_UNAUTH}
spec:
  devices:
    requests:
    - name: gpu
      exactly:
        deviceClassName: mig.nvidia.com
        adminAccess: true
        count: 1
EOF

APPLY1_CODE=${PIPESTATUS[2]}
echo ""

if [ ${APPLY1_CODE} -ne 0 ]; then
    echo "✅ PASS: Unauthorized namespace rejected adminAccess claim"
    cat ${LOG_DIR}/test1-result.txt
else
    echo "⚠ Claim accepted (unexpected)"
fi
echo ""

echo "--- Testing Regular Claim (no adminAccess) ---"
cat <<EOF | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-regular
  namespace: ${NAMESPACE_UNAUTH}
spec:
  devices:
    requests:
    - name: gpu
      exactly:
        deviceClassName: mig.nvidia.com
        count: 1
EOF

sleep 2
oc get resourceclaim claim-regular -n ${NAMESPACE_UNAUTH} -o yaml > ${LOG_DIR}/test1-regular-claim.yaml
echo "✅ Regular claim created successfully"
echo ""

#==============================================
# Phase 2: Authorized Namespace
#==============================================
echo "=== PHASE 2: Authorized Namespace ==="
NAMESPACE_AUTH="dra-with-admin"

oc create namespace ${NAMESPACE_AUTH}
oc label namespace ${NAMESPACE_AUTH} "resource.kubernetes.io/admin-access=true"
echo "Created namespace WITH admin-access label"
echo ""

oc get namespace ${NAMESPACE_AUTH} -o yaml | tee ${LOG_DIR}/test2-namespace.yaml | grep -A 10 "labels:"
echo ""

echo "--- Creating ResourceClaim with adminAccess=true ---"
cat <<EOF | tee ${LOG_DIR}/test2-claim.yaml | oc apply -f - 2>&1 | tee ${LOG_DIR}/test2-result.txt
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-with-admin
  namespace: ${NAMESPACE_AUTH}
spec:
  devices:
    requests:
    - name: gpu
      exactly:
        deviceClassName: mig.nvidia.com
        adminAccess: true
        count: 1
EOF

APPLY2_CODE=${PIPESTATUS[2]}
echo ""

if [ ${APPLY2_CODE} -eq 0 ]; then
    echo "✅ PASS: Authorized namespace accepted adminAccess claim"
    sleep 2
    
    ADMIN_VAL=$(oc get resourceclaim claim-with-admin -n ${NAMESPACE_AUTH} -o jsonpath='{.spec.devices.requests[0].exactly.adminAccess}')
    echo "adminAccess field value: ${ADMIN_VAL}"
    
    if [ "${ADMIN_VAL}" == "true" ]; then
        echo "✅ adminAccess=true preserved in ResourceClaim"
    fi
    
    oc get resourceclaim claim-with-admin -n ${NAMESPACE_AUTH} -o yaml > ${LOG_DIR}/test2-claim-created.yaml
else
    echo "❌ FAIL: Claim rejected even with label"
    cat ${LOG_DIR}/test2-result.txt
fi
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""
echo "Test Results:"
echo "  Unauthorized namespace: $([ ${APPLY1_CODE} -ne 0 ] && echo 'PASS (rejected)' || echo 'FAIL (accepted)')"
echo "  Authorized namespace:   $([ ${APPLY2_CODE} -eq 0 ] && echo 'PASS (accepted)' || echo 'FAIL (rejected)')"
echo ""

if [ ${APPLY1_CODE} -ne 0 ] && [ ${APPLY2_CODE} -eq 0 ]; then
    echo "🎉 DRA ADMIN ACCESS: VALIDATED"
    EXIT_CODE=0
else
    echo "⚠ VALIDATION INCOMPLETE"
    EXIT_CODE=1

    # Collect debug info on failure
    echo ""
    echo "Collecting debug information..."
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE_UNAUTH}"
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE_AUTH}"
fi
echo ""

echo "Logs: ${LOG_DIR}"
if [ ${EXIT_CODE} -ne 0 ]; then
    echo "Debug: ${LOG_DIR}/debug/"
fi
echo ""
echo "Cleanup:"
echo "  oc delete namespace ${NAMESPACE_UNAUTH} ${NAMESPACE_AUTH}"

exit ${EXIT_CODE}
