#!/usr/bin/env bash
# Install Node Feature Discovery (NFD) on OpenShift cluster
# Required for GPU auto-detection

set -euo pipefail

# Retry helper for transient API errors
retry_command() {
    local max_attempts=3
    local delay=5
    local attempt=1
    local cmd="$@"

    while [ ${attempt} -le ${max_attempts} ]; do
        if eval "${cmd}"; then
            return 0
        else
            if [ ${attempt} -lt ${max_attempts} ]; then
                echo "  Retry ${attempt}/${max_attempts} after ${delay}s..."
                sleep ${delay}
                attempt=$((attempt + 1))
            else
                return 1
            fi
        fi
    done
}

KUBECONFIG_PATH="${1:-}"

if [ -z "${KUBECONFIG_PATH}" ]; then
    echo "ERROR: Missing required argument: kubeconfig-path"
    echo "Usage: $0 <kubeconfig-path>"
    exit 1
fi

export KUBECONFIG="${KUBECONFIG_PATH}"

echo "========================================="
echo "Installing Node Feature Discovery (NFD)"
echo "========================================="
echo ""

# Check if NFD is already installed
if oc get namespace openshift-nfd &>/dev/null; then
    if oc get nodefeaturediscovery -n openshift-nfd &>/dev/null 2>&1; then
        echo "✓ NFD already installed"

        # Wait for NFD pods to be ready
        echo "Waiting for NFD pods to be ready..."
        if oc wait --for=condition=ready pod -l app=nfd -n openshift-nfd --timeout=60s &>/dev/null; then
            echo "✓ NFD pods are ready"
        else
            echo "⚠ NFD pods not ready yet, continuing anyway..."
        fi

        exit 0
    fi
fi

# Create namespace
echo "Creating openshift-nfd namespace..."
retry_command "oc create namespace openshift-nfd --dry-run=client -o yaml | oc apply -f -"
echo "✓ Namespace created"
echo ""

# Create OperatorGroup
echo "Creating OperatorGroup..."
retry_command "cat <<EOF | oc apply -f -
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: nfd-operator
  namespace: openshift-nfd
spec:
  targetNamespaces:
  - openshift-nfd
EOF"
echo "✓ OperatorGroup created"
echo ""

# Create Subscription
echo "Creating Subscription for NFD..."
retry_command "cat <<EOF | oc apply -f -
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: nfd
  namespace: openshift-nfd
spec:
  channel: stable
  name: nfd
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
EOF"
echo "✓ Subscription created"
echo ""

# Wait for CSV to be ready
echo "Waiting for NFD operator installation (this may take 2-3 minutes)..."
TIMEOUT=300
ELAPSED=0
INTERVAL=10

# Check if CSV already exists and is succeeded (handle re-runs)
CSV_NAME=$(oc get csv -n openshift-nfd -o jsonpath='{.items[?(@.spec.displayName=="Node Feature Discovery Operator")].metadata.name}' 2>/dev/null || echo "")
if [ -n "${CSV_NAME}" ]; then
    CSV_PHASE=$(oc get csv ${CSV_NAME} -n openshift-nfd -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [ "${CSV_PHASE}" = "Succeeded" ]; then
        echo "✓ NFD operator already installed (CSV: ${CSV_NAME})"
        ELAPSED=${TIMEOUT}  # Skip the wait loop
    fi
fi

while [ ${ELAPSED} -lt ${TIMEOUT} ]; do
    CSV_NAME=$(oc get csv -n openshift-nfd -o jsonpath='{.items[?(@.spec.displayName=="Node Feature Discovery Operator")].metadata.name}' 2>/dev/null || echo "")

    if [ -n "${CSV_NAME}" ]; then
        CSV_PHASE=$(oc get csv ${CSV_NAME} -n openshift-nfd -o jsonpath='{.status.phase}' 2>/dev/null || echo "")

        if [ "${CSV_PHASE}" = "Succeeded" ]; then
            echo "✓ NFD operator installed successfully (CSV: ${CSV_NAME})"
            break
        else
            echo "  Status: ${CSV_PHASE:-Installing...} (${ELAPSED}s elapsed)"
        fi
    else
        echo "  Waiting for CSV creation... (${ELAPSED}s elapsed)"
    fi

    sleep ${INTERVAL}
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ ${ELAPSED} -ge ${TIMEOUT} ] && [ "${CSV_PHASE}" != "Succeeded" ]; then
    echo "ERROR: NFD operator installation timed out after ${TIMEOUT}s"
    echo ""
    echo "Debug information:"
    echo "  Subscriptions:"
    oc get subscription -n openshift-nfd -o wide 2>&1 || echo "    Failed to get subscriptions"
    echo ""
    echo "  InstallPlans:"
    oc get installplan -n openshift-nfd 2>&1 || echo "    Failed to get installplans"
    echo ""
    echo "  CSVs:"
    oc get csv -n openshift-nfd 2>&1 || echo "    Failed to get CSVs"
    exit 1
fi

echo ""

# Create NodeFeatureDiscovery CR
echo "Creating NodeFeatureDiscovery CR..."
retry_command "cat <<EOF | oc apply -f -
apiVersion: nfd.openshift.io/v1
kind: NodeFeatureDiscovery
metadata:
  name: nfd-instance
  namespace: openshift-nfd
spec:
  operand:
    imagePullPolicy: Always
  workerConfig:
    configData: |
      sources:
        pci:
          deviceClassWhitelist:
            - \"03\"
            - \"0200\"
            - \"0207\"
          deviceLabelFields:
            - vendor
EOF"
echo "✓ NodeFeatureDiscovery CR created"
echo ""

# Wait for NFD pods to be ready
echo "Waiting for NFD pods to be ready..."
TIMEOUT=180
ELAPSED=0
INTERVAL=5

while [ ${ELAPSED} -lt ${TIMEOUT} ]; do
    READY_PODS=$(oc get pods -n openshift-nfd -l app=nfd --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)

    if [ ${READY_PODS} -gt 0 ]; then
        echo "✓ NFD pods are running (${READY_PODS} pods)"
        break
    else
        echo "  Waiting for NFD pods... (${ELAPSED}s elapsed)"
    fi

    sleep ${INTERVAL}
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ ${ELAPSED} -ge ${TIMEOUT} ]; then
    echo "⚠ NFD pods not ready after ${TIMEOUT}s, but continuing..."
    echo "  You may need to wait a bit longer for node labeling to complete"
else
    # Wait additional time for node labeling to complete
    echo ""
    echo "Waiting for NFD to label nodes (30s)..."
    sleep 30
    echo "✓ Node labeling should be complete"
fi

echo ""
echo "========================================="
echo "NFD Installation Complete!"
echo "========================================="
echo ""

# Show labeled nodes summary
TOTAL_NODES=$(oc get nodes --no-headers 2>/dev/null | wc -l)
LABELED_NODES=$(oc get nodes -l feature.node.kubernetes.io/cpu-cpuid.AVX --no-headers 2>/dev/null | wc -l || echo "0")

echo "Nodes labeled: ${LABELED_NODES}/${TOTAL_NODES}"

# Check for GPU labels
NVIDIA_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-10de.present=true' --no-headers 2>/dev/null | wc -l || echo "0")
AMD_NODES=$(oc get nodes -l 'feature.node.kubernetes.io/pci-1002.present=true' --no-headers 2>/dev/null | wc -l || echo "0")

if [ ${NVIDIA_NODES} -gt 0 ]; then
    echo "GPU Detection: ${NVIDIA_NODES} nodes with NVIDIA GPUs"
elif [ ${AMD_NODES} -gt 0 ]; then
    echo "GPU Detection: ${AMD_NODES} nodes with AMD GPUs"
else
    echo "GPU Detection: No GPUs detected (will use example driver)"
fi

echo ""
