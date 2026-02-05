---
name: OpenShift Set Operator Override
description: Detailed implementation guide for managing ClusterVersion overrides to set cluster operators as managed or unmanaged with optional deployment scaling
---

# OpenShift Set Operator Override

This skill provides detailed implementation instructions for managing OpenShift cluster operator overrides via the ClusterVersion API.

**Scope**: This skill applies **only to CVO-managed payload operators** - core platform operators delivered in the OpenShift release payload (e.g., `network`, `authentication`, `dns`, `monitoring`, `ingress`).

**Throughout this skill, the term "operator" refers exclusively to these core platform operators in the release payload.** This skill does **not** apply to:
- Operators installed or managed by OLM (Operator Lifecycle Manager) via OperatorHub
- Custom operators or arbitrary ClusterOperator resources not part of the release payload
- User-installed operators outside the CVO's management scope

## When to Use This Skill

Use this skill when the user wants to:
- Set a cluster operator as unmanaged to prevent CVO from managing it
- Scale down an operator deployment to prevent it from reconciling its operands
- Set an operator back to managed state
- List current ClusterVersion overrides
- Modify operand deployments or configmaps without operator interference
- Test operator patches or fixes without CVO interference

## Prerequisites

Before starting, verify these prerequisites:

1. **OpenShift CLI (`oc`)**: Must be installed and configured
   - Install from: [OpenShift download mirror](https://mirror.openshift.com/pub/openshift-v4/clients/ocp/)
   - Verify with: `oc version`

2. **jq (JSON processor)**: Required for parsing and manipulating ClusterVersion.spec.overrides
   - Install from: [jq download page](https://jqlang.github.io/jq/download/) or use package manager (`apt install jq`, `yum install jq`, `brew install jq`)
   - Verify with: `jq --version`
   - Used for reading/mutating ClusterVersion spec.overrides field

3. **Active cluster connection**: Must be connected to a running OpenShift cluster
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set if needed

4. **Sufficient permissions**: Must have cluster-admin privileges
   - Ability to patch ClusterVersion resource: `oc auth can-i patch clusterversion`
   - Ability to scale deployments in operator namespaces (required for --scale-down): `oc auth can-i update deployments.apps --all-namespaces`

5. **Understanding of risks**: Setting operators as unmanaged can lead to:
   - Cluster upgrade failures
   - Version skew between operators
   - Unsupported cluster configurations
   - Loss of Red Hat support for affected components

## Input Format

The user will provide one of the following operation modes:

1. **Set operator as unmanaged**:
   - Format: `--set-unmanaged <operator-name> [--scale-down]`
   - Example: `--set-unmanaged authentication`
   - Example with scale: `--set-unmanaged network --scale-down`

2. **Set operator as managed**:
   - Format: `--set-managed <operator-name>`
   - Example: `--set-managed authentication`

3. **List current overrides**:
   - Format: `--list`

## Implementation Steps

### Step 1: Verify Prerequisites

Check that `oc` and `jq` are available and connected to a cluster:

```bash
# Check if oc is installed
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
    exit 1
fi

# Check if jq is installed (required for parsing/patching ClusterVersion.spec.overrides)
if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' not found. Please install jq from <https://jqlang.github.io/jq/download/>"
    exit 1
fi

# Check cluster connectivity
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to a cluster. Please login with 'oc login'."
    exit 1
fi

# Check permissions for patching ClusterVersion
if ! oc auth can-i patch clusterversion --quiet; then
    echo "Error: Insufficient permissions to patch ClusterVersion. cluster-admin role required."
    exit 1
fi

# Check permissions for scaling deployments (required for --scale-down option)
if ! oc auth can-i update deployments.apps --all-namespaces --quiet; then
    echo "Warning: No permission to scale deployments. The --scale-down option will not work."
    echo "This is optional - you can still set operators as unmanaged without scaling."
fi
```

**Error Handling**:
- If `oc` not found: Provide installation instructions for user's platform
- If `jq` not found: Provide installation instructions (<https://jqlang.github.io/jq/download/>)
- If not connected: Instruct user to run `oc login`
- If insufficient permissions to patch ClusterVersion: Explain cluster-admin role is required
- If insufficient permissions to scale deployments: Warn that --scale-down will not work (optional)

### Step 2: Validate Operator Name

Verify that the operator exists in the cluster:

```bash
# Get operator name from argument
OPERATOR_NAME="$1"

# Check if the ClusterOperator exists
if ! oc get clusteroperator "$OPERATOR_NAME" &> /dev/null; then
    echo "Error: ClusterOperator '$OPERATOR_NAME' not found."
    echo ""
    echo "Available cluster operators:"
    oc get clusteroperators -o name | sed 's|clusteroperator.config.openshift.io/||'
    exit 1
fi

echo "Found ClusterOperator: $OPERATOR_NAME"
```

**Error Handling**:
- If operator not found: List all available ClusterOperators for user to choose from
- Display helpful error message with correct operator names

### Step 3: Define Operator Deployment Discovery Function

Create a function to locate the operator's deployment for scaling operations:

```bash
# Function to find operator deployment
find_operator_deployment() {
    local operator_name="$1"
    local deployment_name=""
    local namespace=""

    # Common patterns for operator namespaces
    # Pattern 1: openshift-<operator>-operator
    namespace="openshift-${operator_name}-operator"
    if oc get namespace "$namespace" &> /dev/null; then
        # Try common deployment names
        for deploy_name in "${operator_name}-operator" "cluster-${operator_name}-operator"; do
            if oc get deployment "$deploy_name" -n "$namespace" &> /dev/null; then
                deployment_name="$deploy_name"
                break
            fi
        done

        # If not found, get the first deployment (if any exist in this namespace)
        if [ -z "$deployment_name" ]; then
            deployment_name=$(oc get deployment -n "$namespace" -o name 2>/dev/null | head -1 | sed 's|deployment.apps/||')
            # Note: if namespace exists but has no deployments, deployment_name remains empty
            # and Pattern 2 will be tried (see line 169)
        fi
    fi

    # Pattern 2: openshift-<operator>
    if [ -z "$deployment_name" ]; then
        namespace="openshift-${operator_name}"
        if oc get namespace "$namespace" &> /dev/null; then
            deployment_name=$(oc get deployment -n "$namespace" -o name 2>/dev/null | head -1 | sed 's|deployment.apps/||')
            # Note: if namespace exists but has no deployments, deployment_name remains empty
            # and Pattern 3 will be tried (see line 177)
        fi
    fi

    # Pattern 3: Search by label
    if [ -z "$deployment_name" ]; then
        result=$(oc get deployment --all-namespaces -l "app=${operator_name}" -o jsonpath='{.items[0].metadata.namespace} {.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$result" ]; then
            namespace=$(echo "$result" | awk '{print $1}')
            deployment_name=$(echo "$result" | awk '{print $2}')
        fi
    fi

    if [ -n "$deployment_name" ] && [ -n "$namespace" ]; then
        echo "$namespace $deployment_name"
        return 0
    else
        return 1
    fi
}
```

**Function Behavior**:
- Tries multiple common namespace patterns for OpenShift operators
- Returns both namespace and deployment name as space-separated values
- Returns exit code 0 on success, 1 on failure
- Searches in order: `openshift-{operator}-operator`, `openshift-{operator}`, then by label

### Step 4: List Current Overrides (--list option)

Display all current overrides in the ClusterVersion:

```bash
echo "Current ClusterVersion Overrides:"
echo ""

# Get overrides from ClusterVersion
OVERRIDES=$(oc get clusterversion version -o json | jq -r '.spec.overrides[]? | "\(.name)\t\(.namespace)\t\(.unmanaged)"')

if [ -z "$OVERRIDES" ]; then
    echo "  No overrides configured (all operators are managed)"
else
    echo "DEPLOYMENT NAME                        NAMESPACE                              UNMANAGED    SCALED DOWN"
    echo "----------------------------------------------------------------------------------------------------"
    echo "$OVERRIDES" | while IFS=$'\t' read -r name namespace unmanaged; do
        # Check if deployment is scaled to 0
        replicas=$(oc get deployment "$name" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null)
        if [ $? -eq 0 ]; then
            if [ "$replicas" = "0" ]; then
                scaled_down="Yes"
            else
                scaled_down="No"
            fi
        else
            scaled_down="Unknown"
        fi
        printf "%-40s %-40s %-12s %s\n" "$name" "$namespace" "$unmanaged" "$scaled_down"
    done
fi
```

**Output Format**:
- Displays a formatted table with columns: DEPLOYMENT NAME, NAMESPACE, UNMANAGED, SCALED DOWN
- Shows which operators are currently unmanaged
- Checks each deployment's replica count to show if it's scaled down
- If no overrides exist, display friendly message

### Step 5: Set Operator as Unmanaged with Optional Scale Down

Add the operator to ClusterVersion spec.overrides and optionally scale down:

```bash
OPERATOR_NAME="$1"
SCALE_DOWN="$2"  # "true" if --scale-down is specified

# Show current status
echo "Current status of operator '$OPERATOR_NAME':"
oc get clusteroperator "$OPERATOR_NAME"
echo ""

# Find the operator deployment to get correct name and namespace
echo "Finding operator deployment..."
deployment_info=$(find_operator_deployment "$OPERATOR_NAME")
if [ $? -ne 0 ]; then
    echo "❌ Error: Could not find operator deployment for '$OPERATOR_NAME'"
    echo "   Cannot determine the correct deployment name and namespace for the override"
    exit 1
fi

namespace=$(echo "$deployment_info" | awk '{print $1}')
deploy_name=$(echo "$deployment_info" | awk '{print $2}')
echo "Found deployment: $deploy_name in namespace $namespace"
echo ""

# Check if already unmanaged
ALREADY_UNMANAGED=$(oc get clusterversion version -o json | jq -r ".spec.overrides[]? | select(.name==\"$deploy_name\" and .namespace==\"$namespace\") | .unmanaged")

if [ "$ALREADY_UNMANAGED" = "true" ]; then
    echo "⚠️  Warning: Operator '$OPERATOR_NAME' is already unmanaged."
else
    # Get existing overrides
    EXISTING_OVERRIDES=$(oc get clusterversion version -o json | jq -c '.spec.overrides // []')

    # Add new override to existing list with actual deployment name and namespace
    # Use -c flag to output compact JSON for reliable embedding in patch command
    NEW_OVERRIDES=$(echo "$EXISTING_OVERRIDES" | jq -c --arg name "$deploy_name" --arg ns "$namespace" '. + [{"kind": "Deployment", "group": "apps", "name": $name, "namespace": $ns, "unmanaged": true}]')

    # Apply patch - use compact JSON to avoid embedding issues
    echo "Setting operator '$OPERATOR_NAME' as unmanaged..."
    oc patch clusterversion version --type=merge --patch "{\"spec\":{\"overrides\":$NEW_OVERRIDES}}"

    if [ $? -eq 0 ]; then
        echo "✅ Successfully set operator '$OPERATOR_NAME' as unmanaged"
    else
        echo "❌ Failed to set operator as unmanaged"
        exit 1
    fi
fi

# Handle scale down if requested
if [ "$SCALE_DOWN" = "true" ]; then
    echo ""
    echo "Scaling operator deployment..."
    echo "Using deployment: $deploy_name in namespace $namespace"
    # Get current replica count
    current_replicas=$(oc get deployment "$deploy_name" -n "$namespace" -o jsonpath='{.spec.replicas}')

    if [ "$current_replicas" = "0" ]; then
        echo "⚠️  Deployment is already scaled to 0 replicas"
    else
        # Scale down to 0
        echo "Scaling deployment to 0 replicas..."
        oc scale deployment "$deploy_name" -n "$namespace" --replicas=0

        if [ $? -eq 0 ]; then
            echo "✅ Successfully scaled down operator deployment to 0 replicas"
        else
            echo "❌ Failed to scale down operator deployment"
            exit 1
        fi
    fi
fi

echo ""
echo "⚠️  IMPORTANT REMINDERS:"
echo "  - The CVO will no longer manage this operator"
if [ "$SCALE_DOWN" = "true" ]; then
    echo "  - The operator is scaled to 0 and will NOT reconcile its operands"
    echo "  - You can now safely modify operand deployments and configmaps"
fi
echo "  - This may cause cluster upgrade issues"
echo "  - Remember to restore when done:"
echo "    /openshift:set-operator-override --set-managed $OPERATOR_NAME"
```

**Key Steps**:
1. Display current operator status using `oc get clusteroperator`
2. Find the operator deployment using the discovery function
3. Check if already unmanaged to avoid duplicate entries
4. Get existing overrides as JSON array
5. Add new override entry with correct deployment name and namespace
6. Use `jq -c` to generate compact JSON for reliable shell embedding
7. Apply patch to ClusterVersion using `oc patch`
8. If `--scale-down` specified, scale the deployment to 0 replicas
9. Display important warnings and reminders

**Important Notes**:
- Must use actual deployment name and namespace in override, not ClusterOperator name
- Use compact JSON output (`jq -c`) to avoid shell escaping issues
- Check if already unmanaged before adding duplicate override
- Scaling is separate from setting unmanaged - both can be done independently

### Step 6: Set Operator as Managed

Remove the operator from ClusterVersion spec.overrides:

```bash
OPERATOR_NAME="$1"

# Find the operator deployment to get correct name and namespace
echo "Finding operator deployment..."
deployment_info=$(find_operator_deployment "$OPERATOR_NAME")
if [ $? -ne 0 ]; then
    echo "❌ Error: Could not find operator deployment for '$OPERATOR_NAME'"
    echo "   Cannot determine the correct deployment name and namespace to remove from overrides"
    exit 1
fi

namespace=$(echo "$deployment_info" | awk '{print $1}')
deploy_name=$(echo "$deployment_info" | awk '{print $2}')
echo "Found deployment: $deploy_name in namespace $namespace"
echo ""

# Check if currently unmanaged
CURRENTLY_UNMANAGED=$(oc get clusterversion version -o json | jq -r ".spec.overrides[]? | select(.name==\"$deploy_name\" and .namespace==\"$namespace\") | .unmanaged")

if [ "$CURRENTLY_UNMANAGED" != "true" ]; then
    echo "⚠️  Warning: Operator '$OPERATOR_NAME' is not currently unmanaged."
else
    # Get existing overrides
    EXISTING_OVERRIDES=$(oc get clusterversion version -o json | jq -c '.spec.overrides // []')

    # Remove the override for this operator by matching both name and namespace
    # Use positive matching with 'not' to avoid shell escaping issues with !=
    NEW_OVERRIDES=$(echo "$EXISTING_OVERRIDES" | jq -c --arg name "$deploy_name" --arg ns "$namespace" 'map(select((.name == $name and .namespace == $ns) | not))')

    # Apply patch - use compact JSON to avoid embedding issues
    echo "Setting operator '$OPERATOR_NAME' back to managed..."
    oc patch clusterversion version --type=merge --patch "{\"spec\":{\"overrides\":$NEW_OVERRIDES}}"

    if [ $? -eq 0 ]; then
        echo "✅ Successfully set operator '$OPERATOR_NAME' back to managed"
        echo ""
        echo "The CVO will now resume managing this operator and scale it up automatically."
    else
        echo "❌ Failed to set operator as managed"
        exit 1
    fi
fi

# Wait a moment and show updated status
echo ""
echo "Updated status of operator '$OPERATOR_NAME':"
sleep 2
oc get clusteroperator "$OPERATOR_NAME"
```

**Key Steps**:
1. Find the operator deployment to get correct name and namespace
2. Check if currently unmanaged (warn if not)
3. Get existing overrides as JSON array
4. Filter out the override matching both name and namespace
5. Use `jq -c` with `map(select(...))` to remove the entry
6. Apply patch to ClusterVersion
7. Wait 2 seconds and display updated operator status

**Important Notes**:
- CVO automatically scales the operator back up when set to managed (no explicit `--scale-up` needed)
- Must match both name AND namespace when removing override (using both fields ensures correct override deletion)
- Use `jq 'map(select(... | not))'` pattern for filtering

### Step 7: Handle Arguments and Route to Operations

Parse command-line arguments and route to appropriate operation:

```bash
# Invalid argument
if [ $# -eq 0 ]; then
    echo "Error: No arguments provided."
    echo ""
    echo "Usage:"
    echo "  /openshift:set-operator-override --set-unmanaged <operator-name> [--scale-down]"
    echo "  /openshift:set-operator-override --set-managed <operator-name>"
    echo "  /openshift:set-operator-override --list"
    exit 1
fi

# Check for conflicts (e.g., trying to patch a non-existent ClusterVersion)
if ! oc get clusterversion version &> /dev/null; then
    echo "Error: ClusterVersion 'version' not found. Is this an OpenShift cluster?"
    exit 1
fi

# Parse arguments
ARG1="$1"
ARG2="$2"
ARG3="$3"

# Validate --scale-down is only used with --set-unmanaged
if [ "$ARG2" = "--scale-down" ] || [ "$ARG3" = "--scale-down" ]; then
    if [ "$ARG1" != "--set-unmanaged" ]; then
        echo "Error: --scale-down can only be used with --set-unmanaged"
        echo ""
        echo "Usage:"
        echo "  /openshift:set-operator-override --set-unmanaged <operator-name> [--scale-down]"
        exit 1
    fi
fi

# Route to appropriate operation
if [ "$ARG1" = "--list" ]; then
    # Execute Step 4: List Current Overrides
    # ... (code from Step 4)
elif [ "$ARG1" = "--set-unmanaged" ]; then
    OPERATOR_NAME="$ARG2"
    SCALE_DOWN="false"

    if [ -z "$OPERATOR_NAME" ]; then
        echo "Error: --set-unmanaged requires an operator name"
        exit 1
    fi

    if [ "$ARG3" = "--scale-down" ]; then
        SCALE_DOWN="true"
    fi

    # Execute Step 2: Validate Operator Name
    # Execute Step 5: Set Operator as Unmanaged
    # ... (code from Steps 2 and 5)
elif [ "$ARG1" = "--set-managed" ]; then
    OPERATOR_NAME="$ARG2"

    if [ -z "$OPERATOR_NAME" ]; then
        echo "Error: --set-managed requires an operator name"
        exit 1
    fi

    # Execute Step 2: Validate Operator Name
    # Execute Step 6: Set Operator as Managed
    # ... (code from Steps 2 and 6)
else
    echo "Error: Unknown option '$ARG1'"
    echo ""
    echo "Usage:"
    echo "  /openshift:set-operator-override --set-unmanaged <operator-name> [--scale-down]"
    echo "  /openshift:set-operator-override --set-managed <operator-name>"
    echo "  /openshift:set-operator-override --list"
    exit 1
fi
```

**Validation**:
- Validate --scale-down is only used with --set-unmanaged
- Ensure operator name is provided when required
- Check ClusterVersion resource exists
- Provide helpful usage message on error

## Error Handling

Handle these error scenarios gracefully:

### 1. oc CLI Not Installed

**Detection**: `command -v oc` returns non-zero

**Response**:
```bash
echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
echo "Download from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
exit 1
```

### 2. jq Not Installed

**Detection**: `command -v jq` returns non-zero

**Response**:
```bash
echo "Error: 'jq' not found. jq is required for parsing/patching ClusterVersion.spec.overrides."
echo "Install from: <https://jqlang.github.io/jq/download/>"
echo "Or use package manager: apt install jq, yum install jq, or brew install jq"
exit 1
```

### 3. Not Connected to Cluster

**Detection**: `oc whoami` returns non-zero

**Response**:
```bash
echo "Error: Not connected to a cluster. Please login with 'oc login'."
exit 1
```

### 4. Insufficient Permissions

**Detection**: `oc auth can-i patch clusterversion --quiet` returns non-zero

**Response**:
```bash
echo "Error: Insufficient permissions. cluster-admin role required."
echo "Contact your cluster administrator to grant cluster-admin role."
exit 1
```

### 5. Operator Not Found

**Detection**: `oc get clusteroperator $OPERATOR_NAME` returns non-zero

**Response**:
```bash
echo "Error: ClusterOperator '$OPERATOR_NAME' not found."
echo ""
echo "Available cluster operators:"
oc get clusteroperators -o name | sed 's|clusteroperator.config.openshift.io/||'
exit 1
```

### 6. ClusterVersion Not Found

**Detection**: `oc get clusterversion version` returns non-zero

**Response**:
```bash
echo "Error: ClusterVersion 'version' not found. Is this an OpenShift cluster?"
exit 1
```

### 7. Operator Deployment Not Found

**Detection**: `find_operator_deployment` returns non-zero

**Response**:
```bash
echo "❌ Error: Could not find operator deployment for '$OPERATOR_NAME'"
echo "   Cannot determine the correct deployment name and namespace for the override"
echo ""
echo "You can manually find the deployment with:"
echo "  oc get deployments --all-namespaces | grep $OPERATOR_NAME"
exit 1
```

### 8. Patch Operation Failed

**Detection**: `oc patch clusterversion` returns non-zero

**Response**:
```bash
echo "❌ Failed to set operator as unmanaged"
echo "Check that you have cluster-admin permissions and the ClusterVersion is accessible"
exit 1
```

### 9. Scale Operation Failed

**Detection**: `oc scale deployment` returns non-zero

**Response**:
```bash
echo "❌ Failed to scale down operator deployment"
echo "Check that the deployment exists and you have permission to scale it"
exit 1
```

### 10. Invalid Argument Combination

**Detection**: `--scale-down` used with `--set-managed` or `--list` (validated on line 445)

**Response**:
```bash
echo "Error: --scale-down can only be used with --set-unmanaged"
echo ""
echo "Usage:"
echo "  /openshift:set-operator-override --set-unmanaged <operator-name> [--scale-down]"
exit 1
```

### 11. Missing Required Argument

**Detection**: No operator name provided after `--set-unmanaged` or `--set-managed`

**Response**:
```bash
echo "Error: --set-unmanaged requires an operator name"
echo "Usage: /openshift:set-operator-override --set-unmanaged <operator-name> [--scale-down]"
exit 1
```

## Performance Considerations

1. **ClusterVersion API Calls**:
   - Minimize calls to `oc get clusterversion` by storing JSON in variables
   - Use `jq` for JSON manipulation instead of multiple `oc` calls

2. **Deployment Discovery**:
   - Check common patterns first before expensive label searches
   - Cache deployment info in variable for reuse

3. **Validation**:
   - Perform all validation checks before making any changes
   - Fail fast on prerequisite failures

4. **JSON Processing**:
   - Use `jq -c` for compact JSON to avoid shell escaping issues
   - Store JSON in variables to avoid parsing multiple times

## Examples

### Example 1: List Current Overrides

**Input**: `--list`

**Expected Output**:
```text
Current ClusterVersion Overrides:

DEPLOYMENT NAME                        NAMESPACE                              UNMANAGED    SCALED DOWN
----------------------------------------------------------------------------------------------------
authentication-operator                openshift-authentication-operator      true         Yes
network-operator                       openshift-network-operator             true         No
```

### Example 2: Set Operator as Unmanaged (Without Scaling)

**Input**: `--set-unmanaged authentication`

**Expected Output**:
```text
Found ClusterOperator: authentication

Current status of operator 'authentication':
NAME             VERSION   AVAILABLE   PROGRESSING   DEGRADED   SINCE   MESSAGE
authentication   4.15.2    True        False         False      5d

Finding operator deployment...
Found deployment: authentication-operator in namespace openshift-authentication-operator

Setting operator 'authentication' as unmanaged...
clusterversion.config.openshift.io/version patched

✅ Successfully set operator 'authentication' as unmanaged

⚠️  IMPORTANT REMINDERS:
  - The CVO will no longer manage this operator
  - This may cause cluster upgrade issues
  - Remember to restore when done:
    /openshift:set-operator-override --set-managed authentication
```

### Example 3: Set Operator as Unmanaged AND Scale Down

**Input**: `--set-unmanaged network --scale-down`

**Expected Output**:
```text
Found ClusterOperator: network

Current status of operator 'network':
NAME      VERSION   AVAILABLE   PROGRESSING   DEGRADED   SINCE   MESSAGE
network   4.15.2    True        False         False      5d

Finding operator deployment...
Found deployment: network-operator in namespace openshift-network-operator

Setting operator 'network' as unmanaged...
clusterversion.config.openshift.io/version patched

✅ Successfully set operator 'network' as unmanaged

Finding operator deployment to scale down...
Found deployment: network-operator in namespace openshift-network-operator
Scaling deployment to 0 replicas...
deployment.apps/network-operator scaled

✅ Successfully scaled down operator deployment to 0 replicas

⚠️  IMPORTANT REMINDERS:
  - The CVO will no longer manage this operator
  - The operator is scaled to 0 and will NOT reconcile its operands
  - You can now safely modify operand deployments and configmaps
  - This may cause cluster upgrade issues
  - Remember to restore when done:
    /openshift:set-operator-override --set-managed network
```

### Example 4: Set Operator Back to Managed

**Input**: `--set-managed network`

**Expected Output**:
```text
Finding operator deployment...
Found deployment: network-operator in namespace openshift-network-operator

Setting operator 'network' back to managed...
clusterversion.config.openshift.io/version patched

✅ Successfully set operator 'network' back to managed

The CVO will now resume managing this operator and scale it up automatically.

Updated status of operator 'network':
NAME      VERSION   AVAILABLE   PROGRESSING   DEGRADED   SINCE   MESSAGE
network   4.15.2    True        True          False      5s      Progressing: Working towards 4.15.2
```

## Tips

- Always verify prerequisites before starting to avoid partial operations
- Use the `find_operator_deployment()` function to correctly identify deployment name and namespace
- Use `jq -c` for compact JSON output when embedding in shell commands
- Check if operator is already unmanaged before adding duplicate overrides
- Display clear warnings and reminders about the risks and restoration steps
- Wait 2 seconds after setting to managed to allow CVO to reconcile before showing status
- The CVO automatically handles scaling up when setting operator to managed - no manual scale-up needed
- When scaling down, always check current replica count to avoid redundant operations
- Use both deployment name and namespace when matching overrides - ClusterOperator name alone is not sufficient

## Important Notes

1. **Deployment Name vs ClusterOperator Name**:
   - ClusterVersion overrides use the actual Deployment resource name and namespace
   - ClusterOperator name frequently differs from Deployment name
   - Example: ClusterOperator "authentication" → Deployment "authentication-operator" in namespace "openshift-authentication-operator"
   - Always use `find_operator_deployment()` to get correct names

2. **JSON Processing**:
   - Use `jq -c` for compact JSON to avoid shell embedding issues
   - Store JSON in variables rather than piping through multiple commands
   - Use `--arg` with jq to safely pass shell variables into JSON manipulation

3. **CVO Behavior**:
   - When set to managed, CVO automatically scales operators back up (no explicit `--scale-up` needed)
   - CVO may take 1-2 minutes to reconcile the operator
   - Operator status will show "Progressing" during reconciliation

4. **Scaling vs Unmanaged**:
   - Setting unmanaged: CVO won't update the operator to match cluster version
   - Scaling to 0: Operator won't reconcile its operands (managed resources)
   - Both operations are independent and can be combined or used separately
   - Use `--scale-down` only when you need to modify operands

5. **Common Operator Namespace Patterns**:
   - `openshift-{operator}-operator` (most common)
   - `openshift-{operator}`
   - Some operators use custom namespaces (discovered by label)
   - The discovery function tries all patterns automatically

6. **Security and Support Implications**:
   - Setting operators as unmanaged creates unsupported configurations
   - May prevent cluster upgrades from completing
   - Can cause version skew between components
   - Always restore operators to managed state before upgrades
   - Red Hat support may be limited for clusters with unmanaged operators
