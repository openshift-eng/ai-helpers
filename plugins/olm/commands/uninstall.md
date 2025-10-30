---
description: Uninstall a day-2 operator and optionally remove its resources
argument-hint: <operator-name> [namespace] [--remove-crds] [--remove-namespace]
---

## Name
olm:uninstall

## Synopsis
```
/olm:uninstall <operator-name> [namespace] [--remove-crds] [--remove-namespace]
```

## Description
The `olm:uninstall` command uninstalls a day-2 operator from an OpenShift cluster by removing its Subscription, ClusterServiceVersion (CSV), and optionally its Custom Resource Definitions (CRDs) and namespace.

This command provides a comprehensive uninstallation workflow:
- Removes the operator's Subscription
- Deletes the ClusterServiceVersion (CSV)
- Optionally removes operator-managed deployments
- Optionally deletes Custom Resource Definitions (CRDs)
- Optionally removes the operator's namespace
- Provides detailed feedback on each step

The command is designed to safely clean up operators installed via OLM, with optional flags for thorough cleanup of all operator-related resources.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Operator name (required) - The name of the operator to uninstall
   - `$2`: Namespace (optional) - The namespace where operator is installed. If not provided, defaults to `{operator-name}-operator`
   - `$3+`: Flags (optional):
     - `--remove-crds`: Remove Custom Resource Definitions after uninstalling
     - `--remove-namespace`: Remove the operator's namespace after cleanup
     - `--force`: Skip confirmation prompts

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check if user has cluster-admin or sufficient privileges

3. **Verify Operator Installation**:
   - Check if namespace exists:
     ```bash
     oc get namespace {namespace} --ignore-not-found
     ```
   - Check if subscription exists:
     ```bash
     oc get subscription {operator-name} -n {namespace} --ignore-not-found
     ```
   - If not found, display error: "Operator {operator-name} is not installed in namespace {namespace}"
   - List what will be uninstalled

4. **Display Uninstallation Plan**:
   - Show operator details:
     ```bash
     oc get subscription {operator-name} -n {namespace} -o yaml
     oc get csv -n {namespace}
     ```
   - Display what will be removed:
     - Subscription name and namespace
     - CSV name and version
     - Deployments (if any)
     - CRDs (if `--remove-crds` flag is set)
     - Namespace (if `--remove-namespace` flag is set)

5. **Request User Confirmation** (unless `--force` flag is set):
   - Display warning:
     ```
     WARNING: You are about to uninstall {operator-name} from namespace {namespace}.
     This will remove:
       - Subscription: {subscription-name}
       - ClusterServiceVersion: {csv-name}
       - Operator deployments
       [- Custom Resource Definitions (if --remove-crds is set)]
       [- Namespace {namespace} (if --remove-namespace is set)]
     
     Are you sure you want to continue? (yes/no)
     ```
   - Wait for user confirmation
   - If user says no, abort operation

6. **Delete Subscription**:
   - Remove the operator's subscription:
     ```bash
     oc delete subscription {operator-name} -n {namespace}
     ```
   - Verify deletion:
     ```bash
     oc get subscription {operator-name} -n {namespace} --ignore-not-found
     ```
   - Display result

7. **Delete ClusterServiceVersion (CSV)**:
   - Get the CSV name:
     ```bash
     oc get csv -n {namespace} -o jsonpath='{.items[?(@.spec.displayName contains "{operator-name}")].metadata.name}'
     ```
   - Delete the CSV:
     ```bash
     oc delete csv {csv-name} -n {namespace}
     ```
   - This will automatically remove operator deployments
   - Verify CSV is deleted:
     ```bash
     oc get csv -n {namespace} --ignore-not-found
     ```

8. **Remove Operator Deployments** (if still present):
   - List deployments created by the operator:
     ```bash
     oc get deployments -n {namespace}
     ```
   - For operators like cert-manager with labeled resources:
     ```bash
     oc delete deployment -n {namespace} -l app.kubernetes.io/instance={operator-base-name}
     ```
   - Verify deployments are deleted:
     ```bash
     oc get deployments -n {namespace}
     ```

8.5. **Check for Orphaned Custom Resources** (before removing CRDs):
   - Get list of CRDs managed by the operator from CSV:
     ```bash
     oc get csv -n {namespace} -o jsonpath='{.items[0].spec.customresourcedefinitions.owned[*].name}'
     ```
   - For each CRD, search for CR instances across all namespaces:
     ```bash
     oc get <crd-kind> --all-namespaces --ignore-not-found
     ```
   - If CRs exist, list them with details:
     ```
     WARNING: Found custom resources that may prevent clean uninstallation:
       - namespace-1/<cr-name-1> (kind: <CRD-kind>)
       - namespace-2/<cr-name-2> (kind: <CRD-kind>)
     
     These resources should be deleted before uninstalling the operator.
     Do you want to delete these custom resources? (yes/no)
     ```
   - If user confirms, delete each CR:
     ```bash
     oc delete <crd-kind> <cr-name> -n <namespace>
     ```
   - This prevents namespace from getting stuck in Terminating state
   - Reference: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-reinstalling-operators-after-failed-uninstallation_olm-troubleshooting-operator-issues

9. **Remove Custom Resource Definitions** (if `--remove-crds` flag is set):
   - **WARNING**: Display critical warning to user:
     ```
     WARNING: Removing CRDs will delete ALL custom resources of these types across the entire cluster!
     This action is irreversible and will affect all namespaces.
     
     Are you absolutely sure you want to remove CRDs? (yes/no)
     ```
   - If user confirms, proceed with CRD removal
   - Get list of CRDs owned by the operator:
     ```bash
     oc get csv {csv-name} -n {namespace} -o jsonpath='{.spec.customresourcedefinitions.owned[*].name}'
     ```
   - For each CRD, check if custom resources exist:
     ```bash
     oc get {crd-name} --all-namespaces --ignore-not-found
     ```
   - Display warning if custom resources exist
   - Delete CRDs:
     ```bash
     oc delete crd {crd-name}
     ```

10. **Remove Namespace** (if `--remove-namespace` flag is set):
    - **WARNING**: Display warning:
      ```
      WARNING: Removing namespace {namespace} will delete all resources in this namespace!
      
      Are you sure you want to remove namespace {namespace}? (yes/no)
      ```
    - If user confirms:
      ```bash
      oc delete namespace {namespace}
      ```
    - Monitor namespace deletion with timeout:
      ```bash
      oc wait --for=delete namespace/{namespace} --timeout=120s
      ```
    - If namespace gets stuck in "Terminating" state after 120 seconds:
      - Check for resources preventing deletion:
        ```bash
        oc api-resources --verbs=list --namespaced -o name | \
          xargs -n 1 oc get --show-kind --ignore-not-found -n {namespace}
        ```
      - Check for finalizers on the namespace:
        ```bash
        oc get namespace {namespace} -o jsonpath='{.metadata.finalizers}'
        ```
      - Display helpful error message:
        ```
        ERROR: Namespace {namespace} is stuck in Terminating state.
        
        Possible causes:
        - Resources with finalizers preventing deletion
        - API services that are unavailable
        - Custom resources that cannot be deleted
        
        To diagnose and fix, run: /olm:diagnose {operator-name} {namespace}
        
        Manual troubleshooting:
        1. Check remaining resources:
           oc api-resources --verbs=list --namespaced -o name | \
             xargs -n 1 oc get --show-kind --ignore-not-found -n {namespace}
        
        2. Check namespace finalizers:
           oc get namespace {namespace} -o yaml | grep -A5 finalizers
        
        WARNING: Do NOT force-delete the namespace as it can lead to unstable cluster behavior.
        See: https://access.redhat.com/solutions/4165791
        ```
      - Exit with error code
    - Note: OperatorGroup will be automatically deleted with the namespace

11. **Post-Uninstall Verification**:
    - Verify all resources are cleaned up:
      ```bash
      oc get subscription,csv,installplan -n {namespace} --ignore-not-found
      ```
    - Check if any CRDs remain (if they were supposed to be deleted):
      ```bash
      oc get crd | grep <operator-related-pattern>
      ```
    - If uninstalling without `--remove-namespace`, check namespace is clean:
      ```bash
      oc get all -n {namespace}
      ```
    - Display any remaining resources with suggestions for cleanup

12. **Display Uninstallation Summary**:
    - Show what was successfully removed:
      ```
      ✓ Uninstallation Summary:
        ✓ Subscription '{operator-name}' deleted
        ✓ CSV '{csv-name}' deleted
        ✓ Operator deployments removed
        [✓ X custom resources deleted]
        [✓ Y CRDs removed]
        [✓ Namespace '{namespace}' deleted]
      ```
    - If CRDs or namespace were NOT removed, provide instructions:
      ```
      Note: The following resources were NOT removed:
      - Custom Resource Definitions (use --remove-crds to remove)
      - Namespace {namespace} (use --remove-namespace to remove)
      
      To completely remove all operator resources, run:
      /olm:uninstall {operator-name} {namespace} --remove-crds --remove-namespace
      ```
    - **Important warning about reinstallation**:
      ```
      IMPORTANT: Before reinstalling this operator, verify all resources are cleaned:
      
      oc get subscription,csv,installplan -n {namespace}
      oc get crd | grep <operator-pattern>
      
      Failure to completely uninstall may cause reinstallation issues.
      See: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-reinstalling-operators-after-failed-uninstallation_olm-troubleshooting-operator-issues
      ```

## Return Value
- **Success**: Operator uninstalled successfully with summary of removed resources
- **Partial Success**: Some resources removed with warnings about remaining resources
- **Error**: Uninstallation failed with specific error message
- **Format**: Structured output showing:
  - Subscription deletion status
  - CSV deletion status
  - Deployment removal status
  - CRD removal status (if applicable)
  - Namespace deletion status (if applicable)

## Examples

1. **Uninstall cert-manager-operator (basic)**:
   ```
   /olm:uninstall openshift-cert-manager-operator
   ```

2. **Uninstall with custom namespace**:
   ```
   /olm:uninstall openshift-cert-manager-operator my-cert-manager
   ```

3. **Complete cleanup including namespace**:
   ```
   /olm:uninstall openshift-cert-manager-operator cert-manager-operator --remove-crds --remove-namespace
   ```
   This performs a complete cleanup of all operator-related resources.

4. **Force uninstall without prompts**:
   ```
   /olm:uninstall openshift-cert-manager-operator cert-manager-operator --force
   ```
   Skips all confirmation prompts (use with caution!).

## Arguments
- **$1** (operator-name): The name of the operator to uninstall (required)
  - Example: "openshift-cert-manager-operator"
  - Must match the Subscription name
- **$2** (namespace): The namespace where operator is installed (optional)
  - Default: `{operator-name}` (operator name without "openshift-" prefix)
  - Example: "cert-manager-operator"
- **$3+** (flags): Optional flags (can combine multiple):
  - `--remove-crds`: Remove Custom Resource Definitions (WARNING: affects entire cluster)
  - `--remove-namespace`: Remove the operator's namespace and all its resources
  - `--force`: Skip all confirmation prompts (use with caution)

## Safety Features

1. **Multiple Confirmations**: Separate confirmations for CRD and namespace removal
2. **Detailed Warnings**: Clear warnings about the scope of deletions
3. **Verification Steps**: Checks that resources exist before attempting deletion
4. **Summary Report**: Detailed summary of what was and wasn't removed
5. **Graceful Failures**: Continues with remaining steps if individual deletions fail

## Troubleshooting

- **Subscription not found**: Verify the operator name and namespace:
  ```bash
  oc get subscriptions --all-namespaces | grep {operator-name}
  ```
- **CSV won't delete**: Check for finalizers:
  ```bash
  oc get csv {csv-name} -n {namespace} -o yaml | grep finalizers
  ```
  If finalizers are present, they may be waiting for resources to be cleaned up. Check operator logs and events.

- **Namespace stuck in Terminating**: This is a common issue after operator uninstallation.
  ```bash
  # Find remaining resources
  oc api-resources --verbs=list --namespaced -o name | \
    xargs -n 1 oc get --show-kind --ignore-not-found -n {namespace}
  
  # Check namespace finalizers
  oc get namespace {namespace} -o yaml | grep -A5 finalizers
  ```
  **IMPORTANT**: Do not force-delete the namespace. This can cause cluster instability.
  Instead, use `/olm:diagnose {operator-name} {namespace}` to diagnose and fix the issue.

- **CRDs won't delete**: Check for remaining custom resources:
  ```bash
  oc get {crd-name} --all-namespaces
  ```
  CRDs cannot be deleted while CR instances exist. Delete all CRs first.

- **Custom resources won't delete**: Some CRs may have finalizers preventing deletion:
  ```bash
  oc get <crd-kind> <cr-name> -n <namespace> -o yaml | grep finalizers
  ```
  The operator controller (if still running) should remove finalizers. If operator is already deleted, you may need to manually patch the CR to remove finalizers (use with extreme caution).

- **Permission denied**: Ensure you have cluster-admin privileges for CRD deletion:
  ```bash
  oc auth can-i delete crd
  ```

- **Reinstallation fails after uninstall**: This usually means cleanup was incomplete.
  Run these checks before reinstalling:
  ```bash
  # Check for remaining subscriptions/CSVs
  oc get subscription,csv -n {namespace}
  
  # Check for remaining CRDs
  oc get crd | grep <operator-pattern>
  
  # Check if namespace is clean or stuck
  oc get namespace {namespace}
  ```
  See: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-reinstalling-operators-after-failed-uninstallation_olm-troubleshooting-operator-issues

## Related Commands

- `/olm:install` - Install a day-2 operator
- `/olm:list` - List installed operators
- `/olm:status` - Check operator status before uninstalling
- `/olm:diagnose` - Diagnose and fix uninstallation issues
- `/olm:upgrade` - Upgrade an operator

## Additional Resources

- [Red Hat OpenShift: Deleting Operators from a cluster](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-deleting-operators-from-a-cluster)
- [Red Hat OpenShift: Reinstalling Operators after failed uninstallation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-reinstalling-operators-after-failed-uninstallation_olm-troubleshooting-operator-issues)
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)

