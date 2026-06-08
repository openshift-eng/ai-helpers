#!/usr/bin/env bash
# DRA OCP Validator - Setup workflow
# Installs NFD, detects hardware, and installs appropriate DRA driver

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common utilities
if [ -f "${SCRIPT_DIR}/common.sh" ]; then
    source "${SCRIPT_DIR}/common.sh"
fi

# Parse arguments
KUBECONFIG_PATH=""
DRIVER=""
ENABLE_DYNAMIC_MIG=false
DRIVER_VERSION=""  # Will be set based on driver type

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --driver)
      DRIVER="${2}"
      shift 2
      ;;
    --enable-dynamic-mig)
      ENABLE_DYNAMIC_MIG=true
      shift
      ;;
    --driver-version)
      DRIVER_VERSION="${2}"
      shift 2
      ;;
    *)
      if [ -z "${KUBECONFIG_PATH}" ]; then
        KUBECONFIG_PATH="${1}"
      else
        echo "ERROR: Unknown argument: ${1}"
        exit 1
      fi
      shift
      ;;
  esac
done

# Validate required arguments
if [ -z "${KUBECONFIG_PATH}" ]; then
  echo "ERROR: Missing required argument: kubeconfig-path"
  echo "Usage: $0 <kubeconfig-path> [options]"
  exit 1
fi

# Expand tilde
KUBECONFIG_PATH="${KUBECONFIG_PATH/#\~/$HOME}"

# Validate kubeconfig exists
if [ ! -f "${KUBECONFIG_PATH}" ]; then
  echo "ERROR: Kubeconfig not found: ${KUBECONFIG_PATH}"
  exit 1
fi

export KUBECONFIG="${KUBECONFIG_PATH}"

echo "========================================="
echo "DRA OCP Validator - Setup"
echo "========================================="
echo ""

# Step 1: Verify cluster access
echo "=== Step 1: Cluster verification ==="

if ! validate_cluster_connectivity "true"; then
  exit 1
fi

OCP_VERSION=$(oc version -o json | jq -r '.openshiftVersion // "unknown"')
K8S_VERSION=$(oc version -o json | jq -r '.serverVersion.gitVersion // "unknown"')

echo "✓ Cluster accessible (OCP ${OCP_VERSION}, K8s ${K8S_VERSION})"
echo ""

# Step 2: Install NFD (always required for hardware auto-detection)
echo "=== Step 2: Installing NFD for hardware detection ==="

# Check if NFD is already installed
if oc get namespace openshift-nfd &>/dev/null && oc get nodefeaturediscovery -n openshift-nfd &>/dev/null 2>&1; then
  echo "ℹ NFD is already installed, skipping installation"
  echo ""
else
  echo "Installing NFD..."
  "${SCRIPT_DIR}/install-nfd.sh" "${KUBECONFIG_PATH}"
  echo ""
fi

# Step 3: Hardware detection (now that NFD is installed)
echo "=== Step 3: Hardware detection ==="
echo ""

# Auto-detect driver if not specified (requires NFD)
if [ -z "${DRIVER}" ]; then
  # Check for NVIDIA GPUs via NFD labels
  NVIDIA_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-10de.present=true' --no-headers 2>/dev/null | wc -l || echo "0")

  # Check for AMD GPUs via NFD labels
  AMD_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-1002.present=true' --no-headers 2>/dev/null | wc -l || echo "0")

  if [ ${NVIDIA_NODES} -gt 0 ]; then
    DRIVER="nvidia"
    echo "✓ Hardware detected: NVIDIA GPUs on ${NVIDIA_NODES} node(s)"
    echo "  → Auto-selecting NVIDIA DRA driver"
  elif [ ${AMD_NODES} -gt 0 ]; then
    DRIVER="amd"
    echo "⚠ Hardware detected: AMD GPUs on ${AMD_NODES} node(s)"
    echo "ERROR: AMD driver support not yet implemented"
    exit 1
  else
    echo "ℹ No physical GPUs detected on this cluster"
    echo ""
    echo "  Checked for:"
    echo "    • NVIDIA GPUs (PCI vendor ID 0x10de): Not found"
    echo "    • AMD GPUs (PCI vendor ID 0x1002): Not found"
    echo ""
    echo "  → Proceeding with dra-example-driver (software-only testing)"
    echo "    This driver simulates GPU resources without requiring physical hardware."
    echo ""
    DRIVER="example"
  fi
else
  echo "ℹ Using user-specified driver: ${DRIVER}"
fi

echo ""

# Step 4: Enable OCP feature gate if partitionable devices requested
if [ "${ENABLE_DYNAMIC_MIG}" = true ]; then
  echo "=== Step 4a: Enable DRAPartitionableDevices feature gate ==="
  echo ""
  echo "Partitionable devices require OCP cluster feature gate enablement."
  echo ""

  # Enable feature gate via CustomNoUpgrade
  FEATURE_GATE="DRAPartitionableDevices"
  CURRENT_GATES=$(oc get featuregate cluster -o json | jq -r '.spec.customNoUpgrade.enabled[]?' 2>/dev/null | tr '\n' ' ' || true)

  if [[ ! " ${CURRENT_GATES} " =~ " ${FEATURE_GATE} " ]]; then
    echo "Enabling ${FEATURE_GATE} feature gate..."
    ALL_GATES=$(echo "${CURRENT_GATES} ${FEATURE_GATE}" | tr ' ' '\n' | grep -v '^$' | sort -u | jq -R . | jq -s .)
    oc patch featuregate cluster --type=merge -p "{\"spec\":{\"customNoUpgrade\":{\"enabled\":${ALL_GATES}}}}"
    echo "✓ Feature gate enabled, waiting for propagation..."
    sleep 30
  else
    echo "✓ Feature gate '${FEATURE_GATE}' is already enabled"
  fi
  echo ""
fi

# Step 5: Install DRA driver
echo "=== Step 5: Installing DRA driver ==="

case "${DRIVER}" in
  nvidia)
    # Default NVIDIA DRA driver chart version if not specified
    # This is the Helm chart version, not the CUDA driver version
    NVIDIA_DRA_CHART_VERSION="${DRIVER_VERSION:-25.12.0}"

    INSTALL_FLAGS=()
    if [ "${ENABLE_DYNAMIC_MIG}" = true ]; then
      INSTALL_FLAGS+=("--enable-dynamic-mig")
      echo "Installing NVIDIA driver with DYNAMIC_MIG support for partitionable devices"
    fi
    INSTALL_FLAGS+=("--driver-version" "${NVIDIA_DRA_CHART_VERSION}")

    "${SCRIPT_DIR}/install-nvidia-stack.sh" "${KUBECONFIG_PATH}" "${INSTALL_FLAGS[@]}"
    ;;

  example)
    # Example driver version (matches upstream releases)
    EXAMPLE_VERSION="${DRIVER_VERSION:-v0.3.0}"

    if [ "${ENABLE_DYNAMIC_MIG}" = true ]; then
      # For example driver, enable partitions
      GPU_PARTITIONS="4"
      echo "Installing example driver with partition support (4 partitions)"
    else
      GPU_PARTITIONS="0"
      echo "Installing example driver without partition support"
    fi

    "${SCRIPT_DIR}/install-dra-example.sh" "${KUBECONFIG_PATH}" "${EXAMPLE_VERSION}" "${GPU_PARTITIONS}"
    ;;

  amd)
    echo "ERROR: AMD driver support not yet implemented"
    exit 1
    ;;

  *)
    echo "ERROR: Unknown driver type: ${DRIVER}"
    echo "Supported: nvidia, example"
    exit 1
    ;;
esac

echo ""

# Step 6: Verification
echo "=== Step 6: Installation verification ==="

# Check DeviceClasses
DEVICECLASS_COUNT=$(oc get deviceclass --no-headers 2>/dev/null | wc -l || echo "0")
echo "DeviceClasses: ${DEVICECLASS_COUNT}"

# Check ResourceSlices
RESOURCESLICE_COUNT=$(oc get resourceslice --no-headers 2>/dev/null | wc -l || echo "0")
echo "ResourceSlices: ${RESOURCESLICE_COUNT}"

if [ ${DEVICECLASS_COUNT} -eq 0 ]; then
  echo ""
  echo "⚠ WARNING: No DeviceClasses found - DRA driver may not be ready yet"
  echo "  Wait a few minutes and check: oc get deviceclass"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "DRA driver installed and ready for testing."
echo ""
echo "Next steps:"
echo "  1. Run tests: /dra-ocp-validator:test ${KUBECONFIG_PATH}"
echo "  2. Full validation: /dra-ocp-validator:validate ${KUBECONFIG_PATH}"
echo "  3. Cleanup: /dra-ocp-validator:cleanup ${KUBECONFIG_PATH}"
echo ""
