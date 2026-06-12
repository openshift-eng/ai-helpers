#!/bin/bash
# Cluster access verification and hardware discovery tool

set -euo pipefail

KUBECONFIG_PATH=$1

# Get script directory and plugin root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "${SCRIPT_DIR}")"

# Verify required tools
for cmd in oc kubectl jq yq; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: Required command not found: $cmd"
        exit 1
    fi
done

# Source the feature metadata helper
METADATA_HELPER="${SCRIPT_DIR}/feature-metadata.sh"
if [ ! -f "${METADATA_HELPER}" ]; then
    echo "ERROR: feature-metadata.sh not found at ${METADATA_HELPER}"
    exit 1
fi
source "${METADATA_HELPER}"

# Export kubeconfig
export KUBECONFIG=${KUBECONFIG_PATH}

echo "=== Cluster Access Verification ==="

# Test cluster access
if ! oc cluster-info >/dev/null 2>&1; then
    echo "ERROR: Cannot access cluster with kubeconfig: ${KUBECONFIG_PATH}"
    exit 1
fi

echo "✓ Cluster accessible"

# Get cluster versions
OCP_VERSION=$(oc version -o json 2>/dev/null | jq -r '.openshiftVersion // "unknown"')
K8S_VERSION=$(oc version -o json 2>/dev/null | jq -r '.serverVersion.gitVersion // "unknown"')
K8S_MINOR=$(echo ${K8S_VERSION} | sed -E 's/v1\.([0-9]+)\..*/\1/')

echo "OCP Version: ${OCP_VERSION}"
echo "Kubernetes Version: ${K8S_VERSION}"

# Get node count
NODE_COUNT=$(oc get nodes --no-headers 2>/dev/null | wc -l)
echo "Nodes: ${NODE_COUNT}"

echo ""
echo "=== Hardware Discovery ==="

# Check if NFD is installed (check for NFD CR, not just namespace)
NFD_INSTALLED=0
if oc get namespace openshift-nfd &>/dev/null && oc get nodefeaturediscovery -n openshift-nfd &>/dev/null 2>&1; then
    NFD_INSTALLED=1
fi

if [ ${NFD_INSTALLED} -gt 0 ]; then
    echo "✓ NFD installed"

    # Detect NVIDIA GPUs (PCI vendor 10de)
    NVIDIA_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-10de.present=true' --no-headers 2>/dev/null | wc -l || echo "0")

    # Detect AMD GPUs (PCI vendor 1002)
    AMD_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-1002.present=true' --no-headers 2>/dev/null | wc -l || echo "0")

    # Detect Intel GPUs (PCI vendor 8086)
    INTEL_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-8086.present=true' --no-headers 2>/dev/null | wc -l || echo "0")

    if [ ${NVIDIA_NODES} -gt 0 ]; then
        GPU_VENDOR="nvidia"
        GPU_NODES=${NVIDIA_NODES}
    elif [ ${AMD_NODES} -gt 0 ]; then
        GPU_VENDOR="amd"
        GPU_NODES=${AMD_NODES}
    elif [ ${INTEL_NODES} -gt 0 ]; then
        GPU_VENDOR="intel"
        GPU_NODES=${INTEL_NODES}
    else
        GPU_VENDOR="none"
        GPU_NODES=0
    fi
else
    echo "⚠ NFD not installed - cannot auto-detect GPUs"
    GPU_VENDOR="unknown"
    GPU_NODES=0
fi

echo "GPU Vendor: ${GPU_VENDOR}"
echo "GPU Nodes: ${GPU_NODES}"

# Initialize GPU_MODEL
GPU_MODEL=""

# Detect GPU model (if NVIDIA)
if [ "${GPU_VENDOR}" = "nvidia" ] && [ ${GPU_NODES} -gt 0 ]; then
    # Get first GPU node
    GPU_NODE=$(oc get nodes -l 'feature.node.kubernetes.io/pci-10de.present=true' -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    # Try to get GPU model from node labels
    GPU_MODEL=$(oc get node ${GPU_NODE} -o json 2>/dev/null | \
        jq -r '.metadata.labels | to_entries[] | select(.key | contains("nvidia.com/gpu.product")) | .value' | head -1)

    if [ -z "${GPU_MODEL}" ]; then
        GPU_MODEL="Unknown NVIDIA GPU"
    fi

    echo "GPU Model: ${GPU_MODEL}"
fi

echo ""
echo "=== DRA Feature Detection ==="

# Use metadata system to detect features by graduation level
K8S_VERSION_FULL=$(echo "${K8S_VERSION}" | sed -E 's/v(1\.[0-9]+)\..*/\1/')

ALPHA_FEATURES=()
BETA_FEATURES=()
GA_FEATURES=()

for feature in $(list_all_features); do
    if is_feature_available "${feature}" "${K8S_MINOR}" 2>/dev/null; then
        GRADUATION=$(get_feature_graduation "${feature}" "${K8S_VERSION_FULL}" 2>/dev/null || echo "unknown")
        case "${GRADUATION}" in
            alpha)
                ALPHA_FEATURES+=("${feature}")
                ;;
            beta)
                BETA_FEATURES+=("${feature}")
                ;;
            ga)
                GA_FEATURES+=("${feature}")
                ;;
        esac
    fi
done

# Convert arrays to comma-separated strings for backward compatibility
ALPHA_FEATURES_STR=$(IFS=,; echo "${ALPHA_FEATURES[*]}")
BETA_FEATURES_STR=$(IFS=,; echo "${BETA_FEATURES[*]}")
GA_FEATURES_STR=$(IFS=,; echo "${GA_FEATURES[*]}")

echo "GA Features: ${GA_FEATURES_STR:-none}"
echo "Beta Features: ${BETA_FEATURES_STR:-none}"
echo "Alpha Features: ${ALPHA_FEATURES_STR:-none}"

# Check DRA driver installation
echo ""
echo "=== DRA Driver Status ==="

if oc get deviceclass &>/dev/null; then
    DEVICECLASS_COUNT=$(oc get deviceclass --no-headers 2>/dev/null | wc -l)
    echo "DeviceClasses: ${DEVICECLASS_COUNT}"

    if [ ${DEVICECLASS_COUNT} -gt 0 ]; then
        oc get deviceclass -o name
    fi
else
    echo "⚠ No DeviceClasses found - DRA driver may not be installed"
fi

if oc get resourceslice &>/dev/null; then
    RESOURCESLICE_COUNT=$(oc get resourceslice --no-headers 2>/dev/null | wc -l)
    echo "ResourceSlices: ${RESOURCESLICE_COUNT}"
else
    echo "⚠ No ResourceSlices found"
fi

# CDMM detection (NVIDIA Grace-Blackwell only)
echo ""
echo "=== CDMM Detection (NVIDIA Grace-Blackwell) ==="

if [ "${GPU_VENDOR}" = "nvidia" ] && [[ "${GPU_MODEL}" =~ "GB" ]]; then
    # Get first GPU node
    GPU_NODE=$(oc get nodes -l 'feature.node.kubernetes.io/pci-10de.present=true' -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    # Check NUMA node count (requires debug pod)
    NUMA_COUNT=$(oc debug node/${GPU_NODE} -- chroot /host lscpu 2>/dev/null | \
        grep "NUMA node(s):" | awk '{print $3}' || echo "0")

    echo "NUMA nodes: ${NUMA_COUNT}"

    if [ "${NUMA_COUNT}" -gt 10 ]; then
        echo "CDMM Status: Disabled (MIG tests can run)"
        SKIP_MIG="false"
    elif [ "${NUMA_COUNT}" -gt 0 ] && [ "${NUMA_COUNT}" -le 10 ]; then
        echo "CDMM Status: Enabled (MIG tests will be skipped - NVIDIA limitation)"
        SKIP_MIG="true"
    else
        echo "CDMM Status: Unknown (could not determine NUMA count)"
        SKIP_MIG="false"
    fi
else
    echo "CDMM detection not applicable (not NVIDIA Grace-Blackwell)"
    SKIP_MIG="false"
fi

# Output summary as JSON for programmatic consumption
echo ""
echo "=== Summary (JSON) ==="
cat <<EOF
{
  "cluster": {
    "ocp_version": "${OCP_VERSION}",
    "k8s_version": "${K8S_VERSION}",
    "k8s_minor": ${K8S_MINOR},
    "node_count": ${NODE_COUNT}
  },
  "hardware": {
    "gpu_vendor": "${GPU_VENDOR}",
    "gpu_nodes": ${GPU_NODES},
    "gpu_model": "${GPU_MODEL:-unknown}",
    "nfd_installed": $([ ${NFD_INSTALLED} -gt 0 ] && echo "true" || echo "false")
  },
  "dra": {
    "beta_features": "${BETA_FEATURES}",
    "alpha_features": "${ALPHA_FEATURES}",
    "deviceclass_count": ${DEVICECLASS_COUNT:-0},
    "resourceslice_count": ${RESOURCESLICE_COUNT:-0}
  },
  "cdmm": {
    "skip_mig": ${SKIP_MIG}
  }
}
EOF
