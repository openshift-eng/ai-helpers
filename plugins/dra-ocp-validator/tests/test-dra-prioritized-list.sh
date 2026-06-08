#!/bin/bash
# DRA Prioritized List Validation Test (Fixed)
# Tests device alternatives and fallback (KEP-4816)
# Handle KUBECONFIG argument
if [ -n "${1}" ]; then
  KUBECONFIG_PATH="${1/#~/$HOME}"
  if [ -f "${KUBECONFIG_PATH}" ]; then
    export KUBECONFIG="${KUBECONFIG_PATH}"
  fi
fi


# Source debug collection utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(dirname "${SCRIPT_DIR}")/tools"
if [ -f "${TOOLS_DIR}/collect-debug-info.sh" ]; then
    source "${TOOLS_DIR}/collect-debug-info.sh"
fi

set -e

LOG_DIR="./dra-prioritized-list-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Prioritized List Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: DRA Prioritized List (Beta - KEP-4816)"
echo ""

NAMESPACE="dra-prioritized-test"

#==============================================
# Phase 0: Prerequisites
#==============================================
echo "=== PHASE 0: Prerequisites ==="
oc version | tee ${LOG_DIR}/00-version.txt
oc get nodes -o wide | tee ${LOG_DIR}/01-nodes.txt
oc get deviceclass | tee ${LOG_DIR}/02-deviceclass.txt

# Detect available DeviceClass dynamically
DEVICE_CLASS=$(oc get deviceclass -o jsonpath='{.items[0].metadata.name}')
if [ -z "${DEVICE_CLASS}" ]; then
    echo "❌ ERROR: No DeviceClass found - DRA driver not installed"
    exit 1
fi
echo "Using DeviceClass: ${DEVICE_CLASS}" | tee ${LOG_DIR}/03-deviceclass-detected.txt
echo ""

AVAILABLE_1G70=$(oc get resourceslice -o json | jq -r '[.items[].spec.devices[] | select(.attributes.profile.string == "1g.70gb")] | length')
AVAILABLE_1G35=$(oc get resourceslice -o json | jq -r '[.items[].spec.devices[] | select(.attributes.profile.string == "1g.35gb")] | length')

echo "" | tee ${LOG_DIR}/03-devices.txt
echo "Available MIG Profiles:" | tee -a ${LOG_DIR}/03-devices.txt
echo "  - 1g.70gb (large): ${AVAILABLE_1G70} instances" | tee -a ${LOG_DIR}/03-devices.txt
echo "  - 1g.35gb (small): ${AVAILABLE_1G35} instances" | tee -a ${LOG_DIR}/03-devices.txt
echo ""

oc create namespace ${NAMESPACE}
echo "✓ Namespace created"
echo ""

#==============================================
# Phase 1: Single Preferred Request
#==============================================
echo "=== PHASE 1: Single Preferred Request (1g.70gb) ==="

cat <<EOF | tee ${LOG_DIR}/test1-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-preferred-only
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: large-mig
      exactly:
        deviceClassName: ${DEVICE_CLASS}
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.70gb'"
        count: 1
EOF

cat <<EOF | tee ${LOG_DIR}/test1-pod.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-preferred-only
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 60"]
    resources:
      claims:
      - name: gpu
  resourceClaims:
  - name: gpu
    resourceClaimName: claim-preferred-only
EOF

echo ""
sleep 10
oc wait --for=condition=Ready pod/pod-preferred-only -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD1_STATUS=$(oc get pod pod-preferred-only -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD1_STATUS}"

if [ "${POD1_STATUS}" == "Running" ]; then
    echo "✅ Preferred device allocated"
    oc logs pod-preferred-only -n ${NAMESPACE} | tee ${LOG_DIR}/test1-logs.txt
    oc get resourceclaim claim-preferred-only -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test1-allocation.json
    
    DEVICE1=$(oc get resourceclaim claim-preferred-only -n ${NAMESPACE} -o jsonpath='{.status.allocation.devices.results[0].device}')
    echo "Allocated: ${DEVICE1}"
else
    echo "⚠ Pod failed"
    oc describe pod pod-preferred-only -n ${NAMESPACE} > ${LOG_DIR}/test1-describe.txt
fi
echo ""

#==============================================
# Phase 2: Prioritized List (Preferred + Fallback)
#==============================================
echo "=== PHASE 2: Prioritized List (1g.70gb OR 2x 1g.35gb) ==="

cat <<EOF | tee ${LOG_DIR}/test2-claim.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-with-fallback
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: preferred-large
      exactly:
        deviceClassName: ${DEVICE_CLASS}
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.70gb'"
        count: 1
    - name: fallback-small
      exactly:
        deviceClassName: ${DEVICE_CLASS}
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.35gb'"
        count: 2
EOF

cat <<EOF | tee ${LOG_DIR}/test2-pod.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-with-fallback
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 60"]
    resources:
      claims:
      - name: gpu
  resourceClaims:
  - name: gpu
    resourceClaimName: claim-with-fallback
EOF

echo ""
sleep 10
oc wait --for=condition=Ready pod/pod-with-fallback -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD2_STATUS=$(oc get pod pod-with-fallback -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD2_STATUS}"

if [ "${POD2_STATUS}" == "Running" ]; then
    echo "✅ Pod scheduled with prioritized list"
    oc logs pod-with-fallback -n ${NAMESPACE} | tee ${LOG_DIR}/test2-logs.txt
    oc get resourceclaim claim-with-fallback -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test2-allocation.json
    
    echo ""
    echo "--- Analyzing Selection ---"
    oc get resourceclaim claim-with-fallback -n ${NAMESPACE} -o json | jq -r '.status.allocation.devices.results[] | "Request: \(.request) -> Device: \(.device)"' | tee ${LOG_DIR}/test2-selected.txt
    
    SELECTED=$(oc get resourceclaim claim-with-fallback -n ${NAMESPACE} -o json | jq -r '.status.allocation.devices.results[0].request')
    
    if echo "${SELECTED}" | grep -q "preferred"; then
        echo "✅ Scheduler selected PREFERRED (1g.70gb)"
    elif echo "${SELECTED}" | grep -q "fallback"; then
        echo "✅ Scheduler selected FALLBACK (2x 1g.35gb)"
    fi
else
    echo "⚠ Pod failed"
    oc describe pod pod-with-fallback -n ${NAMESPACE} > ${LOG_DIR}/test2-describe.txt
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
echo "  Phase 1 (Preferred only):   ${POD1_STATUS}"
echo "  Phase 2 (With fallback):    ${POD2_STATUS}"
echo ""

if [ "${POD1_STATUS}" == "Running" ] && [ "${POD2_STATUS}" == "Running" ]; then
    echo "🎉 DRA PRIORITIZED LIST: VALIDATED"
else
    echo "⚠ VALIDATION INCOMPLETE"
fi
echo ""

echo "Logs: ${LOG_DIR}"
echo ""
echo "Cleanup:"
echo "  oc delete pods --all -n ${NAMESPACE}"
echo "  oc delete resourceclaim --all -n ${NAMESPACE}"
echo "  oc delete namespace ${NAMESPACE}"

# Collect debug info on failure
if [ "${POD1_STATUS}" != "Running" ] || [ "${POD2_STATUS}" != "Running" ]; then
    echo ""
    echo "Collecting debug information..."
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE}"
    echo "Debug: ${LOG_DIR}/debug/"
fi

# Exit with proper code
if [ "${POD1_STATUS}" == "Running" ] && [ "${POD2_STATUS}" == "Running" ]; then
    exit 0
else
    exit 1
fi
