#!/bin/bash
# Install NVIDIA GPU Operator + DRA Driver on OpenShift
# Based on: https://github.com/openshift/release/pull/74984

set -euo pipefail

# First argument is always kubeconfig
KUBECONFIG_PATH=$1
shift

# Parse remaining flags
NVIDIA_DRA_DRIVER_VERSION="v0.10.0"
MIG_STRATEGY=""
NVIDIA_DRA_FEATURE_GATES=""
ENABLE_DYNAMIC_MIG=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --driver-version)
      NVIDIA_DRA_DRIVER_VERSION="$2"
      shift 2
      ;;
    --enable-dynamic-mig)
      ENABLE_DYNAMIC_MIG=true
      MIG_STRATEGY="mixed"
      shift
      ;;
    --feature-gates)
      NVIDIA_DRA_FEATURE_GATES="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

export KUBECONFIG=${KUBECONFIG_PATH}

echo "========================================="
echo "NVIDIA GPU Stack Installation"
echo "========================================="
echo "GPU Operator + DRA Driver"
echo ""
echo "Configuration:"
echo "  DRA Driver Version: ${NVIDIA_DRA_DRIVER_VERSION}"
if [ -n "${MIG_STRATEGY}" ]; then
  echo "  MIG Strategy: ${MIG_STRATEGY}"
fi
if [ -n "${NVIDIA_DRA_FEATURE_GATES}" ]; then
  echo "  Feature Gates: ${NVIDIA_DRA_FEATURE_GATES}"
fi
echo ""

# Verify required tools
for cmd in oc kubectl; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: Required command not found: $cmd"
        exit 1
    fi
done

#=========================================
# Install jq if needed
#=========================================
if ! command -v jq &>/dev/null; then
  echo "Installing jq..."
  JQ_VERSION="1.7.1"
  curl -sL "https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/jq-linux-amd64" -o /tmp/jq
  chmod +x /tmp/jq
  export PATH="/tmp:${PATH}"
fi

#=========================================
# Install Helm if needed
#=========================================
if ! command -v helm &>/dev/null; then
  echo "Installing Helm..."
  HELM_VERSION="3.14.0"
  curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" -o /tmp/helm.tar.gz
  tar -xzf /tmp/helm.tar.gz -C /tmp
  mkdir -p /tmp/bin
  mv /tmp/linux-amd64/helm /tmp/bin/helm
  chmod +x /tmp/bin/helm
  export PATH="/tmp/bin:$PATH"
  rm -rf /tmp/helm.tar.gz /tmp/linux-amd64
  echo "Helm installed: $(helm version --short)"
else
  echo "Helm already installed: $(helm version --short)"
fi

echo ""

#=========================================
# Step 1: Install Node Feature Discovery (NFD)
#=========================================
echo "=== Step 1: Install Node Feature Discovery (NFD) ==="
echo ""

# Check if NFD is already installed
SKIP_NFD=false
if oc get namespace openshift-nfd &>/dev/null; then
  echo "INFO: openshift-nfd namespace already exists"
  if oc get csv -n openshift-nfd -l operators.coreos.com/nfd.openshift-nfd &>/dev/null; then
    CSV_NAME=$(oc get csv -n openshift-nfd -l operators.coreos.com/nfd.openshift-nfd -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "${CSV_NAME}" ]; then
      CSV_PHASE=$(oc get csv -n openshift-nfd "${CSV_NAME}" -o jsonpath='{.status.phase}')
      if [ "${CSV_PHASE}" == "Succeeded" ]; then
        echo "INFO: NFD Operator is already installed: ${CSV_NAME}"
        if oc get nodefeaturediscovery -n openshift-nfd &>/dev/null; then
          echo "INFO: NodeFeatureDiscovery CR already exists"
          SKIP_NFD=true
        fi
      fi
    fi
  fi
fi

if [ "${SKIP_NFD}" != "true" ]; then
  # Create namespace
  echo "Creating openshift-nfd namespace..."
  oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: openshift-nfd
EOF

  # Create OperatorGroup
  echo "Creating OperatorGroup..."
  oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: openshift-nfd-group
  namespace: openshift-nfd
spec:
  targetNamespaces:
  - openshift-nfd
EOF

  # Wait for redhat-operators catalog
  echo "Waiting for redhat-operators catalog source..."
  CATALOG_READY=false
  for retry in $(seq 1 60); do
    if ! oc get catalogsource redhat-operators -n openshift-marketplace &>/dev/null; then
      echo "  Waiting for catalog... (${retry}/60)"
      sleep 10
      continue
    fi

    CATALOG_STATUS=$(oc get catalogsource redhat-operators -n openshift-marketplace -o jsonpath='{.status.connectionState.lastObservedState}' 2>/dev/null || echo "")
    if [ "${CATALOG_STATUS}" == "READY" ]; then
      CATALOG_READY=true
      echo "✓ Catalog source is READY"
      break
    fi
    echo "  Waiting... (${retry}/60) Status: ${CATALOG_STATUS}"
    sleep 10
  done

  if [ "${CATALOG_READY}" != "true" ]; then
    echo "ERROR: redhat-operators catalog did not become READY"
    exit 1
  fi

  # Wait for NFD packagemanifest
  echo "Waiting for NFD packagemanifest..."
  PACKAGE_EXISTS=false
  for retry in $(seq 1 30); do
    if oc get packagemanifest nfd -n openshift-marketplace &>/dev/null; then
      PACKAGE_EXISTS=true
      echo "✓ NFD packagemanifest found"
      break
    fi
    echo "  Waiting... (${retry}/30)"
    sleep 10
  done

  if [ "${PACKAGE_EXISTS}" != "true" ]; then
    echo "ERROR: NFD packagemanifest not found"
    exit 1
  fi

  # Get default channel
  CHANNEL=$(oc get packagemanifest nfd -n openshift-marketplace -o jsonpath='{.status.defaultChannel}')
  echo "NFD channel: ${CHANNEL}"

  # Create Subscription
  echo "Creating NFD subscription..."
  oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: nfd
  namespace: openshift-nfd
spec:
  channel: ${CHANNEL}
  installPlanApproval: Automatic
  name: nfd
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

  # Wait for CSV
  echo "Waiting for NFD CSV..."
  NFD_CSV=""
  for retry in $(seq 1 60); do
    NFD_CSV=$(oc get subscription nfd -n openshift-nfd -o jsonpath='{.status.currentCSV}' 2>/dev/null || echo "")
    if [ -n "${NFD_CSV}" ]; then
      echo "✓ CSV found: ${NFD_CSV}"
      break
    fi
    echo "  Waiting... (${retry}/60)"
    sleep 10
  done

  if [ -z "${NFD_CSV}" ]; then
    echo "ERROR: CSV not created"
    exit 1
  fi

  # Wait for CSV to be ready
  echo "Waiting for CSV to be ready..."
  for retry in $(seq 1 40); do
    CSV_PHASE=$(oc get csv -n openshift-nfd "${NFD_CSV}" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [ "${CSV_PHASE}" == "Succeeded" ]; then
      echo "✓ CSV is ready"
      break
    fi
    echo "  Waiting... (${retry}/40) Phase: ${CSV_PHASE}"
    sleep 15
  done

  if [ "${CSV_PHASE}" != "Succeeded" ]; then
    echo "ERROR: CSV did not reach Succeeded phase"
    exit 1
  fi

  # Create NodeFeatureDiscovery CR
  echo "Creating NodeFeatureDiscovery CR..."
  oc get csv -n openshift-nfd "${NFD_CSV}" -o jsonpath='{.metadata.annotations.alm-examples}' | \
    jq '.[] | select(.kind=="NodeFeatureDiscovery")' | \
    oc apply -f -

  # Wait for NFD to be available
  echo "Waiting for NodeFeatureDiscovery to be available..."
  if ! oc wait nodefeaturediscovery -n openshift-nfd --for=condition=Available --timeout=15m --all; then
    echo "ERROR: NodeFeatureDiscovery did not become available"
    exit 1
  fi

  echo "✓ NodeFeatureDiscovery is available"
  echo ""

  # Wait for NFD to detect NVIDIA GPUs
  echo "Waiting for NFD to detect NVIDIA GPUs..."
  NFD_GPU_NODES=0
  for retry in $(seq 1 30); do
    NFD_GPU_NODES=$(oc get nodes -l feature.node.kubernetes.io/pci-10de.present=true -o name 2>/dev/null | wc -l)
    if [ "${NFD_GPU_NODES}" -gt 0 ]; then
      echo "✓ NFD detected ${NFD_GPU_NODES} node(s) with NVIDIA GPUs"
      break
    fi
    echo "  Waiting... (${retry}/30)"
    sleep 10
  done

  if [ "${NFD_GPU_NODES}" -eq 0 ]; then
    echo "WARNING: NFD did not detect any NVIDIA GPUs"
    echo "This may be expected if there are no physical GPUs in the cluster"
  else
    # Label GPU nodes for GPU operator
    echo "Labeling GPU nodes with nvidia.com/gpu.present=true..."
    GPU_NODE_NAMES=$(oc get nodes -l feature.node.kubernetes.io/pci-10de.present=true -o jsonpath='{.items[*].metadata.name}')
    for node in ${GPU_NODE_NAMES}; do
      echo "  Labeling node: ${node}"
      oc label node "${node}" nvidia.com/gpu.present=true --overwrite
    done
    echo "✓ ${NFD_GPU_NODES} GPU node(s) labeled"
  fi

  echo ""
  echo "NFD installation complete!"
else
  echo "Skipping NFD installation (already installed)"
fi

echo ""

#=========================================
# Step 2: Install NVIDIA GPU Operator via OLM
#=========================================
echo "=== Step 2: Install NVIDIA GPU Operator ==="
echo ""

# Check if already installed
SKIP_GPU_OPERATOR=false
if oc get namespace nvidia-gpu-operator &>/dev/null; then
  echo "INFO: nvidia-gpu-operator namespace already exists"
  if oc get csv -n nvidia-gpu-operator -l operators.coreos.com/gpu-operator-certified.nvidia-gpu-operator &>/dev/null; then
    CSV_NAME=$(oc get csv -n nvidia-gpu-operator -l operators.coreos.com/gpu-operator-certified.nvidia-gpu-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "${CSV_NAME}" ]; then
      CSV_PHASE=$(oc get csv -n nvidia-gpu-operator "${CSV_NAME}" -o jsonpath='{.status.phase}')
      if [ "${CSV_PHASE}" == "Succeeded" ]; then
        echo "INFO: GPU Operator is already installed: ${CSV_NAME}"

        # Check if ClusterPolicy exists and verify CDI
        if oc get clusterpolicy gpu-cluster-policy &>/dev/null; then
          CDI_ENABLED=$(oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.spec.cdi.enabled}' 2>/dev/null || echo "false")
          if [ "${CDI_ENABLED}" == "true" ]; then
            echo "INFO: ClusterPolicy exists with CDI enabled"
            SKIP_GPU_OPERATOR=true
          else
            echo "WARNING: ClusterPolicy exists but CDI not enabled, patching..."
            oc patch clusterpolicy gpu-cluster-policy --type=merge -p '{"spec":{"operator":{"defaultRuntime":"crio"},"cdi":{"enabled":true,"default":false}}}'
            echo "INFO: ClusterPolicy patched with CDI enabled"
            SKIP_GPU_OPERATOR=true
          fi
        fi
      fi
    fi
  fi
fi

if [ "${SKIP_GPU_OPERATOR}" != "true" ]; then
  # Create namespace
  echo "Creating nvidia-gpu-operator namespace..."
  oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: nvidia-gpu-operator
  labels:
    openshift.io/cluster-monitoring: "true"
    pod-security.kubernetes.io/enforce: "privileged"
EOF

  # Create OperatorGroup
  echo "Creating OperatorGroup..."
  oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: nvidia-gpu-operator-group
  namespace: nvidia-gpu-operator
spec:
  targetNamespaces:
  - nvidia-gpu-operator
EOF

  # Wait for certified-operators catalog source
  echo "Waiting for certified-operators catalog source to be READY..."
  CATALOG_READY=false
  for retry in $(seq 1 60); do
    CATALOG_STATE=$(oc get catalogsource certified-operators -n openshift-marketplace -o jsonpath='{.status.connectionState.lastObservedState}' 2>/dev/null || echo "UNKNOWN")
    if [ "${CATALOG_STATE}" == "READY" ]; then
      CATALOG_READY=true
      echo "✓ Catalog source is READY"
      break
    fi
    echo "  Waiting... (${retry}/60) State: ${CATALOG_STATE}"
    sleep 5
  done

  if [ "${CATALOG_READY}" != "true" ]; then
    echo "ERROR: Catalog source did not become READY in time"
    exit 1
  fi

  # Create Subscription
  echo "Creating GPU Operator subscription..."
  oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: gpu-operator-certified
  namespace: nvidia-gpu-operator
spec:
  channel: "stable"
  name: gpu-operator-certified
  source: certified-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
EOF

  # Wait for CSV to be ready
  echo "Waiting for GPU Operator CSV to be ready..."
  CSV_READY=false
  for retry in $(seq 1 60); do
    CSV_NAME=$(oc get csv -n nvidia-gpu-operator -l operators.coreos.com/gpu-operator-certified.nvidia-gpu-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "${CSV_NAME}" ]; then
      CSV_PHASE=$(oc get csv -n nvidia-gpu-operator "${CSV_NAME}" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
      if [ "${CSV_PHASE}" == "Succeeded" ]; then
        CSV_READY=true
        echo "✓ GPU Operator CSV is ready: ${CSV_NAME}"
        break
      fi
      echo "  Waiting... (${retry}/60) Phase: ${CSV_PHASE}"
    else
      echo "  Waiting for CSV... (${retry}/60)"
    fi
    sleep 10
  done

  if [ "${CSV_READY}" != "true" ]; then
    echo "ERROR: GPU Operator CSV did not become ready in time"
    exit 1
  fi

  # Create ClusterPolicy with CDI enabled
  echo "Creating ClusterPolicy for DRA with partitionable devices..."

  if [ -n "${MIG_STRATEGY}" ]; then
    echo "DRA mode: Traditional device plugin disabled, MIG manager disabled"
    echo "DRA driver will handle dynamic MIG partitioning"
  fi

  cat <<EOF | oc apply -f -
apiVersion: nvidia.com/v1
kind: ClusterPolicy
metadata:
  name: gpu-cluster-policy
spec:
  daemonsets:
    rollingUpdate:
      maxUnavailable: '1'
    updateStrategy: RollingUpdate
  operator:
    runtimeClass: nvidia
    use_ocp_driver_toolkit: true
    defaultRuntime: crio
  driver:
    enabled: true
    use_ocp_driver_toolkit: true
    licensingConfig:
      nlsEnabled: true
    kernelModuleType: auto
    upgradePolicy:
      autoUpgrade: true
      drain:
        enable: false
      maxParallelUpgrades: 1
  toolkit:
    enabled: true
    installDir: /usr/local/nvidia
  devicePlugin:
    enabled: false
    config:
      default: ''
      name: ''
  dcgm:
    enabled: true
  dcgmExporter:
    enabled: true
    serviceMonitor:
      enabled: true
  gfd:
    enabled: true
  migManager:
    enabled: false
    config:
      default: all-disabled
  mig:
    strategy: none
  nodeStatusExporter:
    enabled: true
  cdi:
    enabled: true
    default: false
    nriPluginEnabled: false
  vfioManager:
    enabled: true
  ccManager:
    enabled: true
  sandboxDevicePlugin:
    enabled: true
  kataSandboxDevicePlugin:
    enabled: true
  vgpuDeviceManager:
    enabled: true
    config:
      default: default
  validator:
    plugin:
      env: []
EOF

  # Wait for ClusterPolicy to be ready
  echo "Waiting for ClusterPolicy to be ready..."
  sleep 30

  for retry in $(seq 1 60); do
    POLICY_STATE=$(oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.state}' 2>/dev/null || echo "")
    if [ "${POLICY_STATE}" == "ready" ]; then
      echo "✓ ClusterPolicy is ready"
      break
    fi
    echo "  Waiting... (${retry}/60) State: ${POLICY_STATE}"
    sleep 10
  done

  echo ""
  echo "GPU Operator installation complete!"
else
  echo "Skipping GPU Operator installation (already installed)"
fi

echo ""

#=========================================
# Step 3: Install NVIDIA DRA Driver
#=========================================
echo "=== Step 3: Install NVIDIA DRA Driver ==="
echo ""

NVIDIA_DRA_DRIVER_NAMESPACE="nvidia-dra-driver"

# Check if DRA driver is already installed
if oc get namespace "${NVIDIA_DRA_DRIVER_NAMESPACE}" &>/dev/null; then
  echo "INFO: ${NVIDIA_DRA_DRIVER_NAMESPACE} namespace already exists"
  if helm list -n "${NVIDIA_DRA_DRIVER_NAMESPACE}" 2>/dev/null | grep -q nvidia-dra-driver; then
    INSTALLED_VERSION=$(helm list -n "${NVIDIA_DRA_DRIVER_NAMESPACE}" -o json | jq -r '.[] | select(.name=="nvidia-dra-driver") | .app_version')
    echo "INFO: NVIDIA DRA driver is already installed (version: ${INSTALLED_VERSION})"
    echo "Skipping DRA driver installation"
    exit 0
  fi
fi

# Verify GPU Operator prerequisites
echo "Verifying GPU Operator is installed..."
if ! oc get clusterpolicy gpu-cluster-policy &>/dev/null; then
  echo "ERROR: GPU Operator ClusterPolicy not found!"
  echo "Please ensure GPU Operator is installed first"
  exit 1
fi

CDI_ENABLED=$(oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.spec.cdi.enabled}' 2>/dev/null || echo "false")
if [ "${CDI_ENABLED}" != "true" ]; then
  echo "ERROR: CDI is not enabled in GPU Operator ClusterPolicy"
  echo "DRA requires CDI to be enabled"
  exit 1
fi

echo "✓ GPU Operator is installed with CDI enabled"
echo ""

# Create namespace
echo "Creating namespace ${NVIDIA_DRA_DRIVER_NAMESPACE}..."
oc create namespace "${NVIDIA_DRA_DRIVER_NAMESPACE}" || true
oc label namespace "${NVIDIA_DRA_DRIVER_NAMESPACE}" \
  openshift.io/cluster-monitoring=true \
  pod-security.kubernetes.io/enforce=privileged \
  --overwrite

# Add privileged SCC for DRA driver service accounts (required for OpenShift)
echo "Adding privileged SCC for DRA driver service accounts..."
oc adm policy add-scc-to-user privileged -z nvidia-dra-driver-gpu-service-account-controller -n "${NVIDIA_DRA_DRIVER_NAMESPACE}"
oc adm policy add-scc-to-user privileged -z nvidia-dra-driver-gpu-service-account-kubeletplugin -n "${NVIDIA_DRA_DRIVER_NAMESPACE}"
oc adm policy add-scc-to-user privileged -z compute-domain-daemon-service-account -n "${NVIDIA_DRA_DRIVER_NAMESPACE}"

# Add NVIDIA Helm repository
echo "Adding NVIDIA Helm repository..."
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia || true
helm repo update

echo ""

# Prepare feature gate arguments
FEATURE_GATE_ARGS=""

# Add DynamicMIG feature gate if enabled
if [ "${ENABLE_DYNAMIC_MIG}" = true ]; then
  FEATURE_GATE_ARGS="${FEATURE_GATE_ARGS} --set featureGates.DynamicMIG=true"
  echo "Enabling DynamicMIG feature gate for partitionable devices"
fi

# Add any additional feature gates from command line
if [ -n "${NVIDIA_DRA_FEATURE_GATES}" ]; then
  echo "Additional feature gates: ${NVIDIA_DRA_FEATURE_GATES}"
  IFS=',' read -ra GATES <<< "${NVIDIA_DRA_FEATURE_GATES}"
  for gate in "${GATES[@]}"; do
    key="${gate%%=*}"
    value="${gate#*=}"
    FEATURE_GATE_ARGS="${FEATURE_GATE_ARGS} --set featureGates.${key}=${value}"
  done
fi

if [ -n "${FEATURE_GATE_ARGS}" ]; then
  echo "Helm feature gate arguments: ${FEATURE_GATE_ARGS}"
  echo ""
fi

# Install NVIDIA DRA driver
echo "Installing NVIDIA DRA driver ${NVIDIA_DRA_DRIVER_VERSION}..."
helm install nvidia-dra-driver nvidia/nvidia-dra-driver-gpu \
  --namespace "${NVIDIA_DRA_DRIVER_NAMESPACE}" \
  --version "${NVIDIA_DRA_DRIVER_VERSION}" \
  --set nvidiaDriverRoot=/run/nvidia/driver \
  --set resources.gpus.enabled=true \
  --set gpuResourcesEnabledOverride=true \
  --set resources.computeDomains.enabled=false \
  --set 'controller.tolerations[0].key=node-role.kubernetes.io/master' \
  --set 'controller.tolerations[0].operator=Exists' \
  --set 'controller.tolerations[0].effect=NoSchedule' \
  --set 'controller.tolerations[1].key=node-role.kubernetes.io/control-plane' \
  --set 'controller.tolerations[1].operator=Exists' \
  --set 'controller.tolerations[1].effect=NoSchedule' \
  ${FEATURE_GATE_ARGS} \
  --wait \
  --timeout 10m

echo ""
echo "✓ NVIDIA DRA driver installed successfully"

# Wait for pods to be ready
echo ""
echo "Waiting for DRA driver pods to be ready..."
oc wait --for=condition=Ready pods \
  --all \
  -n "${NVIDIA_DRA_DRIVER_NAMESPACE}" \
  --timeout=10m

echo "✓ All DRA driver pods are ready"

# List pods
echo ""
echo "DRA driver pods:"
oc get pods -n "${NVIDIA_DRA_DRIVER_NAMESPACE}"

# Wait for DeviceClass
echo ""
echo "Waiting for DeviceClass to be created..."
timeout 5m bash -c '
while true; do
  if oc get deviceclass gpu.nvidia.com &>/dev/null; then
    echo "✓ DeviceClass created: gpu.nvidia.com"
    break
  fi
  echo "  Waiting for DeviceClass..."
  sleep 10
done
'

# Wait for ResourceSlices
echo ""
echo "Waiting for ResourceSlices to be published..."
timeout 5m bash -c '
while true; do
  RESOURCE_SLICES=$(oc get resourceslice -o json 2>/dev/null | jq -r ".items[] | select(.spec.driver == \"nvidia.com/gpu\" or .spec.driver == \"mig.nvidia.com\") | .metadata.name" | wc -l)
  if [ "${RESOURCE_SLICES}" -gt 0 ]; then
    echo "✓ Found ${RESOURCE_SLICES} NVIDIA ResourceSlice(s)"
    break
  fi
  echo "  Waiting for ResourceSlices..."
  sleep 10
done
'

echo ""
echo "ResourceSlices:"
oc get resourceslice

echo ""
echo "========================================="
echo "NVIDIA GPU Stack Installation Complete"
echo "========================================="
echo ""
echo "Summary:"
echo "  ✓ GPU Operator installed (namespace: nvidia-gpu-operator)"
echo "  ✓ NVIDIA DRA Driver installed (namespace: ${NVIDIA_DRA_DRIVER_NAMESPACE})"
echo "  ✓ DRA Driver Version: ${NVIDIA_DRA_DRIVER_VERSION}"
echo "  ✓ CDI enabled: true"
if [ -n "${MIG_STRATEGY}" ]; then
  echo "  ✓ MIG Strategy: ${MIG_STRATEGY}"
fi
echo "  ✓ DeviceClass: gpu.nvidia.com"
echo ""
