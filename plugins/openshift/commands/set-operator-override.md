---
description: Set cluster operators as managed or unmanaged for troubleshooting
argument-hint: "[--set-unmanaged <operator> [--scale-down]] [--set-managed <operator>] [--list]"
---

## Name
openshift:set-operator-override

## Synopsis
```
/openshift:set-operator-override --set-unmanaged <operator-name> [--scale-down]
/openshift:set-operator-override --set-managed <operator-name>
/openshift:set-operator-override --list
```

## Description

The `set-operator-override` command manages ClusterVersion overrides to set cluster operators as managed or unmanaged. This is primarily used for troubleshooting and testing scenarios where you need to prevent the Cluster Version Operator (CVO) from managing specific operators.

When an operator is set as unmanaged, the CVO will not:
- Update the operator to match the cluster version
- Monitor or reconcile the operator's resources
- Report issues if the operator version drifts from the cluster version

Additionally, the `--scale-down` option allows you to scale the operator deployment to 0 replicas, which prevents the operator from reconciling its operands (managed resources). This is essential when you need to modify operand deployments or configmaps without the operator reverting your changes.

**⚠️ WARNING**: Setting operators as unmanaged should only be done for troubleshooting and testing. Unmanaged operators may cause cluster instability, upgrade failures, or support issues.

This command is useful for:
- Testing operator patches or fixes without CVO interference
- Modifying operand deployments/configmaps without operator reconciliation
- Temporarily preventing operator updates during troubleshooting
- Investigating operator-specific issues in isolation
- Developing and testing operator changes locally

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Must be installed and configured
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Verify with: `oc version`

2. **Active cluster connection**: Must be connected to a running OpenShift cluster
   - Verify with: `oc whoami`
   - Ensure KUBECONFIG is set if needed

3. **Sufficient permissions**: Must have cluster-admin privileges
   - Ability to patch ClusterVersion resource
   - Ability to scale deployments in operator namespaces
   - Verify with: `oc auth can-i patch clusterversion`

4. **Understanding of risks**: Setting operators as unmanaged can lead to:
   - Cluster upgrade failures
   - Version skew between operators
   - Unsupported cluster configurations
   - Loss of Red Hat support for affected components

## Arguments

The command accepts one of the following options:

- **--set-unmanaged <operator-name>**: Set the specified operator as unmanaged
  - Operator name should match the ClusterOperator name
  - Example: `authentication`, `network`, `ingress`, `monitoring`
  - Prevents CVO from managing this operator
  - Optional: Add `--scale-down` to also scale operator deployment to 0 replicas

- **--scale-down**: (Used with --set-unmanaged) Scale the operator deployment to 0 replicas
  - Prevents the operator from reconciling its operands
  - Required when you need to modify operand deployments or configmaps

- **--set-managed <operator-name>**: Remove the override and set operator back to managed
  - Operator name should match the previously unmanaged operator
  - Removes the operator from spec.overrides
  - CVO will resume managing the operator and scale it up automatically

- **--list**: Display current ClusterVersion overrides
  - Shows all operators currently set as unmanaged
  - Shows which operators have been scaled down

**Note:** The `--scale-up` flag is not required when setting an operator back to managed. The Cluster Version Operator (CVO) automatically resumes managing the operator and scales it up to the appropriate replica count.

## Implementation

The command performs the following operations:

### 1. Verify Prerequisites

Check that `oc` is available and connected to a cluster:

```bash
# Check if oc is installed
if ! command -v oc &> /dev/null; then
    echo "Error: 'oc' CLI not found. Please install OpenShift CLI."
    exit 1
fi

# Check cluster connectivity
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to a cluster. Please login with 'oc login'."
    exit 1
fi

# Check permissions
if ! oc auth can-i patch clusterversion &> /dev/null; then
    echo "Error: Insufficient permissions. cluster-admin role required."
    exit 1
fi
```

### 2. Validate Operator Name

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

### 3. Find Operator Deployment

Locate the operator's deployment for scaling operations:

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

        # If not found, get the first deployment
        if [ -z "$deployment_name" ]; then
            deployment_name=$(oc get deployment -n "$namespace" -o name | head -1 | sed 's|deployment.apps/||')
        fi
    fi

    # Pattern 2: openshift-<operator>
    if [ -z "$deployment_name" ]; then
        namespace="openshift-${operator_name}"
        if oc get namespace "$namespace" &> /dev/null; then
            deployment_name=$(oc get deployment -n "$namespace" -o name | head -1 | sed 's|deployment.apps/||')
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

### 4. List Current Overrides (--list option)

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

### 5. Set Operator as Unmanaged with Optional Scale Down

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
    echo "Finding operator deployment to scale down..."

    deployment_info=$(find_operator_deployment "$OPERATOR_NAME")
    if [ $? -eq 0 ]; then
        namespace=$(echo "$deployment_info" | awk '{print $1}')
        deploy_name=$(echo "$deployment_info" | awk '{print $2}')

        echo "Found deployment: $deploy_name in namespace $namespace"

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
    else
        echo "⚠️  Warning: Could not find operator deployment for '$OPERATOR_NAME'"
        echo "   You may need to manually scale down the operator deployment if needed"
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

### 6. Set Operator as Managed

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

### 7. Error Handling

Handle common error scenarios:

```bash
# Invalid argument
if [ $# -eq 0 ]; then
    echo "Error: No arguments provided."
    echo ""
    echo "Usage:"
    echo "  /openshift:set-operator-override --set-unmanaged <operator> [--scale-down]"
    echo "  /openshift:set-operator-override --set-managed <operator>"
    echo "  /openshift:set-operator-override --list"
    exit 1
fi

# Check for conflicts (e.g., trying to patch a non-existent ClusterVersion)
if ! oc get clusterversion version &> /dev/null; then
    echo "Error: ClusterVersion 'version' not found. Is this an OpenShift cluster?"
    exit 1
fi

# Validate --scale-down is only used with --set-unmanaged
if [ "$ARG1" = "--scale-down" ] && [ "$ARG2" != "--set-unmanaged" ]; then
    echo "Error: --scale-down can only be used with --set-unmanaged"
    exit 1
fi
```

## Return Value

The command provides different outputs based on the operation:

**Exit codes:**
- **0**: Operation completed successfully
- **1**: Error occurred (operator not found, insufficient permissions, patch failed)

**Output format:**
- Shows current operator status before making changes
- Displays success/failure message for each operation
- Provides important warnings and reminders
- For `--list`, displays a formatted table of current overrides with scale status

## Examples

### Example 1: List current overrides

```
/openshift:set-operator-override --list
```

Output:
```
Current ClusterVersion Overrides:

DEPLOYMENT NAME                        NAMESPACE                              UNMANAGED    SCALED DOWN
----------------------------------------------------------------------------------------------------
authentication-operator                openshift-authentication-operator      true         Yes
network-operator                       openshift-network-operator             true         No
```

### Example 2: Set operator as unmanaged (without scaling)

```
/openshift:set-operator-override --set-unmanaged authentication
```

Output:
```
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

### Example 3: Set operator as unmanaged AND scale down

```
/openshift:set-operator-override --set-unmanaged network --scale-down
```

Output:
```
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

### Example 4: Set operator back to managed

```
/openshift:set-operator-override --set-managed network
```

Output:
```
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

### Example 5: Typical workflow for modifying operand configmaps

```
# Step 1: Set operator as unmanaged and scale down
/openshift:set-operator-override --set-unmanaged dns --scale-down

# Step 2: Modify the operand configmap (the operator won't reconcile it back)
oc edit configmap dns-default -n openshift-dns

# Step 3: Test your changes

# Step 4: Restore operator to managed state
/openshift:set-operator-override --set-managed dns
```

## Common Use Cases

### Modifying Operand Deployments or ConfigMaps

When you need to change resources managed by an operator:

1. Set as unmanaged and scale down:
   ```
   /openshift:set-operator-override --set-unmanaged monitoring --scale-down
   ```

2. Make your changes (operator won't reconcile them back):
   ```bash
   oc edit deployment prometheus-operator -n openshift-monitoring
   oc edit configmap cluster-monitoring-config -n openshift-monitoring
   ```

3. Test the changes

4. Restore to normal operation:
   ```
   /openshift:set-operator-override --set-managed monitoring
   ```

### Testing Operator Patches (Without Scaling)

When testing a fix for the operator itself (not its operands):

1. Set as unmanaged (keep operator running):
   ```
   /openshift:set-operator-override --set-unmanaged network
   ```

2. Apply your patch to the operator:
   ```bash
   oc set image deployment/network-operator -n openshift-network-operator \
     network-operator=quay.io/myrepo/network-operator:test
   ```

3. Test the operator changes

4. Restore to managed state:
   ```
   /openshift:set-operator-override --set-managed network
   ```

### Before Cluster Upgrades

Always check for unmanaged operators before upgrading:

```
/openshift:set-operator-override --list
```

If any operators are unmanaged, set them back to managed before upgrading.

## When to Use --scale-down

Use `--scale-down` when you need to:
- ✅ Modify operand deployments without the operator reverting changes
- ✅ Edit operand configmaps without the operator overwriting them
- ✅ Test operand behavior without operator interference
- ✅ Debug issues caused by operator reconciliation

Do NOT use `--scale-down` when you:
- ❌ Only want to patch/update the operator itself
- ❌ Want to prevent CVO from updating the operator (but keep operator running)
- ❌ Need the operator to continue managing its operands

## Security Considerations

- **cluster-admin required**: This command modifies cluster-level resources and scales deployments
- **Audit trail**: All changes to ClusterVersion and deployments are logged
- **Support implications**: Unmanaged operators may void Red Hat support
- **Production clusters**: Avoid using this in production unless absolutely necessary
- **Scaling risks**: Scaling critical operators to 0 can impact cluster functionality

## Best Practices

1. **Document your changes**: Always note which operators you've set as unmanaged and why
2. **Temporary use only**: Set operators back to managed as soon as troubleshooting is complete
3. **Check before upgrades**: List all overrides before attempting cluster upgrades
4. **Limited scope**: Only set specific operators as unmanaged, not multiple operators at once
5. **Monitor impact**: Watch for unexpected behavior after scaling down operators
6. **Use --scale-down judiciously**: Only scale down when you need to modify operands

## Troubleshooting

### Permission Denied

**Symptom**: Error when trying to patch ClusterVersion or scale deployment

**Solution**:
```bash
# Check your permissions
oc auth can-i patch clusterversion
oc auth can-i scale deployment

# You need cluster-admin role
oc adm policy add-cluster-role-to-user cluster-admin <your-username>
```

### Operator Deployment Not Found

**Symptom**: Cannot find operator deployment for scaling

**Solution**:
```bash
# Manually find the operator deployment
oc get deployments --all-namespaces | grep <operator-name>

# Common namespaces to check:
oc get deployments -n openshift-<operator-name>-operator
oc get deployments -n openshift-<operator-name>

# Then manually scale if needed
oc scale deployment <deployment-name> -n <namespace> --replicas=0
```

### Operator Still Reconciling After Scale Down

**Symptom**: Operator still modifies operands after being scaled to 0

**Solution**:
- Wait 30-60 seconds for pods to terminate
- Verify pods are gone: `oc get pods -n openshift-<operator>-operator`
- Check if there are multiple operator deployments

### Operator Not Scaling Up After Setting to Managed

**Symptom**: Operator deployment doesn't scale up after setting operator to managed

**Solution**:
Wait for the CVO to reconcile (typically 1-2 minutes). If the operator still doesn't scale up:
```bash
# Check if the deployment was scaled down
oc get deployment <deployment-name> -n <namespace>

# Manually scale if needed
oc scale deployment <deployment-name> -n <namespace> --replicas=1
```

## See Also

- ClusterVersion API: https://docs.openshift.com/container-platform/latest/rest_api/config_apis/clusterversion-config-openshift-io-v1.html
- Cluster Version Operator: https://github.com/openshift/cluster-version-operator
- Operator Lifecycle: https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html
- Related commands: `/openshift:cluster-health-check`

## Notes

- This command only works on OpenShift clusters (not vanilla Kubernetes)
- The ClusterVersion resource must exist (standard in OpenShift 4.x+)
- Override changes are immediate but may take 1-2 minutes for CVO to process
- Scaling changes are immediate once the deployment is patched
- Setting critical operators as unmanaged (e.g., `kube-apiserver`) can destabilize the cluster
- Scaling critical operators to 0 can cause cluster outages
- Always consult with Red Hat support before using this in production environments
- When setting an operator back to managed, the CVO automatically scales it to the correct replica count
