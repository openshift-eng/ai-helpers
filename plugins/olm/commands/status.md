---
description: Get detailed status and health information for an operator
argument-hint: <operator-name> [namespace]
---

## Name
olm:status

## Synopsis
```
/olm:status <operator-name> [namespace]
```

## Description
The `olm:status` command provides comprehensive health and status information for a specific operator in an OpenShift cluster. It displays detailed information about the operator's CSV, Subscription, InstallPlan, deployments, and pods to help diagnose issues and verify proper operation.

This command helps you:
- Check if an operator is running correctly
- Diagnose installation or upgrade problems
- View operator version and available updates
- Inspect operator deployments and pods
- Review recent events and conditions
- Identify resource issues or configuration problems

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Operator name (required) - Name of the operator to inspect
   - `$2`: Namespace (optional) - Namespace where operator is installed
     - If not provided, searches for the operator across all namespaces
     - If multiple instances found, prompts user to specify namespace

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - If not installed or not authenticated, provide clear instructions

3. **Locate Operator**:
   - If namespace provided, verify operator exists in that namespace:
     ```bash
     oc get subscription {operator-name} -n {namespace} --ignore-not-found
     ```
   - If no namespace provided, search across all namespaces:
     ```bash
     oc get subscription --all-namespaces -o json | jq -r '.items[] | select(.spec.name=="{operator-name}") | .metadata.namespace'
     ```
   - If not found, display error with suggestions
   - If multiple instances found, list them and ask user to specify namespace

4. **Gather Subscription Information**:
   - Get Subscription details:
     ```bash
     oc get subscription {operator-name} -n {namespace} -o json
     ```
   - Extract:
     - Channel: `.spec.channel`
     - Install Plan Approval: `.spec.installPlanApproval`
     - Source: `.spec.source`
     - Source Namespace: `.spec.sourceNamespace`
     - Installed CSV: `.status.installedCSV`
     - Current CSV: `.status.currentCSV`
     - State: `.status.state`
     - Conditions: `.status.conditions[]`

5. **Gather CSV Information**:
   - Get CSV details:
     ```bash
     oc get csv {csv-name} -n {namespace} -o json
     ```
   - Extract:
     - Display Name: `.spec.displayName`
     - Version: `.spec.version`
     - Phase: `.status.phase`
     - Message: `.status.message`
     - Reason: `.status.reason`
     - Creation Time: `.metadata.creationTimestamp`
     - Conditions: `.status.conditions[]`
     - Requirements: `.status.requirementStatus[]`

6. **Gather InstallPlan Information**:
   - Get related InstallPlans:
     ```bash
     oc get installplan -n {namespace} -o json
     ```
   - Find InstallPlans related to this operator by checking `.spec.clusterServiceVersionNames`
   - Extract:
     - Name: `.metadata.name`
     - Phase: `.status.phase` (e.g., "Complete", "Installing", "Failed")
     - Approved: `.spec.approved`
     - Bundle Resources: `.status.bundleLookups[]`

7. **Gather Deployment Information**:
   - Get deployments owned by the CSV:
     ```bash
     oc get deployments -n {namespace} -o json
     ```
   - Filter deployments with owner reference to the CSV
   - For each deployment, extract:
     - Name: `.metadata.name`
     - Ready Replicas: `.status.readyReplicas` / `.status.replicas`
     - Available: `.status.availableReplicas`
     - Conditions: `.status.conditions[]`

8. **Gather Pod Information**:
   - Get pods managed by operator deployments:
     ```bash
     oc get pods -n {namespace} -l app={operator-label} -o json
     ```
   - For each pod, extract:
     - Name: `.metadata.name`
     - Status: `.status.phase`
     - Ready: Count of ready containers vs total
     - Restarts: Sum of `.status.containerStatuses[].restartCount`
     - Age: Calculate from `.metadata.creationTimestamp`

9. **Check for Recent Events**:
   - Get events related to the operator:
     ```bash
     oc get events -n {namespace} --field-selector involvedObject.name={csv-name} --sort-by='.lastTimestamp'
     ```
   - Show last 5-10 events, especially warnings and errors

10. **Check for Available Updates**:
    - Get PackageManifest to check for newer versions:
      ```bash
      oc get packagemanifest {operator-name} -n openshift-marketplace -o json
      ```
    - Extract current channel information:
      - Current channel from Subscription: `.spec.channel`
      - Latest version in current channel
      - Available channels
    - Compare installed CSV version with latest available version
    - Check for pending InstallPlans:
      ```bash
      oc get installplan -n {namespace} -o json | jq '.items[] | select(.spec.approved==false)'
      ```
    - Determine if manual approval is required:
      ```bash
      oc get subscription {operator-name} -n {namespace} -o jsonpath='{.spec.installPlanApproval}'
      ```
    - Reference: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-approving-operator-upgrades_olm-updating-operators

11. **Format Comprehensive Report**:
    Create a structured report with sections:
    
    **A. Overview**
    ```
    Operator: {display-name}
    Name: {operator-name}
    Namespace: {namespace}
    Version: {version}
    Status: {phase}
    ```
    
    **B. Subscription**
    ```
    Channel: {channel}
    Source: {source}
    Install Plan Approval: {approval-mode} (Automatic|Manual)
    State: {state}
    Installed CSV: {installed-csv-name}
    Current CSV: {current-csv-name}
    ```
    
    **C. ClusterServiceVersion (CSV)**
    ```
    Name: {csv-name}
    Phase: {phase}
    Message: {message}
    Requirements: [list requirements status]
    ```
    
    **D. InstallPlan**
    ```
    Name: {installplan-name}
    Phase: {phase} (Complete|Installing|RequiresApproval|Failed)
    Approved: {true/false}
    
    [If Phase=RequiresApproval and Approved=false:]
    ⚠️  Manual approval required for installation/upgrade
    To approve: /olm:approve {operator-name} {namespace}
    Or manually: oc patch installplan {installplan-name} -n {namespace} \
                   --type merge --patch '{"spec":{"approved":true}}'
    ```
    
    **E. Deployments**
    ```
    NAME                     READY   AVAILABLE   AGE
    cert-manager             1/1     1           5d
    cert-manager-webhook     1/1     1           5d
    ```
    
    **F. Pods**
    ```
    NAME                                      STATUS    READY   RESTARTS   AGE
    cert-manager-7d4f8f8b4-abcde             Running   1/1     0          5d
    cert-manager-webhook-6b7c9d5f-fghij      Running   1/1     0          5d
    ```
    
    **G. Recent Events** (if any warnings/errors)
    ```
    5m    Warning   InstallPlanFailed   Failed to install...
    2m    Normal    InstallSucceeded    Successfully installed
    ```
    
    **H. Update Information**
    ```
    Current Version: {current-version}
    Latest Available: {latest-version} (in channel: {channel})
    Update Status: [Up to date | Update available | Unknown]
    
    Available Channels:
    - stable-v1 (latest: v1.13.1)
    - tech-preview-v1.14 (latest: v1.14.0)
    
    [If update available in current channel:]
    📦 Update available: {current-version} → {latest-version}
    To update: /olm:upgrade {operator-name} {namespace}
    
    [If newer version in different channel:]
    💡 Newer version available in channel '{new-channel}': {newer-version}
    To switch channels: /olm:upgrade {operator-name} {namespace} --channel={new-channel}
    ```
    
    **I. Health Summary**
    ```
    ✅ Operator is healthy and running
    ⚠️ Operator has warnings (see events)
    ❌ Operator is not healthy (see details)
    🔄 Operator is upgrading (Current: {old-version} → Target: {new-version})
    ⏸️  Operator upgrade pending manual approval
    ```

12. **Provide Actionable Recommendations**:
    - If operator is failed: 
      ```
      ❌ Operator failed: {reason}
      
      Troubleshooting steps:
      1. Check operator logs: oc logs -n {namespace} deployment/{operator-deployment}
      2. Check events: oc get events -n {namespace} --sort-by='.lastTimestamp'
      3. Check CSV conditions: oc describe csv {csv-name} -n {namespace}
      4. Run diagnostics: /olm:diagnose {operator-name} {namespace}
      ```
    - If upgrade available:
      ```
      📦 Update available: {current} → {latest}
      To upgrade: /olm:upgrade {operator-name} {namespace}
      ```
    - If pods are crashing:
      ```
      ⚠️ Pods are crashing (restarts: {count})
      Check logs: oc logs -n {namespace} {pod-name}
      Previous logs: oc logs -n {namespace} {pod-name} --previous
      ```
    - If InstallPlan requires approval:
      ```
      ⏸️  InstallPlan requires manual approval
      
      InstallPlan: {installplan-name}
      Version: {target-version}
      
      To approve: /olm:approve {operator-name} {namespace}
      Or manually: oc patch installplan {installplan-name} -n {namespace} \
                     --type merge --patch '{"spec":{"approved":true}}'
      
      To switch to automatic approvals:
      oc patch subscription {operator-name} -n {namespace} \
        --type merge --patch '{"spec":{"installPlanApproval":"Automatic"}}'
      ```
    - If operator is upgrading:
      ```
      🔄 Operator upgrade in progress: {old-version} → {new-version}
      Monitor progress: watch oc get csv,installplan -n {namespace}
      ```

## Return Value
- **Success**: Comprehensive status report with all operator details
- **Not Found**: Error message with suggestions to list operators or check spelling
- **Multiple Instances**: List of namespaces where operator is installed
- **Error**: Connection or permission error with troubleshooting guidance
- **Format**: Multi-section report with:
  - Overview
  - Subscription details
  - CSV status
  - InstallPlan status
  - Deployment status
  - Pod status
  - Recent events
  - Health summary
  - Recommendations

## Examples

1. **Check status of cert-manager operator**:
   ```
   /olm:status openshift-cert-manager-operator
   ```

2. **Check status with specific namespace**:
   ```
   /olm:status external-secrets-operator external-secrets-operator
   ```

## Arguments
- **$1** (operator-name): Name of the operator to inspect (required)
  - Example: "openshift-cert-manager-operator"
  - Must match the operator's Subscription name
- **$2** (namespace): Namespace where operator is installed (optional)
  - If not provided, searches all namespaces
  - Example: "cert-manager-operator"

## Notes

- **Comprehensive View**: This command aggregates data from multiple resources (Subscription, CSV, InstallPlan, Deployments, Pods) for a complete picture
- **Permissions**: Requires read permissions for subscriptions, csvs, installplans, deployments, pods, and events in the target namespace
- **Performance**: May take a few seconds to gather all information for large operators with many resources
- **Auto-Discovery**: If namespace is not specified, the command automatically finds the operator across all namespaces
- **Health Checks**: The command evaluates multiple factors to determine overall operator health
- **Troubleshooting**: Provides context-aware recommendations based on detected issues

## Troubleshooting

- **Operator not found**: 
  - Verify operator name: `oc get subscriptions --all-namespaces | grep {operator-name}`
  - List all operators: `/olm:list`
- **Multiple instances found**:
  - Specify namespace explicitly: `/olm:status {operator-name} {namespace}`
- **Permission denied**:
  - Ensure you have read permissions in the target namespace
  - Check: `oc auth can-i get csv -n {namespace}`
- **Incomplete information**:
  - Some operators may not have all resources (e.g., manually installed CSVs without Subscriptions)

## Related Commands

- `/olm:list` - List all installed operators
- `/olm:install <operator-name>` - Install a new operator
- `/olm:uninstall <operator-name>` - Uninstall an operator
- `/olm:upgrade <operator-name>` - Upgrade an operator
- `/olm:approve <operator-name>` - Approve pending InstallPlans
- `/olm:diagnose <operator-name>` - Diagnose and fix operator issues

## Additional Resources

- [Viewing Operator Status](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-status-viewing-operator-status)
- [Updating Installed Operators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-updating-operators)
- [Troubleshooting Operator Issues](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-troubleshooting-operator-issues)

