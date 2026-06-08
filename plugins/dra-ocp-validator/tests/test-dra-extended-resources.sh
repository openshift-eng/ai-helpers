#!/bin/bash
# DRA Extended Resources Validation Test
# Uses existing NVIDIA DeviceClasses created by the driver
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

NAMESPACE="dra-extended-test"
LOG_DIR="./dra-extended-validation-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Extended Resources Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

# Redirect all output
exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: DRAExtendedResources"
echo "Allows DRA devices to be requested via standard extended resource syntax"
echo ""

# Prerequisites check
echo "=== Phase 0: Prerequisites ===" 
oc get featuregate cluster -o json | jq '.status.featureGates[0].enabled[] | select(.name | contains("DRA"))' | tee ${LOG_DIR}/00-featuregates.json
echo ""

DRA_EXTENDED=$(oc get featuregate cluster -o json | jq -r '.status.featureGates[0].enabled[] | select(.name == "DRAExtendedResources") | .name' || echo "")
if [ -z "${DRA_EXTENDED}" ]; then
    echo "❌ DRAExtendedResources NOT enabled"
    exit 1
fi
echo "✅ DRAExtendedResources enabled"
echo ""

# Capture cluster state
oc version | tee ${LOG_DIR}/01-version.txt
oc get nodes -o wide | tee ${LOG_DIR}/02-nodes.txt
oc get deviceclass | tee ${LOG_DIR}/03-deviceclass-list.txt
oc get deviceclass -o yaml > ${LOG_DIR}/03-deviceclass-full.yaml

# Create namespace
oc create namespace ${NAMESPACE} 2>/dev/null || true
echo ""

# Define implicit resource names
IMPLICIT_MIG="deviceclass.resource.kubernetes.io/mig.nvidia.com"
IMPLICIT_GPU="deviceclass.resource.kubernetes.io/gpu.nvidia.com"

echo "Implicit extended resource names:"
echo "  MIG: ${IMPLICIT_MIG}"
echo "  GPU: ${IMPLICIT_GPU}"
echo ""

# Test 1: MIG implicit
echo "=== Test 1: MIG Implicit Extended Resource ==="
cat <<EOF | tee ${LOG_DIR}/test1-manifest.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-mig
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 300"]
    resources:
      requests:
        ${IMPLICIT_MIG}: "1"
      limits:
        ${IMPLICIT_MIG}: "1"
EOF

sleep 10
oc wait --for=condition=Ready pod/pod-mig -n ${NAMESPACE} --timeout=90s || true
sleep 5

POD1=$(oc get pod pod-mig -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod status: ${POD1}"

oc get pod pod-mig -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-pod.yaml
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/test1-claims.txt

if [ "${POD1}" == "Running" ]; then
    echo "✅ MIG pod running"
    oc logs pod-mig -n ${NAMESPACE} > ${LOG_DIR}/test1-logs.txt
    oc get pod pod-mig -n ${NAMESPACE} -o json | jq '.status.extendedResourceClaimStatus' | tee ${LOG_DIR}/test1-claim-status.json
    CLAIM=$(oc get pod pod-mig -n ${NAMESPACE} -o jsonpath='{.status.extendedResourceClaimStatus.resourceClaimName}')
    if [ -n "${CLAIM}" ]; then
        oc get resourceclaim ${CLAIM} -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-resourceclaim.yaml
    fi
else
    echo "❌ MIG pod failed"
    oc describe pod pod-mig -n ${NAMESPACE} > ${LOG_DIR}/test1-describe.txt
fi
echo ""

# Test 2: GPU implicit
echo "=== Test 2: GPU Implicit Extended Resource ==="
cat <<EOF | tee ${LOG_DIR}/test2-manifest.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-gpu
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 300"]
    resources:
      requests:
        ${IMPLICIT_GPU}: "1"
      limits:
        ${IMPLICIT_GPU}: "1"
EOF

sleep 10
oc wait --for=condition=Ready pod/pod-gpu -n ${NAMESPACE} --timeout=90s || true
sleep 5

POD2=$(oc get pod pod-gpu -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod status: ${POD2}"

oc get pod pod-gpu -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-pod.yaml

if [ "${POD2}" == "Running" ]; then
    echo "✅ GPU pod running"
    oc logs pod-gpu -n ${NAMESPACE} > ${LOG_DIR}/test2-logs.txt
    oc get pod pod-gpu -n ${NAMESPACE} -o json | jq '.status.extendedResourceClaimStatus' > ${LOG_DIR}/test2-claim-status.json
fi
echo ""

# Test 3: Multi-container
echo "=== Test 3: Multi-Container ==="
cat <<EOF | tee ${LOG_DIR}/test3-manifest.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-multi
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  containers:
  - name: c1
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 300"]
    resources:
      requests:
        ${IMPLICIT_MIG}: "1"
      limits:
        ${IMPLICIT_MIG}: "1"
  - name: c2
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 300"]
    resources:
      requests:
        ${IMPLICIT_MIG}: "1"
      limits:
        ${IMPLICIT_MIG}: "1"
EOF

sleep 10
oc wait --for=condition=Ready pod/pod-multi -n ${NAMESPACE} --timeout=90s || true
sleep 5

POD3=$(oc get pod pod-multi -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod status: ${POD3}"

oc get pod pod-multi -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test3-pod.yaml

if [ "${POD3}" == "Running" ]; then
    echo "✅ Multi-container pod running"
    oc get pod pod-multi -n ${NAMESPACE} -o json | jq '.status.extendedResourceClaimStatus.requestMappings' > ${LOG_DIR}/test3-mappings.json
fi
echo ""

# Final state
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods.txt
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-claims.txt
oc get resourceclaim -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-claims-full.yaml
oc get events -n ${NAMESPACE} --sort-by='.lastTimestamp' > ${LOG_DIR}/99-events.txt

# Summary
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo "Test 1 (MIG): ${POD1}"
echo "Test 2 (GPU): ${POD2}"
echo "Test 3 (Multi): ${POD3}"
echo ""

SUCCESS=0
[ "${POD1}" == "Running" ] && SUCCESS=$((SUCCESS + 1))
[ "${POD2}" == "Running" ] && SUCCESS=$((SUCCESS + 1))
[ "${POD3}" == "Running" ] && SUCCESS=$((SUCCESS + 1))

if [ ${SUCCESS} -ge 2 ]; then
    echo "🎉 DRA EXTENDED RESOURCES: VALIDATED"
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
if [ ${SUCCESS} -lt 2 ]; then
    echo ""
    echo "Collecting debug information..."
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE}"
    echo "Debug: ${LOG_DIR}/debug/"
fi

# Exit with proper code
if [ ${SUCCESS} -ge 2 ]; then
    exit 0
else
    exit 1
fi
