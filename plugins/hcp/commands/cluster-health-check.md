---
description: Perform comprehensive health check on HCP cluster and report issues
argument-hint: <cluster-name> [--verbose] [--output-format json|text]
---

## Name
hcp:cluster-health-check

## Synopsis

```
/hcp:cluster-health-check <cluster-name> [--verbose] [--output-format json|text]
```

## Description

The `/hcp:cluster-health-check` command performs an extensive diagnostic of a Hosted Control Plane (HCP) cluster to assess its operational health, stability, and performance. It automates the validation of multiple control plane and infrastructure components to ensure the cluster is functioning as expected.

The command runs a comprehensive set of health checks covering control plane pods, etcd, node pools, networking, and infrastructure readiness. It also detects degraded or progressing states, certificate issues, and recent warning events.

Specifically, it performs the following:

- Detects and validates the availability of oc or kubectl CLI tools and verifies cluster connectivity.
- Checks the HostedCluster resource status (Available, Progressing, Degraded) and reports any abnormal conditions with detailed reasons and messages.
- Validates control plane pod health in the management cluster, detecting non-running pods, crash loops, high restart counts, and image pull errors.
- Performs etcd health checks to ensure data consistency and availability.
- Inspects NodePools for replica mismatches, readiness, and auto-scaling configuration accuracy.
- Evaluates infrastructure readiness (including AWS/Azure-specific validations like endpoint services).
- Examines networking and ingress components, including Konnectivity servers and router pods.
- Scans for recent warning events across HostedCluster, NodePool, and control plane namespaces.
- Reviews certificate conditions to identify expiring or invalid certificates.
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
   - Minimum: ability to view nodes, pods, and cluster operators

## Arguments

- **[cluster-name]** (required): Name of the HostedCluster to check. This uniquely identifies the HCP instance whose health will be analyzed. Example: `hcp-demo`
- **[namespace]** (optional): The namespace in which the HostedCluster resides. Defaults to clusters if not provided. Example: `/hcp:cluster-health-check hcp-demo clusters-dev`
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
CLUSTER_NAME=$1
NAMESPACE=${2:-"clusters"}
CONTROL_PLANE_NS="${NAMESPACE}-${CLUSTER_NAME}"

REPORT_FILE=".work/hcp-health-check/report-${CLUSTER_NAME}-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p .work/hcp-health-check

# Initialize counters
CRITICAL_ISSUES=0
WARNING_ISSUES=0
INFO_MESSAGES=0
```

Arguments:
- $1 (cluster-name): Name of the HostedCluster resource to check. This is the name visible in `kubectl get hostedcluster` output. Required.
- $2 (namespace): Namespace containing the HostedCluster resource. Defaults to "clusters" if not specified. Optional.

### 3. Check HostedCluster Status

Verify the HostedCluster resource health:

```bash
echo "Checking HostedCluster Status..."

# Check if HostedCluster exists
if ! $CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo "❌ CRITICAL: HostedCluster '$CLUSTER_NAME' not found in namespace '$NAMESPACE'"
    exit 1
fi

# Get HostedCluster conditions
HC_AVAILABLE=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Available") | .status')
HC_PROGRESSING=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Progressing") | .status')
HC_DEGRADED=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Degraded") | .status')

if [ "$HC_AVAILABLE" != "True" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
    echo "❌ CRITICAL: HostedCluster is not Available"
    # Get reason and message
    $CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Available") | "    Reason: \(.reason)\n    Message: \(.message)"'
fi

if [ "$HC_DEGRADED" == "True" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
    echo "❌ CRITICAL: HostedCluster is Degraded"
    $CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Degraded") | "    Reason: \(.reason)\n    Message: \(.message)"'
fi

if [ "$HC_PROGRESSING" == "True" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + 1))
    echo "⚠️  WARNING: HostedCluster is Progressing"
    $CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Progressing") | "    Reason: \(.reason)\n    Message: \(.message)"'
fi

# Check version and upgrade status
HC_VERSION=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.version.history[0].version // "unknown"')
echo "ℹ️  HostedCluster version: $HC_VERSION"
```

### 4. Check Control Plane Pod Health

Examine control plane components in the management cluster:

```bash
echo "Checking Control Plane Pods..."

# Check if control plane namespace exists
if ! $CLI get namespace "$CONTROL_PLANE_NS" &> /dev/null; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
    echo "❌ CRITICAL: Control plane namespace '$CONTROL_PLANE_NS' not found"
else
    # Get pods that are not Running
    FAILED_CP_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r '.items[] | select(.status.phase != "Running" and .status.phase != "Succeeded") | "\(.metadata.name) [\(.status.phase)]"')

    if [ -n "$FAILED_CP_PODS" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$FAILED_CP_PODS" | wc -l)))
        echo "❌ CRITICAL: Control plane pods in failed state:"
        echo "$FAILED_CP_PODS" | while read pod; do
            echo "  - $pod"
        done
    fi

    # Check for pods with high restart count
    HIGH_RESTART_CP_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r '.items[] | select(.status.containerStatuses[]? | .restartCount > 3) | "\(.metadata.name) [Restarts: \(.status.containerStatuses[0].restartCount)]"')

    if [ -n "$HIGH_RESTART_CP_PODS" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + $(echo "$HIGH_RESTART_CP_PODS" | wc -l)))
        echo "⚠️  WARNING: Control plane pods with high restart count (>3):"
        echo "$HIGH_RESTART_CP_PODS" | while read pod; do
            echo "  - $pod"
        done
    fi

    # Check for CrashLoopBackOff pods
    CRASHLOOP_CP_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r '.items[] | select(.status.containerStatuses[]? | .state.waiting?.reason == "CrashLoopBackOff") | .metadata.name')

    if [ -n "$CRASHLOOP_CP_PODS" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$CRASHLOOP_CP_PODS" | wc -l)))
        echo "❌ CRITICAL: Control plane pods in CrashLoopBackOff:"
        echo "$CRASHLOOP_CP_PODS" | while read pod; do
            echo "  - $pod"
        done
    fi

    # Check for ImagePullBackOff
    IMAGE_PULL_CP_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r '.items[] | select(.status.containerStatuses[]? | .state.waiting?.reason == "ImagePullBackOff" or .state.waiting?.reason == "ErrImagePull") | .metadata.name')

    if [ -n "$IMAGE_PULL_CP_PODS" ]; then
        CRITICAL_ISSUES=$((CRITICAL_ISSUES + $(echo "$IMAGE_PULL_CP_PODS" | wc -l)))
        echo "❌ CRITICAL: Control plane pods with image pull errors:"
        echo "$IMAGE_PULL_CP_PODS" | while read pod; do
            echo "  - $pod"
        done
    fi

    # Check critical control plane components
    echo "Checking critical control plane components..."
    CRITICAL_COMPONENTS="kube-apiserver etcd kube-controller-manager kube-scheduler"
    
    for component in $CRITICAL_COMPONENTS; do
        COMPONENT_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -l app="$component" -o json 2>/dev/null | jq -r '.items[].metadata.name')
        
        if [ -z "$COMPONENT_PODS" ]; then
            # Try alternative label
            COMPONENT_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r ".items[] | select(.metadata.name | startswith(\"$component\")) | .metadata.name")
        fi
        
        if [ -z "$COMPONENT_PODS" ]; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: No pods found for component: $component"
        else
            # Check if any are not running
            for pod in $COMPONENT_PODS; do
                POD_STATUS=$($CLI get pod "$pod" -n "$CONTROL_PLANE_NS" -o json | jq -r '.status.phase')
                if [ "$POD_STATUS" != "Running" ]; then
                    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
                    echo "❌ CRITICAL: $component pod $pod is not Running (Status: $POD_STATUS)"
                fi
            done
        fi
    done
fi
```

### 5. Check Etcd Health

Verify etcd cluster health and performance:

```bash
echo "Checking Etcd Health..."

# Find etcd pods
ETCD_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -l app=etcd -o json 2>/dev/null | jq -r '.items[].metadata.name')

if [ -z "$ETCD_PODS" ]; then
    ETCD_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r '.items[] | select(.metadata.name | startswith("etcd")) | .metadata.name')
fi

if [ -n "$ETCD_PODS" ]; then
    for pod in $ETCD_PODS; do
        # Check etcd endpoint health
        ETCD_HEALTH=$($CLI exec -n "$CONTROL_PLANE_NS" "$pod" -- etcdctl endpoint health 2>/dev/null || echo "failed")
        
        if echo "$ETCD_HEALTH" | grep -q "unhealthy"; then
            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            echo "❌ CRITICAL: Etcd pod $pod is unhealthy"
        elif echo "$ETCD_HEALTH" | grep -q "failed"; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: Could not check etcd health for pod $pod"
        fi
    done
else
    WARNING_ISSUES=$((WARNING_ISSUES + 1))
    echo "⚠️  WARNING: No etcd pods found"
fi
```

### 6. Check NodePool Status

Verify NodePool health and scaling:

```bash
echo "Checking NodePool Status..."

# Get all NodePools for this HostedCluster
NODEPOOLS=$($CLI get nodepool -n "$NAMESPACE" -l hypershift.openshift.io/hostedcluster="$CLUSTER_NAME" -o json | jq -r '.items[].metadata.name')

if [ -z "$NODEPOOLS" ]; then
    WARNING_ISSUES=$((WARNING_ISSUES + 1))
    echo "⚠️  WARNING: No NodePools found for HostedCluster $CLUSTER_NAME"
else
    for nodepool in $NODEPOOLS; do
        # Get NodePool status
        NP_REPLICAS=$($CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.spec.replicas // 0')
        NP_READY=$($CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.status.replicas // 0')
        NP_AVAILABLE=$($CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Ready") | .status')

        echo "  NodePool: $nodepool [Ready: $NP_READY/$NP_REPLICAS]"

        if [ "$NP_AVAILABLE" != "True" ]; then
            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            echo "❌ CRITICAL: NodePool $nodepool is not Ready"
            $CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="Ready") | "    Reason: \(.reason)\n    Message: \(.message)"'
        fi

        if [ "$NP_READY" != "$NP_REPLICAS" ]; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: NodePool $nodepool has mismatched replicas (Ready: $NP_READY, Desired: $NP_REPLICAS)"
        fi

        # Check for auto-scaling
        AUTOSCALING=$($CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.spec.autoScaling // empty')
        if [ -n "$AUTOSCALING" ]; then
            MIN=$($CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.spec.autoScaling.min')
            MAX=$($CLI get nodepool "$nodepool" -n "$NAMESPACE" -o json | jq -r '.spec.autoScaling.max')
            echo "    Auto-scaling enabled: Min=$MIN, Max=$MAX"
        fi
    done
fi
```

### 7. Check Infrastructure Status

Validate infrastructure components (AWS/Azure specific):

```bash
echo "Checking Infrastructure Status..."

# Get infrastructure platform
PLATFORM=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.spec.platform.type')
echo "  Platform: $PLATFORM"

# Check for infrastructure-related conditions
INFRA_READY=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="InfrastructureReady") | .status')

if [ "$INFRA_READY" != "True" ]; then
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
    echo "❌ CRITICAL: Infrastructure is not ready"
    $CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type=="InfrastructureReady") | "    Reason: \(.reason)\n    Message: \(.message)"'
fi

# Platform-specific checks
if [ "$PLATFORM" == "AWS" ]; then
    # Check AWS-specific resources
    echo "  Performing AWS-specific checks..."
    
    # Check if endpoint service is configured
    ENDPOINT_SERVICE=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.platform.aws.endpointService // "not-found"')
    if [ "$ENDPOINT_SERVICE" == "not-found" ]; then
        WARNING_ISSUES=$((WARNING_ISSUES + 1))
        echo "⚠️  WARNING: AWS endpoint service not configured"
    fi
fi
```

### 8. Check Network and Ingress

Verify network connectivity and ingress configuration:

```bash
echo "Checking Network and Ingress..."

# Check if connectivity is healthy (for private clusters)
CONNECTIVITY_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -l app=connectivity-server -o json 2>/dev/null | jq -r '.items[].metadata.name')

if [ -n "$CONNECTIVITY_PODS" ]; then
    for pod in $CONNECTIVITY_PODS; do
        POD_STATUS=$($CLI get pod "$pod" -n "$CONTROL_PLANE_NS" -o json | jq -r '.status.phase')
        if [ "$POD_STATUS" != "Running" ]; then
            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            echo "❌ CRITICAL: Connectivity server pod $pod is not Running"
        fi
    done
fi

# Check ingress/router pods
ROUTER_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -l app=router -o json 2>/dev/null | jq -r '.items[].metadata.name')

if [ -z "$ROUTER_PODS" ]; then
    ROUTER_PODS=$($CLI get pods -n "$CONTROL_PLANE_NS" -o json | jq -r '.items[] | select(.metadata.name | contains("router") or contains("ingress")) | .metadata.name')
fi

if [ -n "$ROUTER_PODS" ]; then
    for pod in $ROUTER_PODS; do
        POD_STATUS=$($CLI get pod "$pod" -n "$CONTROL_PLANE_NS" -o json | jq -r '.status.phase')
        if [ "$POD_STATUS" != "Running" ]; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: Router/Ingress pod $pod is not Running"
        fi
    done
fi
```

### 9. Check Recent Events

Look for recent warning/error events:

```bash
echo "Checking Recent Events..."

# Get recent warning events for HostedCluster
HC_EVENTS=$($CLI get events -n "$NAMESPACE" --field-selector involvedObject.name="$CLUSTER_NAME",involvedObject.kind=HostedCluster,type=Warning --sort-by='.lastTimestamp' | tail -10)

if [ -n "$HC_EVENTS" ]; then
    echo "⚠️  Recent Warning Events for HostedCluster:"
    echo "$HC_EVENTS"
fi

# Get recent warning events in control plane namespace
CP_EVENTS=$($CLI get events -n "$CONTROL_PLANE_NS" --field-selector type=Warning --sort-by='.lastTimestamp' 2>/dev/null | tail -10)

if [ -n "$CP_EVENTS" ]; then
    echo "⚠️  Recent Warning Events in Control Plane:"
    echo "$CP_EVENTS"
fi

# Get recent events for NodePools
for nodepool in $NODEPOOLS; do
    NP_EVENTS=$($CLI get events -n "$NAMESPACE" --field-selector involvedObject.name="$nodepool",involvedObject.kind=NodePool,type=Warning --sort-by='.lastTimestamp' 2>/dev/null | tail -5)
    
    if [ -n "$NP_EVENTS" ]; then
        echo "⚠️  Recent Warning Events for NodePool $nodepool:"
        echo "$NP_EVENTS"
    fi
done
```

### 10. Check Certificate Status

Verify certificate validity:

```bash
echo "Checking Certificate Status..."

# Check certificate expiration warnings
CERT_CONDITIONS=$($CLI get hostedcluster "$CLUSTER_NAME" -n "$NAMESPACE" -o json | jq -r '.status.conditions[] | select(.type | contains("Certificate")) | "\(.type): \(.status) - \(.message // "N/A")"')

if [ -n "$CERT_CONDITIONS" ]; then
    echo "$CERT_CONDITIONS" | while read line; do
        if echo "$line" | grep -q "False"; then
            WARNING_ISSUES=$((WARNING_ISSUES + 1))
            echo "⚠️  WARNING: $line"
        fi
    done
fi
```

### 11. Generate Summary Report

Create a summary of findings:

```bash
echo ""
echo "==============================================="
echo "HCP Cluster Health Check Summary"
echo "==============================================="
echo "Cluster Name: $CLUSTER_NAME"
echo "Namespace: $NAMESPACE"
echo "Control Plane Namespace: $CONTROL_PLANE_NS"
echo "Platform: $PLATFORM"
echo "Version: $HC_VERSION"
echo "Check Time: $(date)"
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

### 12. Optional: Export to JSON Format

If `--output-format json` is specified, export findings as JSON:

```json
{
  "cluster": {
    "name": "my-hcp-cluster",
    "namespace": "clusters",
    "controlPlaneNamespace": "clusters-my-hcp-cluster",
    "platform": "AWS",
    "version": "4.21.0",
    "checkTime": "2025-11-11T12:00:00Z"
  },
  "summary": {
    "criticalIssues": 1,
    "warnings": 3,
    "overallStatus": "WARNING"
  },
  "findings": {
    "hostedCluster": {
      "available": true,
      "progressing": true,
      "degraded": false,
      "infrastructureReady": true
    },
    "controlPlane": {
      "failedPods": [],
      "crashLoopingPods": [],
      "highRestartPods": ["kube-controller-manager-xxx"],
      "imagePullErrors": []
    },
    "etcd": {
      "healthy": true,
      "pods": ["etcd-0", "etcd-1", "etcd-2"]
    },
    "nodePools": {
      "total": 2,
      "ready": 2,
      "details": [
        {
          "name": "workers",
          "replicas": 3,
          "ready": 3,
          "autoScaling": {
            "enabled": true,
            "min": 2,
            "max": 5
          }
        }
      ]
    },
    "network": {
      "konnectivityHealthy": true,
      "ingressHealthy": true
    },
    "events": {
      "recentWarnings": 5
    }
  }
}
```

## Examples

### Example 1: Basic health check with default namespace
```bash
/hcp:cluster-health-check my-cluster
```

Output, for healthy cluster:
```text
HCP Cluster Health Check: my-cluster (namespace: clusters)
================================================================================

OVERALL STATUS: ✅ HEALTHY

COMPONENT STATUS:
✅ HostedCluster: Available
✅ Control Plane: All pods running (0 restarts)
✅ NodePool: 3/3 nodes ready
✅ Infrastructure: AWS resources validated
✅ Network: Operational
✅ Storage/Etcd: Healthy

No critical issues found. Cluster is operating normally.

DIAGNOSTIC COMMANDS:
Run these commands for detailed information:

kubectl get hostedcluster my-cluster -n clusters -o yaml
kubectl get pods -n clusters-my-cluster
kubectl get nodepool -n clusters
```

Output, with warnings:
```text
HCP Cluster Health Check: test-cluster (namespace: clusters)
================================================================================

OVERALL STATUS: ⚠️  WARNING

COMPONENT STATUS:
✅ HostedCluster: Available
⚠️  Control Plane: 1 pod restarting
✅ NodePool: 2/2 nodes ready
✅ Infrastructure: Validated
✅ Network: Operational
⚠️  Storage/Etcd: High latency detected

ISSUES FOUND:

[WARNING] Control Plane Pod Restarting
- Component: kube-controller-manager
- Location: clusters-test-cluster namespace
- Restarts: 3 in the last hour
- Impact: May cause temporary API instability
- Recommended Action:
  kubectl logs -n clusters-test-cluster kube-controller-manager-xxx --previous
  Check for configuration issues or resource constraints

[WARNING] Etcd High Latency
- Component: etcd
- Metrics: Backend commit duration > 100ms
- Impact: Slower cluster operations
- Recommended Action:
  Check management cluster node performance
  Review etcd disk I/O with: kubectl exec -n clusters-test-cluster etcd-0 -- etcdctl endpoint status

DIAGNOSTIC COMMANDS:

1. Check HostedCluster details:
   kubectl get hostedcluster test-cluster -n clusters -o yaml

2. View control plane events:
   kubectl get events -n clusters-test-cluster --sort-by='.lastTimestamp' | tail -20

3. Check etcd metrics:
   kubectl exec -n clusters-test-cluster etcd-0 -- etcdctl endpoint health
```

### Example 2: Health check with custom namespace
```bash
/hcp:cluster-health-check production-cluster prod-clusters
```
Performs health check on cluster "production-cluster" in the "prod-clusters" namespace.

### Example 3: Verbose health check
```bash
/hcp:cluster-health-check my-cluster --verbose
```

### Example 4: JSON output for automation
```bash
/hcp:cluster-health-check my-cluster --output-format json
```

## Return Value

The command returns a structured health report containing:

- **OVERALL STATUS**: Health summary (Healthy ✅ / Warning ⚠️ / Critical ❌)
- **COMPONENT STATUS**: Status of each checked component with visual indicators
- **ISSUES FOUND**: Detailed list of problems with:
  - Severity level (Critical/Warning/Info)
  - Component location
  - Impact assessment
  - Recommended actions
- **DIAGNOSTIC COMMANDS**: kubectl commands for further investigation

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

## Notes

- This command requires appropriate RBAC permissions to view HostedCluster, NodePool, and Pod resources
- The command provides diagnostic guidance but does not automatically remediate issues
- For critical production issues, always follow your organization's incident response procedures
- Regular health checks (daily or before changes) help catch issues early
- Some checks may be skipped if user lacks sufficient permissions
