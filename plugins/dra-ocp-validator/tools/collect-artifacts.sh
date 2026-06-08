#!/bin/bash
# Collect all DRA validation artifacts and generate report

set -euo pipefail

KUBECONFIG_PATH=$1
OUTPUT_DIR=$2
CLUSTER_NAME=${3:-cluster}

export KUBECONFIG=${KUBECONFIG_PATH}

echo "======================================"
echo "Artifact Collection"
echo "======================================"
echo "Output Directory: ${OUTPUT_DIR}"
echo ""

mkdir -p "${OUTPUT_DIR}"

#========================================
# Cluster Information
#========================================
echo "=== Collecting Cluster Information ==="

oc version -o json > "${OUTPUT_DIR}/cluster-version.json" 2>/dev/null || true
oc get nodes -o wide > "${OUTPUT_DIR}/nodes.txt" 2>/dev/null || true
oc get nodes -o json > "${OUTPUT_DIR}/nodes.json" 2>/dev/null || true

echo "✓ Cluster info collected"

#========================================
# DRA Resources
#========================================
echo "=== Collecting DRA Resources ==="

oc get deviceclass -o yaml > "${OUTPUT_DIR}/deviceclass.yaml" 2>/dev/null || echo "⚠ No DeviceClasses"
oc get deviceclass -o json > "${OUTPUT_DIR}/deviceclass.json" 2>/dev/null || true

oc get resourceslice -o yaml > "${OUTPUT_DIR}/resourceslice.yaml" 2>/dev/null || echo "⚠ No ResourceSlices"
oc get resourceslice -o json > "${OUTPUT_DIR}/resourceslice.json" 2>/dev/null || true

oc get resourceclaim --all-namespaces -o yaml > "${OUTPUT_DIR}/resourceclaims-all.yaml" 2>/dev/null || true

echo "✓ DRA resources collected"

#========================================
# Driver Logs
#========================================
echo "=== Collecting Driver Logs ==="

# NVIDIA DRA driver
if oc get namespace nvidia-dra-driver &>/dev/null 2>&1; then
    echo "Collecting NVIDIA DRA driver logs..."
    oc logs -n nvidia-dra-driver daemonset/nvidia-dra-driver --tail=2000 \
        > "${OUTPUT_DIR}/nvidia-dra-driver-logs.txt" 2>/dev/null || true

    oc get pods -n nvidia-dra-driver -o wide \
        > "${OUTPUT_DIR}/nvidia-dra-driver-pods.txt" 2>/dev/null || true
fi

# dra-example-driver
if oc get namespace dra-example-driver &>/dev/null 2>&1; then
    echo "Collecting dra-example-driver logs..."
    oc logs -n dra-example-driver -l app=dra-example-driver --tail=2000 \
        > "${OUTPUT_DIR}/dra-example-driver-logs.txt" 2>/dev/null || true

    oc get pods -n dra-example-driver -o wide \
        > "${OUTPUT_DIR}/dra-example-driver-pods.txt" 2>/dev/null || true
fi

# GPU Operator
if oc get namespace gpu-operator-resources &>/dev/null 2>&1; then
    echo "Collecting GPU Operator logs..."
    oc logs -n gpu-operator-resources deployment/gpu-operator --tail=1000 \
        > "${OUTPUT_DIR}/gpu-operator-logs.txt" 2>/dev/null || true

    oc get pods -n gpu-operator-resources -o wide \
        > "${OUTPUT_DIR}/gpu-operator-pods.txt" 2>/dev/null || true
fi

echo "✓ Driver logs collected"

#========================================
# Test Logs
#========================================
echo "=== Collecting Test Logs ==="

# Copy test log directories
for dir in dra-*-20*/; do
    if [ -d "$dir" ]; then
        cp -r "$dir" "${OUTPUT_DIR}/" 2>/dev/null || true
        echo "  ✓ Copied: $dir"
    fi
done

# Count test logs
TEST_LOG_COUNT=$(find "${OUTPUT_DIR}" -type d -name "dra-*-20*" | wc -l)
echo "✓ Collected ${TEST_LOG_COUNT} test log directories"

#========================================
# Feature Gates
#========================================
echo "=== Collecting Feature Gate Status ==="

oc get featuregate cluster -o json > "${OUTPUT_DIR}/featuregate.json" 2>/dev/null || true
oc get featuregate cluster -o json | \
    jq -r '.status.featureGates[].enabled[] | select(.name | contains("DRA"))' \
    > "${OUTPUT_DIR}/featuregate-dra.json" 2>/dev/null || true

echo "✓ Feature gates collected"

#========================================
# Events
#========================================
echo "=== Collecting Events ==="

# Get events from all test namespaces
for ns in $(oc get namespaces -o name | grep 'dra-.*-test' | sed 's|namespace/||'); do
    oc get events -n ${ns} --sort-by='.lastTimestamp' \
        > "${OUTPUT_DIR}/events-${ns}.txt" 2>/dev/null || true
done

echo "✓ Events collected"

#========================================
# Generate Validation Report
#========================================
echo "=== Generating Validation Report ==="

# Extract cluster info
OCP_VERSION=$(jq -r '.openshiftVersion // "unknown"' "${OUTPUT_DIR}/cluster-version.json" 2>/dev/null || echo "unknown")
K8S_VERSION=$(jq -r '.serverVersion.gitVersion // "unknown"' "${OUTPUT_DIR}/cluster-version.json" 2>/dev/null || echo "unknown")
NODE_COUNT=$(wc -l < "${OUTPUT_DIR}/nodes.txt" 2>/dev/null || echo "0")

# Count DRA resources
DEVICECLASS_COUNT=$(oc get deviceclass --no-headers 2>/dev/null | wc -l || echo "0")
RESOURCESLICE_COUNT=$(oc get resourceslice --no-headers 2>/dev/null | wc -l || echo "0")

# Detect GPU info
GPU_INFO=$(oc get nodes -o json | \
    jq -r '.items[0].metadata.labels | to_entries[] | select(.key | contains("pci-10de")) | .key' 2>/dev/null | head -1 || echo "")

if [ -n "${GPU_INFO}" ]; then
    GPU_VENDOR="NVIDIA"
else
    GPU_VENDOR="Unknown/Example Driver"
fi

# Generate report
cat > "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md" <<EOF
# DRA Validation Report

**Date**: $(date +%Y-%m-%d)
**Cluster**: ${CLUSTER_NAME}
**OCP Version**: ${OCP_VERSION}
**Kubernetes Version**: ${K8S_VERSION}
**Nodes**: ${NODE_COUNT}
**GPU Vendor**: ${GPU_VENDOR}

---

## Cluster Summary

- **DeviceClasses**: ${DEVICECLASS_COUNT}
- **ResourceSlices**: ${RESOURCESLICE_COUNT}
- **Test Logs**: ${TEST_LOG_COUNT} feature validations

---

## DRA Resources

### DeviceClasses
\`\`\`
$(oc get deviceclass 2>/dev/null || echo "None")
\`\`\`

### ResourceSlices (sample)
\`\`\`
$(oc get resourceslice 2>/dev/null | head -10 || echo "None")
\`\`\`

---

## Test Results

EOF

# Parse test results from log directories
for dir in "${OUTPUT_DIR}"/dra-*-20*/; do
    if [ -d "$dir" ]; then
        TEST_NAME=$(basename "$dir" | sed 's/dra-\(.*\)-20.*/\1/' | tr '-' ' ' | sed 's/\b\(.\)/\u\1/g')
        if [ -f "${dir}/test-output.log" ]; then
            # Check for validation status in log
            if grep -q "VALIDATED\|PASS" "${dir}/test-output.log"; then
                echo "### ✅ ${TEST_NAME}" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
                echo "**Status**: PASS" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
            elif grep -q "SKIP" "${dir}/test-output.log"; then
                echo "### ⚠️ ${TEST_NAME}" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
                echo "**Status**: SKIP" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
            else
                echo "### ❌ ${TEST_NAME}" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
                echo "**Status**: UNKNOWN" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
            fi
            echo "**Logs**: $(basename "$dir")" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
            echo "" >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
        fi
    fi
done

cat >> "${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md" <<EOF

---

## Artifacts

All validation artifacts are available in this directory:

- \`cluster-version.json\` - Cluster version information
- \`nodes.txt/json\` - Node details
- \`deviceclass.yaml/json\` - DeviceClass configurations
- \`resourceslice.yaml/json\` - ResourceSlice states
- \`*-driver-logs.txt\` - Driver logs
- \`dra-*-20*/\` - Individual test logs

---

## References

- [Kubernetes DRA Documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/)
- [NVIDIA DRA Driver](https://github.com/NVIDIA/k8s-dra-driver)
- [dra-example-driver](https://github.com/kubernetes-sigs/dra-example-driver)

---

**Generated by**: dra-ocp-validator plugin
**Timestamp**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
EOF

echo "✓ Report generated: ${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"

#========================================
# Create Tarball
#========================================
echo "=== Creating Tarball ==="

TARBALL="${OUTPUT_DIR}.tar.gz"
tar -czf "${TARBALL}" -C "$(dirname "${OUTPUT_DIR}")" "$(basename "${OUTPUT_DIR}")"

TARBALL_SIZE=$(du -h "${TARBALL}" | cut -f1)
echo "✓ Tarball created: ${TARBALL} (${TARBALL_SIZE})"

echo ""
echo "======================================"
echo "Artifact Collection Complete!"
echo "======================================"
echo ""
echo "Report: ${OUTPUT_DIR}/DRA-VALIDATION-REPORT.md"
echo "Tarball: ${TARBALL}"
echo ""
echo "Artifacts ready for attachment to JIRA"
