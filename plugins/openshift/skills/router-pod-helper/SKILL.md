---
name: Router Pod Helper
description: Discover and validate OpenShift router pods for inspection commands
---

# Router Pod Helper

This skill provides reusable logic for discovering and validating OpenShift router pods in the `openshift-ingress` namespace. It's designed to be used by any command that needs to interact with router pods (configuration, sessions, stats, etc.).

## When to Use This Skill

Use this skill when implementing commands that need to:
- Access router configuration or runtime data from router pods
- Execute commands inside router pods
- Inspect router pod state or logs

## Prerequisites

This skill assumes the **oc-prereqs** skill has already been executed to verify:
- oc CLI is installed
- User is connected to an OpenShift cluster

## Router Pod Discovery

### 1. Find Router Pods

Discover router pods in the `openshift-ingress` namespace using the standard label selector:

```bash
NAMESPACE="openshift-ingress"

# If no specific pod name provided, discover available router pods
if [ -z "$router_pod_name" ]; then
    echo "Finding router pods in namespace: $NAMESPACE"

    # List router pods using the standard ingresscontroller label
    ROUTER_PODS=$(oc get pods -n $NAMESPACE \
        -l ingresscontroller.operator.openshift.io/deployment-ingresscontroller=default \
        -o jsonpath='{.items[*].metadata.name}')

    if [ -z "$ROUTER_PODS" ]; then
        echo "Error: No router pods found in namespace $NAMESPACE"
        echo "Please verify the cluster has router pods running."
        exit 1
    fi

    # Select the first router pod
    ROUTER_POD=$(echo $ROUTER_PODS | awk '{print $1}')
    echo "Selected router pod: $ROUTER_POD"
else
    ROUTER_POD="$router_pod_name"
    echo "Using specified router pod: $ROUTER_POD"
fi
```

**What this does:**
- Checks if user provided a specific pod name
- If not, queries for pods with the standard router label
- Selects the first available router pod
- Provides clear error if no router pods exist

**Label used:**
- `ingresscontroller.operator.openshift.io/deployment-ingresscontroller=default`
- This is the standard label for default ingress controller router pods

### 2. Verify Pod Status

Ensure the selected pod is in Running state before proceeding:

```bash
POD_STATUS=$(oc get pod -n $NAMESPACE $ROUTER_POD -o jsonpath='{.status.phase}' 2>/dev/null)

if [ "$POD_STATUS" != "Running" ]; then
    echo "Error: Router pod $ROUTER_POD is not running (status: $POD_STATUS)"
    exit 1
fi

echo "Router pod status: Running"
```

**What this does:**
- Retrieves the pod's phase (Pending/Running/Succeeded/Failed/Unknown)
- Exits with error if not Running
- Prevents commands from failing when executed against non-ready pods

### 3. Optional: List All Available Router Pods

For commands that might benefit from showing all available pods:

```bash
echo "Available router pods:"
oc get pods -n $NAMESPACE \
    -l ingresscontroller.operator.openshift.io/deployment-ingresscontroller=default \
    -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName,AGE:.metadata.creationTimestamp
echo ""
```

## Usage Pattern

Commands should use this flow:

1. **Prerequisite**: Run `oc-prereqs` checks first
2. **Discovery**: Find router pod (auto-discover or use provided name)
3. **Validation**: Verify pod is Running
4. **Execution**: Execute command-specific logic against the pod

## Complete Example

```bash
# Step 1: Prerequisites (from oc-prereqs skill)
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found."
    exit 1
fi

if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to an OpenShift cluster."
    exit 1
fi

# Step 2: Router Pod Discovery (from router-pod-helper skill)
NAMESPACE="openshift-ingress"

if [ -z "$router_pod_name" ]; then
    echo "Finding router pods in namespace: $NAMESPACE"

    ROUTER_PODS=$(oc get pods -n $NAMESPACE \
        -l ingresscontroller.operator.openshift.io/deployment-ingresscontroller=default \
        -o jsonpath='{.items[*].metadata.name}')

    if [ -z "$ROUTER_PODS" ]; then
        echo "Error: No router pods found in namespace $NAMESPACE"
        exit 1
    fi

    ROUTER_POD=$(echo $ROUTER_PODS | awk '{print $1}')
    echo "Selected router pod: $ROUTER_POD"
else
    ROUTER_POD="$router_pod_name"
    echo "Using specified router pod: $ROUTER_POD"
fi

# Step 3: Pod Status Validation
POD_STATUS=$(oc get pod -n $NAMESPACE $ROUTER_POD -o jsonpath='{.status.phase}' 2>/dev/null)

if [ "$POD_STATUS" != "Running" ]; then
    echo "Error: Router pod $ROUTER_POD is not running (status: $POD_STATUS)"
    exit 1
fi

# Step 4: Execute command-specific logic
# (e.g., get HAProxy config, show sessions, etc.)
oc exec -n $NAMESPACE $ROUTER_POD -- <your-command-here>
```

## Environment Variables

After running this skill, the following variables are set:

- `$NAMESPACE` - Always `openshift-ingress`
- `$ROUTER_POD` - Name of the selected router pod
- `$POD_STATUS` - Status of the pod (should be "Running")

## Error Handling

This skill will exit with errors if:
- No router pods are found in the namespace
- The specified pod doesn't exist
- The pod is not in Running state

All errors provide clear, actionable messages to the user.

## Related Skills

- `oc-prereqs` - OpenShift CLI prerequisites (must be run before this skill)

## Commands Using This Skill

Commands that use this skill to interact with router pods:
- `/openshift:router-show-config` - Display router configuration
- `/openshift:router-show-sessions` - Display active sessions
- `/openshift:router-show-info` - Display router process information

## Notes

### Non-Default Ingress Controllers

This skill targets the `default` ingress controller. For custom ingress controllers, the label selector would need to be adjusted:

```bash
# For custom ingress controller named "custom-router"
-l ingresscontroller.operator.openshift.io/deployment-ingresscontroller=custom-router
```

### Multiple Router Pods

In HA deployments, there are typically multiple router pods. This skill selects the first one, but commands could be enhanced to:
- Query all router pods
- Aggregate statistics from multiple pods
