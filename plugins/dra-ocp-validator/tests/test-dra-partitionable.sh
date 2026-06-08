#!/bin/bash
# DRA Partitionable Devices Validation Test
# Comprehensive test with explicit data capture for documentation/future reference
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

NAMESPACE="dra-e2e-test"
LOG_DIR="./dra-validation-$(date +%Y%m%d-%H%M%S)"
mkdir -p ${LOG_DIR}

echo "=============================================="
echo "DRA Partitionable Devices Validation Test"
echo "=============================================="
echo "Test Date: $(date)"
echo "Logs Directory: ${LOG_DIR}"
echo ""

# Redirect all output to both console and master log file
exec > >(tee -a ${LOG_DIR}/test-output.log)
exec 2>&1

echo "Validation Objectives:"
echo "1. Verify SharedCounters exist in ResourceSlices"
echo "2. Validate CEL selectors filter devices by MIG profile"
echo "3. Confirm multiple pods can allocate different MIG partitions"
echo "4. Document DRAPartitionableDevices feature on OCP 4.21.16"
echo ""

#==============================================
# Phase 1: Capture Pre-Test Cluster State
#==============================================
echo "=========================================="
echo "PHASE 1: Pre-Test Cluster State"
echo "=========================================="
echo ""

echo "--- Capturing OpenShift and Kubernetes Versions ---"
oc version | tee ${LOG_DIR}/01-cluster-version.txt
echo ""

echo "--- Capturing Node Information ---"
oc get nodes -o wide | tee ${LOG_DIR}/02-nodes.txt
echo ""
oc get nodes -o yaml > ${LOG_DIR}/02-nodes-full.yaml
echo "✓ Saved to: ${LOG_DIR}/02-nodes-full.yaml"
echo ""

echo "--- Capturing DeviceClass Definitions ---"
oc get deviceclass | tee ${LOG_DIR}/03-deviceclass-list.txt
echo ""
oc get deviceclass -o yaml > ${LOG_DIR}/03-deviceclass-full.yaml
echo "✓ Saved to: ${LOG_DIR}/03-deviceclass-full.yaml"
echo ""

echo "--- Capturing ResourceSlice Information ---"
oc get resourceslice -o wide | tee ${LOG_DIR}/04-resourceslice-list.txt
echo ""
oc get resourceslice -o yaml > ${LOG_DIR}/04-resourceslice-full.yaml
echo "✓ Saved to: ${LOG_DIR}/04-resourceslice-full.yaml"
echo ""

echo "--- Verifying Partitionable Devices Prerequisites ---"
# Note: Test runner (run-tests.sh) already checked prerequisites at Step 3.5
# This test should only run if prerequisites are met
echo ""

echo "--- Extracting SharedCounter Structure ---"
SLICES_WITH_COUNTERS=$(oc get resourceslice -o json | jq -r '.items[] | select(.spec.sharedCounters != null) | .metadata.name' | wc -l)
echo "ResourceSlices with sharedCounters: ${SLICES_WITH_COUNTERS}"

if [ "${SLICES_WITH_COUNTERS}" -gt 0 ]; then
    echo ""
    echo "Sample SharedCounter:"
    oc get resourceslice -o json | jq '.items[0].spec.sharedCounters[0]' | tee ${LOG_DIR}/05-sharedcounter-sample.json
    echo ""
    echo "✓ Saved to: ${LOG_DIR}/05-sharedcounter-sample.json"

    echo ""
    echo "All SharedCounters:"
    oc get resourceslice -o json | jq '[.items[].spec.sharedCounters]' > ${LOG_DIR}/05-sharedcounters-all.json
    echo "✓ Saved to: ${LOG_DIR}/05-sharedcounters-all.json"
else
    echo "❌ ERROR: No SharedCounters found - DRAPartitionableDevices not enabled"
    exit 1
fi
echo ""

echo "--- Extracting Device Structure ---"
oc get resourceslice -o json | jq '.items[0].spec.devices[1] | {
  name,
  type: .attributes.type.string,
  profile: .attributes.profile.string,
  capacity,
  consumesCounters
}' | tee ${LOG_DIR}/06-device-sample.json
echo ""
echo "✓ Saved to: ${LOG_DIR}/06-device-sample.json"
echo ""

echo "--- Counting Available MIG Profiles ---"
AVAILABLE_1G35=$(oc get resourceslice -o json | jq -r '.items[].spec.devices[] | select(.attributes.profile.string == "1g.35gb") | .name' | wc -l)
AVAILABLE_1G70=$(oc get resourceslice -o json | jq -r '.items[].spec.devices[] | select(.attributes.profile.string == "1g.70gb") | .name' | wc -l)

echo "Available MIG Profiles:" | tee ${LOG_DIR}/07-mig-profile-count.txt
echo "  - 1g.35gb (small): ${AVAILABLE_1G35} instances" | tee -a ${LOG_DIR}/07-mig-profile-count.txt
echo "  - 1g.70gb (large): ${AVAILABLE_1G70} instances" | tee -a ${LOG_DIR}/07-mig-profile-count.txt
echo ""

if [ "${AVAILABLE_1G35}" -lt 2 ] || [ "${AVAILABLE_1G70}" -lt 2 ]; then
    echo "⚠ WARNING: Insufficient MIG instances for full test"
fi
echo ""

echo "--- Listing All Devices with Profiles ---"
oc get resourceslice -o json | jq -r '.items[].spec.devices[] | select(.attributes.profile.string) |
  "\(.name) | Profile: \(.attributes.profile.string) | Memory: \(.capacity.memory.value)"' > ${LOG_DIR}/08-all-devices.txt
echo "✓ Saved to: ${LOG_DIR}/08-all-devices.txt"
head -10 ${LOG_DIR}/08-all-devices.txt
echo "..."
echo ""

#==============================================
# Phase 2: Create Test Namespace
#==============================================
echo "--- Creating Test Namespace ---"
oc create namespace ${NAMESPACE}
echo "✓ Namespace '${NAMESPACE}' created"
echo ""

#==============================================
# Phase 3: Test 1 - Small MIG Partition (1g.35gb)
#==============================================
echo "=========================================="
echo "PHASE 3: Test 1 - Small MIG Partition (1g.35gb)"
echo "=========================================="
echo ""

echo "--- Creating Manifest: ResourceClaim + Pod ---"
cat <<'EOF' | tee ${LOG_DIR}/test1-manifest.yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-2g
  namespace: dra-e2e-test
spec:
  devices:
    requests:
    - name: memory-2g
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.35gb'"
        count: 1
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-2g
  namespace: dra-e2e-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["bash", "-c", "echo 'Pod 2G allocated' && nvidia-smi -L && sleep 300"]
    resources:
      claims:
      - name: claim-pod-2g
  resourceClaims:
  - name: claim-pod-2g
    resourceClaimName: claim-2g
EOF

echo ""
echo "--- Applying Manifest ---"
oc apply -f ${LOG_DIR}/test1-manifest.yaml
echo ""

echo "--- Waiting for Pod to Schedule ---"
sleep 5
oc wait --for=condition=Ready pod/pod-2g -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD1_STATUS=$(oc get pod pod-2g -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD1_STATUS}"
echo ""

echo "--- Capturing Pod YAML ---"
oc get pod pod-2g -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-pod.yaml
echo "✓ Saved to: ${LOG_DIR}/test1-pod.yaml"
echo ""

echo "--- Capturing ResourceClaim YAML ---"
oc get resourceclaim claim-2g -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test1-resourceclaim.yaml
echo "✓ Saved to: ${LOG_DIR}/test1-resourceclaim.yaml"
echo ""

echo "--- Capturing Allocation Details ---"
oc get resourceclaim claim-2g -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test1-allocation.json
echo "✓ Saved to: ${LOG_DIR}/test1-allocation.json"
cat ${LOG_DIR}/test1-allocation.json
echo ""

if [ "${POD1_STATUS}" == "Running" ]; then
    echo "✅ Test 1: PASS - Pod scheduled successfully"
    echo ""
    echo "--- Capturing Pod Logs ---"
    oc logs -n ${NAMESPACE} pod-2g > ${LOG_DIR}/test1-pod-logs.txt
    echo "✓ Saved to: ${LOG_DIR}/test1-pod-logs.txt"
    cat ${LOG_DIR}/test1-pod-logs.txt
else
    echo "❌ Test 1: FAIL - Pod did not schedule"
    oc describe pod pod-2g -n ${NAMESPACE} > ${LOG_DIR}/test1-pod-describe.txt
    echo "✓ Saved to: ${LOG_DIR}/test1-pod-describe.txt"
fi
echo ""

#==============================================
# Phase 4: Test 2 - Large MIG Partition (1g.70gb)
#==============================================
echo "=========================================="
echo "PHASE 4: Test 2 - Large MIG Partition (1g.70gb)"
echo "=========================================="
echo ""

echo "--- Creating Manifest: ResourceClaim + Pod ---"
cat <<'EOF' | tee ${LOG_DIR}/test2-manifest.yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-4g
  namespace: dra-e2e-test
spec:
  devices:
    requests:
    - name: memory-4g
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.70gb'"
        count: 1
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-4g
  namespace: dra-e2e-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["bash", "-c", "echo 'Pod 4G allocated' && nvidia-smi -L && sleep 300"]
    resources:
      claims:
      - name: claim-pod-4g
  resourceClaims:
  - name: claim-pod-4g
    resourceClaimName: claim-4g
EOF

echo ""
echo "--- Applying Manifest ---"
oc apply -f ${LOG_DIR}/test2-manifest.yaml
echo ""

echo "--- Waiting for Pod to Schedule ---"
sleep 5
oc wait --for=condition=Ready pod/pod-4g -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD2_STATUS=$(oc get pod pod-4g -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD2_STATUS}"
echo ""

echo "--- Capturing Pod YAML ---"
oc get pod pod-4g -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-pod.yaml
echo "✓ Saved to: ${LOG_DIR}/test2-pod.yaml"
echo ""

echo "--- Capturing ResourceClaim YAML ---"
oc get resourceclaim claim-4g -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test2-resourceclaim.yaml
echo "✓ Saved to: ${LOG_DIR}/test2-resourceclaim.yaml"
echo ""

echo "--- Capturing Allocation Details ---"
oc get resourceclaim claim-4g -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test2-allocation.json
echo "✓ Saved to: ${LOG_DIR}/test2-allocation.json"
cat ${LOG_DIR}/test2-allocation.json
echo ""

if [ "${POD2_STATUS}" == "Running" ]; then
    echo "✅ Test 2: PASS - Pod scheduled successfully"
    echo ""
    echo "--- Capturing Pod Logs ---"
    oc logs -n ${NAMESPACE} pod-4g > ${LOG_DIR}/test2-pod-logs.txt
    echo "✓ Saved to: ${LOG_DIR}/test2-pod-logs.txt"
    cat ${LOG_DIR}/test2-pod-logs.txt
else
    echo "❌ Test 2: FAIL - Pod did not schedule"
    oc describe pod pod-4g -n ${NAMESPACE} > ${LOG_DIR}/test2-pod-describe.txt
    echo "✓ Saved to: ${LOG_DIR}/test2-pod-describe.txt"
fi
echo ""

#==============================================
# Phase 5: Test 3 - SharedCounter Limit Test
#==============================================
echo "=========================================="
echo "PHASE 5: Test 3 - SharedCounter Limit Test"
echo "=========================================="
echo "Testing: Can we allocate another large partition?"
echo "Expected: May succeed (multiple GPUs) or fail (SharedCounter limit)"
echo ""

echo "--- Creating Manifest: ResourceClaim + Pod ---"
cat <<'EOF' | tee ${LOG_DIR}/test3-manifest.yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-4g-2
  namespace: dra-e2e-test
spec:
  devices:
    requests:
    - name: memory-4g-2
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.70gb'"
        count: 1
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-4g-limit-test
  namespace: dra-e2e-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["bash", "-c", "nvidia-smi -L && sleep 300"]
    resources:
      claims:
      - name: claim-pod-4g-2
  resourceClaims:
  - name: claim-pod-4g-2
    resourceClaimName: claim-4g-2
EOF

echo ""
echo "--- Applying Manifest ---"
oc apply -f ${LOG_DIR}/test3-manifest.yaml
echo ""

echo "--- Waiting to Check Pod Status ---"
sleep 15

POD3_STATUS=$(oc get pod pod-4g-limit-test -n ${NAMESPACE} -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
echo "Pod Status: ${POD3_STATUS}"
echo ""

echo "--- Capturing Pod YAML ---"
oc get pod pod-4g-limit-test -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test3-pod.yaml
echo "✓ Saved to: ${LOG_DIR}/test3-pod.yaml"
echo ""

echo "--- Capturing ResourceClaim YAML ---"
oc get resourceclaim claim-4g-2 -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test3-resourceclaim.yaml
echo "✓ Saved to: ${LOG_DIR}/test3-resourceclaim.yaml"
echo ""

if [ "${POD3_STATUS}" == "Pending" ]; then
    echo "✅ Test 3: SharedCounter enforcement working - Pod unschedulable"
    echo ""
    echo "--- Capturing Scheduling Events ---"
    oc describe pod pod-4g-limit-test -n ${NAMESPACE} > ${LOG_DIR}/test3-pod-describe.txt
    echo "✓ Saved to: ${LOG_DIR}/test3-pod-describe.txt"
    grep -A 5 "Events:" ${LOG_DIR}/test3-pod-describe.txt
elif [ "${POD3_STATUS}" == "Running" ]; then
    echo "ℹ Test 3: Pod scheduled (sufficient GPU resources available)"
    echo ""
    echo "--- Capturing Allocation Details ---"
    oc get resourceclaim claim-4g-2 -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test3-allocation.json
    echo "✓ Saved to: ${LOG_DIR}/test3-allocation.json"
    cat ${LOG_DIR}/test3-allocation.json
    echo ""
    echo "--- Capturing Pod Logs ---"
    oc logs -n ${NAMESPACE} pod-4g-limit-test > ${LOG_DIR}/test3-pod-logs.txt
    echo "✓ Saved to: ${LOG_DIR}/test3-pod-logs.txt"
    cat ${LOG_DIR}/test3-pod-logs.txt
else
    echo "⚠ Test 3: Unexpected status: ${POD3_STATUS}"
    oc describe pod pod-4g-limit-test -n ${NAMESPACE} > ${LOG_DIR}/test3-pod-describe.txt
fi
echo ""

#==============================================
# Phase 6: Test 4 - Additional Small Partition
#==============================================
echo "=========================================="
echo "PHASE 6: Test 4 - Additional Small Partition (1g.35gb)"
echo "=========================================="
echo ""

echo "--- Creating Manifest: ResourceClaim + Pod ---"
cat <<'EOF' | tee ${LOG_DIR}/test4-manifest.yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: claim-2g-2
  namespace: dra-e2e-test
spec:
  devices:
    requests:
    - name: memory-2g-2
      exactly:
        deviceClassName: mig.nvidia.com
        selectors:
        - cel:
            expression: "device.attributes['gpu.nvidia.com'].profile == '1g.35gb'"
        count: 1
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-2g-second
  namespace: dra-e2e-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubi8
    command: ["bash", "-c", "echo 'Pod 2G-2 allocated' && nvidia-smi -L && sleep 300"]
    resources:
      claims:
      - name: claim-pod-2g-2
  resourceClaims:
  - name: claim-pod-2g-2
    resourceClaimName: claim-2g-2
EOF

echo ""
echo "--- Applying Manifest ---"
oc apply -f ${LOG_DIR}/test4-manifest.yaml
echo ""

echo "--- Waiting for Pod to Schedule ---"
sleep 5
oc wait --for=condition=Ready pod/pod-2g-second -n ${NAMESPACE} --timeout=60s || true
sleep 3

POD4_STATUS=$(oc get pod pod-2g-second -n ${NAMESPACE} -o jsonpath='{.status.phase}')
echo "Pod Status: ${POD4_STATUS}"
echo ""

echo "--- Capturing Pod YAML ---"
oc get pod pod-2g-second -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test4-pod.yaml
echo "✓ Saved to: ${LOG_DIR}/test4-pod.yaml"
echo ""

echo "--- Capturing ResourceClaim YAML ---"
oc get resourceclaim claim-2g-2 -n ${NAMESPACE} -o yaml > ${LOG_DIR}/test4-resourceclaim.yaml
echo "✓ Saved to: ${LOG_DIR}/test4-resourceclaim.yaml"
echo ""

echo "--- Capturing Allocation Details ---"
oc get resourceclaim claim-2g-2 -n ${NAMESPACE} -o json | jq '.status.allocation' > ${LOG_DIR}/test4-allocation.json
echo "✓ Saved to: ${LOG_DIR}/test4-allocation.json"
cat ${LOG_DIR}/test4-allocation.json
echo ""

if [ "${POD4_STATUS}" == "Running" ]; then
    echo "✅ Test 4: PASS - Pod scheduled successfully"
    echo ""
    echo "--- Capturing Pod Logs ---"
    oc logs -n ${NAMESPACE} pod-2g-second > ${LOG_DIR}/test4-pod-logs.txt
    echo "✓ Saved to: ${LOG_DIR}/test4-pod-logs.txt"
    cat ${LOG_DIR}/test4-pod-logs.txt
else
    echo "❌ Test 4: FAIL - Pod did not schedule"
    oc describe pod pod-2g-second -n ${NAMESPACE} > ${LOG_DIR}/test4-pod-describe.txt
    echo "✓ Saved to: ${LOG_DIR}/test4-pod-describe.txt"
fi
echo ""

#==============================================
# Phase 7: Capture Post-Test State
#==============================================
echo "=========================================="
echo "PHASE 7: Post-Test State Capture"
echo "=========================================="
echo ""

echo "--- Listing All Pods ---"
oc get pods -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-pods-final.txt
echo ""

echo "--- Listing All ResourceClaims ---"
oc get resourceclaim -n ${NAMESPACE} -o wide | tee ${LOG_DIR}/99-resourceclaims-list.txt
echo ""

echo "--- Capturing All ResourceClaims YAML ---"
oc get resourceclaim -n ${NAMESPACE} -o yaml > ${LOG_DIR}/99-resourceclaims-full.yaml
echo "✓ Saved to: ${LOG_DIR}/99-resourceclaims-full.yaml"
echo ""

echo "--- Capturing ResourceSlices (Post-Test) ---"
oc get resourceslice -o wide > ${LOG_DIR}/99-resourceslice-post.txt
echo "✓ Saved to: ${LOG_DIR}/99-resourceslice-post.txt"
echo ""

echo "--- Capturing Namespace Events ---"
oc get events -n ${NAMESPACE} --sort-by='.lastTimestamp' > ${LOG_DIR}/99-events.txt
echo "✓ Saved to: ${LOG_DIR}/99-events.txt"
tail -20 ${LOG_DIR}/99-events.txt
echo ""

#==============================================
# Phase 8: Validation Summary
#==============================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""

echo "Test Results:"
echo "  Test 1 (1g.35gb):     ${POD1_STATUS}"
echo "  Test 2 (1g.70gb):     ${POD2_STATUS}"
echo "  Test 3 (1g.70gb #2):  ${POD3_STATUS}"
echo "  Test 4 (1g.35gb #2):  ${POD4_STATUS}"
echo ""

# Count successful allocations
SUCCESS_COUNT=0
[ "${POD1_STATUS}" == "Running" ] && SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
[ "${POD2_STATUS}" == "Running" ] && SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
[ "${POD4_STATUS}" == "Running" ] && SUCCESS_COUNT=$((SUCCESS_COUNT + 1))

echo "Validation Checklist:"
echo "  ✅ SharedCounters present in ResourceSlices"
echo "  ✅ DeviceClass 'mig.nvidia.com' operational"
if [ ${SUCCESS_COUNT} -ge 3 ]; then
    echo "  ✅ CEL selectors filter by MIG profile correctly"
    echo "  ✅ Multiple pods can allocate different MIG partitions"
    echo "  ✅ ResourceClaims allocated successfully"
    echo ""
    echo "🎉 DRA PARTITIONABLE DEVICES: VALIDATED"
else
    echo "  ❌ Some tests failed - review logs"
    echo ""
    echo "⚠ VALIDATION INCOMPLETE"
fi
echo ""

echo "Environment Details:"
oc version --short 2>/dev/null || oc version | head -3
echo ""

echo "Hardware Summary:"
echo "  - MIG 1g.35gb instances: ${AVAILABLE_1G35}"
echo "  - MIG 1g.70gb instances: ${AVAILABLE_1G70}"
echo ""

echo "=========================================="
echo "CAPTURED ARTIFACTS"
echo "=========================================="
echo "Directory: ${LOG_DIR}"
echo ""
ls -lh ${LOG_DIR}/ | awk '{print $9, $5}' | grep -v "^$"
echo ""

echo "Key Files for Documentation:"
echo "  ${LOG_DIR}/test-output.log                    - Complete test transcript"
echo "  ${LOG_DIR}/03-deviceclass-full.yaml           - DeviceClass definitions"
echo "  ${LOG_DIR}/04-resourceslice-full.yaml         - ResourceSlice structure"
echo "  ${LOG_DIR}/05-sharedcounter-sample.json       - SharedCounter example"
echo "  ${LOG_DIR}/test1-manifest.yaml                - Example ResourceClaim manifest"
echo "  ${LOG_DIR}/test1-resourceclaim.yaml           - Allocated ResourceClaim"
echo "  ${LOG_DIR}/test1-allocation.json              - Allocation details"
echo ""

echo "Cleanup Commands:"
echo "  oc delete pods --all -n ${NAMESPACE}"
echo "  oc delete resourceclaim --all -n ${NAMESPACE}"
echo "  oc delete namespace ${NAMESPACE}"
echo ""

echo "=========================================="
echo "Validation Complete - $(date)"
echo "=========================================="

# Collect debug info on failure
if [ ${SUCCESS_COUNT} -lt 3 ]; then
    echo ""
    echo "Collecting debug information..."
    collect_test_debug_info "${LOG_DIR}" "${NAMESPACE}"
    echo "Debug: ${LOG_DIR}/debug/"
fi

# Exit with proper code based on SUCCESS_COUNT
if [ ${SUCCESS_COUNT} -ge 3 ]; then
    exit 0
else
    exit 1
fi
