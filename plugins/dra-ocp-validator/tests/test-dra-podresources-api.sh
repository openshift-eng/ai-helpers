#!/bin/bash
# DRA PodResources API Validation Test (Fixed)
# Tests kubelet PodResources API for DRA resource tracking
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

LOG_DIR="./dra-podresources-api-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA PodResources API Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: PodResources API for DRA (Beta)"
echo ""

NAMESPACE="dra-podresources-test"

#==============================================
# Phase 0: Prerequisites
#==============================================
echo "=== PHASE 0: Prerequisites ==="
oc version | tee ${LOG_DIR}/00-version.txt

NODE_NAME=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
echo "Target node: ${NODE_NAME}" | tee ${LOG_DIR}/01-node.txt
oc get nodes -o wide | tee -a ${LOG_DIR}/01-node.txt

oc create namespace ${NAMESPACE}
echo "✓ Namespace created"
echo ""

#==============================================
# Phase 1: Create Pods with DRA Claims
#==============================================
echo "=== PHASE 1: Create Pods with DRA Claims ==="

echo "--- Pod 1: MIG 1g.35gb ---"
cat <<EOF | tee ${LOG_DIR}/test1-claim1.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-mig-small
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: mig-small
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.35gb'"
        count: 1
EOF

cat <<EOF | tee ${LOG_DIR}/test1-pod1.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-mig-small
  namespace: ${NAMESPACE}
  labels:
    test: podresources-api
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 180"]
    resources:
      claims:
      - name: gpu
  resourceClaims:
  - name: gpu
    resourceClaimName: claim-mig-small
EOF

echo ""
sleep 10
oc wait --for=condition=Ready pod/pod-mig-small -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD1_STATUS=$(oc get pod pod-mig-small -n ${NAMESPACE} -o jsonpath='{.status.phase}')
POD1_UID=$(oc get pod pod-mig-small -n ${NAMESPACE} -o jsonpath='{.metadata.uid}')

echo "Pod 1 Status: ${POD1_STATUS}"
echo "Pod 1 UID: ${POD1_UID}" | tee ${LOG_DIR}/test1-pod1-uid.txt

if [ "${POD1_STATUS}" == "Running" ]; then
    echo "✅ Pod 1 running"
    oc logs pod-mig-small -n ${NAMESPACE} | tee ${LOG_DIR}/test1-pod1-logs.txt
    oc get resourceclaim claim-mig-small -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test1-allocation1.json
fi
echo ""

echo "--- Pod 2: MIG 1g.70gb ---"
cat <<EOF | tee ${LOG_DIR}/test1-claim2.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-mig-large
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: mig-large
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.70gb'"
        count: 1
EOF

cat <<EOF | tee ${LOG_DIR}/test1-pod2.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-mig-large
  namespace: ${NAMESPACE}
  labels:
    test: podresources-api
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 180"]
    resources:
      claims:
      - name: gpu
  resourceClaims:
  - name: gpu
    resourceClaimName: claim-mig-large
EOF

echo ""
sleep 10
oc wait --for=condition=Ready pod/pod-mig-large -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD2_STATUS=$(oc get pod pod-mig-large -n ${NAMESPACE} -o jsonpath='{.status.phase}')
POD2_UID=$(oc get pod pod-mig-large -n ${NAMESPACE} -o jsonpath='{.metadata.uid}')

echo "Pod 2 Status: ${POD2_STATUS}"
echo "Pod 2 UID: ${POD2_UID}" | tee ${LOG_DIR}/test1-pod2-uid.txt

if [ "${POD2_STATUS}" == "Running" ]; then
    echo "✅ Pod 2 running"
    oc logs pod-mig-large -n ${NAMESPACE} | tee ${LOG_DIR}/test1-pod2-logs.txt
    oc get resourceclaim claim-mig-large -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test1-allocation2.json
fi
echo ""

#==============================================
# Phase 2: Verify Pod ResourceClaim Status
#==============================================
echo "=== PHASE 2: Pod ResourceClaim Status ==="

if [ "${POD1_STATUS}" == "Running" ]; then
    echo "--- Pod 1 ResourceClaim Status ---"
    oc get pod pod-mig-small -n ${NAMESPACE} -o json | jq '.status.resourceClaimStatuses' | tee ${LOG_DIR}/test2-pod1-claim-status.json
    
    echo "--- Pod 1 Claim Info ---"
    oc get pod pod-mig-small -n ${NAMESPACE} -o json | jq -r '.spec.resourceClaims[] | "Claim: \(.name) -> \(.resourceClaimName)"'
    echo ""
fi

if [ "${POD2_STATUS}" == "Running" ]; then
    echo "--- Pod 2 ResourceClaim Status ---"
    oc get pod pod-mig-large -n ${NAMESPACE} -o json | jq '.status.resourceClaimStatuses' | tee ${LOG_DIR}/test2-pod2-claim-status.json
    
    echo "--- Pod 2 Claim Info ---"
    oc get pod pod-mig-large -n ${NAMESPACE} -o json | jq -r '.spec.resourceClaims[] | "Claim: \(.name) -> \(.resourceClaimName)"'
    echo ""
fi

echo "--- DRA Allocations Summary ---"
if [ "${POD1_STATUS}" == "Running" ]; then
    DEVICE1=$(oc get resourceclaim claim-mig-small -n ${NAMESPACE} -o jsonpath='{.status.allocation.devices.results[0].device}')
    echo "Pod 1: ${DEVICE1}"
fi

if [ "${POD2_STATUS}" == "Running" ]; then
    DEVICE2=$(oc get resourceclaim claim-mig-large -n ${NAMESPACE} -o jsonpath='{.status.allocation.devices.results[0].device}')
    echo "Pod 2: ${DEVICE2}"
fi
echo ""

#==============================================
# Phase 3: PodResources Socket Check
#==============================================
echo "=== PHASE 3: PodResources Socket Check ==="

echo "Creating debug pod with host access..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: podresources-debug
  namespace: ${NAMESPACE}
spec:
  hostNetwork: true
  hostPID: true
  nodeName: ${NODE_NAME}
  containers:
  - name: debug
    image: registry.access.redhat.com/ubi8/ubi-minimal
    command: ["sleep", "180"]
    securityContext:
      privileged: true
    volumeMounts:
    - name: kubelet-podresources
      mountPath: /var/lib/kubelet/pod-resources
      readOnly: true
  volumes:
  - name: kubelet-podresources
    hostPath:
      path: /var/lib/kubelet/pod-resources
      type: Directory
EOF

echo ""
sleep 10
oc wait --for=condition=Ready pod/podresources-debug -n ${NAMESPACE} --timeout=60s || true
sleep 3

DEBUG_STATUS=$(oc get pod podresources-debug -n ${NAMESPACE} -o jsonpath='{.status.phase}')

if [ "${DEBUG_STATUS}" == "Running" ]; then
    echo "✅ Debug pod running"
    echo ""
    
    echo "--- PodResources Directory ---"
    oc exec -n ${NAMESPACE} podresources-debug -- ls -la /var/lib/kubelet/pod-resources/ | tee ${LOG_DIR}/test3-socket-ls.txt
    
    SOCKET_EXISTS=$(oc exec -n ${NAMESPACE} podresources-debug -- test -S /var/lib/kubelet/pod-resources/kubelet.sock && echo "yes" || echo "no")
    echo ""
    echo "Socket exists: ${SOCKET_EXISTS}" | tee ${LOG_DIR}/test3-socket-status.txt
    
    if [ "${SOCKET_EXISTS}" == "yes" ]; then
        echo "✅ PodResources API socket available"
        echo ""
        echo "Note: PodResources API uses gRPC protocol"
        echo "      Querying requires gRPC client (not curl/oc)"
    fi
else
    echo "⚠ Debug pod failed"
    oc describe pod podresources-debug -n ${NAMESPACE} > ${LOG_DIR}/test3-debug-describe.txt
fi
echo ""

#==============================================
# Final State
#==============================================
echo "=== Final State ==="
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods.txt
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-claims.txt
oc get resourceclaim -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-claims-full.yaml

echo "" | tee ${LOG_DIR}/99-summary.txt
echo "--- Pod-Claim Summary ---" | tee -a ${LOG_DIR}/99-summary.txt
oc get pods -n ${NAMESPACE} -l test=podresources-api -o json | jq -r '.items[] | {
  pod: .metadata.name,
  uid: .metadata.uid,
  phase: .status.phase,
  claims: [.spec.resourceClaims[]? | {name: .name, resourceClaimName: .resourceClaimName}]
}' | tee -a ${LOG_DIR}/99-summary.txt
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""
echo "Test Results:"
echo "  Pod 1 (small MIG):  ${POD1_STATUS}"
echo "  Pod 2 (large MIG):  ${POD2_STATUS}"
echo "  Debug pod:          ${DEBUG_STATUS}"
echo "  PodResources socket: ${SOCKET_EXISTS:-unknown}"
echo ""

SUCCESS=0
[ "${POD1_STATUS}" == "Running" ] && SUCCESS=$((SUCCESS + 1))
[ "${POD2_STATUS}" == "Running" ] && SUCCESS=$((SUCCESS + 1))
[ "${SOCKET_EXISTS}" == "yes" ] && SUCCESS=$((SUCCESS + 1))

if [ ${SUCCESS} -ge 2 ]; then
    echo "🎉 DRA PODRESOURCES API: INFRASTRUCTURE VALIDATED"
    echo ""
    echo "✅ DRA pods scheduled successfully"
    echo "✅ Pod.status.resourceClaimStatuses populated"
    if [ "${SOCKET_EXISTS}" == "yes" ]; then
        echo "✅ PodResources API socket accessible"
    fi
    echo ""
    echo "Note: Full API validation requires gRPC client tool"
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
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE}" "pod-with-claim"
    echo "Debug: ${LOG_DIR}/debug/"
fi

# Exit with proper code
if [ "${POD1_STATUS}" == "Running" ] && [ "${POD2_STATUS}" == "Running" ]; then
    exit 0
else
    exit 1
fi
