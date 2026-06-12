#!/usr/bin/env bash
# Setup prerequisites for DRAPartitionableDevices testing (Tech Preview feature)
# This is ONLY needed for partitionable devices - other DRA features work out-of-box
#
# Two-step setup:
# 1. OCP cluster: Enable DRAPartitionableDevices feature gate
# 2. Driver: Verify driver has partition support enabled

set -euo pipefail

KUBECONFIG_PATH="${1:-}"
AUTO_ENABLE="${2:-}"

if [ -z "${KUBECONFIG_PATH}" ]; then
    echo "ERROR: Missing required argument: kubeconfig-path"
    exit 1
fi

export KUBECONFIG="${KUBECONFIG_PATH}"

echo "=========================================="
echo "DRAPartitionableDevices Prerequisites"
echo "=========================================="
echo ""
echo "⚠ ALPHA/TECH PREVIEW FEATURE"
echo ""
echo "DRAPartitionableDevices requires:"
echo "  1. OCP cluster feature gate (CustomNoUpgrade for granular control)"
echo "  2. Driver installed with partition support"
echo ""

# Check OCP version
OCP_VERSION=$(oc version -o json | jq -r '.openshiftVersion // "unknown"')
OCP_MAJOR=$(echo "${OCP_VERSION}" | cut -d. -f1)
OCP_MINOR=$(echo "${OCP_VERSION}" | cut -d. -f2)

echo "OCP Version: ${OCP_VERSION}"
echo ""

#==============================================
# Step 1: Check OCP cluster feature gate
#==============================================
echo "=== Step 1: OCP Cluster Feature Gate ==="
echo ""

FEATURE_GATE="DRAPartitionableDevices"

# Determine feature gate strategy based on OCP version
# OCP 4.21 (K8s 1.34): DRAPartitionableDevices is Alpha upstream - requires TechPreviewNoUpgrade
# OCP 4.22+: May be Beta/GA, check status
# OCP 5.0+: Feature is GA/Beta, auto-enabled
if [ "${OCP_MAJOR}" -ge 5 ]; then
    echo "OCP 5.0+ detected: DRAPartitionableDevices is enabled by default"
    echo "✓ No feature gate configuration needed"
    echo ""
elif [ "${OCP_MAJOR}" -eq 4 ] && [ "${OCP_MINOR}" -eq 21 ]; then
    echo "OCP 4.21 (K8s 1.34) detected: DRAPartitionableDevices is Alpha upstream"
    echo "  Requires TechPreviewNoUpgrade feature set for alpha Kubernetes features"
    echo ""

    # Check if TechPreviewNoUpgrade is already set
    CURRENT_FEATURE_SET=$(oc get featuregate cluster -o json 2>/dev/null | \
        jq -r '.spec.featureSet // ""' || true)

    if [ "${CURRENT_FEATURE_SET}" = "TechPreviewNoUpgrade" ]; then
        echo "✓ TechPreviewNoUpgrade is enabled - DRAPartitionableDevices is available"
        echo ""
    else
        echo "⚠ TechPreviewNoUpgrade is NOT enabled (current: ${CURRENT_FEATURE_SET:-none})"
        echo ""

        if [ "${AUTO_ENABLE}" != "--auto-enable" ]; then
            # Check if running in non-interactive mode (stdin not a terminal)
            if [ ! -t 0 ]; then
                echo "Running in non-interactive mode - skipping prompt"
                echo ""
                echo "To enable DRAPartitionableDevices on OCP 4.21, run:"
                echo "  oc patch featuregate cluster --type=merge \\"
                echo "    -p '{\"spec\":{\"featureSet\":\"TechPreviewNoUpgrade\"}}'"
                echo ""
                echo "Or use --enable-dynamic-mig during setup:"
                echo "  /dra-ocp-validator:setup <kubeconfig> --enable-dynamic-mig"
                exit 1
            fi

            echo "⚠ WARNING: TechPreviewNoUpgrade enables ALL tech preview features."
            echo "           This will prevent cluster upgrades and is only for test clusters."
            echo ""
        fi

        echo "Enabling TechPreviewNoUpgrade feature set..."

        # Patch featuregate to TechPreviewNoUpgrade
        oc patch featuregate cluster --type=merge -p '{"spec":{"featureSet":"TechPreviewNoUpgrade"}}'

        echo ""
        echo "✓ TechPreviewNoUpgrade enabled"
        echo ""
        echo "⚠ Cluster components will restart:"
        echo "  - API server: ~3-6 minutes"
        echo "  - Kubelets: ~2-4 minutes per node"
        echo ""
        echo "Waiting 120 seconds for API server rollout to begin..."
        sleep 120
    fi

elif [ "${OCP_MAJOR}" -eq 4 ] && [ "${OCP_MINOR}" -ge 22 ]; then
    echo "OCP 4.${OCP_MINOR} detected: Checking DRAPartitionableDevices availability"
    echo ""

    # Check if feature is in status (may be Beta/GA in later versions)
    FEATURE_IN_STATUS=$(oc get featuregate cluster -o json 2>/dev/null | \
        jq -r --arg fg "${FEATURE_GATE}" '.status.featureGates[].enabled[]? | select(.name == $fg).name' || true)

    if [ -n "${FEATURE_IN_STATUS}" ]; then
        echo "✓ Feature gate '${FEATURE_GATE}' is enabled by default"
        echo ""
    else
        echo "⚠ Feature gate '${FEATURE_GATE}' not found in default feature set"
        echo ""
        echo "For OCP 4.22+, consult documentation for proper enablement method."
        echo "It may require TechPreviewNoUpgrade or a version-specific feature set."
        exit 1
    fi

else
    echo "⚠ OCP version < 4.21 or > 4.23 detected"
    echo "DRAPartitionableDevices may not be available or may have different enablement"
    echo ""
fi

#==============================================
# Step 2: Verify driver partition support
#==============================================
echo "=== Step 2: Driver Partition Support ==="
echo ""

# Detect which driver is installed
NVIDIA_DRIVER=$(oc get namespace nvidia-dra-driver 2>/dev/null && echo "true" || echo "false")
EXAMPLE_DRIVER=$(oc get namespace dra-example-driver 2>/dev/null && echo "true" || echo "false")

if [ "${NVIDIA_DRIVER}" = "true" ]; then
    echo "Detected: NVIDIA DRA driver"
    echo ""

    # Check if DYNAMIC_MIG is enabled
    DYNAMIC_MIG=$(oc get configmap -n nvidia-dra-driver nvidia-dra-driver-config -o jsonpath='{.data.config\.yaml}' 2>/dev/null | grep -i "DYNAMIC_MIG" || true)

    if [ -n "${DYNAMIC_MIG}" ]; then
        echo "✓ NVIDIA driver has DYNAMIC_MIG configuration"
        echo ""
    else
        echo "⚠ NVIDIA driver may not have DYNAMIC_MIG enabled"
        echo ""
        echo "To enable partitionable devices on NVIDIA, reinstall with:"
        echo "  /dra-ocp-validator:setup --driver nvidia --enable-dynamic-mig"
        echo ""
        exit 1
    fi

elif [ "${EXAMPLE_DRIVER}" = "true" ]; then
    echo "Detected: dra-example-driver"
    echo ""

    # Check if partitions are configured
    PARTITIONS=$(helm get values dra-example-driver -n dra-example-driver -o json 2>/dev/null | \
        jq -r '.kubeletPlugin.gpuPartitions // 0' || echo "0")

    if [ "${PARTITIONS}" -gt 0 ]; then
        echo "✓ Example driver has ${PARTITIONS} GPU partitions configured"
        echo ""
    else
        echo "⚠ Example driver does not have partitions configured"
        echo ""
        echo "To enable partitionable devices, reinstall with:"
        echo "  /dra-ocp-validator:cleanup --keep-operator"
        echo "  /dra-ocp-validator:setup --driver example"
        echo ""
        echo "(setup script automatically configures partitions)"
        exit 1
    fi

else
    echo "❌ No DRA driver found"
    echo ""
    echo "Install a driver first:"
    echo "  /dra-ocp-validator:setup"
    exit 1
fi

# Verify SharedCounters exist in ResourceSlices
echo "=== Step 3: Verify SharedCounters ==="
echo ""

SLICES_WITH_COUNTERS=$(oc get resourceslice -o json | \
    jq -r '.items[] | select(.spec.sharedCounters != null) | .metadata.name' | wc -l || echo "0")

if [ "${SLICES_WITH_COUNTERS}" -gt 0 ]; then
    echo "✓ Found ${SLICES_WITH_COUNTERS} ResourceSlices with SharedCounters"
    echo ""
else
    echo "⚠ No SharedCounters found in ResourceSlices"
    echo ""
    echo "This may indicate:"
    echo "  1. Driver needs restart after feature gate enabled"
    echo "  2. Driver not configured with partitioning"
    echo ""
    echo "Try restarting driver pods:"
    if [ "${NVIDIA_DRIVER}" = "true" ]; then
        echo "  oc delete pods -n nvidia-dra-driver --all"
    elif [ "${EXAMPLE_DRIVER}" = "true" ]; then
        echo "  oc delete pods -n dra-example-driver --all"
    fi
    echo ""
    echo "Wait 30 seconds, then check ResourceSlices again:"
    echo "  oc get resourceslice -o json | jq '.items[0].spec.sharedCounters'"
    echo ""
    exit 1
fi

echo "=========================================="
echo "Prerequisites Complete!"
echo "=========================================="
echo ""
echo "✓ OCP feature gate enabled"
echo "✓ Driver partition support verified"
echo "✓ SharedCounters present in ResourceSlices"
echo ""
echo "Ready to run partitionable devices tests."
