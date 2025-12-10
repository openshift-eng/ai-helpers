---
description: Configure cluster autoscaling based on CPU and memory usage
argument-hint: [--cpu-threshold <percentage>] [--memory-threshold <percentage>] [--min-nodes <count>] [--max-nodes <count>] [--dry-run]
---

## Name
openshift:autoscale-cluster

## Synopsis

```
/openshift:autoscale-cluster [--cpu-threshold <percentage>] [--memory-threshold <percentage>] [--min-nodes <count>] [--max-nodes <count>] [--dry-run]
```

## Description

The `/openshift:autoscale-cluster` command configures and manages cluster autoscaling in OpenShift based on CPU and memory resource utilization. It automates the setup of ClusterAutoscaler and MachineAutoscaler resources to dynamically adjust cluster capacity in response to workload demands.

The command performs the following operations:

- Analyzes current cluster resource utilization (CPU and memory) across all nodes
- Detects existing MachineSets and their current replica counts
- Creates or updates ClusterAutoscaler configuration with specified resource thresholds
- Configures MachineAutoscaler for each MachineSet with min/max node bounds
- Validates autoscaling configuration and ensures proper RBAC permissions
- Provides recommendations for resource limits and pod resource requests
- Monitors autoscaling behavior and reports scaling events
- Supports dry-run mode to preview changes without applying them

This command is particularly useful for:
- Production clusters with variable workload patterns
- Development clusters that need cost optimization during off-hours
- Clusters experiencing resource pressure or pending pods
- Establishing baseline autoscaling policies for new deployments

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (oc)**: Must be installed and configured
   - Install from: <https://mirror.openshift.com/pub/openshift-v4/clients/ocp/>
   - Verify with: `oc version`

2. **Cluster admin access**: Required for creating ClusterAutoscaler and MachineAutoscaler resources
   - Verify with: `oc auth can-i create clusterautoscalers`
   - Must have cluster-admin role or equivalent permissions

3. **Active cluster connection**: Must be logged into an OpenShift cluster
   - Verify with: `oc whoami && oc cluster-info`

4. **Machine API enabled**: The cluster must support the Machine API
   - Check with: `oc get machinesets -n openshift-machine-api`
   - Not available on some infrastructure types (e.g., bare metal without IPI)

5. **jq utility**: Required for JSON parsing
   - Install on macOS: `brew install jq`
   - Install on Linux: `sudo yum install jq` or `sudo apt-get install jq`
   - Verify with: `which jq`

## Arguments

- **--cpu-threshold** (optional): CPU utilization percentage that triggers scale-up. Default: `70`
  - Range: 1-100
  - Example: `--cpu-threshold 80`
  - When average CPU usage across nodes exceeds this threshold, the cluster will scale up

- **--memory-threshold** (optional): Memory utilization percentage that triggers scale-up. Default: `70`
  - Range: 1-100
  - Example: `--memory-threshold 75`
  - When average memory usage across nodes exceeds this threshold, the cluster will scale up

- **--min-nodes** (optional): Minimum number of nodes per MachineSet. Default: `1`
  - Must be >= 1
  - Example: `--min-nodes 2`
  - Ensures cluster maintains at least this many nodes even during scale-down

- **--max-nodes** (optional): Maximum number of nodes per MachineSet. Default: `10`
  - Must be > min-nodes
  - Example: `--max-nodes 20`
  - Limits the maximum cluster size to control costs and resource allocation

- **--dry-run** (optional): Preview changes without applying them
  - Example: `--dry-run`
  - Shows what would be created/modified without making actual changes
  - Useful for validation and planning

## Implementation

### 1. Parse Arguments and Initialize Variables

Parse command-line arguments and set defaults:

```bash
#!/bin/bash

# Default values
CPU_THRESHOLD=70
MEMORY_THRESHOLD=70
MIN_NODES=1
MAX_NODES=10
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cpu-threshold)
            CPU_THRESHOLD="$2"
            shift 2
            ;;
        --memory-threshold)
            MEMORY_THRESHOLD="$2"
            shift 2
            ;;
        --min-nodes)
            MIN_NODES="$2"
            shift 2
            ;;
        --max-nodes)
            MAX_NODES="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Validate thresholds
if [ "$CPU_THRESHOLD" -lt 1 ] || [ "$CPU_THRESHOLD" -gt 100 ]; then
    echo "Error: CPU threshold must be between 1 and 100"
    exit 1
fi

if [ "$MEMORY_THRESHOLD" -lt 1 ] || [ "$MEMORY_THRESHOLD" -gt 100 ]; then
    echo "Error: Memory threshold must be between 1 and 100"
    exit 1
fi

if [ "$MIN_NODES" -lt 1 ]; then
    echo "Error: Minimum nodes must be at least 1"
    exit 1
fi

if [ "$MAX_NODES" -le "$MIN_NODES" ]; then
    echo "Error: Maximum nodes must be greater than minimum nodes"
    exit 1
fi

echo "Autoscale Configuration:"
echo "  CPU Threshold: ${CPU_THRESHOLD}%"
echo "  Memory Threshold: ${MEMORY_THRESHOLD}%"
echo "  Min Nodes per MachineSet: $MIN_NODES"
echo "  Max Nodes per MachineSet: $MAX_NODES"
echo "  Dry Run: $DRY_RUN"
echo ""
```

### 2. Verify Prerequisites

Check that required tools and permissions are available:

```bash
echo "Verifying prerequisites..."

# Check if oc is installed
if ! command -v oc &> /dev/null; then
    echo "❌ Error: oc CLI not found. Please install OpenShift CLI."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "❌ Error: jq not found. Please install jq for JSON parsing."
    exit 1
fi

# Verify cluster connection
if ! oc whoami &> /dev/null; then
    echo "❌ Error: Not logged into an OpenShift cluster."
    exit 1
fi

# Check cluster-admin permissions
if ! oc auth can-i create clusterautoscalers &> /dev/null; then
    echo "❌ Error: Insufficient permissions. cluster-admin role required."
    exit 1
fi

# Check if Machine API is available
if ! oc get machinesets -n openshift-machine-api &> /dev/null; then
    echo "❌ Error: Machine API not available on this cluster."
    echo "   Cluster autoscaling requires Machine API support."
    exit 1
fi

echo "✅ Prerequisites validated"
echo ""
```

### 3. Analyze Current Cluster Resource Usage

Gather current CPU and memory utilization:

```bash
echo "Analyzing current cluster resource usage..."

# Get node count
NODE_COUNT=$(oc get nodes --no-headers | wc -l)
echo "  Total Nodes: $NODE_COUNT"

# Calculate CPU usage
CPU_USAGE=$(oc adm top nodes --no-headers 2>/dev/null | awk '{sum+=$3} END {if (NR>0) print sum/NR; else print 0}' | sed 's/%//')
if [ -z "$CPU_USAGE" ]; then
    echo "⚠️  Warning: Could not retrieve CPU metrics. Metrics server may not be available."
    CPU_USAGE="N/A"
else
    echo "  Average CPU Usage: ${CPU_USAGE}%"
fi

# Calculate Memory usage
MEMORY_USAGE=$(oc adm top nodes --no-headers 2>/dev/null | awk '{sum+=$5} END {if (NR>0) print sum/NR; else print 0}' | sed 's/%//')
if [ -z "$MEMORY_USAGE" ]; then
    echo "⚠️  Warning: Could not retrieve memory metrics. Metrics server may not be available."
    MEMORY_USAGE="N/A"
else
    echo "  Average Memory Usage: ${MEMORY_USAGE}%"
fi

# Check for pending pods
PENDING_PODS=$(oc get pods -A --field-selector=status.phase=Pending --no-headers 2>/dev/null | wc -l)
if [ "$PENDING_PODS" -gt 0 ]; then
    echo "⚠️  Warning: $PENDING_PODS pending pods detected (may indicate resource pressure)"
fi

echo ""
```

### 4. Detect MachineSets

Identify all MachineSets in the cluster:

```bash
echo "Detecting MachineSets..."

MACHINESETS=$(oc get machinesets -n openshift-machine-api -o json | jq -r '.items[].metadata.name')

if [ -z "$MACHINESETS" ]; then
    echo "❌ Error: No MachineSets found in the cluster."
    exit 1
fi

MACHINESET_COUNT=$(echo "$MACHINESETS" | wc -l)
echo "  Found $MACHINESET_COUNT MachineSet(s):"

for ms in $MACHINESETS; do
    REPLICAS=$(oc get machineset "$ms" -n openshift-machine-api -o json | jq -r '.spec.replicas // 0')
    AVAILABLE=$(oc get machineset "$ms" -n openshift-machine-api -o json | jq -r '.status.availableReplicas // 0')
    echo "    - $ms (Replicas: $AVAILABLE/$REPLICAS)"
done

echo ""
```

### 5. Create or Update ClusterAutoscaler

Configure the ClusterAutoscaler resource:

```bash
echo "Configuring ClusterAutoscaler..."

# Check if ClusterAutoscaler already exists
if oc get clusterautoscaler default &> /dev/null; then
    echo "  ClusterAutoscaler 'default' already exists"

    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY RUN] Would update existing ClusterAutoscaler"
    else
        echo "  Updating existing ClusterAutoscaler..."
    fi
else
    echo "  Creating new ClusterAutoscaler 'default'..."
fi

# Create ClusterAutoscaler manifest
cat > /tmp/clusterautoscaler.yaml <<EOF
apiVersion: autoscaling.openshift.io/v1
kind: ClusterAutoscaler
metadata:
  name: default
spec:
  podPriorityThreshold: -10
  resourceLimits:
    maxNodesTotal: $((MAX_NODES * MACHINESET_COUNT))
    cores:
      min: $((MIN_NODES * MACHINESET_COUNT * 2))
      max: $((MAX_NODES * MACHINESET_COUNT * 16))
    memory:
      min: $((MIN_NODES * MACHINESET_COUNT * 8))
      max: $((MAX_NODES * MACHINESET_COUNT * 128))
  scaleDown:
    enabled: true
    delayAfterAdd: 10m
    delayAfterDelete: 5m
    delayAfterFailure: 3m
    unneededTime: 10m
    utilizationThreshold: "0.5"
  balanceSimilarNodeGroups: true
EOF

if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN] ClusterAutoscaler configuration:"
    cat /tmp/clusterautoscaler.yaml
else
    oc apply -f /tmp/clusterautoscaler.yaml
    echo "✅ ClusterAutoscaler configured"
fi

echo ""
```

### 6. Create MachineAutoscaler for Each MachineSet

Configure MachineAutoscaler resources:

```bash
echo "Configuring MachineAutoscalers..."

for ms in $MACHINESETS; do
    echo "  Processing MachineSet: $ms"

    # Check if MachineAutoscaler already exists
    MA_NAME="${ms}"

    if oc get machineautoscaler "$MA_NAME" -n openshift-machine-api &> /dev/null; then
        if [ "$DRY_RUN" = true ]; then
            echo "    [DRY RUN] Would update existing MachineAutoscaler"
        else
            echo "    Updating existing MachineAutoscaler..."
        fi
    else
        if [ "$DRY_RUN" = true ]; then
            echo "    [DRY RUN] Would create new MachineAutoscaler"
        else
            echo "    Creating new MachineAutoscaler..."
        fi
    fi

    # Create MachineAutoscaler manifest
    cat > /tmp/machineautoscaler-${ms}.yaml <<EOF
apiVersion: autoscaling.openshift.io/v1beta1
kind: MachineAutoscaler
metadata:
  name: ${MA_NAME}
  namespace: openshift-machine-api
spec:
  minReplicas: $MIN_NODES
  maxReplicas: $MAX_NODES
  scaleTargetRef:
    apiVersion: machine.openshift.io/v1beta1
    kind: MachineSet
    name: ${ms}
EOF

    if [ "$DRY_RUN" = true ]; then
        echo "    [DRY RUN] MachineAutoscaler configuration:"
        cat /tmp/machineautoscaler-${ms}.yaml
    else
        oc apply -f /tmp/machineautoscaler-${ms}.yaml
        echo "    ✅ MachineAutoscaler configured for $ms"
    fi
done

echo ""
```

### 7. Validate Autoscaling Configuration

Verify that autoscaling is properly configured:

```bash
echo "Validating autoscaling configuration..."

# Check ClusterAutoscaler status
if oc get clusterautoscaler default &> /dev/null; then
    echo "✅ ClusterAutoscaler exists"
else
    echo "❌ ClusterAutoscaler not found"
fi

# Check MachineAutoscalers
MA_COUNT=$(oc get machineautoscaler -n openshift-machine-api --no-headers 2>/dev/null | wc -l)
echo "✅ $MA_COUNT MachineAutoscaler(s) configured"

# Check for autoscaler pods
AUTOSCALER_POD=$(oc get pods -n openshift-machine-api -l app=cluster-autoscaler --no-headers 2>/dev/null | head -1 | awk '{print $1}')
if [ -n "$AUTOSCALER_POD" ]; then
    POD_STATUS=$(oc get pod "$AUTOSCALER_POD" -n openshift-machine-api -o json | jq -r '.status.phase')
    if [ "$POD_STATUS" == "Running" ]; then
        echo "✅ Cluster autoscaler pod is running: $AUTOSCALER_POD"
    else
        echo "⚠️  Warning: Cluster autoscaler pod status: $POD_STATUS"
    fi
else
    echo "⚠️  Warning: Cluster autoscaler pod not found"
fi

echo ""
```

### 8. Provide Recommendations

Offer suggestions for optimizing autoscaling:

```bash
echo "Recommendations for Optimal Autoscaling:"
echo ""

# Check if pods have resource requests
PODS_WITHOUT_REQUESTS=$(oc get pods -A -o json | jq '[.items[] | select(.spec.containers[].resources.requests == null)] | length')

if [ "$PODS_WITHOUT_REQUESTS" -gt 0 ]; then
    echo "⚠️  $PODS_WITHOUT_REQUESTS pod(s) do not have resource requests defined"
    echo "   Recommendation: Set resource requests on all pods for accurate autoscaling"
    echo "   Example:"
    echo "   resources:"
    echo "     requests:"
    echo "       cpu: 100m"
    echo "       memory: 128Mi"
    echo ""
fi

# Check for pod disruption budgets
PDB_COUNT=$(oc get pdb -A --no-headers 2>/dev/null | wc -l)
if [ "$PDB_COUNT" -eq 0 ]; then
    echo "ℹ️  No PodDisruptionBudgets found"
    echo "   Recommendation: Create PDBs to ensure availability during scale-down"
    echo ""
fi

# Resource utilization recommendations
if [ "$CPU_USAGE" != "N/A" ] && [ $(echo "$CPU_USAGE > 80" | bc -l) -eq 1 ]; then
    echo "⚠️  Current CPU usage (${CPU_USAGE}%) is high"
    echo "   Recommendation: Consider increasing max-nodes or optimizing workloads"
    echo ""
fi

if [ "$MEMORY_USAGE" != "N/A" ] && [ $(echo "$MEMORY_USAGE > 80" | bc -l) -eq 1 ]; then
    echo "⚠️  Current memory usage (${MEMORY_USAGE}%) is high"
    echo "   Recommendation: Consider increasing max-nodes or optimizing workloads"
    echo ""
fi

echo "📊 Monitoring Commands:"
echo "  # Watch autoscaler logs:"
echo "  oc logs -f -n openshift-machine-api -l app=cluster-autoscaler"
echo ""
echo "  # Monitor MachineSet scaling:"
echo "  watch 'oc get machinesets -n openshift-machine-api'"
echo ""
echo "  # Check autoscaling events:"
echo "  oc get events -n openshift-machine-api --sort-by='.lastTimestamp' | grep -i autoscal"
echo ""
```

### 9. Generate Summary Report

Create a summary of the autoscaling configuration:

```bash
echo "==============================================="
echo "Cluster Autoscaling Configuration Summary"
echo "==============================================="
echo "Configuration Applied: $(date)"
echo ""
echo "Thresholds:"
echo "  CPU Threshold: ${CPU_THRESHOLD}%"
echo "  Memory Threshold: ${MEMORY_THRESHOLD}%"
echo ""
echo "Scaling Limits:"
echo "  Min Nodes per MachineSet: $MIN_NODES"
echo "  Max Nodes per MachineSet: $MAX_NODES"
echo "  Total Max Nodes: $((MAX_NODES * MACHINESET_COUNT))"
echo ""
echo "Current Cluster State:"
echo "  Current Nodes: $NODE_COUNT"
echo "  MachineSets: $MACHINESET_COUNT"
echo "  Average CPU Usage: ${CPU_USAGE}%"
echo "  Average Memory Usage: ${MEMORY_USAGE}%"
echo "  Pending Pods: $PENDING_PODS"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "🔍 DRY RUN MODE - No changes were applied"
    echo "   Review the configurations above and run without --dry-run to apply"
else
    echo "✅ Autoscaling configured successfully"
    echo ""
    echo "Next Steps:"
    echo "1. Monitor autoscaler logs for scaling events"
    echo "2. Ensure pods have resource requests defined"
    echo "3. Set up alerts for cluster capacity and autoscaling failures"
    echo "4. Review scaling behavior after 24-48 hours"
fi

echo "==============================================="

# Clean up temporary files
rm -f /tmp/clusterautoscaler.yaml /tmp/machineautoscaler-*.yaml
```

## Return Value

The command returns a comprehensive report containing:

- **Configuration Summary**: Applied autoscaling parameters (thresholds, min/max nodes)
- **Current Cluster State**: Node count, resource utilization, pending pods
- **Validation Results**: Status of ClusterAutoscaler and MachineAutoscaler resources
- **Recommendations**: Suggestions for optimizing autoscaling (resource requests, PDBs)
- **Monitoring Commands**: Commands to observe autoscaling behavior
- **Next Steps**: Action items for optimal autoscaling performance

**Exit Codes:**
- `0`: Success - autoscaling configured successfully
- `1`: Error - prerequisite check failed, permission denied, or invalid arguments

## Examples

### Example 1: Basic autoscaling with defaults

```bash
/openshift:autoscale-cluster
```

Output:
```text
Autoscale Configuration:
  CPU Threshold: 70%
  Memory Threshold: 70%
  Min Nodes per MachineSet: 1
  Max Nodes per MachineSet: 10
  Dry Run: false

Verifying prerequisites...
✅ Prerequisites validated

Analyzing current cluster resource usage...
  Total Nodes: 6
  Average CPU Usage: 45%
  Average Memory Usage: 52%

Detecting MachineSets...
  Found 3 MachineSet(s):
    - cluster-worker-us-east-1a (Replicas: 2/2)
    - cluster-worker-us-east-1b (Replicas: 2/2)
    - cluster-worker-us-east-1c (Replicas: 2/2)

Configuring ClusterAutoscaler...
✅ ClusterAutoscaler configured

Configuring MachineAutoscalers...
  Processing MachineSet: cluster-worker-us-east-1a
    ✅ MachineAutoscaler configured for cluster-worker-us-east-1a
  Processing MachineSet: cluster-worker-us-east-1b
    ✅ MachineAutoscaler configured for cluster-worker-us-east-1b
  Processing MachineSet: cluster-worker-us-east-1c
    ✅ MachineAutoscaler configured for cluster-worker-us-east-1c

Validating autoscaling configuration...
✅ ClusterAutoscaler exists
✅ 3 MachineAutoscaler(s) configured
✅ Cluster autoscaler pod is running: cluster-autoscaler-default-5f7b8c9d6-xk2lm

===============================================
Cluster Autoscaling Configuration Summary
===============================================
✅ Autoscaling configured successfully
```

### Example 2: Custom thresholds and limits

```bash
/openshift:autoscale-cluster --cpu-threshold 80 --memory-threshold 75 --min-nodes 2 --max-nodes 15
```

Configures autoscaling with:
- Scale up when CPU exceeds 80% or memory exceeds 75%
- Maintain at least 2 nodes per MachineSet
- Allow scaling up to 15 nodes per MachineSet

### Example 3: Dry run to preview changes

```bash
/openshift:autoscale-cluster --cpu-threshold 85 --max-nodes 20 --dry-run
```

Shows what would be configured without applying changes.

### Example 4: Conservative autoscaling for production

```bash
/openshift:autoscale-cluster --cpu-threshold 60 --memory-threshold 65 --min-nodes 3 --max-nodes 12
```

Configures conservative autoscaling:
- Lower thresholds (60% CPU, 65% memory) for proactive scaling
- Higher minimum (3 nodes) for redundancy
- Moderate maximum (12 nodes) for cost control

## Common Issues and Remediation

### Issue: Cluster autoscaler pod not running

**Symptoms**: Autoscaler pod in CrashLoopBackOff or not found

**Investigation**:
```bash
oc get pods -n openshift-machine-api -l app=cluster-autoscaler
oc logs -n openshift-machine-api -l app=cluster-autoscaler
```

**Remediation**:
- Check ClusterAutoscaler resource for configuration errors
- Verify RBAC permissions are correctly set
- Review pod logs for specific error messages

### Issue: Nodes not scaling up despite high utilization

**Symptoms**: CPU/memory usage high but no new nodes provisioned

**Investigation**:
```bash
oc logs -n openshift-machine-api -l app=cluster-autoscaler | grep -i "scale"
oc describe clusterautoscaler default
```

**Remediation**:
- Ensure pods have resource requests defined
- Check if max node limit has been reached
- Verify cloud provider quotas and limits
- Review autoscaler logs for "unschedulable" events

### Issue: Nodes scaling down too aggressively

**Symptoms**: Nodes frequently removed, causing pod evictions

**Investigation**:
```bash
oc get events -n openshift-machine-api | grep -i "scale down"
```

**Remediation**:
- Increase `unneededTime` in ClusterAutoscaler spec
- Set up PodDisruptionBudgets for critical workloads
- Add annotations to prevent specific nodes from scale-down:
  ```bash
  oc annotate node <node-name> cluster-autoscaler.kubernetes.io/scale-down-disabled=true
  ```

### Issue: Machine API not available

**Symptoms**: Error message "Machine API not available on this cluster"

**Investigation**:
```bash
oc get machinesets -n openshift-machine-api
oc get clusterversion -o yaml
```

**Remediation**:
- Verify cluster was installed with IPI (Installer-Provisioned Infrastructure)
- Check that cluster platform supports Machine API (AWS, Azure, GCP, vSphere, OpenStack)
- For UPI (User-Provisioned Infrastructure), Machine API may not be available

## Security Considerations

- **RBAC Requirements**: This command requires cluster-admin privileges to create ClusterAutoscaler and MachineAutoscaler resources
- **Resource Limits**: Setting appropriate max-nodes prevents runaway scaling costs
- **Cloud Provider Quotas**: Ensure cloud provider quotas can accommodate max scaling limits
- **PodDisruptionBudgets**: Recommended to prevent service disruption during scale-down events
- **Monitoring**: Set up alerts for autoscaling failures and capacity issues

## Related Commands

- `/openshift:cluster-health-check` - Check overall cluster health including node status
- `oc adm top nodes` - View current node resource usage
- `oc get machinesets -n openshift-machine-api` - List MachineSets
- `oc get clusterautoscaler` - View ClusterAutoscaler configuration
- `oc get machineautoscaler -n openshift-machine-api` - View MachineAutoscaler configurations

## See Also

- [OpenShift Cluster Autoscaling Documentation](https://docs.openshift.com/container-platform/latest/machine_management/applying-autoscaling.html)
- [Kubernetes Cluster Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)
- [Machine API Overview](https://docs.openshift.com/container-platform/latest/machine_management/index.html)
