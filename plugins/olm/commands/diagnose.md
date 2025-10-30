---
description: Diagnose and optionally fix common OLM and operator issues
argument-hint: [operator-name] [namespace] [--fix] [--cluster]
---

## Name
olm:diagnose

## Synopsis
```
/olm:diagnose [operator-name] [namespace] [--fix] [--cluster]
```

## Description
The `olm:diagnose` command diagnoses common OLM and operator issues, including orphaned CRDs, stuck namespaces, failed installations, and catalog source problems. It can optionally attempt to fix detected issues automatically.

This command helps you:
- Detect and clean up orphaned CRDs from deleted operators
- Fix namespaces stuck in Terminating state
- Identify and resolve failed operator installations
- Detect conflicting OperatorGroups
- Check catalog source health
- Identify resources preventing clean uninstallation
- Generate comprehensive troubleshooting reports

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Operator name (optional) - Specific operator to diagnose
   - `$2`: Namespace (optional) - Specific namespace to check
   - `$3+`: Flags (optional):
     - `--fix`: Automatically attempt to fix detected issues (requires confirmation)
     - `--cluster`: Run cluster-wide diagnostics (catalog sources, global CRDs, etc.)

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check if user has cluster-admin or sufficient privileges
   - Warn if running without `--fix` flag (dry-run mode)

3. **Determine Scope**:
   - **Operator-specific**: If operator name provided, focus on that operator
   - **Namespace-specific**: If namespace provided, check all operators in that namespace
   - **Cluster-wide**: If `--cluster` flag or no arguments, check entire cluster

4. **Scan for Orphaned CRDs**:
   - Get all CRDs in the cluster:
     ```bash
     oc get crd -o json
     ```
   - For each CRD, check if there's a corresponding operator:
     - Look for CSVs that own this CRD
     - Look for active Subscriptions related to this CRD
   - Identify orphaned CRDs (no owning operator found):
     ```bash
     # Find CRDs without active operators
     # This is a simplified check - actual implementation should verify operator ownership
     oc get crd -o json | jq -r '.items[] | 
       select(.metadata.annotations["operators.coreos.com/owner"] // "" | length == 0) | 
       .metadata.name'
     ```
   - Check if CRs exist for orphaned CRDs:
     ```bash
     oc get <crd-kind> --all-namespaces --ignore-not-found
     ```
   - Report findings:
     ```
     ⚠️  Orphaned CRDs Detected
     
     The following CRDs have no active operator:
     - certificates.cert-manager.io (3 CR instances in 2 namespaces)
     - issuers.cert-manager.io (5 CR instances in 3 namespaces)
     
     These CRDs may be leftovers from uninstalled operators.
     
     [If --fix flag:]
     Do you want to delete these CRDs and their CRs? (yes/no)
     WARNING: This will delete all custom resources of these types!
     ```

5. **Check for Stuck Namespaces**:
   - Get all namespaces in Terminating state:
     ```bash
     oc get namespaces -o json | jq -r '.items[] | select(.status.phase=="Terminating") | .metadata.name'
     ```
   - For each stuck namespace:
     - Check remaining resources:
       ```bash
       oc api-resources --verbs=list --namespaced -o name | \
         xargs -n 1 oc get --show-kind --ignore-not-found -n {namespace}
       ```
     - Check namespace finalizers:
       ```bash
       oc get namespace {namespace} -o jsonpath='{.metadata.finalizers}'
       ```
     - Identify blocking resources
   - Report findings:
     ```
     ❌ Stuck Namespace Detected
     
     Namespace: {namespace}
     State: Terminating (stuck for {duration})
     
     Blocking resources:
     - CustomResourceDefinition: {crd-name} (finalizer: {finalizer})
     - ServiceAccount: {sa-name} (token secret)
     
     Finalizers on namespace:
     - kubernetes
     
     [If --fix flag:]
     Attempted fixes:
     1. Delete remaining resources
     2. Remove finalizers from CRs
     3. Patch namespace to remove finalizers (CAUTION)
     
     WARNING: Force-deleting namespace can cause cluster instability.
     ```

6. **Scan for Failed Operator Installations**:
   - Get all CSVs not in "Succeeded" phase:
     ```bash
     oc get csv --all-namespaces -o json | \
       jq -r '.items[] | select(.status.phase != "Succeeded") | "\(.metadata.namespace)/\(.metadata.name): \(.status.phase)"'
     ```
   - For each failed CSV:
     - Get failure reason: `.status.reason`
     - Get failure message: `.status.message`
     - Check related InstallPlan status
     - Check deployment status
     - Check recent events
   - Report findings:
     ```
     ❌ Failed Operator Installation
     
     Operator: {operator-name}
     Namespace: {namespace}
     CSV: {csv-name}
     Phase: Failed
     Reason: {reason}
     Message: {message}
     
     Related InstallPlan: {installplan-name} (Phase: {phase})
     
     Recent Events:
     - {timestamp} Warning: {event-message}
     
     Troubleshooting suggestions:
     - Check operator logs: oc logs -n {namespace} deployment/{deployment}
     - Check image pull issues: oc describe pod -n {namespace}
     - Verify catalog source health
     - Check RBAC permissions
     ```

7. **Check for Conflicting OperatorGroups**:
   - Get all OperatorGroups per namespace:
     ```bash
     oc get operatorgroup --all-namespaces -o json
     ```
   - Identify namespaces with multiple OperatorGroups (conflict):
     ```bash
     oc get operatorgroup --all-namespaces -o json | \
       jq -r '.items | group_by(.metadata.namespace) | .[] | select(length > 1) | .[0].metadata.namespace'
     ```
   - Check for OperatorGroups with overlapping target namespaces
   - Report findings:
     ```
     ⚠️  Conflicting OperatorGroups Detected
     
     Namespace: {namespace}
     OperatorGroups: {count}
     - {og-1} (targets: {target-namespaces-1})
     - {og-2} (targets: {target-namespaces-2})
     
     Multiple OperatorGroups in a namespace can cause conflicts.
     Only one OperatorGroup should exist per namespace.
     
     [If --fix flag:]
     Keep which OperatorGroup? (1/2)
     ```

8. **Verify Catalog Source Health** (if `--cluster` flag):
   - Get all CatalogSources:
     ```bash
     oc get catalogsource -n openshift-marketplace -o json
     ```
   - For each catalog:
     - Check status: `.status.connectionState.lastObservedState`
     - Check pod status
     - Check last update time
     - Verify grpc connection
   - Report findings:
     ```
     🔍 Catalog Source Health Check
     
     ✓ redhat-operators: READY (last updated: 2h ago)
     ✓ certified-operators: READY (last updated: 3h ago)
     ✓ community-operators: READY (last updated: 1h ago)
     ❌ custom-catalog: CONNECTION_FAILED (pod: CrashLoopBackOff)
     
     [If issues found:]
     Unhealthy Catalog: custom-catalog
     Pod: custom-catalog-abc123 (Status: CrashLoopBackOff)
     
     To troubleshoot:
     oc logs -n openshift-marketplace custom-catalog-abc123
     oc describe catalogsource custom-catalog -n openshift-marketplace
     ```

9. **Check for Subscription/CSV Mismatches**:
   - Get all Subscriptions:
     ```bash
     oc get subscription --all-namespaces -o json
     ```
   - For each Subscription:
     - Compare `installedCSV` with `currentCSV`
     - Check if CSV exists
     - Verify CSV phase
   - Report findings:
     ```
     ⚠️  Subscription/CSV Mismatch
     
     Operator: {operator-name}
     Namespace: {namespace}
     Installed CSV: {installed-csv}
     Current CSV: {current-csv}
     
     CSV {installed-csv} not found in namespace.
     This may indicate a failed installation or upgrade.
     
     Suggested fix:
     oc delete subscription {operator-name} -n {namespace}
     /olm:install {operator-name} {namespace}
     ```

10. **Check for Pending Manual Approvals**:
    - Find all unapproved InstallPlans:
      ```bash
      oc get installplan --all-namespaces -o json | \
        jq -r '.items[] | select(.spec.approved==false)'
      ```
    - Report findings:
      ```
      ℹ️  Pending Manual Approvals
      
      The following operators have pending InstallPlans requiring approval:
      
      - Operator: openshift-cert-manager-operator
        Namespace: cert-manager-operator
        InstallPlan: install-abc123
        Target Version: v1.14.0
        To approve: /olm:approve openshift-cert-manager-operator cert-manager-operator
      
      - Operator: external-secrets-operator
        Namespace: eso-operator
        InstallPlan: install-def456
        Target Version: v0.11.0
        To approve: /olm:approve external-secrets-operator eso-operator
      ```

11. **Generate Comprehensive Report**:
    ```
    ═══════════════════════════════════════════════════════════
    OLM HEALTH CHECK REPORT
    ═══════════════════════════════════════════════════════════
    
    Scan Scope: [Operator-specific | Namespace | Cluster-wide]
    Scan Time: {timestamp}
    
    ✓ HEALTHY CHECKS: {count}
    - Catalog sources operational
    - No conflicting OperatorGroups
    - All CSVs in Succeeded phase
    
    ⚠️  WARNINGS: {count}
    - {warning-count} orphaned CRDs detected
    - {warning-count} pending manual approvals
    
    ❌ ERRORS: {count}
    - {error-count} stuck namespaces
    - {error-count} failed operator installations
    - {error-count} unhealthy catalog sources
    
    ═══════════════════════════════════════════════════════════
    DETAILED FINDINGS
    ═══════════════════════════════════════════════════════════
    
    [Details for each finding...]
    
    ═══════════════════════════════════════════════════════════
    RECOMMENDATIONS
    ═══════════════════════════════════════════════════════════
    
    1. Clean up orphaned CRDs: /olm:diagnose --fix
    2. Fix stuck namespace: /olm:diagnose {namespace} --fix
    3. Approve pending upgrades: /olm:approve {operator-name}
    
    For more details on troubleshooting, see:
    https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-troubleshooting-operator-issues
    ```

12. **Auto-Fix Issues** (if `--fix` flag):
    - For each detected issue, ask for confirmation
    - Attempt fixes based on issue type:
      - **Orphaned CRDs**: Delete CRs first, then CRDs
      - **Stuck namespaces**: Delete remaining resources, remove finalizers
      - **Failed installations**: Restart by deleting and recreating
      - **Conflicting OperatorGroups**: Remove unwanted OperatorGroup
      - **Unhealthy catalogs**: Restart catalog pod
    - Display results of each fix attempt
    - Generate final summary

## Return Value
- **Success**: Report generated with findings
- **Issues Found**: Detailed report with warnings and errors
- **Fixed**: Issues resolved (if `--fix` flag used)
- **Format**: Structured report showing:
  - Summary of health checks
  - Detailed findings for each issue
  - Recommendations and next steps
  - Links to documentation

## Examples

1. **Check specific operator**:
   ```
   /olm:diagnose openshift-cert-manager-operator
   ```

2. **Cluster-wide health check**:
   ```
   /olm:diagnose --cluster
   ```

3. **Diagnose and fix issues**:
   ```
   /olm:diagnose openshift-cert-manager-operator cert-manager-operator --fix
   ```

4. **Full cluster scan with auto-fix**:
   ```
   /olm:diagnose --cluster --fix
   ```

## Arguments
- **$1** (operator-name): Name of specific operator to diagnose (optional)
  - If not provided, checks all operators (or cluster-wide with `--cluster`)
  - Example: "openshift-cert-manager-operator"
- **$2** (namespace): Specific namespace to check (optional)
  - If not provided with operator-name, searches all namespaces
  - Example: "cert-manager-operator"
- **$3+** (flags): Optional flags
  - `--fix`: Attempt to automatically fix detected issues
    - Prompts for confirmation before each fix
    - Use with caution in production environments
  - `--cluster`: Run cluster-wide diagnostics
    - Checks catalog sources
    - Scans for orphaned CRDs across all namespaces
    - Identifies global issues

## Troubleshooting

- **Permission denied**:
  ```bash
  # Check required permissions
  oc auth can-i get crd
  oc auth can-i get csv --all-namespaces
  oc auth can-i patch namespace
  ```

- **Unable to fix stuck namespace**:
  - Some resources may require manual intervention
  - Check API service availability:
    ```bash
    oc get apiservice
    ```

- **CRDs won't delete**:
  ```bash
  # Check for remaining CRs
  oc get <crd-kind> --all-namespaces
  
  # Check for finalizers
  oc get crd <crd-name> -o jsonpath='{.metadata.finalizers}'
  ```

- **Catalog source issues persist**:
  ```bash
  # Restart catalog pod
  oc delete pod -n openshift-marketplace <catalog-pod>
  
  # Check catalog source definition
  oc get catalogsource <catalog-name> -n openshift-marketplace -o yaml
  ```

## Related Commands

- `/olm:status <operator-name>` - Check specific operator status
- `/olm:list` - List all operators
- `/olm:uninstall <operator-name>` - Clean uninstall with orphan cleanup
- `/olm:approve <operator-name>` - Approve pending InstallPlans

## Additional Resources

- [Troubleshooting Operator Issues](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-troubleshooting-operator-issues)
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)


