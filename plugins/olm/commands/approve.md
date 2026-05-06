---
description: Approve pending InstallPlans for operator installations and upgrades
argument-hint: <operator-name> [namespace] [--all]
---

## Name
olm:approve

## Synopsis
```
/olm:approve <operator-name> [namespace] [--all]
```

## Description
The `olm:approve` command approves pending InstallPlans for operators with manual approval mode. This is required for operators that have `installPlanApproval: Manual` in their Subscription to proceed with installation or upgrades.

This command helps you:
- Approve operator installations that are waiting for manual approval
- Approve operator upgrades
- Review what will be installed/upgraded before approval
- Batch approve multiple pending InstallPlans

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Operator name (required) - Name of the operator
   - `$2`: Namespace (optional) - Namespace where operator is installed
     - If not provided, searches for the operator across all namespaces
   - `$3`: Flag (optional):
     - `--all`: Approve all pending InstallPlans in the namespace

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check if user has sufficient privileges

3. **Locate Operator**:
   - If namespace provided, verify operator exists:
     ```bash
     oc get subscription {operator-name} -n {namespace} --ignore-not-found
     ```
   - If no namespace provided, search across all namespaces:
     ```bash
     oc get subscription --all-namespaces -o json | jq -r '.items[] | select(.spec.name=="{operator-name}") | .metadata.namespace'
     ```
   - If not found, display error with suggestions

4. **Check Subscription Approval Mode**:
   - Get Subscription approval mode:
     ```bash
     oc get subscription {operator-name} -n {namespace} -o jsonpath='{.spec.installPlanApproval}'
     ```
   - If mode is "Automatic", display informational message:
     ```
     ℹ️  Operator '{operator-name}' has automatic approval enabled.
     InstallPlans are approved automatically and don't require manual intervention.
     
     Current Subscription approval mode: Automatic
     
     To switch to manual approval mode:
     oc patch subscription {operator-name} -n {namespace} \
       --type merge --patch '{"spec":{"installPlanApproval":"Manual"}}'
     ```
   - Exit if automatic (no approval needed)

5. **Find Pending InstallPlans**:
   - Get all InstallPlans for the operator:
     ```bash
     oc get installplan -n {namespace} -o json
     ```
   - Filter for unapproved plans related to this operator:
     ```bash
     oc get installplan -n {namespace} -o json | \
       jq '.items[] | select(.spec.approved==false and .spec.clusterServiceVersionNames[] | contains("{operator-name}"))'
     ```
   - If no pending InstallPlans found:
     ```
     ✓ No pending InstallPlans found for operator '{operator-name}'
     
     The operator is up to date or already approved.
     
     To check operator status: /olm:status {operator-name} {namespace}
     ```
     - Exit with success

6. **Display InstallPlan Details**:
   For each pending InstallPlan, display:
   ```
   ⏸️  Pending InstallPlan Found
   
   InstallPlan: {installplan-name}
   Namespace: {namespace}
   Phase: {phase}
   Approved: false
   
   ClusterServiceVersions to be installed/upgraded:
     - {csv-name-1} ({version-1})
     - {csv-name-2} ({version-2})
   
   Resources to be created/updated:
     - CustomResourceDefinitions: {crd-count}
     - ServiceAccounts: {sa-count}
     - ClusterRoles: {role-count}
     - Deployments: {deployment-count}
   
   [If upgrade:]
   Current Version: {current-version}
   Target Version: {target-version}
   ```

7. **Request User Confirmation** (unless `--all` or `--force` flag):
   - Display confirmation prompt:
     ```
     Do you want to approve this InstallPlan? (yes/no)
     ```
   - If user says no, skip this InstallPlan
   - If user says yes, proceed to approval

8. **Approve InstallPlan**:
   - Patch the InstallPlan to approve it:
     ```bash
     oc patch installplan {installplan-name} -n {namespace} \
       --type merge --patch '{"spec":{"approved":true}}'
     ```
   - Verify approval:
     ```bash
     oc get installplan {installplan-name} -n {namespace} -o jsonpath='{.spec.approved}'
     ```
   - Display confirmation:
     ```
     ✓ InstallPlan approved: {installplan-name}
     ```
   - Reference: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-approving-operator-upgrades_olm-updating-operators

9. **Monitor InstallPlan Execution** (optional):
   - Watch InstallPlan phase change to "Complete":
     ```bash
     oc get installplan {installplan-name} -n {namespace} -w --timeout=120s
     ```
   - Display progress:
     ```
     🔄 InstallPlan executing...
     ⏳ Installing resources...
     ```

10. **Verify Installation/Upgrade**:
    - Wait for CSV to reach "Succeeded" phase:
      ```bash
      oc get csv -n {namespace} -o json | \
        jq -r '.items[] | select(.status.phase=="Succeeded") | .metadata.name'
      ```
    - Display result:
      ```
      ✓ Operator installation/upgrade complete
      
      CSV: {csv-name}
      Version: {version}
      Phase: Succeeded
      
      To check operator status: /olm:status {operator-name} {namespace}
      ```

11. **Handle Multiple InstallPlans** (if `--all` flag):
    - Process all pending InstallPlans for the operator
    - Display summary:
      ```
      ✓ Approved {count} InstallPlan(s)
      
      Approved:
        - {installplan-1}
        - {installplan-2}
      
      Monitoring installation progress...
      ```

12. **Display Approval Summary**:
    ```
    ✓ Approval Complete!
    
    Operator: {operator-name}
    Namespace: {namespace}
    Approved InstallPlans: {count}
    
    InstallPlan Status:
      - {installplan-1}: Complete
      - {installplan-2}: Installing...
    
    Monitor progress: watch oc get csv,installplan -n {namespace}
    ```

## Return Value
- **Success**: InstallPlan(s) approved successfully
- **No Pending Plans**: No InstallPlans require approval
- **Automatic Mode**: Operator has automatic approval (no action needed)
- **Error**: Approval failed with specific error message
- **Format**: Structured output showing:
  - Approved InstallPlan names
  - Installation/upgrade status
  - Next steps or related commands

## Examples

1. **Approve pending InstallPlan for an operator**:
   ```
   /olm:approve openshift-cert-manager-operator
   ```

2. **Approve with specific namespace**:
   ```
   /olm:approve external-secrets-operator eso-operator
   ```

3. **Approve all pending InstallPlans**:
   ```
   /olm:approve openshift-cert-manager-operator cert-manager-operator --all
   ```
   This approves all pending InstallPlans for the operator in the namespace.

4. **Check and approve after upgrade command**:
   ```
   /olm:upgrade openshift-cert-manager-operator --channel=tech-preview
   # Wait for InstallPlan to be created
   /olm:approve openshift-cert-manager-operator
   ```

## Arguments
- **$1** (operator-name): Name of the operator (required)
  - Example: "openshift-cert-manager-operator"
  - Must match the operator's Subscription name
- **$2** (namespace): Namespace where operator is installed (optional)
  - If not provided, searches all namespaces
  - Example: "cert-manager-operator"
- **$3** (flag): Optional flag
  - `--all`: Approve all pending InstallPlans for this operator
    - Useful when multiple upgrades are pending
    - Skips individual confirmation prompts

## Notes

- **Manual Approval Mode**: This command only works for operators with `installPlanApproval: Manual` in their Subscription
- **Automatic Operators**: Operators with automatic approval don't need this command
- **Review Before Approval**: Always review what will be installed/upgraded before approving
- **Multiple InstallPlans**: An operator may have multiple pending InstallPlans if updates accumulated while waiting for approval
- **InstallPlan Retention**: Approved InstallPlans remain in the namespace for audit purposes

## Troubleshooting

- **No pending InstallPlans**:
  ```bash
  # List all InstallPlans
  oc get installplan -n {namespace}
  
  # Check if operator is in automatic mode
  oc get subscription {operator-name} -n {namespace} -o jsonpath='{.spec.installPlanApproval}'
  ```

- **InstallPlan not executing after approval**:
  ```bash
  # Check InstallPlan status
  oc describe installplan {installplan-name} -n {namespace}
  
  # Check for errors
  oc get events -n {namespace} --sort-by='.lastTimestamp' | grep InstallPlan
  ```

- **CSV not reaching Succeeded phase**:
  ```bash
  # Check CSV status
  oc describe csv -n {namespace}
  
  # Check operator deployment
  oc get deployments -n {namespace}
  
  # Check operator logs
  oc logs -n {namespace} deployment/{operator-deployment}
  ```

- **Permission denied**:
  ```bash
  # Check if you can patch InstallPlans
  oc auth can-i patch installplan -n {namespace}
  ```

- **Multiple namespaces found**:
  - Specify the namespace explicitly in the command:
    ```
    /olm:approve {operator-name} {specific-namespace}
    ```

## Related Commands

- `/olm:status <operator-name>` - Check if InstallPlans are pending approval
- `/olm:upgrade <operator-name>` - Trigger upgrade and approve in one command
- `/olm:install <operator-name>` - Install operator with approval mode
- `/olm:list` - List operators and their approval modes

## Additional Resources

- [Red Hat OpenShift: Approving Operator Upgrades](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-approving-operator-upgrades_olm-updating-operators)
- [Red Hat OpenShift: Updating Installed Operators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-updating-operators)
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)


