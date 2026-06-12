#!/bin/bash
# Install dra-example-driver for testing without physical GPUs
# Based on: https://github.com/openshift/release/blob/master/ci-operator/step-registry/dra-example-driver/install/dra-example-driver-install-commands.sh

set -euo pipefail

KUBECONFIG_PATH=$1
DRA_EXAMPLE_DRIVER_VERSION="${2:-v0.3.0}"  # Default version, can be overridden
GPU_PARTITIONS="${3:-0}"  # Default to 0 partitions (disabled unless explicitly enabled via setup --enable-dynamic-mig)

export KUBECONFIG=${KUBECONFIG_PATH}

echo "========================================="
echo "dra-example-driver Installation via Helm"
echo "========================================="
echo "Version: ${DRA_EXAMPLE_DRIVER_VERSION}"
echo ""

DRA_EXAMPLE_DRIVER_NAMESPACE="dra-example-driver"

# Verify required tools
for cmd in oc kubectl curl tar; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: Required command not found: $cmd"
        exit 1
    fi
done

# Check if dra-example-driver is already installed
if oc get namespace "${DRA_EXAMPLE_DRIVER_NAMESPACE}" &>/dev/null; then
  echo "INFO: ${DRA_EXAMPLE_DRIVER_NAMESPACE} namespace already exists"
  if helm list -n "${DRA_EXAMPLE_DRIVER_NAMESPACE}" 2>/dev/null | grep -q dra-example-driver; then
    echo "INFO: dra-example-driver is already installed, skipping installation"
    echo "To reinstall, first run:"
    echo "  helm uninstall dra-example-driver -n ${DRA_EXAMPLE_DRIVER_NAMESPACE}"
    echo "  oc delete namespace ${DRA_EXAMPLE_DRIVER_NAMESPACE}"
    exit 0
  fi
fi

# Install Helm if not present
if ! command -v helm &> /dev/null; then
  echo "Installing Helm..."
  HELM_VERSION="3.17.3"
  HELM_ARCHIVE="helm-v${HELM_VERSION}-linux-amd64.tar.gz"
  curl -fsSL "https://get.helm.sh/${HELM_ARCHIVE}" -o "/tmp/${HELM_ARCHIVE}"
  curl -fsSL "https://get.helm.sh/${HELM_ARCHIVE}.sha256sum" -o "/tmp/${HELM_ARCHIVE}.sha256sum"
  echo "Verifying checksum..."
  (cd /tmp && sha256sum --check --status "${HELM_ARCHIVE}.sha256sum") || {
    echo "ERROR: Helm checksum verification failed"
    rm -rf "/tmp/${HELM_ARCHIVE}" "/tmp/${HELM_ARCHIVE}.sha256sum"
    exit 1
  }
  tar -xzf "/tmp/${HELM_ARCHIVE}" -C /tmp
  mkdir -p /tmp/bin
  mv /tmp/linux-amd64/helm /tmp/bin/helm
  chmod +x /tmp/bin/helm
  export PATH="/tmp/bin:$PATH"
  rm -rf "/tmp/${HELM_ARCHIVE}" "/tmp/${HELM_ARCHIVE}.sha256sum" /tmp/linux-amd64
  echo "Helm installed: $(helm version --short)"
else
  echo "Helm already installed: $(helm version --short)"
fi

echo ""

# Download dra-example-driver source tarball for the Helm chart
echo "Downloading dra-example-driver ${DRA_EXAMPLE_DRIVER_VERSION}..."
curl -fsSL "https://github.com/kubernetes-sigs/dra-example-driver/archive/refs/tags/${DRA_EXAMPLE_DRIVER_VERSION}.tar.gz" -o /tmp/dra-example-driver.tar.gz
tar -xzf /tmp/dra-example-driver.tar.gz -C /tmp
DRA_CHART_DIR="/tmp/dra-example-driver-${DRA_EXAMPLE_DRIVER_VERSION#v}/deployments/helm/dra-example-driver"
echo "Chart directory: ${DRA_CHART_DIR}"
ls "${DRA_CHART_DIR}/Chart.yaml"

echo ""

# Create namespace
echo "Creating namespace ${DRA_EXAMPLE_DRIVER_NAMESPACE}..."
oc create namespace "${DRA_EXAMPLE_DRIVER_NAMESPACE}" 2>/dev/null || true

# Grant privileged SCC for dra-example-driver service account (required for OpenShift)
echo "Adding privileged SCC for dra-example-driver service account..."
oc adm policy add-scc-to-user privileged -z dra-example-driver-service-account -n "${DRA_EXAMPLE_DRIVER_NAMESPACE}"

echo ""

# Install dra-example-driver via Helm from local chart
echo "Installing dra-example-driver ${DRA_EXAMPLE_DRIVER_VERSION}..."
if [ "${GPU_PARTITIONS}" -gt 0 ]; then
  echo "  - GPU Partitions: ${GPU_PARTITIONS} (SharedCounters enabled for DRAPartitionableDevices)"
else
  echo "  - GPU Partitions: ${GPU_PARTITIONS} (SharedCounters disabled)"
fi
helm upgrade --install \
  --namespace "${DRA_EXAMPLE_DRIVER_NAMESPACE}" \
  dra-example-driver \
  "${DRA_CHART_DIR}" \
  --set kubeletPlugin.gpuPartitions=${GPU_PARTITIONS} \
  --set kubeletPlugin.containers.plugin.securityContext.privileged=true \
  --wait \
  --timeout 10m

echo ""
echo "dra-example-driver installed successfully"

# Wait for dra-example-driver pods to be ready
echo ""
echo "Waiting for dra-example-driver pods to be ready..."
oc wait --for=condition=Ready pods \
  --all \
  -n "${DRA_EXAMPLE_DRIVER_NAMESPACE}" \
  --timeout=10m

echo "All dra-example-driver pods are ready"

# List pods
echo ""
echo "dra-example-driver pods:"
oc get pods -n "${DRA_EXAMPLE_DRIVER_NAMESPACE}"

# Wait for DeviceClass to be created
echo ""
echo "Waiting for DeviceClass to be created..."
timeout 5m bash -c '
while true; do
  if oc get deviceclass gpu.example.com &>/dev/null; then
    echo "DeviceClass created: gpu.example.com"
    break
  fi
  echo "Waiting for DeviceClass..."
  sleep 10
done
'

# Wait for ResourceSlices to be published
echo ""
echo "Waiting for dra-example-driver ResourceSlices..."
timeout 5m bash -c '
while true; do
  RESOURCE_SLICES=$(oc get resourceslice -o json 2>/dev/null | grep -c "example.com" || true)
  if [ "${RESOURCE_SLICES}" -gt 0 ]; then
    echo "Found dra-example-driver ResourceSlice(s)"
    break
  fi
  echo "Waiting for ResourceSlices..."
  sleep 10
done
'

echo ""
echo "ResourceSlices:"
oc get resourceslice

echo ""
echo "========================================="
echo "dra-example-driver Installation Complete"
echo "========================================="
echo ""
echo "Summary:"
echo "  - Namespace: ${DRA_EXAMPLE_DRIVER_NAMESPACE}"
echo "  - Version: ${DRA_EXAMPLE_DRIVER_VERSION}"
echo "  - DeviceClass: gpu.example.com"
echo ""

# Cleanup temporary files
rm -rf /tmp/dra-example-driver.tar.gz /tmp/dra-example-driver-*
