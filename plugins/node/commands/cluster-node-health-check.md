---
description: Perform comprehensive health check on cluster nodes and report kubelet, CRI-O, and node-level issues
argument-hint: "[--node <node-name>] [--verbose] [--output-format json|text]"
---

## Name
node:cluster-node-health-check

## Synopsis

```
/node:cluster-node-health-check [--node <node-name>] [--verbose] [--output-format json|text]
```

## Description

The `/node:cluster-node-health-check` command performs an extensive diagnostic of Kubernetes/OpenShift cluster nodes to assess their operational health, stability, and performance. It automates the validation of node-level components including kubelet, CRI-O container runtime, system resources, and node conditions to ensure nodes are functioning as expected.

The command runs a comprehensive set of health checks covering node status, kubelet health, container runtime (CRI-O) operations, resource utilization, system daemons, and kernel parameters. It also detects degraded states, disk/memory pressure, network issues, and recent warning events.

Specifically, it performs the following:

- Detects and validates the availability of oc or kubectl CLI tools and verifies cluster connectivity.
- Checks all node statuses (Ready, MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable) and reports any abnormal conditions with detailed reasons and messages.
- Validates kubelet service health on each node, detecting service failures, high restart counts, and configuration issues.
- Performs CRI-O runtime health checks to ensure container operations are functioning correctly.
- Inspects resource utilization including CPU, memory, disk space, and process/pod counts against allocatable resources.
- Evaluates system daemon health (systemd services) critical for node operations.
- Examines kernel parameters and system tunables relevant to Kubernetes operations.
- Scans for recent warning events at the node level and for pods running on nodes.
- Reviews certificate validity for kubelet client certificates.
- Identifies node taints, labels, and scheduling constraints that may affect workload placement.
- Generates a clear, color-coded summary report and optionally exports findings in JSON format for automation or CI integration.

## Prerequisites

Before using this command, ensure you have:

1. **Kubernetes/OpenShift CLI**: Either `oc` (OpenShift) or `kubectl` (Kubernetes)
   - Install `oc` from: <https://mirror.openshift.com/pub/openshift-v4/clients/ocp/>
   - Or install `kubectl` from: <https://kubernetes.io/docs/tasks/tools/>
   - Verify with: `oc version` or `kubectl version`

2. **Active cluster connection**: Must be connected to a running cluster
   - Verify with: `oc whoami` or `kubectl cluster-info`
   - Ensure KUBECONFIG is set if needed

3. **Sufficient permissions**: Must have read access to cluster resources
   - Cluster-admin or monitoring role recommended for comprehensive checks
   - Minimum: ability to view nodes, pods, and node metrics
   - For node debugging (accessing journalctl, crictl): ability to create debug pods or ssh access

## Arguments

- **--node** (optional): Name of a specific node to check. If not provided, checks all nodes in the cluster. Example: `--node ip-10-0-1-23.ec2.internal`

- **--verbose** (optional): Enable detailed output with additional context
  - Shows resource-level details
  - Includes warning conditions
  - Provides remediation suggestions

- **--output-format** (optional): Output format for results
  - `text` (default): Human-readable text format
  - `json`: Machine-readable JSON format for automation

## Implementation

The command performs the following health checks:

### 1. Determine CLI Tool and Verify Connectivity

Detect which Kubernetes CLI is available and verify cluster connection:

```bash
if command -v oc &> /dev/null; then
    CLI="oc"
elif command -v kubectl &> /dev/null; then
    CLI="kubectl"
else
    echo "Error: Neither 'oc' nor 'kubectl' CLI found. Please install one of them."
    exit 1
fi

# Verify cluster connectivity
if ! $CLI cluster-info &> /dev/null; then
    echo "Error: Not connected to a cluster. Please configure your KUBECONFIG."
    exit 1
fi
```

### 2. Initialize Health Check Report

Create a report structure to collect findings:

```bash
NODE_FILTER=${NODE_FILTER:-""}
VERBOSE=${VERBOSE:-false}
OUTPUT_FORMAT=${OUTPUT_FORMAT:-"text"}

REPORT_FILE=".work/node-health-check/report-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p .work/node-health-check

# Initialize counters
CRITICAL_ISSUES=0
WARNING_ISSUES=0
INFO_MESSAGES=0
```

### 3. Check Node Status and Conditions

Verify node health and readiness:

```bash
echo "Checking Node Status..."

# Get all nodes or specific node
if [ -n "$NODE_FILTER" ]; then
    NODES=$NODE_FILTER
else
    NODES=$($CLI get nodes -o jsonpath='{.items[*].metadata.name}')
fi

for node in $NODES; do
    echo "  Checking node: $node"

    # Check if node exists
    if ! $CLI get node "$node" &> /dev/null; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: Node '$node' not found"
        continue
    fi

    # Get node conditions
    NODE_READY=$($CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="Ready") | .status')
    NODE_MEMORY_PRESSURE=$($CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="MemoryPressure") | .status')
    NODE_DISK_PRESSURE=$($CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="DiskPressure") | .status')
    NODE_PID_PRESSURE=$($CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="PIDPressure") | .status')
    NODE_NETWORK=$($CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="NetworkUnavailable") | .status // "False"')

    if [ "$NODE_READY" != "True" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: Node $node is not Ready"
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="Ready") | "    Reason: \(.reason)\n    Message: \(.message)"'
    fi

    if [ "$NODE_MEMORY_PRESSURE" == "True" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: Node $node has MemoryPressure"
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="MemoryPressure") | "    Reason: \(.reason)\n    Message: \(.message)"'
    fi

    if [ "$NODE_DISK_PRESSURE" == "True" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: Node $node has DiskPressure"
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="DiskPressure") | "    Reason: \(.reason)\n    Message: \(.message)"'
    fi

    if [ "$NODE_PID_PRESSURE" == "True" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  WARNING: Node $node has PIDPressure"
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="PIDPressure") | "    Reason: \(.reason)\n    Message: \(.message)"'
    fi

    if [ "$NODE_NETWORK" == "True" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: Node $node has NetworkUnavailable"
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="NetworkUnavailable") | "    Reason: \(.reason)\n    Message: \(.message)"'
    fi

    # Check node version and kubelet version
    KUBELET_VERSION=$($CLI get node "$node" -o json | jq -r '.status.nodeInfo.kubeletVersion')
    echo "    ℹ️  Kubelet version: $KUBELET_VERSION"

    # Check for taints
    TAINTS=$($CLI get node "$node" -o json | jq -r '.spec.taints // [] | length')
    if [ "$TAINTS" -gt 0 ]; then
        echo "    ℹ️  Node has $TAINTS taint(s)"
        $CLI get node "$node" -o json | jq -r '.spec.taints[] | "      - \(.key)=\(.value):\(.effect)"'
    fi
done
```

### 4. Check Kubelet Service Health

Examine kubelet service status on each node using debug pods:

```bash
echo "Checking Kubelet Service Health..."

for node in $NODES; do
    echo "  Checking kubelet on node: $node"

    # Use debug pod to check kubelet service
    KUBELET_STATUS=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host systemctl is-active kubelet 2>/dev/null || echo "failed")

    if [ "$KUBELET_STATUS" != "active" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: Kubelet service is not active on node $node (Status: $KUBELET_STATUS)"

        # Get kubelet logs for troubleshooting
        if [ "$VERBOSE" = true ]; then
            echo "    Recent kubelet logs:"
            $CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host journalctl -u kubelet -n 20 --no-pager 2>/dev/null
        fi
    else
        # Check for kubelet restarts
        KUBELET_RESTART_COUNT=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host systemctl show kubelet -p NRestarts --value 2>/dev/null || echo "0")

        if [ "$KUBELET_RESTART_COUNT" -gt 3 ]; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: Kubelet has restarted $KUBELET_RESTART_COUNT times on node $node"
        fi
    fi

    # Check kubelet certificate expiration
    CERT_EXPIRY=$($CLI get node "$node" -o json | jq -r '.status.conditions[] | select(.type=="Ready") | .message' | grep -i "certificate" || echo "")
    if [ -n "$CERT_EXPIRY" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  WARNING: Certificate issue on node $node: $CERT_EXPIRY"
    fi
done
```

### 5. Check CRI-O Container Runtime Health

Verify CRI-O runtime health and operations:

```bash
echo "Checking CRI-O Container Runtime..."

for node in $NODES; do
    echo "  Checking CRI-O on node: $node"

    # Check crio service status
    CRIO_STATUS=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host systemctl is-active crio 2>/dev/null || echo "failed")

    if [ "$CRIO_STATUS" != "active" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        echo "❌ CRITICAL: CRI-O service is not active on node $node (Status: $CRIO_STATUS)"

        if [ "$VERBOSE" = true ]; then
            echo "    Recent CRI-O logs:"
            $CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host journalctl -u crio -n 20 --no-pager 2>/dev/null
        fi
    else
        # Check CRI-O version
        CRIO_VERSION=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host crictl version -o json 2>/dev/null | jq -r '.runtimeVersion // "unknown"')
        echo "    ℹ️  CRI-O version: $CRIO_VERSION"

        # Check for container runtime errors
        RUNTIME_ERRORS=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host journalctl -u crio --since "1 hour ago" -p err --no-pager 2>/dev/null | wc -l)

        if [ "$RUNTIME_ERRORS" -gt 10 ]; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: CRI-O has $RUNTIME_ERRORS errors in the last hour on node $node"
        fi
    fi
done
```

### 6. Check Node Resource Utilization

Verify resource usage against allocatable capacity:

```bash
echo "Checking Node Resource Utilization..."

for node in $NODES; do
    echo "  Checking resources on node: $node"

    # Get allocatable and capacity
    CPU_CAPACITY=$($CLI get node "$node" -o json | jq -r '.status.capacity.cpu')
    CPU_ALLOCATABLE=$($CLI get node "$node" -o json | jq -r '.status.allocatable.cpu')
    MEMORY_CAPACITY=$($CLI get node "$node" -o json | jq -r '.status.capacity.memory')
    MEMORY_ALLOCATABLE=$($CLI get node "$node" -o json | jq -r '.status.allocatable.memory')
    PODS_CAPACITY=$($CLI get node "$node" -o json | jq -r '.status.capacity.pods')

    # Get current pod count
    POD_COUNT=$($CLI get pods --all-namespaces --field-selector spec.nodeName="$node" --no-headers 2>/dev/null | wc -l)

    echo "    CPU: $CPU_ALLOCATABLE/$CPU_CAPACITY allocatable"
    echo "    Memory: $MEMORY_ALLOCATABLE/$MEMORY_CAPACITY allocatable"
    echo "    Pods: $POD_COUNT/$PODS_CAPACITY"

    # Check if pod count is near capacity
    if [ "$POD_COUNT" -ge "$((PODS_CAPACITY * 90 / 100))" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  WARNING: Node $node is running $POD_COUNT pods (near capacity of $PODS_CAPACITY)"
    fi

    # Check disk usage
    if [ "$VERBOSE" = true ]; then
        echo "    Disk usage:"
        $CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host df -h / /var /var/lib/kubelet /var/lib/containers 2>/dev/null | grep -v "Filesystem"
    fi

    # Check ephemeral storage pressure
    EPHEMERAL_STORAGE=$($CLI get node "$node" -o json | jq -r '.status.allocatable."ephemeral-storage" // "unknown"')
    if [ "$EPHEMERAL_STORAGE" != "unknown" ]; then
        echo "    Ephemeral Storage: $EPHEMERAL_STORAGE allocatable"
    fi
done
```

### 7. Check System Daemons and Services

Validate critical system services:

```bash
echo "Checking System Daemons..."

CRITICAL_SERVICES="kubelet crio"

for node in $NODES; do
    echo "  Checking system services on node: $node"

    for service in $CRITICAL_SERVICES; do
        SERVICE_STATUS=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host systemctl is-active "$service" 2>/dev/null || echo "failed")

        if [ "$SERVICE_STATUS" != "active" ]; then
            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            echo "❌ CRITICAL: Service $service is not active on node $node"
        fi
    done

    # Check for failed systemd units
    FAILED_UNITS=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host systemctl list-units --state=failed --no-pager --no-legend 2>/dev/null | wc -l)

    if [ "$FAILED_UNITS" -gt 0 ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  WARNING: Node $node has $FAILED_UNITS failed systemd unit(s)"

        if [ "$VERBOSE" = true ]; then
            $CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host systemctl list-units --state=failed --no-pager 2>/dev/null
        fi
    fi
done
```

### 8. Check Kernel Parameters and System Tunables

Verify important kernel parameters for Kubernetes:

```bash
echo "Checking Kernel Parameters..."

for node in $NODES; do
    if [ "$VERBOSE" = true ]; then
        echo "  Checking kernel parameters on node: $node"

        # Check key sysctl parameters
        echo "    Key sysctl parameters:"
        $CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host sysctl -a 2>/dev/null | grep -E "(vm.overcommit_memory|vm.panic_on_oom|kernel.panic|kernel.panic_on_oops|net.ipv4.ip_forward)" || true

        # Check SELinux status
        SELINUX_STATUS=$($CLI debug node/"$node" --image=registry.access.redhat.com/ubi9/ubi-minimal -- chroot /host getenforce 2>/dev/null || echo "unknown")
        echo "    SELinux: $SELINUX_STATUS"
    fi
done
```

### 9. Check Recent Node Events

Look for recent warning/error events:

```bash
echo "Checking Recent Node Events..."

for node in $NODES; do
    # Get recent warning events for the node
    NODE_EVENTS=$($CLI get events --all-namespaces --field-selector involvedObject.name="$node",involvedObject.kind=Node,type=Warning --sort-by='.lastTimestamp' 2>/dev/null | tail -10)

    if [ -n "$NODE_EVENTS" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  Recent Warning Events for Node $node:"
        echo "$NODE_EVENTS"
    fi

    # Get recent pod events on this node
    POD_EVENTS=$($CLI get events --all-namespaces --field-selector spec.nodeName="$node",type=Warning --sort-by='.lastTimestamp' 2>/dev/null | tail -10)

    if [ -n "$POD_EVENTS" ] && [ "$VERBOSE" = true ]; then
        echo "ℹ️  Recent Pod Warning Events on Node $node:"
        echo "$POD_EVENTS"
    fi
done
```

### 10. Check Pod Status on Nodes

Verify pods running on each node:

```bash
echo "Checking Pods on Nodes..."

for node in $NODES; do
    echo "  Checking pods on node: $node"

    # Count pods by phase
    RUNNING_PODS=$($CLI get pods --all-namespaces --field-selector spec.nodeName="$node",status.phase=Running --no-headers 2>/dev/null | wc -l)
    PENDING_PODS=$($CLI get pods --all-namespaces --field-selector spec.nodeName="$node",status.phase=Pending --no-headers 2>/dev/null | wc -l)
    FAILED_PODS=$($CLI get pods --all-namespaces --field-selector spec.nodeName="$node",status.phase=Failed --no-headers 2>/dev/null | wc -l)

    echo "    Running: $RUNNING_PODS, Pending: $PENDING_PODS, Failed: $FAILED_PODS"

    if [ "$FAILED_PODS" -gt 0 ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  WARNING: Node $node has $FAILED_PODS failed pod(s)"

        if [ "$VERBOSE" = true ]; then
            $CLI get pods --all-namespaces --field-selector spec.nodeName="$node",status.phase=Failed --no-headers
        fi
    fi

    # Check for pods with high restart counts
    HIGH_RESTART_PODS=$($CLI get pods --all-namespaces --field-selector spec.nodeName="$node" -o json 2>/dev/null | jq -r '.items[] | select(.status.containerStatuses[]? | .restartCount > 5) | "\(.metadata.namespace)/\(.metadata.name) [Restarts: \(.status.containerStatuses[0].restartCount)]"')

    if [ -n "$HIGH_RESTART_PODS" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$HIGH_RESTART_PODS" | wc -l)))
        echo "⚠️  WARNING: Pods with high restart count (>5) on node $node:"
        echo "$HIGH_RESTART_PODS" | while read pod; do
            echo "    - $pod"
        done
    fi
done
```

### 11. Check Node Labels and Roles

Verify node labels and role assignments:

```bash
echo "Checking Node Labels and Roles..."

for node in $NODES; do
    if [ "$VERBOSE" = true ]; then
        echo "  Node: $node"

        # Get node roles
        ROLES=$($CLI get node "$node" -o json | jq -r '.metadata.labels | to_entries[] | select(.key | startswith("node-role.kubernetes.io/")) | .key' | sed 's/node-role.kubernetes.io\///' | tr '\n' ',' | sed 's/,$//')
        echo "    Roles: ${ROLES:-none}"

        # Check for custom labels
        CUSTOM_LABELS=$($CLI get node "$node" -o json | jq -r '.metadata.labels | to_entries[] | select(.key | startswith("node-role.kubernetes.io/") | not) | "\(.key)=\(.value)"' | head -5)
        if [ -n "$CUSTOM_LABELS" ]; then
            echo "    Custom labels:"
            echo "$CUSTOM_LABELS" | while read label; do
                echo "      - $label"
            done
        fi
    fi
done
```

### 12. Generate Summary Report

Create a summary of findings:

```bash
echo ""
echo "==============================================="
echo "Node Health Check Summary"
echo "==============================================="
echo "Check Time: $(date)"
echo "Nodes Checked: $(echo $NODES | wc -w)"
echo ""
echo "Results:"
echo "  Critical Issues: $CRITICAL_ISSUES"
echo "  Warnings: $WARNING_ISSUES"
echo ""

if [ $CRITICAL_ISSUES -eq 0 ] && [ $WARNING_ISSUES -eq 0 ]; then
    echo "✅ OVERALL STATUS: HEALTHY - No issues detected"
    exit 0
elif [ $CRITICAL_ISSUES -gt 0 ]; then
    echo "❌ OVERALL STATUS: CRITICAL - Immediate attention required"
    exit 1
else
    echo "⚠️  OVERALL STATUS: WARNING - Monitoring recommended"
    exit 0
fi
```

### 13. Optional: Export to JSON Format

If `--output-format json` is specified, export findings as JSON:

```json
{
  "cluster": {
    "checkTime": "2025-11-27T12:00:00Z",
    "nodesChecked": 3
  },
  "summary": {
    "criticalIssues": 0,
    "warnings": 2,
    "overallStatus": "WARNING"
  },
  "nodes": [
    {
      "name": "worker-0",
      "status": {
        "ready": true,
        "memoryPressure": false,
        "diskPressure": false,
        "pidPressure": false,
        "networkUnavailable": false
      },
      "kubelet": {
        "version": "v1.28.5",
        "status": "active",
        "restartCount": 0
      },
      "crio": {
        "version": "1.28.2",
        "status": "active",
        "errorCount": 0
      },
      "resources": {
        "cpu": {
          "capacity": "4",
          "allocatable": "3800m"
        },
        "memory": {
          "capacity": "16Gi",
          "allocatable": "15Gi"
        },
        "pods": {
          "running": 25,
          "capacity": 110
        }
      },
      "issues": []
    }
  ]
}
```

## Examples

### Example 1: Check all nodes in the cluster
```bash
/node:cluster-node-health-check
```

Output, for healthy cluster:
```text
Node Health Check Summary
================================================================================

OVERALL STATUS: ✅ HEALTHY

NODE STATUS:
✅ worker-0: Ready (Kubelet v1.28.5, CRI-O 1.28.2)
   - CPU: 3800m/4 allocatable, Memory: 15Gi/16Gi
   - Pods: 25/110
✅ worker-1: Ready (Kubelet v1.28.5, CRI-O 1.28.2)
   - CPU: 3800m/4 allocatable, Memory: 15Gi/16Gi
   - Pods: 28/110
✅ worker-2: Ready (Kubelet v1.28.5, CRI-O 1.28.2)
   - CPU: 3800m/4 allocatable, Memory: 15Gi/16Gi
   - Pods: 22/110

No critical issues found. All nodes are operating normally.

DIAGNOSTIC COMMANDS:
Run these commands for detailed information:

kubectl get nodes -o wide
kubectl describe node <node-name>
kubectl top nodes
```

Output, with issues:
```text
Node Health Check Summary
================================================================================

OVERALL STATUS: ⚠️  WARNING

NODE STATUS:
✅ worker-0: Ready
⚠️  worker-1: Ready (with warnings)
❌ worker-2: Not Ready

ISSUES FOUND:

[CRITICAL] Node Not Ready
- Node: worker-2
- Condition: Ready=False
- Reason: KubeletNotReady
- Message: container runtime network not ready: NetworkReady=false reason:NetworkPluginNotReady message:Network plugin returns error: cni plugin not initialized
- Impact: Node cannot schedule new pods
- Recommended Action:
  kubectl describe node worker-2
  kubectl debug node/worker-2 -- chroot /host journalctl -u kubelet -n 50

[WARNING] High Pod Restart Count
- Node: worker-1
- Pod: openshift-monitoring/prometheus-k8s-0 [Restarts: 8]
- Impact: May indicate application or resource issues
- Recommended Action:
  kubectl logs -n openshift-monitoring prometheus-k8s-0 --previous
  kubectl describe pod -n openshift-monitoring prometheus-k8s-0

[WARNING] Disk Pressure
- Node: worker-1
- Condition: DiskPressure=True
- Message: ephemeral-storage usage(92%) exceeds the threshold(85%)
- Impact: Pods may be evicted to free disk space
- Recommended Action:
  kubectl debug node/worker-1 -- chroot /host df -h
  kubectl get pods -A --field-selector spec.nodeName=worker-1 -o json | jq '.items[] | {name:.metadata.name, ephemeralStorage:.spec.containers[].resources.requests."ephemeral-storage"}'

DIAGNOSTIC COMMANDS:

1. Check node details:
   kubectl get nodes -o wide
   kubectl describe node worker-2

2. Check kubelet logs:
   kubectl debug node/worker-2 -- chroot /host journalctl -u kubelet -n 100

3. Check CRI-O logs:
   kubectl debug node/worker-2 -- chroot /host journalctl -u crio -n 100

4. Check node resource usage:
   kubectl top nodes
```

### Example 2: Check a specific node
```bash
/node:cluster-node-health-check --node worker-1
```

### Example 3: Verbose health check with detailed output
```bash
/node:cluster-node-health-check --verbose
```

### Example 4: JSON output for automation
```bash
/node:cluster-node-health-check --output-format json
```

## Return Value

The command returns a structured health report containing:

- **OVERALL STATUS**: Health summary (Healthy ✅ / Warning ⚠️ / Critical ❌)
- **NODE STATUS**: Status of each checked node with visual indicators
- **ISSUES FOUND**: Detailed list of problems with:
  - Severity level (Critical/Warning/Info)
  - Node location
  - Impact assessment
  - Recommended actions
- **DIAGNOSTIC COMMANDS**: kubectl commands for further investigation

## Common Issues and Remediation

### Node Not Ready

**Symptoms**: Node showing Ready=False

**Investigation**:
```bash
kubectl describe node <node-name>
kubectl debug node/<node-name> -- chroot /host journalctl -u kubelet -n 100
```

**Remediation**: Common causes include:
- Kubelet service failure
- Container runtime (CRI-O) issues
- Network plugin not initialized
- Certificate expiration

### Kubelet Service Failures

**Symptoms**: Kubelet service not active or frequently restarting

**Investigation**:
```bash
kubectl debug node/<node-name> -- chroot /host systemctl status kubelet
kubectl debug node/<node-name> -- chroot /host journalctl -u kubelet --since "1 hour ago"
```

**Remediation**: Check kubelet logs for configuration errors, certificate issues, or API server connectivity problems

### CRI-O Runtime Issues

**Symptoms**: Pods failing to start, container runtime errors

**Investigation**:
```bash
kubectl debug node/<node-name> -- chroot /host systemctl status crio
kubectl debug node/<node-name> -- chroot /host journalctl -u crio -p err --since "1 hour ago"
kubectl debug node/<node-name> -- chroot /host crictl ps -a
```

**Remediation**: Check for CRI-O configuration issues, storage problems, or network misconfigurations

### Memory/Disk Pressure

**Symptoms**: MemoryPressure=True or DiskPressure=True

**Investigation**:
```bash
kubectl describe node <node-name>
kubectl debug node/<node-name> -- chroot /host df -h
kubectl debug node/<node-name> -- chroot /host free -h
kubectl top node <node-name>
kubectl top pods --all-namespaces --field-selector spec.nodeName=<node-name>
```

**Remediation**:
- Increase node resources
- Clean up unused images: `crictl rmi --prune`
- Evict or delete unnecessary pods
- Check for pod resource limits

### Network Unavailable

**Symptoms**: NetworkUnavailable=True

**Investigation**:
```bash
kubectl describe node <node-name>
kubectl get pods -n openshift-multus -o wide
kubectl get pods -n openshift-sdn -o wide  # or openshift-ovn-kubernetes
```

**Remediation**: Check CNI plugin status, network operator logs, and node network configuration

### Certificate Expiration

**Symptoms**: Certificate warnings in kubelet logs

**Investigation**:
```bash
kubectl debug node/<node-name> -- chroot /host openssl x509 -in /var/lib/kubelet/pki/kubelet-client-current.pem -noout -dates
```

**Remediation**: Rotate kubelet certificates (automatic in most cases, manual intervention may be needed for expired certs)

## Security Considerations

- **Read-only access**: This command primarily reads cluster state, but uses debug pods for node-level inspection
- **Debug pods**: Creates temporary debug pods with host access for system-level checks
- **Sensitive data**: Node logs and system information may contain sensitive data
- **RBAC requirements**: Ensure user has appropriate permissions for nodes, pods, and debug pod creation

## Notes

- This command requires appropriate RBAC permissions to view nodes, pods, and create debug pods
- Debug pods are automatically cleaned up after inspection
- Some checks require debug pod creation which may not work in all cluster configurations
- For OpenShift clusters, some checks leverage OpenShift-specific features
- The command provides diagnostic guidance but does not automatically remediate issues
- Regular health checks help catch node issues before they impact workloads
- Node-level issues can cascade to affect pod scheduling and cluster capacity
