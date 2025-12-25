---
description: Uninstall the External Secrets Operator and optionally clean up all related resources
argument-hint: "[--namespace <namespace>] [--remove-crds] [--remove-namespace] [--force]"
---

## Name
external-secrets-operator:uninstall

## Synopsis
```
/external-secrets-operator:uninstall [--namespace <namespace>] [--remove-crds] [--remove-namespace] [--force]
```

## Description
The `external-secrets-operator:uninstall` command uninstalls the External Secrets Operator for Red Hat OpenShift and optionally removes all related resources including Custom Resource Definitions (CRDs) and the operator namespace.

This command provides a comprehensive uninstallation workflow:
- Removes the operator's Subscription and ClusterServiceVersion
- Optionally removes all ExternalSecrets, SecretStores, and ClusterSecretStores
- Optionally deletes Custom Resource Definitions (CRDs)
- Optionally removes the operator's namespace
- Provides detailed feedback on each step

**WARNING**: Removing CRDs will delete all ExternalSecrets, SecretStores, and ClusterSecretStores across the entire cluster. The Kubernetes secrets that were synced will remain, but they will no longer be automatically updated.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `--namespace`: Operator namespace (default: `external-secrets-operator`)
   - `--remove-crds`: Remove Custom Resource Definitions after uninstalling
   - `--remove-namespace`: Remove the operator's namespace after cleanup
   - `--force`: Skip confirmation prompts

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check if user has cluster-admin or sufficient privileges

3. **Verify Operator Installation**:
   - Find the operator namespace:
     ```bash
     oc get subscription external-secrets-operator -A -o jsonpath='{.items[0].metadata.namespace}'
     ```
   - If not found, display error: "External Secrets Operator is not installed"
   - Get the installed CSV:
     ```bash
     oc get csv -n {namespace} -l operators.coreos.com/external-secrets-operator.{namespace}= -o jsonpath='{.items[0].metadata.name}'
     ```

4. **Inventory Resources to Remove**:
   - Count ExternalSecrets:
     ```bash
     oc get externalsecrets -A --no-headers | wc -l
     ```
   - Count ClusterExternalSecrets:
     ```bash
     oc get clusterexternalsecrets --no-headers 2>/dev/null | wc -l
     ```
   - Count SecretStores:
     ```bash
     oc get secretstores -A --no-headers | wc -l
     ```
   - Count ClusterSecretStores:
     ```bash
     oc get clustersecretstores --no-headers | wc -l
     ```
   - Count PushSecrets:
     ```bash
     oc get pushsecrets -A --no-headers 2>/dev/null | wc -l
     ```

5. **Display Uninstallation Plan**:
   ```
   ⚠️  External Secrets Operator Uninstallation Plan
   
   Operator Details:
   - Namespace: {namespace}
   - CSV: {csv-name}
   - Version: {version}
   
   Resources in Cluster:
   - ExternalSecrets: {count} (across {namespace-count} namespaces)
   - ClusterExternalSecrets: {count}
   - SecretStores: {count}
   - ClusterSecretStores: {count}
   - PushSecrets: {count}
   
   Will be removed:
   ✓ Subscription: external-secrets-operator
   ✓ ClusterServiceVersion: {csv-name}
   ✓ Operator deployments and pods
   [✓ Custom Resource Definitions (if --remove-crds)]
   [✓ Namespace {namespace} (if --remove-namespace)]
   
   ⚠️  NOTE: Synced Kubernetes secrets will NOT be deleted.
   They will remain but will no longer be automatically refreshed.
   ```

6. **Request User Confirmation** (unless `--force` flag):
   - If `--remove-crds` is set:
     ```
     ⚠️  WARNING: Removing CRDs will delete ALL ExternalSecrets, SecretStores,
     ClusterSecretStores, ClusterExternalSecrets, and PushSecrets
     across the ENTIRE cluster!
     
     This action is IRREVERSIBLE and affects ALL namespaces.
     
     The following resources will be permanently deleted:
     - {es-count} ExternalSecrets
     - {ces-count} ClusterExternalSecrets  
     - {ss-count} SecretStores
     - {css-count} ClusterSecretStores
     - {ps-count} PushSecrets
     
     Are you absolutely sure you want to continue? (yes/no)
     ```
   - Wait for user confirmation
   - If user says no, abort operation

7. **Delete Custom Resources First** (if `--remove-crds` is set):
   - Delete all ExternalSecrets:
     ```bash
     oc delete externalsecrets -A --all
     ```
   - Delete all ClusterExternalSecrets:
     ```bash
     oc delete clusterexternalsecrets --all
     ```
   - Delete all SecretStores:
     ```bash
     oc delete secretstores -A --all
     ```
   - Delete all ClusterSecretStores:
     ```bash
     oc delete clustersecretstores --all
     ```
   - Delete all PushSecrets:
     ```bash
     oc delete pushsecrets -A --all
     ```
   - Wait for resources to be deleted (with timeout):
     ```bash
     oc wait --for=delete externalsecrets -A --all --timeout=120s
     ```
   - Note: Resources may have finalizers; if they get stuck, inform user

8. **Delete Subscription**:
   - Remove the operator's subscription:
     ```bash
     oc delete subscription external-secrets-operator -n {namespace}
     ```
   - Verify deletion:
     ```bash
     oc get subscription external-secrets-operator -n {namespace} --ignore-not-found
     ```

9. **Delete ClusterServiceVersion (CSV)**:
   - Delete the CSV:
     ```bash
     oc delete csv {csv-name} -n {namespace}
     ```
   - This will automatically remove operator deployments
   - Verify CSV is deleted:
     ```bash
     oc get csv -n {namespace} --ignore-not-found
     ```

10. **Remove Custom Resource Definitions** (if `--remove-crds` flag):
    - Get list of CRDs owned by the operator:
      ```bash
      oc get crd -o name | grep external-secrets.io
      ```
    - Expected CRDs:
      - `externalsecrets.external-secrets.io`
      - `clustersecretstores.external-secrets.io`
      - `secretstores.external-secrets.io`
      - `clusterexternalsecrets.external-secrets.io`
      - `pushsecrets.external-secrets.io`
      - Additional CRDs may exist depending on version
    - Delete each CRD:
      ```bash
      oc delete crd externalsecrets.external-secrets.io
      oc delete crd clustersecretstores.external-secrets.io
      oc delete crd secretstores.external-secrets.io
      oc delete crd clusterexternalsecrets.external-secrets.io
      oc delete crd pushsecrets.external-secrets.io
      ```
    - Handle stuck CRDs (finalizers):
      ```bash
      # If CRD is stuck, check for remaining CRs
      oc get {crd-kind} -A --ignore-not-found
      
      # May need to patch to remove finalizers as last resort
      oc patch crd {crd-name} --type=merge -p '{"metadata":{"finalizers":[]}}'
      ```

11. **Remove Namespace** (if `--remove-namespace` flag):
    - Display warning:
      ```
      ⚠️  Removing namespace {namespace} will delete all resources in this namespace!
      
      Are you sure you want to remove namespace {namespace}? (yes/no)
      ```
    - Delete namespace:
      ```bash
      oc delete namespace {namespace}
      ```
    - Monitor namespace deletion:
      ```bash
      oc wait --for=delete namespace/{namespace} --timeout=120s
      ```
    - If namespace gets stuck in Terminating state:
      - Check for remaining resources:
        ```bash
        oc api-resources --verbs=list --namespaced -o name | \
          xargs -n 1 oc get --show-kind --ignore-not-found -n {namespace}
        ```
      - Provide troubleshooting guidance:
        ```
        ❌ Namespace {namespace} is stuck in Terminating state.
        
        To diagnose and fix:
        /external-secrets:diagnose --namespace {namespace}
        
        Or manually check:
        oc get namespace {namespace} -o yaml | grep -A5 finalizers
        
        WARNING: Do NOT force-delete the namespace.
        See: https://access.redhat.com/solutions/4165791
        ```

12. **Post-Uninstall Verification**:
    - Verify all resources are cleaned up:
      ```bash
      # Check for remaining operator resources
      oc get subscription,csv -n {namespace} --ignore-not-found
      
      # Check for remaining CRDs
      oc get crd | grep external-secrets.io
      
      # Check for any remaining external-secrets resources
      oc get externalsecrets,secretstores,clustersecretstores -A --ignore-not-found
      ```
    - Report any remaining resources

13. **Display Uninstallation Summary**:
    ```
    ✓ External Secrets Operator Uninstallation Complete
    
    Removed:
    ✓ Subscription: external-secrets-operator
    ✓ CSV: {csv-name}
    ✓ Operator deployments
    [✓ {es-count} ExternalSecrets]
    [✓ {css-count} ClusterSecretStores]
    [✓ {ss-count} SecretStores]
    [✓ {crd-count} Custom Resource Definitions]
    [✓ Namespace: {namespace}]
    
    ℹ️  Note: Kubernetes secrets that were synced by ExternalSecrets remain in their namespaces.
    These secrets will no longer be automatically refreshed.
    
    To list synced secrets (if labeled):
    oc get secrets -A -l 'reconcile.external-secrets.io/created-by'
    ```

    - If CRDs or namespace were NOT removed:
      ```
      ℹ️  The following resources were NOT removed:
      - Custom Resource Definitions (use --remove-crds to remove)
      - Namespace {namespace} (use --remove-namespace to remove)
      
      To completely remove all operator resources, run:
      /external-secrets-operator:uninstall --remove-crds --remove-namespace
      ```

14. **Cleanup Temporary Files**:
    - Remove any temporary files created during uninstallation

## Return Value
- **Success**: Operator uninstalled successfully with summary of removed resources
- **Partial Success**: Some resources removed with warnings about remaining resources
- **Error**: Uninstallation failed with specific error message
- **Format**: Structured output showing:
  - Subscription deletion status
  - CSV deletion status
  - Custom resources removed
  - CRD removal status (if applicable)
  - Namespace deletion status (if applicable)

## Examples

1. **Basic uninstall (keep CRDs and namespace)**:
   ```
   /external-secrets:uninstall
   ```
   Removes the operator but keeps CRDs, ExternalSecrets, and namespace.

2. **Uninstall with custom namespace**:
   ```
   /external-secrets:uninstall --namespace my-eso
   ```

3. **Complete cleanup (remove everything)**:
   ```
   /external-secrets-operator:uninstall --remove-crds --remove-namespace
   ```
   Removes the operator, all CRDs (and therefore all ExternalSecrets), and the namespace.

4. **Force uninstall without prompts**:
   ```
   /external-secrets:uninstall --remove-crds --force
   ```
   ⚠️ Use with caution! Skips all confirmation prompts.

## Arguments
- **--namespace** (optional): The namespace where operator is installed
  - Default: `external-secrets-operator`
  - Example: `--namespace my-eso`
- **--remove-crds** (optional): Remove Custom Resource Definitions
  - ⚠️ WARNING: This deletes ALL ExternalSecrets, SecretStores, etc. across the entire cluster
  - Example: `--remove-crds`
- **--remove-namespace** (optional): Remove the operator's namespace
  - Example: `--remove-namespace`
- **--force** (optional): Skip all confirmation prompts
  - ⚠️ Use with extreme caution
  - Example: `--force`

## Safety Features

1. **Multiple Confirmations**: Separate confirmations for CRD removal
2. **Detailed Warnings**: Clear warnings about the scope of deletions
3. **Resource Inventory**: Shows exactly what will be deleted before proceeding
4. **Verification Steps**: Checks that resources exist before attempting deletion
5. **Graceful Failures**: Continues with remaining steps if individual deletions fail
6. **Synced Secrets Preserved**: Kubernetes secrets created by ExternalSecrets are not deleted

## Troubleshooting

- **Subscription not found**:
  ```bash
  oc get subscriptions -A | grep external-secrets
  ```
  The operator may be installed in a different namespace.

- **CRDs won't delete**:
  ```bash
  # Check for remaining custom resources
  oc get externalsecrets,secretstores,clustersecretstores -A
  
  # Check for finalizers on CRD
  oc get crd externalsecrets.external-secrets.io -o jsonpath='{.metadata.finalizers}'
  ```
  CRDs cannot be deleted while CR instances exist. Delete all CRs first.

- **Namespace stuck in Terminating**:
  ```bash
  # Find remaining resources
  oc api-resources --verbs=list --namespaced -o name | \
    xargs -n 1 oc get --show-kind --ignore-not-found -n {namespace}
  
  # Check namespace finalizers
  oc get namespace {namespace} -o yaml | grep -A5 finalizers
  ```
  **IMPORTANT**: Do not force-delete the namespace.
        Use `/external-secrets-operator:diagnose` to identify and fix the issue.

- **ExternalSecrets won't delete**:
  ```bash
  # Check for finalizers
  oc get externalsecret {name} -n {namespace} -o jsonpath='{.metadata.finalizers}'
  ```
  The operator controller should remove finalizers. If operator is already deleted, you may need to manually patch the CR.

- **Reinstallation fails after uninstall**:
  ```bash
  # Verify cleanup is complete
  oc get subscription,csv -n external-secrets-operator
  oc get crd | grep external-secrets.io
  ```
  See: [Reinstalling Operators after failed uninstallation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-reinstalling-operators-after-failed-uninstallation_olm-troubleshooting-operator-issues)

## What Happens to Synced Secrets?

When you uninstall the External Secrets Operator:

1. **Kubernetes Secrets Remain**: All secrets that were synced from external providers remain in the cluster
2. **No Automatic Updates**: These secrets will no longer be automatically refreshed
3. **Manual Management Required**: You'll need to manually update these secrets going forward

To identify secrets that were synced by External Secrets:
```bash
# If secrets are labeled (depends on configuration):
oc get secrets -A -l 'reconcile.external-secrets.io/created-by'

# Or check secrets in namespaces that had ExternalSecrets:
oc get secrets -n {namespace}
```

## Migrating from Community to Red Hat Operator

If you're migrating from the community External Secrets Operator to the Red Hat version, see:
[Migrating from the community External Secrets Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift#eso-migration_external-secrets-operator-for-red-hat-openshift)

## Related Commands

- `/external-secrets-operator:status` - Check status before uninstalling
- `/external-secrets-operator:list` - List resources before cleanup
- `/external-secrets-operator:install` - Install the operator
- `/external-secrets-operator:diagnose` - Diagnose issues before/after uninstall
- `/external-secrets-operator:guide` - Get provider-specific configuration guides

## Additional Resources

- [Uninstalling the External Secrets Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift#eso-uninstall_external-secrets-operator-for-red-hat-openshift)
- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [Red Hat OpenShift: Deleting Operators from a cluster](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-deleting-operators-from-a-cluster)

