---
description: Quick analysis of must-gather data - runs all analysis scripts and provides comprehensive cluster diagnostics
argument-hint: [must-gather-path] [component]
---

## Name
must-gather:analyze

## Synopsis
```
/must-gather:analyze [must-gather-path] [component]
```

## Description

The `must-gather:analyze` command performs comprehensive analysis of OpenShift must-gather diagnostic data. It runs specialized Python analysis scripts to extract and summarize cluster health information across multiple components.

The command can analyze:
- Cluster version and update status
- Cluster operator health (degraded, progressing, unavailable)
- Node conditions and resource status
- Pod failures, restarts, and crash loops
- Network configuration and OVN health
- OVN databases - logical topology, ACLs, pods
- Kubernetes events (warnings and errors)
- etcd cluster health and quorum status
- Persistent volume and claim status
- Ingress controllers and route admission
- MachineConfigPool rollout status
- Service logs (systemd services on master nodes)
- Pod logs (container application logs)
- Node logs (kubelet logs from all nodes)

You can request analysis of the entire cluster or focus on a specific component.

## Prerequisites

**Required Directory Structure:**

Must-gather data typically has this structure:
```
must-gather/
└── registry-ci-openshift-org-origin-...-sha256-<hash>/
    ├── cluster-scoped-resources/
    ├── namespaces/
    ├── nodes/
    ├── network_logs/
    └── etcd_info/
```

The actual must-gather directory is the subdirectory with the hash name, not the parent directory.

**Required Scripts:**

Analysis scripts must be available at:
```
plugins/must-gather/skills/must-gather-analyzer/scripts/
├── analyze_clusterversion.py
├── analyze_clusteroperators.py
├── analyze_nodes.py
├── analyze_pods.py
├── analyze_network.py
├── analyze_ovn_dbs.py
├── analyze_events.py
├── analyze_etcd.py
├── analyze_pvs.py
├── analyze_ingress.py
├── analyze_machineconfigpools.py
├── analyze_servicelogs.py
├── analyze_pod_logs.py
└── analyze_node_logs.py
```

## Error Handling

**CRITICAL: Script-Only Analysis**

- **NEVER** attempt to analyze must-gather data directly using bash commands, grep, or manual file reading
- **ONLY** use the provided Python scripts in `plugins/must-gather/skills/must-gather-analyzer/scripts/`
- If scripts are missing or not found:
  1. Stop immediately
  2. Inform the user that the analysis scripts are not available
  3. Ask the user to ensure the scripts are installed at the correct path
  4. Do NOT attempt alternative approaches

**Script Availability Check:**

Before running any analysis, first verify:
```bash
ls plugins/must-gather/skills/must-gather-analyzer/scripts/analyze_clusteroperators.py
```

If this fails, STOP and report to the user:
```
The must-gather analysis scripts are not available at plugins/must-gather/skills/must-gather-analyzer/scripts/. Please ensure the must-gather-analyzer skill is properly installed before running analysis.
```

## Implementation

The command performs the following steps:

1. **Validate Must-Gather Path**:
   - If path not provided as argument, ask the user
   - Check if path contains `cluster-scoped-resources/` and `namespaces/` directories
   - If user provides root directory, automatically find the correct subdirectory
   - Verify the path exists and is readable

2. **Determine Analysis Scope**:

   **STEP 1: Check for SPECIFIC component keywords**

   If the user mentions a specific component, run ONLY that script:
   - "pods", "pod status", "containers", "crashloop", "failing pods" → `analyze_pods.py` ONLY
   - "etcd", "etcd health", "quorum" → `analyze_etcd.py` ONLY
   - "network", "networking", "ovn", "connectivity" → `analyze_network.py` ONLY
   - "ovn databases", "ovn-dbs", "ovn db", "logical switches", "acls" → `analyze_ovn_dbs.py` ONLY
   - "nodes", "node status", "node conditions" → `analyze_nodes.py` ONLY
   - "operators", "cluster operators", "degraded" → `analyze_clusteroperators.py` ONLY
   - "version", "cluster version", "update", "upgrade" → `analyze_clusterversion.py` ONLY
   - "events", "warnings", "errors" → `analyze_events.py` ONLY
   - "storage", "pv", "pvc", "volumes", "persistent" → `analyze_pvs.py` ONLY
   - "ingress", "ingresscontroller", "routes", "router" → `analyze_ingress.py` ONLY
   - "machineconfigpool", "mcp", "node updates", "node rollout", "stuck nodes" → `analyze_machineconfigpools.py` ONLY
   - "service logs", "kubelet", "crio", "systemd", "host logs" → `analyze_servicelogs.py` ONLY
   - "pod logs", "container logs", "application logs", "log errors", "log patterns" → `analyze_pod_logs.py` ONLY
   - "node logs", "kubelet logs", "kubelet errors", "node errors", "sysinfo" → `analyze_node_logs.py` ONLY

   **STEP 2: No specific component mentioned**

   If generic request like "analyze must-gather", "/must-gather:analyze", or "check the cluster", run ALL scripts in this order:
   1. ClusterVersion (`analyze_clusterversion.py`)
   2. Cluster Operators (`analyze_clusteroperators.py`)
   3. Nodes (`analyze_nodes.py`)
   4. Pods - problems only (`analyze_pods.py --problems-only`)
   5. Network (`analyze_network.py`)
   6. Events - warnings only (`analyze_events.py --type Warning --count 50`)
   7. etcd (`analyze_etcd.py`)
   8. Storage (`analyze_pvs.py`)
   9. Ingress - controllers only (`analyze_ingress.py --ingresscontrollers`)
   10. MachineConfigPools (`analyze_machineconfigpools.py`)
   11. Service Logs - errors only (`analyze_servicelogs.py --errors-only`)
   12. Pod Logs - top errors only (`analyze_pod_logs.py --errors-only --top 5`)
   13. Node Logs - kubelet errors only (`analyze_node_logs.py --log-type kubelet --errors-only --top 5`)

3. **Execute Analysis Scripts**:
   ```bash
   python3 plugins/must-gather/skills/must-gather-analyzer/scripts/<script>.py <must-gather-path>
   ```

4. **Synthesize Results**: Generate findings and recommendations based on script output

## Return Value

The command outputs structured analysis results to stdout:

**For Component-Specific Analysis:**
- Script output for the requested component only
- Focused findings and recommendations

**For Full Analysis:**
- Organized sections for each component
- Executive summary of overall cluster health
- Prioritized list of critical issues
- Actionable recommendations
- Suggested log files to review

## Output Structure

```
================================================================================
MUST-GATHER ANALYSIS SUMMARY
================================================================================

[Script outputs organized by component]

CLUSTER VERSION:
[output from analyze_clusterversion.py]

CLUSTER OPERATORS:
[output from analyze_clusteroperators.py]

NODES:
[output from analyze_nodes.py]

PROBLEMATIC PODS:
[output from analyze_pods.py --problems-only]

NETWORK STATUS:
[output from analyze_network.py]

WARNING EVENTS (Last 50):
[output from analyze_events.py --type Warning --count 50]

ETCD CLUSTER HEALTH:
[output from analyze_etcd.py]

STORAGE (PVs/PVCs):
[output from analyze_pvs.py]

INGRESS CONTROLLERS:
[output from analyze_ingress.py --ingresscontrollers]

MACHINECONFIGPOOLS:
[output from analyze_machineconfigpools.py]

SERVICE LOGS (ERROR PATTERNS):
[output from analyze_servicelogs.py --errors-only]

POD LOGS (ERROR PATTERNS):
[output from analyze_pod_logs.py --errors-only --top 5]

NODE LOGS (KUBELET ERROR PATTERNS):
[output from analyze_node_logs.py --log-type kubelet --errors-only --top 5]

================================================================================
FINDINGS AND RECOMMENDATIONS
================================================================================

Critical Issues:
- [Critical problems requiring immediate attention]

Warnings:
- [Potential issues or degraded components]

Recommendations:
- [Specific next steps for investigation]

Logs to Review:
- [Specific log files to examine based on findings]
```

## Examples

1. **Full cluster analysis**:
   ```
   /must-gather:analyze ./must-gather/registry-ci-openshift-org-origin-4-20-...-sha256-abc123/
   ```
   Runs all analysis scripts and provides comprehensive cluster diagnostics.

2. **Analyze pod issues only**:
   ```
   /must-gather:analyze ./must-gather/registry-ci-openshift-org-origin-4-20-...-sha256-abc123/ analyze the pod statuses
   ```
   Runs only `analyze_pods.py` to focus on pod-related issues.

3. **Check etcd health**:
   ```
   /must-gather:analyze check etcd health
   ```
   Asks for must-gather path, then runs only `analyze_etcd.py`.

4. **Network troubleshooting**:
   ```
   /must-gather:analyze ./must-gather/registry-ci-openshift-org-origin-4-20-...-sha256-abc123/ show me network issues
   ```
   Runs only `analyze_network.py` for network-specific analysis.

5. **Investigate service logs**:
   ```
   /must-gather:analyze analyze service logs
   ```
   Asks for must-gather path, then runs only `analyze_servicelogs.py`.

6. **Check ingress and routes**:
   ```
   /must-gather:analyze check ingress
   ```
   Asks for must-gather path, then runs only `analyze_ingress.py`.

## Notes

- **Must-Gather Path**: Always use the subdirectory containing `cluster-scoped-resources/` and `namespaces/`, not the parent directory
- **Script Dependencies**: Analysis scripts must be executable and have required Python dependencies installed
- **Error Handling**: If scripts are not found or must-gather path is invalid, clear error messages are displayed
- **Cross-Referencing**: The analysis attempts to correlate issues across components (e.g., degraded operator → failing pods)
- **Pattern Detection**: Identifies patterns like multiple pod failures on the same node
- **Actionable Output**: Focuses on insights and recommendations rather than raw data dumps
- **Priority**: Issues are prioritized by severity (Critical > Warning > Info)
- **Event Validation**: Events show historical attempts, not necessarily current failures. Always cross-reference events with current pod/component status to distinguish resolved retries from active issues.

## Arguments

- **$1** (must-gather-path): Optional. Path to the must-gather directory (the subdirectory with the hash name). If not provided, the user will be asked.
- **$2+** (component): Optional. If keywords for a specific component are detected, only that component's analysis script will run. Otherwise, all scripts run.
