---
description: Perform comprehensive health check on OpenShift cluster and report issues
argument-hint: "[--verbose] [--output-format]"
---

## Name
openshift:cluster-health-check

## Synopsis
```
/openshift:cluster-health-check [--verbose] [--output-format json|text]
```

## Description

The `cluster-health-check` command performs a comprehensive health analysis of an OpenShift/Kubernetes cluster and reports any detected issues. It examines cluster operators, nodes, deployments, pods, persistent volumes, and other critical resources to identify problems that may affect cluster stability or workload availability.

This command is useful for:
- Quick cluster status assessment
- Troubleshooting cluster issues
- Pre-deployment validation
- Regular health monitoring
- Identifying degraded components

## Prerequisites

Before using this command, ensure you have:

1. **Kubernetes/OpenShift CLI**: Either `oc` (OpenShift) or `kubectl` (Kubernetes)
   - Install `oc` from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Or install `kubectl` from: https://kubernetes.io/docs/tasks/tools/
   - Verify with: `oc version` or `kubectl version`

2. **Active cluster connection**: Must be connected to a running cluster
   - Verify with: `oc whoami` or `kubectl cluster-info`
   - Ensure KUBECONFIG is set if needed

3. **Sufficient permissions**: Must have read access to cluster resources
   - Cluster-admin or monitoring role recommended for comprehensive checks
   - Minimum: ability to view nodes, pods, and cluster operators

## Arguments

- **--verbose** (optional): Enable detailed output with additional context
  - Shows resource-level details
  - Includes warning conditions
  - Provides remediation suggestions

- **--output-format** (optional): Output format for results
  - `text` (default): Human-readable text format
  - `json`: Machine-readable JSON format for automation

## Implementation

The command performs the following health checks:

### 1. Determine CLI Tool

Detect which Kubernetes CLI is available:

```bash
if command -v oc &> /dev/null; then
    CLI="oc"
    CLUSTER_TYPE="OpenShift"
elif command -v kubectl &> /dev/null; then
    CLI="kubectl"
    CLUSTER_TYPE="Kubernetes"
else
    echo "Error: Neither 'oc' nor 'kubectl' CLI found. Please install one of them."
    exit 1
fi
```

### 2. Verify Cluster Connectivity

Check if connected to a cluster:

```bash
if ! $CLI cluster-info &> /dev/null; then
    echo "Error: Not connected to a cluster. Please configure your KUBECONFIG."
    exit 1
fi

# Get cluster version info
if [ "$CLUSTER_TYPE" = "OpenShift" ]; then
    CLUSTER_VERSION=$($CLI version -o json 2>/dev/null | jq -r '.openshiftVersion // "unknown"')
else
    CLUSTER_VERSION=$($CLI version --short 2>/dev/null | grep -i server | awk '{print $3}')
fi
```

### 3. Initialize Health Check Report

Create a report structure to collect findings:

```bash
REPORT_FILE=".work/cluster-health-check/report-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p .work/cluster-health-check

# Initialize counters
CRITICAL_ISSUES=0
WARNING_ISSUES=0
INFO_MESSAGES=0
```

### 4. Check Cluster Operators (OpenShift only)

For OpenShift clusters, check cluster operator health:

```bash
if [ "$CLUSTER_TYPE" = "OpenShift" ]; then
    echo "Checking Cluster Operators..."

    # Get all cluster operators
    DEGRADED_COs=$($CLI get clusteroperators -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Degraded" and .status=="True")) | .metadata.name')

    UNAVAILABLE_COs=$($CLI get clusteroperators -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Available" and .status=="False")) | .metadata.name')

    PROGRESSING_COs=$($CLI get clusteroperators -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Progressing" and .status=="True")) | .metadata.name')

    if [ -n "$DEGRADED_COs" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$DEGRADED_COs" | wc -l)))
        echo "❌ CRITICAL: Degraded cluster operators found:"
        echo "$DEGRADED_COs" | while read co; do
            echo "  - $co"
            # Get degraded message
            $CLI get clusteroperator "$co" -o json | jq -r '.status.conditions[] | select(.type=="Degraded") | "    Reason: \(.reason)\n    Message: \(.message)"'
        done
    fi

    if [ -n "$UNAVAILABLE_COs" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$UNAVAILABLE_COs" | wc -l)))
        echo "❌ CRITICAL: Unavailable cluster operators found:"
        echo "$UNAVAILABLE_COs" | while read co; do
            echo "  - $co"
        done
    fi

    if [ -n "$PROGRESSING_COs" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$PROGRESSING_COs" | wc -l)))
        echo "⚠️  WARNING: Cluster operators in progress:"
        echo "$PROGRESSING_COs" | while read co; do
            echo "  - $co"
        done
    fi
fi
```

### 5. Check Node Health

Examine all cluster nodes for issues:

```bash
echo "Checking Node Health..."

# Get nodes that are not Ready
NOT_READY_NODES=$($CLI get nodes -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Ready" and .status!="True")) | .metadata.name')

if [ -n "$NOT_READY_NODES" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$NOT_READY_NODES" | wc -l)))
    echo "❌ CRITICAL: Nodes not in Ready state:"
    echo "$NOT_READY_NODES" | while read node; do
        echo "  - $node"
        # Get node conditions
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | "    \(.type): \(.status) - \(.message // "N/A")"'
    done
fi

# Check for SchedulingDisabled nodes
DISABLED_NODES=$($CLI get nodes -o json | jq -r '.items[] | select(.spec.unschedulable==true) | .metadata.name')

if [ -n "$DISABLED_NODES" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$DISABLED_NODES" | wc -l)))
    echo "⚠️  WARNING: Nodes with scheduling disabled:"
    echo "$DISABLED_NODES" | while read node; do
        echo "  - $node"
    done
fi

# Check for node pressure conditions (MemoryPressure, DiskPressure, PIDPressure)
PRESSURE_NODES=$($CLI get nodes -o json | jq -r '.items[] | select(.status.conditions[] | select((.type=="MemoryPressure" or .type=="DiskPressure" or .type=="PIDPressure") and .status=="True")) | .metadata.name')

if [ -n "$PRESSURE_NODES" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$PRESSURE_NODES" | wc -l)))
    echo "⚠️  WARNING: Nodes under resource pressure:"
    echo "$PRESSURE_NODES" | while read node; do
        echo "  - $node"
        $CLI get node "$node" -o json | jq -r '.status.conditions[] | select((.type=="MemoryPressure" or .type=="DiskPressure" or .type=="PIDPressure") and .status=="True") | "    \(.type): \(.message // "N/A")"'
    done
fi

# Check node resource utilization if metrics-server is available
if $CLI top nodes &> /dev/null; then
    echo "Node Resource Utilization:"
    $CLI top nodes
fi
```

### 6. Check Pod Health Across All Namespaces

Identify problematic pods:

```bash
echo "Checking Pod Health..."

# Get pods that are not Running or Completed
FAILED_PODS=$($CLI get pods --all-namespaces -o json | jq -r '.items[] | select(.status.phase != "Running" and .status.phase != "Succeeded") | "\(.metadata.namespace)/\(.metadata.name) [\(.status.phase)]"')

if [ -n "$FAILED_PODS" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$FAILED_PODS" | wc -l)))
    echo "❌ CRITICAL: Pods in failed/pending state:"
    echo "$FAILED_PODS"
fi

# Check for pods with restarts
HIGH_RESTART_PODS=$($CLI get pods --all-namespaces -o json | jq -r '.items[] | select(.status.containerStatuses[]? | .restartCount > 5) | "\(.metadata.namespace)/\(.metadata.name) [Restarts: \(.status.containerStatuses[0].restartCount)]"')

if [ -n "$HIGH_RESTART_PODS" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$HIGH_RESTART_PODS" | wc -l)))
    echo "⚠️  WARNING: Pods with high restart count (>5):"
    echo "$HIGH_RESTART_PODS"
fi

# Check for CrashLoopBackOff pods
CRASHLOOP_PODS=$($CLI get pods --all-namespaces -o json | jq -r '.items[] | select(.status.containerStatuses[]? | .state.waiting?.reason == "CrashLoopBackOff") | "\(.metadata.namespace)/\(.metadata.name)"')

if [ -n "$CRASHLOOP_PODS" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$CRASHLOOP_PODS" | wc -l)))
    echo "❌ CRITICAL: Pods in CrashLoopBackOff:"
    echo "$CRASHLOOP_PODS"
fi

# Check for ImagePullBackOff pods
IMAGE_PULL_PODS=$($CLI get pods --all-namespaces -o json | jq -r '.items[] | select(.status.containerStatuses[]? | .state.waiting?.reason == "ImagePullBackOff" or .state.waiting?.reason == "ErrImagePull") | "\(.metadata.namespace)/\(.metadata.name)"')

if [ -n "$IMAGE_PULL_PODS" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$IMAGE_PULL_PODS" | wc -l)))
    echo "❌ CRITICAL: Pods with image pull errors:"
    echo "$IMAGE_PULL_PODS"
fi
```

### 7. Check Deployment/StatefulSet/DaemonSet Health

Verify workload controllers:

```bash
echo "Checking Deployments..."

# Check deployments with unavailable replicas
UNHEALTHY_DEPLOYMENTS=$($CLI get deployments --all-namespaces -o json | jq -r '.items[] | select(.status.unavailableReplicas > 0 or .status.replicas != .status.readyReplicas) | "\(.metadata.namespace)/\(.metadata.name) [Ready: \(.status.readyReplicas // 0)/\(.spec.replicas)]"')

if [ -n "$UNHEALTHY_DEPLOYMENTS" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$UNHEALTHY_DEPLOYMENTS" | wc -l)))
    echo "⚠️  WARNING: Deployments with unavailable replicas:"
    echo "$UNHEALTHY_DEPLOYMENTS"
fi

echo "Checking StatefulSets..."

UNHEALTHY_STATEFULSETS=$($CLI get statefulsets --all-namespaces -o json | jq -r '.items[] | select(.status.replicas != .status.readyReplicas) | "\(.metadata.namespace)/\(.metadata.name) [Ready: \(.status.readyReplicas // 0)/\(.spec.replicas)]"')

if [ -n "$UNHEALTHY_STATEFULSETS" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$UNHEALTHY_STATEFULSETS" | wc -l)))
    echo "⚠️  WARNING: StatefulSets with unavailable replicas:"
    echo "$UNHEALTHY_STATEFULSETS"
fi

echo "Checking DaemonSets..."

UNHEALTHY_DAEMONSETS=$($CLI get daemonsets --all-namespaces -o json | jq -r '.items[] | select(.status.numberReady != .status.desiredNumberScheduled) | "\(.metadata.namespace)/\(.metadata.name) [Ready: \(.status.numberReady)/\(.status.desiredNumberScheduled)]"')

if [ -n "$UNHEALTHY_DAEMONSETS" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$UNHEALTHY_DAEMONSETS" | wc -l)))
    echo "⚠️  WARNING: DaemonSets with unavailable pods:"
    echo "$UNHEALTHY_DAEMONSETS"
fi
```

### 8. Check Persistent Volume Claims

Check for storage issues:

```bash
echo "Checking Persistent Volume Claims..."

# Get PVCs that are not Bound
PENDING_PVCS=$($CLI get pvc --all-namespaces -o json | jq -r '.items[] | select(.status.phase != "Bound") | "\(.metadata.namespace)/\(.metadata.name) [\(.status.phase)]"')

if [ -n "$PENDING_PVCS" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$PENDING_PVCS" | wc -l)))
    echo "⚠️  WARNING: PVCs not in Bound state:"
    echo "$PENDING_PVCS"
fi
```

### 9. Check Critical Namespace Health

For OpenShift, check critical namespaces:

```bash
if [ "$CLUSTER_TYPE" = "OpenShift" ]; then
    echo "Checking Critical Namespaces..."

    CRITICAL_NAMESPACES="openshift-kube-apiserver openshift-etcd openshift-authentication openshift-console openshift-monitoring"

    for ns in $CRITICAL_NAMESPACES; do
        # Check if namespace exists
        if ! $CLI get namespace "$ns" &> /dev/null; then
            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            echo "❌ CRITICAL: Critical namespace missing: $ns"
            continue
        fi

        # Check for failed pods in critical namespace
        FAILED_IN_NS=$($CLI get pods -n "$ns" -o json | jq -r '.items[] | select(.status.phase != "Running" and .status.phase != "Succeeded") | .metadata.name')

        if [ -n "$FAILED_IN_NS" ]; then
            CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$FAILED_IN_NS" | wc -l)))
            echo "❌ CRITICAL: Failed pods in critical namespace $ns:"
            echo "$FAILED_IN_NS" | while read pod; do
                echo "  - $pod"
            done
        fi
    done
fi
```

### 10. Check Events for Recent Errors

Look for recent warning/error events:

```bash
echo "Checking Recent Events..."

# Get events from last 30 minutes with Warning or Error type
RECENT_WARNINGS=$($CLI get events --all-namespaces --field-selector type=Warning -o json | jq -r --arg since "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" '.items[] | select(.lastTimestamp > $since) | "\(.lastTimestamp) [\(.involvedObject.namespace)/\(.involvedObject.name)]: \(.message)"' | head -20)

if [ -n "$RECENT_WARNINGS" ]; then
    echo "⚠️  Recent Warning Events (last 30 minutes):"
    echo "$RECENT_WARNINGS"
fi
```

### 11. Generate Summary Report

Create a summary of findings:

```bash
echo ""
echo "==============================================="
echo "Cluster Health Check Summary"
echo "==============================================="
echo "Cluster Type: $CLUSTER_TYPE"
echo "Cluster Version: $CLUSTER_VERSION"
echo "Check Time: $(date)"
echo ""
echo "Results:"
echo "  Critical Issues: $CRITICAL_ISSUES"
echo "  Warnings: $WARNING_ISSUES"
echo ""

if [ $CRITICAL_ISSUES -eq 0 ] && [ $WARNING_ISSUES -eq 0 ]; then
    echo "✅ Cluster is healthy - no issues detected"
    exit 0
elif [ $CRITICAL_ISSUES -gt 0 ]; then
    echo "❌ Cluster has CRITICAL issues requiring immediate attention"
    exit 1
else
    echo "⚠️  Cluster has warnings - monitoring recommended"
    exit 0
fi
```

### 12. Optional: Export to JSON Format

If `--output-format json` is specified, export findings as JSON:

```json
{
  "cluster": {
    "type": "OpenShift",
    "version": "4.21.0",
    "checkTime": "2025-10-31T12:00:00Z"
  },
  "summary": {
    "criticalIssues": 2,
    "warnings": 5,
    "healthy": false
  },
  "findings": {
    "clusterOperators": {
      "degraded": ["authentication", "monitoring"],
      "unavailable": [],
      "progressing": ["network"]
    },
    "nodes": {
      "notReady": ["worker-1"],
      "schedulingDisabled": ["worker-2"],
      "underPressure": []
    },
    "pods": {
      "failed": ["namespace/pod-1", "namespace/pod-2"],
      "crashLooping": [],
      "imagePullErrors": ["namespace/pod-3"]
    },
    "workloads": {
      "unhealthyDeployments": [],
      "unhealthyStatefulSets": [],
      "unhealthyDaemonSets": []
    },
    "storage": {
      "pendingPVCs": []
    }
  }
}
```

## Examples

### Example 1: Basic health check
```
/openshift:cluster-health-check
```

Output:
```
Checking Cluster Operators...
✅ All cluster operators healthy

Checking Node Health...
⚠️  WARNING: Nodes with scheduling disabled:
  - ip-10-0-51-201.us-east-2.compute.internal

Checking Pod Health...
✅ All pods healthy

...

===============================================
Cluster Health Check Summary
===============================================
Cluster Type: OpenShift
Cluster Version: 4.21.0
Check Time: 2025-10-31 12:00:00

Results:
  Critical Issues: 0
  Warnings: 1

⚠️  Cluster has warnings - monitoring recommended
```

### Example 2: Verbose health check
```
/openshift:cluster-health-check --verbose
```

### Example 3: JSON output for automation
```
/openshift:cluster-health-check --output-format json
```

## Return Value

The command returns different exit codes based on findings:

- **Exit 0**: No critical issues found (cluster is healthy or has only warnings)
- **Exit 1**: Critical issues detected requiring immediate attention

**Output Format**:
- **Text** (default): Human-readable report with emoji indicators
- **JSON**: Structured data suitable for parsing/automation

## Common Issues and Remediation

### Degraded Cluster Operators

**Symptoms**: Cluster operators showing Degraded=True or Available=False

**Investigation**:
```bash
oc get clusteroperator <operator-name> -o yaml
oc logs -n openshift-<operator-namespace> -l app=<operator-name>
```

**Remediation**: Check operator logs and events for specific errors

### Nodes Not Ready

**Symptoms**: Nodes in NotReady state

**Investigation**:
```bash
oc describe node <node-name>
oc get events --field-selector involvedObject.name=<node-name>
```

**Remediation**: Common causes include network issues, disk pressure, or kubelet problems

### Pods in CrashLoopBackOff

**Symptoms**: Pods continuously restarting

**Investigation**:
```bash
oc logs <pod-name> -n <namespace> --previous
oc describe pod <pod-name> -n <namespace>
```

**Remediation**: Check application logs, resource limits, and configuration

### ImagePullBackOff Errors

**Symptoms**: Pods unable to pull container images

**Investigation**:
```bash
oc describe pod <pod-name> -n <namespace>
```

**Remediation**: Verify image name, registry credentials, and network connectivity

## Security Considerations

- **Read-only access**: This command only reads cluster state, no modifications
- **Sensitive data**: Be cautious when sharing reports as they may contain cluster topology information
- **RBAC requirements**: Ensure user has appropriate permissions for all resource types checked

## See Also

- OpenShift Documentation: https://docs.openshift.com/container-platform/latest/support/troubleshooting/
- Kubernetes Troubleshooting: https://kubernetes.io/docs/tasks/debug/
- Related commands: `/prow-job:analyze-test-failure`, `/must-gather:analyze`

## Notes

- The command checks cluster state at a point in time; transient issues may not be detected
- For OpenShift clusters, cluster operator checks are performed
- For vanilla Kubernetes, cluster operator checks are skipped
- Resource utilization checks require metrics-server to be installed
- Some checks may be skipped if user lacks sufficient permissions
