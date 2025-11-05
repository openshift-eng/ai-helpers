---
description: Update an operator to the latest version or switch channels
argument-hint: <operator-name> [namespace] [--channel=<channel>] [--approve]
---

## Name
olm:upgrade

## Synopsis
```
/olm:upgrade <operator-name> [namespace] [--channel=<channel>] [--approve]
```

## Description
The `olm:upgrade` command updates an installed operator to the latest version in its current channel or switches to a different channel. It can also approve pending InstallPlans for operators with manual approval mode.

This command helps you:
- Update operators to the latest version in their channel
- Switch operators to different channels (e.g., stable to tech-preview)
- Approve pending upgrade InstallPlans for manual approval mode
- Monitor upgrade progress
- Rollback on failure (if possible via OLM)

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Operator name (required) - Name of the operator to upgrade
   - `$2`: Namespace (optional) - Namespace where operator is installed
     - If not provided, searches for the operator across all namespaces
   - `$3+`: Flags (optional):
     - `--channel=<channel-name>`: Switch to a different channel
     - `--approve`: Automatically approve pending InstallPlan (for manual approval mode)

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
   - If multiple instances found, prompt user to specify namespace

4. **Get Current State**:
   - Get current Subscription:
     ```bash
     oc get subscription {operator-name} -n {namespace} -o json
     ```
   - Extract:
     - Current channel: `.spec.channel`
     - Install plan approval: `.spec.installPlanApproval`
     - Installed CSV: `.status.installedCSV`
     - Current CSV: `.status.currentCSV`
   - Get current CSV version:
     ```bash
     oc get csv {installed-csv} -n {namespace} -o jsonpath='{.spec.version}'
     ```

5. **Check for Available Updates**:
   - Get PackageManifest:
     ```bash
     oc get packagemanifest {operator-name} -n openshift-marketplace -o json
     ```
   - Extract available channels and their latest versions
   - If `--channel` flag is specified, verify channel exists
   - If no channel flag, check for updates in current channel
   - Compare current version with latest available version
   - Reference: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-updating-operators

6. **Display Upgrade Plan**:
   ```
   Operator Upgrade Plan:
   
   Operator: {display-name}
   Namespace: {namespace}
   Current Version: {current-version}
   Current Channel: {current-channel}
   
   [If switching channels:]
   Target Channel: {new-channel}
   Target Version: {new-version}
   
   [If upgrading in same channel:]
   Latest Version: {latest-version} (in channel: {current-channel})
   
   Approval Mode: {Automatic|Manual}
   ```

7. **Check for Pending InstallPlans** (for manual approval mode):
   - Get pending InstallPlans:
     ```bash
     oc get installplan -n {namespace} -o json | jq '.items[] | select(.spec.approved==false)'
     ```
   - If pending InstallPlan exists and `--approve` flag is set:
     - Display InstallPlan details
     - Approve the InstallPlan (skip to step 9)
   - If pending InstallPlan exists and no `--approve` flag:
     ```
     ⏸️  Pending InstallPlan found (requires manual approval)
     
     InstallPlan: {installplan-name}
     Target Version: {target-version}
     
     To approve: /olm:upgrade {operator-name} {namespace} --approve
     Or use: /olm:approve {operator-name} {namespace}
     ```
     - Exit, waiting for user to approve

8. **Perform Channel Switch** (if `--channel` flag provided):
   - Confirm with user (unless `--force` flag):
     ```
     WARNING: Switching channels may upgrade or downgrade the operator.
     
     Current: {current-channel} ({current-version})
     Target:  {new-channel} ({target-version})
     
     Continue? (yes/no)
     ```
   - Update Subscription to new channel:
     ```bash
     oc patch subscription {operator-name} -n {namespace} \
       --type merge --patch '{"spec":{"channel":"{new-channel}"}}'
     ```
   - Display confirmation:
     ```
     ✓ Subscription updated to channel: {new-channel}
     ```

9. **Approve Pending InstallPlan** (if `--approve` flag or automatic approval):
   - If approval mode is Manual and `--approve` flag is set:
     ```bash
     oc patch installplan {installplan-name} -n {namespace} \
       --type merge --patch '{"spec":{"approved":true}}'
     ```
   - Display approval confirmation:
     ```
     ✓ InstallPlan approved: {installplan-name}
     ```

10. **Monitor Upgrade Progress**:
    - Wait for new InstallPlan to be created (if switching channels):
      ```bash
      oc get installplan -n {namespace} -w --timeout=60s
      ```
    - Wait for new CSV to reach "Succeeded" phase:
      ```bash
      oc get csv -n {namespace} -w --timeout=300s
      ```
    - Display progress updates:
      ```
      🔄 Upgrade in progress...
      ⏳ Waiting for InstallPlan to complete...
      ⏳ New CSV installing: {new-csv-name}
      ⏳ Old CSV replacing: {old-csv-name}
      ```
    - Poll every 10 seconds to check status
    - Timeout: 10 minutes for upgrade to complete

11. **Verify Upgrade Success**:
    - Check new CSV status:
      ```bash
      oc get csv -n {namespace} -o json
      ```
    - Verify new CSV phase is "Succeeded"
    - Get new version:
      ```bash
      oc get csv {new-csv-name} -n {namespace} -o jsonpath='{.spec.version}'
      ```
    - Check deployments are healthy:
      ```bash
      oc get deployments -n {namespace}
      ```
    - Check pods are running:
      ```bash
      oc get pods -n {namespace}
      ```

12. **Display Upgrade Summary**:
    ```
    ✓ Operator Upgrade Complete!
    
    Operator: {display-name}
    Namespace: {namespace}
    Previous Version: {old-version}
    Current Version: {new-version}
    Channel: {channel}
    
    Deployment Status:
      - {deployment-1}: 1/1 replicas ready
      - {deployment-2}: 1/1 replicas ready
    
    To check status: /olm:status {operator-name} {namespace}
    ```

13. **Handle Upgrade Failures**:
    - If upgrade fails or times out:
      ```
      ❌ Operator upgrade failed
      
      Current State:
      - CSV: {csv-name} (Phase: {phase})
      - Message: {error-message}
      
      Troubleshooting steps:
      1. Check CSV status: oc describe csv {csv-name} -n {namespace}
      2. Check events: oc get events -n {namespace} --sort-by='.lastTimestamp'
      3. Check InstallPlan: oc get installplan -n {namespace}
      4. Run diagnostics: /olm:diagnose {operator-name} {namespace}
      
      To rollback (if OLM supports):
      oc patch subscription {operator-name} -n {namespace} \
        --type merge --patch '{"spec":{"channel":"{old-channel}"}}'
      ```

## Return Value
- **Success**: Operator upgraded successfully with new version details
- **Pending Approval**: Upgrade waiting for manual approval with instructions
- **No Update Available**: Operator is already at the latest version
- **Error**: Upgrade failed with specific error message and troubleshooting guidance
- **Format**: Structured output showing:
  - Previous and current versions
  - Channel information
  - Deployment and pod status
  - Next steps or related commands

## Examples

1. **Check for and install updates in current channel**:
   ```
   /olm:upgrade openshift-cert-manager-operator
   ```

2. **Upgrade with specific namespace**:
   ```
   /olm:upgrade external-secrets-operator eso-operator
   ```

3. **Switch to a different channel**:
   ```
   /olm:upgrade openshift-cert-manager-operator cert-manager-operator --channel=tech-preview-v1.14
   ```
   This switches from stable-v1 to tech-preview-v1.14 channel.

4. **Approve pending upgrade (manual approval mode)**:
   ```
   /olm:upgrade openshift-cert-manager-operator --approve
   ```

5. **Switch channel and approve in one command**:
   ```
   /olm:upgrade prometheus prometheus-operator --channel=beta --approve
   ```

## Arguments
- **$1** (operator-name): Name of the operator to upgrade (required)
  - Example: "openshift-cert-manager-operator"
  - Must match the operator's Subscription name
- **$2** (namespace): Namespace where operator is installed (optional)
  - If not provided, searches all namespaces
  - Example: "cert-manager-operator"
- **$3+** (flags): Optional flags
  - `--channel=<channel-name>`: Switch to specified channel
    - Example: `--channel=stable-v1`, `--channel=tech-preview`
    - Triggers upgrade/downgrade to the version in that channel
  - `--approve`: Automatically approve pending InstallPlan
    - Only needed for operators with Manual approval mode
    - Equivalent to `/olm:approve` command

## Notes

- **Automatic Updates**: Operators with `installPlanApproval: Automatic` will upgrade automatically when new versions are available in their channel
- **Manual Approval**: Operators with `installPlanApproval: Manual` require explicit approval via `--approve` flag or `/olm:approve` command
- **Channel Switching**: Changing channels may result in upgrade or downgrade depending on the versions in each channel
- **Rollback**: OLM has limited rollback support. Switching back to the previous channel may work, but data migration issues may occur
- **Upgrade Timing**: Upgrades happen according to the operator's upgrade strategy (some may cause downtime)

## Troubleshooting

- **No updates available**:
  ```bash
  # Check current version
  oc get csv -n {namespace}
  
  # Check available versions
  oc get packagemanifest {operator-name} -n openshift-marketplace -o json
  ```

- **Upgrade stuck or pending**:
  ```bash
  # Check InstallPlan status
  oc get installplan -n {namespace}
  
  # Check for events
  oc get events -n {namespace} --sort-by='.lastTimestamp' | tail -20
  ```

- **Manual approval required**:
  ```bash
  # List pending InstallPlans
  oc get installplan -n {namespace} -o json | jq '.items[] | select(.spec.approved==false)'
  
  # Approve specific InstallPlan
  /olm:approve {operator-name} {namespace}
  ```

- **Upgrade failed**:
  ```bash
  # Check CSV status
  oc describe csv -n {namespace}
  
  # Check operator logs
  oc logs -n {namespace} deployment/{operator-deployment}
  
  # Run diagnostics
  /olm:diagnose {operator-name} {namespace}
  ```

- **Rollback needed**:
  - OLM doesn't have built-in rollback
  - Can try switching back to previous channel, but may have issues:
    ```bash
    oc patch subscription {operator-name} -n {namespace} \
      --type merge --patch '{"spec":{"channel":"{old-channel}"}}'
    ```
  - Consider backup/restore of custom resources before upgrading

## Related Commands

- `/olm:status <operator-name>` - Check current version and available updates
- `/olm:approve <operator-name>` - Approve pending InstallPlans
- `/olm:install <operator-name>` - Install an operator
- `/olm:diagnose <operator-name>` - Diagnose upgrade issues

## Additional Resources

- [Red Hat OpenShift: Updating Installed Operators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-updating-operators)
- [Red Hat OpenShift: Approving Operator Upgrades](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-approving-operator-upgrades_olm-updating-operators)
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)


