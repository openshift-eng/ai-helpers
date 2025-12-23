---
description: Set cluster operators as managed or unmanaged for troubleshooting
argument-hint: "(--set-unmanaged <operator-name> [--scale-down] | --set-managed <operator-name> | --list)"
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

**Scope**: ClusterVersion overrides **only apply to CVO-managed payload operators** - core platform operators delivered in the OpenShift release payload (e.g., `network`, `authentication`, `dns`, `monitoring`, `ingress`).

**Throughout this document, the term "operator" refers exclusively to these core platform operators in the release payload.** This command does **not** work with:
- Operators installed or managed by OLM (Operator Lifecycle Manager) via OperatorHub
- Custom operators or arbitrary ClusterOperator resources not part of the release payload
- User-installed operators outside the CVO's management scope

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
   - Install from: [OpenShift download mirror](https://mirror.openshift.com/pub/openshift-v4/clients/ocp/)
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
  - Shows which operators have been scaled-down

**Note:** The `--scale-up` flag is not required when setting an operator back to managed. The Cluster Version Operator (CVO) automatically resumes managing the operator and scales it up to the appropriate replica count.

## Implementation

This command uses the `openshift-set-operator-override` skill to manage ClusterVersion overrides. The skill performs the following operations:

### 1. Verify Prerequisites
- Check that `oc` CLI is installed and available
- Verify cluster connectivity via `oc whoami`
- Confirm cluster-admin permissions via `oc auth can-i patch clusterversion`

### 2. Validate Operator Name
- Verify the ClusterOperator resource exists
- Display available operators if validation fails

### 3. Find Operator Deployment
- Discover the operator deployment using common OpenShift namespace patterns
- Try multiple patterns: `openshift-{operator}-operator`, `openshift-{operator}`, label-based search
- Return both deployment name and namespace for override operations

### 4. List Current Overrides (--list option)
- Query ClusterVersion `spec.overrides` field
- Display table showing deployment name, namespace, unmanaged status, and scaled-down status
- Check each deployment's replica count to determine if scaled-down

### 5. Set Operator as Unmanaged (--set-unmanaged option)
- Display current operator status
- Find operator deployment using discovery function
- Add override entry to ClusterVersion `spec.overrides` with correct deployment name and namespace
- Optionally scale deployment to 0 replicas if `--scale-down` specified
- Display warnings and restoration instructions

### 6. Set Operator as Managed (--set-managed option)
- Find operator deployment to identify correct override entry
- Remove override from ClusterVersion `spec.overrides`
- CVO automatically resumes management and scales operator back up
- Display updated operator status after reconciliation

### 7. Error Handling
- Handle missing prerequisites (oc not installed, not connected, insufficient permissions)
- Validate operator exists before operations
- Detect deployment discovery failures
- Provide helpful error messages with actionable solutions

**Note**: The skill contains detailed bash implementation including JSON manipulation with `jq`, deployment discovery logic, and ClusterVersion patch operations. See the skill for complete implementation details.

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

```bash
/openshift:set-operator-override --list
```

Output:
```text
Current ClusterVersion Overrides:

DEPLOYMENT NAME                        NAMESPACE                              UNMANAGED    SCALED DOWN
----------------------------------------------------------------------------------------------------
authentication-operator                openshift-authentication-operator      true         Yes
network-operator                       openshift-network-operator             true         No
```

### Example 2: Set operator as unmanaged (without scaling)

```bash
/openshift:set-operator-override --set-unmanaged authentication
```

Output:
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

### Example 3: Set operator as unmanaged AND scale down

```bash
/openshift:set-operator-override --set-unmanaged network --scale-down
```

Output:
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

### Example 4: Set operator back to managed

```bash
/openshift:set-operator-override --set-managed network
```

Output:
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

### Example 5: Typical workflow for modifying operand configmaps

```bash
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
   ```bash
   /openshift:set-operator-override --set-unmanaged monitoring --scale-down
   ```

2. Make your changes (operator won't reconcile them back):
   ```bash
   oc edit deployment prometheus-operator -n openshift-monitoring
   oc edit configmap cluster-monitoring-config -n openshift-monitoring
   ```

3. Test the changes

4. Restore to normal operation:
   ```bash
   /openshift:set-operator-override --set-managed monitoring
   ```

### Testing Operator Patches (Without Scaling)

When testing a fix for the operator itself (not its operands):

1. Set as unmanaged (keep operator running):
   ```bash
   /openshift:set-operator-override --set-unmanaged network
   ```

2. Apply your patch to the operator:
   ```bash
   oc set image deployment/network-operator -n openshift-network-operator \
     network-operator=quay.io/myrepo/network-operator:test
   ```

3. Test the operator changes

4. Restore to managed state:
   ```bash
   /openshift:set-operator-override --set-managed network
   ```

### Before Cluster Upgrades

Always check for unmanaged operators before upgrading:

```bash
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
- Verify pods are gone: `oc get pods -n openshift-<operator-name>-operator`
- Check if there are multiple operator deployments

### Operator Not Scaling Up After Setting to Managed

**Symptom**: Operator deployment doesn't scale up after setting operator to managed

**Solution**:
Wait for the CVO to reconcile (typically 1-2 minutes). If the operator still doesn't scale up:
```bash
# Check if the deployment was scaled down
oc get deployment <deployment-name> -n <namespace>

# Manually scale the deployment
oc scale deployment <deployment-name> -n <namespace> --replicas=1
```

## See Also

- [ClusterVersion API](https://docs.openshift.com/container-platform/latest/rest_api/config_apis/clusterversion-config-openshift-io-v1.html)
- [Cluster Version Operator](https://github.com/openshift/cluster-version-operator)
- [Operator Lifecycle](https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html)
- Related commands: `/openshift:cluster-health-check`

## Notes

- This command only works on OpenShift clusters (not vanilla Kubernetes)
- The ClusterVersion resource must exist (standard in OpenShift 4.x+)
- Override changes are immediate but may take 1-2 minutes for CVO to process
- Scaling changes are immediate once the deployment is patched
- Setting critical operators as unmanaged (e.g., `kube-apiserver`) can destabilize the cluster
- Scaling critical operators to 0 can cause cluster outages
- Always consult Red Hat support before using this in production environments
- When setting an operator back to managed, the CVO automatically scales it to the correct replica count
