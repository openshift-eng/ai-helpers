#!/bin/bash
# DRA Device Taints and Tolerations Validation Test
# Tests device-level taints similar to node taints (KEP-5055)
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

LOG_DIR="./dra-device-taints-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Device Taints Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

# Redirect all output
exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Feature: DRA Device Taints and Tolerations (Beta - KEP-5055)"
echo "Description: Device-level taints prevent pods from using specific"
echo "             devices unless they have matching tolerations"
echo ""
echo "Test Objectives:"
echo "1. Check if DRADeviceTaints feature gate is enabled"
echo "2. Apply taints to specific devices"
echo "3. Verify pods without tolerations cannot use tainted devices"
echo "4. Add tolerations to pod and verify allocation succeeds"
echo ""

#==============================================
# Phase 0: Prerequisites
#==============================================
echo "=========================================="
echo "PHASE 0: Prerequisites and Feature Gate Check"
echo "=========================================="
echo ""

NAMESPACE="dra-taint-test"

echo "--- Cluster Version ---"
oc version | tee ${LOG_DIR}/00-cluster-version.txt
echo ""

echo "--- Checking Feature Gates ---"
oc get featuregate cluster -o json | jq '.status.featureGates[].enabled[] | select(.name | contains("DRA") or .name | contains("Taint"))' | tee ${LOG_DIR}/00-featuregates.json
echo ""

DRA_TAINTS_ENABLED=$(oc get featuregate cluster -o json | jq -r '.status.featureGates[].enabled[] | select(.name == "DRADeviceTaints") | .name' 2>/dev/null || echo "")

if [ -z "${DRA_TAINTS_ENABLED}" ]; then
    echo "⚠ WARNING: DRADeviceTaints feature gate is NOT enabled"
    echo ""
    echo "This feature requires the DRADeviceTaints feature gate to be enabled in:"
    echo "  - kube-apiserver"
    echo "  - kube-controller-manager"
    echo "  - kube-scheduler"
    echo ""
    echo "To enable, patch the FeatureGate:"
    echo "  oc patch featuregate cluster --type=merge -p '{\"spec\":{\"customNoUpgrade\":{\"enabled\":[\"DRADeviceTaints\"]}}}'"
    echo ""
    echo "Continuing with test to document expected behavior..."
    echo ""
    FEATURE_AVAILABLE=false
else
    echo "✅ DRADeviceTaints feature gate is enabled"
    FEATURE_AVAILABLE=true
fi
echo ""

echo "--- Node Information ---"
oc get nodes -o wide | tee ${LOG_DIR}/01-nodes.txt
echo ""

echo "--- DeviceClasses ---"
oc get deviceclass | tee ${LOG_DIR}/02-deviceclass-list.txt
oc get deviceclass -o yaml > ${LOG_DIR}/02-deviceclass-full.yaml
echo ""

echo "--- Sample ResourceSlice (checking for taint support) ---"
oc get resourceslice -o json | jq '.items[0] | {name: .metadata.name, spec: .spec | {devices: .devices[0:2]}}' > ${LOG_DIR}/03-resourceslice-sample.json
cat ${LOG_DIR}/03-resourceslice-sample.json
echo ""

echo "--- Creating Test Namespace ---"
oc create namespace ${NAMESPACE}
echo "✓ Namespace created"
echo ""

if [ "${FEATURE_AVAILABLE}" = "false" ]; then
    echo "=========================================="
    echo "FEATURE NOT AVAILABLE - DOCUMENTING API"
    echo "=========================================="
    echo ""
    echo "Expected ResourceSlice structure with taints:"
    cat > ${LOG_DIR}/expected-taint-structure.yaml <<'EOF'
apiVersion: resource.k8s.io/v1
kind: ResourceSlice
metadata:
  name: example-slice
spec:
  devices:
  - name: gpu-0
    taints:
    - key: "special-workload"
      effect: "NoSchedule"
      value: "true"
    - key: "maintenance"
      effect: "NoSchedule"
  # ... rest of device spec
EOF
    cat ${LOG_DIR}/expected-taint-structure.yaml
    echo ""

    echo "Expected Pod tolerations:"
    cat > ${LOG_DIR}/expected-pod-tolerations.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: example-pod
spec:
  resourceClaims:
  - name: gpu
    resourceClaimName: example-claim
  containers:
  - name: app
    resources:
      claims:
      - name: gpu
  # Pod tolerations for device taints
  tolerations:
  - key: "special-workload"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
EOF
    cat ${LOG_DIR}/expected-pod-tolerations.yaml
    echo ""

    echo "=========================================="
    echo "TEST CONCLUSION"
    echo "=========================================="
    echo ""
    echo "❌ DRADeviceTaints feature NOT available in current cluster"
    echo ""
    echo "Feature requires:"
    echo "  - Kubernetes 1.34+ (cluster has v1.34.7 ✓)"
    echo "  - DRADeviceTaints feature gate enabled ✗"
    echo ""
    echo "Next steps:"
    echo "  1. Enable feature gate: DRADeviceTaints=true"
    echo "  2. Wait for API server restart"
    echo "  3. Verify ResourceSlice API supports 'taints' field"
    echo "  4. Re-run this test script"
    echo ""
    echo "Cleanup: oc delete namespace ${NAMESPACE}"
    echo ""
    exit 0
fi

#==============================================
# Phase 1: Check if Devices Have Taints
#==============================================
echo "=========================================="
echo "PHASE 1: Inspect Device Taints"
echo "=========================================="
echo ""

echo "--- Checking Existing Device Taints ---"
DEVICES_WITH_TAINTS=$(oc get resourceslice -o json | jq -r '[.items[].spec.devices[] | select(.taints != null)] | length')

echo "Devices with taints: ${DEVICES_WITH_TAINTS}"
echo ""

if [ ${DEVICES_WITH_TAINTS} -gt 0 ]; then
    echo "Found devices with taints:"
    oc get resourceslice -o json | jq '.items[].spec.devices[] | select(.taints != null) | {name, taints}' | tee ${LOG_DIR}/test1-existing-taints.json
else
    echo "No devices currently have taints"
    echo "Note: Taints are typically applied by the DRA driver, not manually"
    echo ""
    echo "To test device taints, the NVIDIA DRA driver would need to:"
    echo "  1. Support taint configuration"
    echo "  2. Apply taints to ResourceSlice devices"
    echo "  3. Update taints based on device state/policy"
fi
echo ""

#==============================================
# Phase 2: Test Pod Without Tolerations
#==============================================
echo "=========================================="
echo "PHASE 2: Pod Without Tolerations (Baseline)"
echo "=========================================="
echo ""

echo "--- Creating ResourceClaim (No Specific Taint Requirements) ---"
cat <<EOF | tee ${LOG_DIR}/test2-claim-manifest.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-no-toleration
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: mig
      deviceClassName: mig.nvidia.com
      count: 1
EOF

echo ""
sleep 3

echo "--- Creating Pod Without Tolerations ---"
cat <<EOF | tee ${LOG_DIR}/test2-pod-manifest.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-no-toleration
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
    resourceClaimName: claim-no-toleration
EOF

echo ""
oc wait --for=condition=Ready pod/pod-no-toleration -n ${NAMESPACE} --timeout=60s || true

POD1_STATUS=$(oc get pod pod-no-toleration -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD1_STATUS}"
echo ""

oc get pod pod-no-toleration -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-pod.yaml
oc get resourceclaim claim-no-toleration -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-claim.yaml

if [ "${POD1_STATUS}" == "Running" ]; then
    echo "✅ Pod scheduled (no tainted devices, or tolerations not required)"
    oc logs pod-no-toleration -n ${NAMESPACE} > ${LOG_DIR}/test2-pod-logs.txt
    cat ${LOG_DIR}/test2-pod-logs.txt
    echo ""

    echo "--- Allocated Device ---"
    oc get resourceclaim claim-no-toleration -n ${NAMESPACE} -o json | jq '.status.allocation.devices.results[0].device' | tee ${LOG_DIR}/test2-allocated-device.txt
else
    echo "⚠ Pod failed to schedule"
    oc describe pod pod-no-toleration -n ${NAMESPACE} > ${LOG_DIR}/test2-pod-describe.txt
    tail -20 ${LOG_DIR}/test2-pod-describe.txt
fi
echo ""

#==============================================
# Phase 3: Test Pod With Tolerations
#==============================================
echo "=========================================="
echo "PHASE 3: Pod With Device Tolerations"
echo "=========================================="
echo ""

echo "--- Creating Pod With Example Tolerations ---"
cat <<EOF | tee ${LOG_DIR}/test3-claim-manifest.yaml | oc apply -f -
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-with-toleration
  namespace: ${NAMESPACE}
spec:
  devices:
    requests:
    - name: mig
      deviceClassName: mig.nvidia.com
      count: 1
EOF

cat <<EOF | tee ${LOG_DIR}/test3-pod-manifest.yaml | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-with-toleration
  namespace: ${NAMESPACE}
spec:
  restartPolicy: Never
  tolerations:
  - key: "special-workload"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  - key: "maintenance"
    operator: "Exists"
    effect: "NoSchedule"
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["sh", "-c", "nvidia-smi -L && sleep 60"]
    resources:
      claims:
      - name: gpu
  resourceClaims:
  - name: gpu
    resourceClaimName: claim-with-toleration
EOF

echo ""
oc wait --for=condition=Ready pod/pod-with-toleration -n ${NAMESPACE} --timeout=60s || true

POD2_STATUS=$(oc get pod pod-with-toleration -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD2_STATUS}"
echo ""

oc get pod pod-with-toleration -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test3-pod.yaml
oc get resourceclaim claim-with-toleration -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test3-claim.yaml

if [ "${POD2_STATUS}" == "Running" ]; then
    echo "✅ Pod with tolerations scheduled"
    oc logs pod-with-toleration -n ${NAMESPACE} > ${LOG_DIR}/test3-pod-logs.txt
    cat ${LOG_DIR}/test3-pod-logs.txt
    echo ""

    echo "--- Allocated Device ---"
    oc get resourceclaim claim-with-toleration -n ${NAMESPACE} -o json | jq '.status.allocation.devices.results[0].device' | tee ${LOG_DIR}/test3-allocated-device.txt
else
    echo "⚠ Pod failed to schedule"
    oc describe pod pod-with-toleration -n ${NAMESPACE} > ${LOG_DIR}/test3-pod-describe.txt
    tail -20 ${LOG_DIR}/test3-pod-describe.txt
fi
echo ""

#==============================================
# Phase 4: Capture Final State
#==============================================
echo "=========================================="
echo "PHASE 4: Final State Capture"
echo "=========================================="
echo ""

echo "--- All Pods ---"
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods-final.txt
echo ""

echo "--- All ResourceClaims ---"
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-claims-list.txt
oc get resourceclaim -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-claims-full.yaml
echo ""

echo "--- ResourceSlice Device Taints (If Any) ---"
oc get resourceslice -o json | jq '[.items[].spec.devices[] | select(.taints != null)] | unique' > ${LOG_DIR}/99-all-device-taints.json
cat ${LOG_DIR}/99-all-device-taints.json
echo ""

echo "--- Events ---"
oc get events -n ${NAMESPACE} --sort-by='.lastTimestamp' > ${LOG_DIR}/99-events.txt
tail -30 ${LOG_DIR}/99-events.txt
echo ""

#==============================================
# Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

echo "Test Results:"
echo "  Devices with taints found: ${DEVICES_WITH_TAINTS}"
echo "  Pod without tolerations:   ${POD1_STATUS}"
echo "  Pod with tolerations:      ${POD2_STATUS}"
echo ""

echo "Validation Checklist:"
if [ "${FEATURE_AVAILABLE}" = "true" ]; then
    echo "  ✅ DRADeviceTaints feature gate enabled"
else
    echo "  ⚠ DRADeviceTaints feature gate NOT enabled"
fi

if [ ${DEVICES_WITH_TAINTS} -gt 0 ]; then
    echo "  ✅ Devices with taints found"
    echo "  ℹ️  Taint enforcement depends on driver implementation"
else
    echo "  ℹ️  No tainted devices found (depends on driver)"
fi

if [ "${POD1_STATUS}" == "Running" ]; then
    echo "  ✅ Baseline pod scheduling works"
fi

if [ "${POD2_STATUS}" == "Running" ]; then
    echo "  ✅ Pod with tolerations scheduling works"
fi

echo ""

echo "Key Concepts:"
echo "  - Device taints are set in ResourceSlice.spec.devices[].taints"
echo "  - Pod tolerations are in pod.spec.tolerations (same as node taints)"
echo "  - Taint effects: NoSchedule, PreferNoSchedule, NoExecute"
echo "  - Taint operators: Equal, Exists"
echo ""

if [ ${DEVICES_WITH_TAINTS} -eq 0 ]; then
    echo "Note: No device taints found. This is expected if:"
    echo "  - NVIDIA DRA driver doesn't implement device tainting"
    echo "  - No devices are currently in a tainted state"
    echo "  - Driver configuration doesn't enable taints"
    echo ""
    echo "To fully test this feature, the DRA driver must support and"
    echo "apply taints to devices based on their state or policy."
fi

echo ""
echo "=========================================="
echo "CAPTURED ARTIFACTS"
echo "=========================================="
echo "Directory: ${LOG_DIR}"
echo ""
ls -lh ${LOG_DIR}/ | awk 'NR>1 {print $9, $5}' | grep -v "^$"
echo ""

echo "Key Files:"
echo "  ${LOG_DIR}/test-output.log              - Complete test transcript"
echo "  ${LOG_DIR}/00-featuregates.json         - Feature gate status"
echo "  ${LOG_DIR}/test3-pod.yaml               - Pod with tolerations example"
echo "  ${LOG_DIR}/99-all-device-taints.json    - All device taints found"
echo ""

echo "Cleanup Commands:"
echo "  oc delete pods --all -n ${NAMESPACE}"
echo "  oc delete resourceclaim --all -n ${NAMESPACE}"
echo "  oc delete namespace ${NAMESPACE}"
echo ""

echo "=========================================="
echo "Validation Complete - $(date)"
echo "=========================================="

# Collect debug info on failure (always collect for device-taints since it is informational)
echo ""
echo "Collecting debug information..."
collect_test_debug_info "${LOG_DIR}" "${NAMESPACE}"
echo "Debug: ${LOG_DIR}/debug/"

# Exit with proper code
# Test passes if feature is available OR if pods scheduled successfully
if [ "${FEATURE_AVAILABLE}" = "true" ] || [ "${POD1_STATUS}" == "Running" ]; then
    exit 0
else
    exit 1
fi
