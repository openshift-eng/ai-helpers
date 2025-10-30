---
description: List installed operators in the cluster
argument-hint: [namespace] [--all-namespaces]
---

## Name
olm:list

## Synopsis
```
/olm:list [namespace] [--all-namespaces]
```

## Description
The `olm:list` command lists all installed operators in an OpenShift cluster, showing their status, version, and namespace. This command provides a quick overview of the operator landscape in your cluster.

This command helps you:
- Discover what operators are currently installed
- Check operator versions and status at a glance
- Identify operators that may need attention (failed, upgrading, etc.)
- Get a comprehensive view across namespaces

The command presents information in an easy-to-read table format with key details about each operator's ClusterServiceVersion (CSV) and Subscription.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Namespace (optional) - Target namespace to list operators from
   - `$2`: Flag (optional):
     - `--all-namespaces` or `-A`: List operators across all namespaces (default behavior if no namespace specified)

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - If not installed or not authenticated, provide clear instructions

3. **Determine Scope**:
   - If namespace is specified: List operators only in that namespace
   - If `--all-namespaces` flag or no arguments: List operators cluster-wide
   - Default behavior: Show all operators across all namespaces

4. **Fetch Operator Data**:
   - Get all ClusterServiceVersions (CSVs):
     ```bash
     # For specific namespace
     oc get csv -n {namespace} -o json
     
     # For all namespaces
     oc get csv --all-namespaces -o json
     ```
   - Get all Subscriptions:
     ```bash
     # For specific namespace
     oc get subscription -n {namespace} -o json
     
     # For all namespaces
     oc get subscription --all-namespaces -o json
     ```

5. **Parse and Correlate Data**:
   - For each CSV, extract:
     - Name: `.metadata.name`
     - Namespace: `.metadata.namespace`
     - Display Name: `.spec.displayName`
     - Version: `.spec.version`
     - Phase/Status: `.status.phase` (e.g., "Succeeded", "Installing", "Failed")
     - Install Time: `.metadata.creationTimestamp`
   - For each Subscription, extract:
     - Operator Name: `.spec.name`
     - Channel: `.spec.channel`
     - Source: `.spec.source`
     - Installed CSV: `.status.installedCSV`
     - Current CSV: `.status.currentCSV`
   - Correlate Subscriptions with CSVs to show complete operator information

6. **Format Output as Table**:
   Create a formatted table with columns:
   ```
   NAMESPACE                    OPERATOR NAME                           VERSION    STATUS      CHANNEL       SOURCE
   cert-manager-operator        cert-manager-operator                   v1.13.1    Succeeded   stable-v1     redhat-operators
   external-secrets-operator    external-secrets-operator               v0.10.5    Succeeded   stable-v0.10  redhat-operators
   openshift-pipelines          openshift-pipelines-operator-rh         v1.14.4    Succeeded   latest        redhat-operators
   ```

7. **Add Summary Statistics**:
   - Total operators installed: X
   - By status:
     - Succeeded: X
     - Installing: X
     - Upgrading: X
     - Failed: X
   - By catalog source:
     - redhat-operators: X
     - certified-operators: X
     - community-operators: X
     - custom catalogs: X

8. **Highlight Issues** (if any):
   - List operators with status other than "Succeeded":
     ```
     ⚠️ Operators requiring attention:
     - namespace/operator-name: Failed (reason: ...)
     - namespace/operator-name: Installing (waiting for...)
     ```

9. **Provide Actionable Suggestions**:
   - If operators are in "Failed" state, suggest: `/olm:status {operator-name} {namespace}` for details
   - If no operators found, suggest: `/olm:search {operator-name}` to find available operators
   - If upgrades available, suggest: `/olm:status {operator-name}` to check upgrade options

## Return Value
- **Success**: Formatted table of installed operators with summary statistics
- **Empty**: No operators found message with suggestion to install operators
- **Error**: Connection or permission error with troubleshooting guidance
- **Format**: 
  - Table with columns: NAMESPACE, OPERATOR NAME, VERSION, STATUS, CHANNEL, SOURCE
  - Summary statistics
  - Warnings for operators requiring attention

## Examples

1. **List all operators cluster-wide**:
   ```
   /olm:list
   ```

2. **List operators in a specific namespace**:
   ```
   /olm:list cert-manager-operator
   ``

## Arguments
- **$1** (namespace): Target namespace to list operators from (optional)
  - If not provided, lists operators from all namespaces
  - Example: "cert-manager-operator"
- **$2** (flag): Optional flag (optional)
  - `--all-namespaces` or `-A`: Explicitly list all operators cluster-wide
  - Default behavior if no namespace is provided

## Notes

- **Performance**: For large clusters with many operators, the command may take a few seconds to collect all data
- **Status Values**: Common CSV status values include:
  - `Succeeded`: Operator is healthy and running
  - `Installing`: Operator is being installed
  - `Upgrading`: Operator is being upgraded
  - `Failed`: Operator installation or operation failed
  - `Replacing`: Old version being replaced
  - `Deleting`: Operator is being removed
- **Correlation**: The command correlates Subscriptions with CSVs to provide complete operator information
- **Sorting**: Results are sorted by namespace, then by operator name

## Troubleshooting

- **Permission denied**: Ensure you have permissions to list CSVs and Subscriptions:
  ```bash
  oc auth can-i list csv --all-namespaces
  oc auth can-i list subscription --all-namespaces
  ```
- **Slow response**: For large clusters, use namespace-specific queries to speed up results
- **Missing operators**: Some operators may not have Subscriptions if installed manually; these will still appear based on CSV presence
- **Version mismatch**: If Subscription's `installedCSV` differs from `currentCSV`, an upgrade may be in progress

## Related Commands

- `/olm:status <operator-name> [namespace]` - Get detailed status of a specific operator
- `/olm:install <operator-name>` - Install a new operator
- `/olm:search <query>` - Search for available operators in catalogs

## Additional Resources
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)

