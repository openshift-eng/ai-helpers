---
description: Generate debugging commands for Windows container issues
argument-hint: "[issue-type]"
---

## Name
utils:winc-debug

## Synopsis
```
/utils:winc-debug [issue-type]
```

## Description
The `utils:winc-debug` command generates comprehensive debugging command sets for troubleshooting Windows container issues in OpenShift clusters. It provides pre-configured commands for common Windows node and workload problems, helping QE engineers and developers quickly diagnose issues without memorizing complex command sequences.

This command addresses the most frequent Windows container failure scenarios:
- Windows Nodes not reaching Ready state
- Windows Machine Config Operator (WMCO) issues
- Windows Pod crashes or startup failures
- Networking problems on Windows nodes
- Windows containerD/runtime issues

Each debugging scenario includes:
- **Diagnostic commands**: Collect relevant logs and status information
- **Common causes**: Known issues and their symptoms
- **Verification steps**: Commands to confirm the root cause
- **Remediation hints**: Suggested fixes or workarounds

## Implementation

When invoked, the command prompts the user to select an issue type (or accepts it as argument), then generates a comprehensive debugging guide including:

1. **Initial cluster state check**: Verify WMCO deployment, Windows nodes, and basic connectivity
2. **Scenario-specific diagnostics**: Tailored commands for the selected issue type
3. **Log collection**: Commands to gather relevant logs from WMCO, nodes, and pods
4. **Analysis guidance**: What to look for in the collected output
5. **Next steps**: Recommendations for resolution or escalation

### Available Issue Types

#### `node-not-ready`
Diagnose Windows nodes stuck in NotReady, Unknown, or continuously restarting states.

**Diagnostic commands:**
- Check Windows node status and conditions
- Review WMCO operator logs for provisioning errors
- Examine Machine API status for Windows machines
- Verify SSH connectivity to Windows nodes
- Check Windows node system logs (if accessible)

**Common causes:**
- WMCO installation/upgrade failures
- Windows image pull failures
- Networking misconfiguration (CNI, OVN-Kubernetes)
- Insufficient resources (memory, disk)
- Machine API provider issues (AWS, Azure, vSphere)

#### `wmco-status`
Check Windows Machine Config Operator health and configuration.

**Diagnostic commands:**
- WMCO deployment status and pod logs
- WMCO version and supported Windows versions
- ConfigMap and Secret verification
- Webhook and certificate status
- Recent WMCO events and errors

**Common causes:**
- Incompatible WMCO/OCP versions
- Missing or invalid SSH keys
- Certificate expiration
- Webhook configuration issues
- Insufficient RBAC permissions

#### `pod-crash`
Debug Windows pods that fail to start or crash repeatedly.

**Diagnostic commands:**
- Pod status, events, and logs
- ContainerD runtime status on the node
- Windows Event Logs for container runtime
- Image pull status and errors
- Resource limits and node capacity

**Common causes:**
- Incompatible Windows container images (wrong base image version)
- Missing or misconfigured Secrets/ConfigMaps
- Resource constraints (CPU, memory limits)
- HostProcess container misconfigurations
- Network policy blocking required traffic

#### `networking`
Troubleshoot Windows pod networking issues (DNS, connectivity, services).

**Diagnostic commands:**
- Pod network configuration (IP, routes)
- DNS resolution from Windows pod
- Service endpoint verification
- OVN-Kubernetes Windows agent logs
- CNI plugin logs and configuration
- Hybrid overlay status (if applicable)

**Common causes:**
- OVN-Kubernetes Windows agent failures
- Incorrect network policy rules
- DNS service unavailable
- Service endpoint not created
- Hybrid overlay misconfiguration

#### `performance`
Investigate Windows node or pod performance issues.

**Diagnostic commands:**
- Node resource utilization (CPU, memory, disk)
- Pod resource consumption
- ContainerD metrics
- Windows performance counters
- I/O and network bandwidth usage

**Common causes:**
- Resource overcommitment
- Disk I/O bottlenecks
- Memory leaks in containers
- Excessive logging or disk writes
- Insufficient node sizing

## Process Flow

1. **Issue Selection**:
   - If `$1` provided: Use specified issue type
   - If no argument: Present interactive menu with issue types
   - Validate issue type is supported

2. **Cluster Context Check**:
   - Verify `KUBECONFIG` is set
   - Check if cluster has Windows nodes (`oc get nodes -l kubernetes.io/os=windows`)
   - Verify WMCO is installed (`oc get deployment -n openshift-windows-machine-config-operator`)
   - Display cluster version and WMCO version

3. **Generate Debugging Commands**:
   - Based on issue type, generate relevant `oc` commands
   - Include commands to:
     - List relevant resources (nodes, pods, deployments)
     - Get detailed resource status (`oc describe`, `oc get -o yaml`)
     - Fetch logs (`oc logs`, `oc adm node-logs`)
     - Execute diagnostic commands (`oc debug node`, `oc exec`)
   - Format output as executable shell commands with explanations

4. **Output Debugging Guide**:
   - Display commands grouped by diagnostic category
   - Include expected output patterns and what to look for
   - Provide common cause checklist
   - Suggest remediation steps based on findings
   - Optionally save guide to file (`winc-debug-<issue-type>-<timestamp>.md`)

5. **Execution Assistance**:
   - Ask if user wants to execute commands automatically
   - If yes: Run commands and collect output
   - If no: Provide copy-paste ready command list
   - Offer to create JIRA ticket with collected diagnostics

## Return Value
- **Debugging guide**: Markdown document with categorized diagnostic commands
- **Analysis checklist**: Common causes and verification steps
- **Collected output** (if auto-execution enabled): Command results saved to file

## Examples

1. **Diagnose Windows node not ready**:
   ```
   /utils:winc-debug node-not-ready
   ```
   Generates commands to check node status, WMCO logs, Machine API, and SSH connectivity.

2. **Check WMCO health**:
   ```
   /utils:winc-debug wmco-status
   ```
   Displays WMCO deployment status, version compatibility, and certificate validity.

3. **Debug Windows pod crash loop**:
   ```
   /utils:winc-debug pod-crash
   ```
   Provides commands to inspect pod events, container logs, image pull status, and resource limits.

4. **Interactive mode** (no argument):
   ```
   /utils:winc-debug
   ```
   Presents menu:
   ```
   Select Windows container issue type:
   1. node-not-ready    - Windows node stuck in NotReady state
   2. wmco-status       - Check WMCO operator health
   3. pod-crash         - Windows pod crashes or won't start
   4. networking        - Networking/DNS issues
   5. performance       - Performance problems
   ```

5. **Investigate networking issues**:
   ```
   /utils:winc-debug networking
   ```
   Generates DNS tests, service endpoint checks, and OVN-Kubernetes diagnostics.

## Arguments
- `$1` (issue-type): Optional. One of: `node-not-ready`, `wmco-status`, `pod-crash`, `networking`, `performance`
  - If omitted, presents interactive selection menu

## Prerequisites
- `KUBECONFIG` environment variable set to target cluster
- `oc` CLI installed and configured
- Cluster must have Windows node capability (WMCO installed)
- Appropriate RBAC permissions to view Windows resources

## Notes

### Platform-Specific Considerations
- **AWS**: Windows instances use specific AMIs; check Machine configuration for correct AMI ID
- **Azure**: Verify Windows license type and VM size in MachineSet
- **vSphere**: Ensure Windows template is compatible with OCP version
- **None/Bare Metal**: SSH key must be correctly configured in WMCO Secret

### WMCO Version Compatibility
Different OpenShift versions support different Windows Server versions:
- OCP 4.12+: Windows Server 2022 LTSC
- OCP 4.10-4.11: Windows Server 2019 LTSC, 2022 LTSC (4.11.40+)
- Always verify WMCO release notes for version compatibility

### Common Quick Checks
Before deep debugging, always verify:
1. WMCO pod is running: `oc get pods -n openshift-windows-machine-config-operator`
2. Windows nodes exist: `oc get nodes -l kubernetes.io/os=windows`
3. Machine/MachineSet status: `oc get machine,machineset -n openshift-machine-api | grep -i windows`
4. Recent events: `oc get events -n openshift-windows-machine-config-operator --sort-by='.lastTimestamp'`

### Related Commands
- `/must-gather:analyze` - Collect comprehensive cluster diagnostics
- `/jira:create-bug` - Create JIRA ticket with debug output
- `/ci:query-test-result` - Check if issue is a known test failure

## See Also
- WMCO Documentation: https://docs.openshift.com/container-platform/latest/windows_containers/understanding-windows-container-workloads.html
- Windows Container Troubleshooting: https://github.com/openshift/windows-machine-config-operator/blob/master/docs/TROUBLESHOOTING.md
- OpenShift Windows Tests: https://github.com/openshift/openshift-tests-private/tree/master/test/extended/winc
