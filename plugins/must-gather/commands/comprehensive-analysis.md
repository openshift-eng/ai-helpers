---
description: Comprehensive must-gather analysis - generates a detailed cluster health report identifying critical issues, warnings, and actionable recommendations
argument-hint: [must-gather-path]
---

## Name
must-gather:comprehensive-analysis

## Synopsis
```
/must-gather:comprehensive-analysis [must-gather-path]
```

## Description

The `must-gather:comprehensive-analysis` command performs a thorough, systematic analysis of OpenShift must-gather data by running all analysis scripts in a structured order and generating a consolidated diagnostic report.

This command orchestrates all available analysis scripts to provide a complete picture of cluster health. The analysis proceeds in layers, from high-level cluster status down to detailed component logs, helping identify root causes of issues.

The comprehensive analysis includes:
- Cluster-level health (version, operators)
- Infrastructure health (nodes, network, ingress)
- Workload health (pods, storage, MachineConfigPools)
- Critical components (etcd, events)
- Detailed diagnostics (service logs, pod logs, node logs)
- Root cause analysis
- Error pattern analysis
- Actionable recommendations

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
.claude-plugin/skills/must-gather-analyzer/scripts/
├── analyze_clusterversion.py
├── analyze_clusteroperators.py
├── analyze_nodes.py
├── analyze_pods.py
├── analyze_network.py
├── analyze_events.py
├── analyze_etcd.py
├── analyze_pvs.py
├── analyze_ingress.py
├── analyze_machineconfigpools.py
├── analyze_servicelogs.py
├── analyze_pod_logs.py
├── analyze_node_logs.py
└── analyze_ovn_dbs.py
```

## Error Handling

**CRITICAL: Script-Only Analysis**

- **NEVER** attempt to analyze must-gather data directly using bash commands, grep, or manual file reading
- **ONLY** use the provided Python scripts in `.claude-plugin/skills/must-gather-analyzer/scripts/`
- If scripts are missing or not found:
  1. Stop immediately
  2. Inform the user that the analysis scripts are not available
  3. Ask the user to ensure the scripts are installed at the correct path
  4. Do NOT attempt alternative approaches

**Script Availability Check:**

Before running any analysis, first verify:
```bash
ls .claude-plugin/skills/must-gather-analyzer/scripts/analyze_clusteroperators.py
```

If this fails, STOP and report to the user:
```
The must-gather analysis scripts are not available at .claude-plugin/skills/must-gather-analyzer/scripts/. Please ensure the must-gather-analyzer skill is properly installed before running analysis.
```

## Implementation

The command performs the following steps:

### 1. Get Must-Gather Path

Ask the user for the must-gather directory path if not provided as an argument.

**Important**: Must-gather data is in a subdirectory with a hash name. If the user provides the root directory, find the subdirectory containing `cluster-scoped-resources/` and `namespaces/`.

### 2. Run Analysis Scripts in Systematic Order

Execute scripts in the following order to build a complete diagnostic picture:

#### Phase 1: Cluster-Level Health (Foundation)
These provide the overall cluster state and identify system-wide issues.

1. **Cluster Version**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_clusterversion.py <must-gather-path>
   ```
   - Identifies cluster version and update status
   - Shows if cluster is progressing through an update
   - Reveals capability configuration

2. **Cluster Operators**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_clusteroperators.py <must-gather-path>
   ```
   - Identifies degraded, unavailable, or progressing operators
   - **Critical**: Operator issues often cascade to other components
   - Note which operators have problems for Phase 2 investigation

#### Phase 2: Infrastructure Health (Compute & Network)
These analyze the underlying infrastructure supporting workloads.

3. **Nodes**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_nodes.py <must-gather-path>
   ```
   - Shows node conditions (Ready, DiskPressure, MemoryPressure)
   - Identifies nodes with issues
   - **Critical**: Node problems affect all pods on that node

4. **Network**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_network.py <must-gather-path>
   ```
   - Shows network type (OVN-Kubernetes, OpenShift SDN)
   - Checks network operator health
   - Validates pod network connectivity

5. **OVN Databases** (OVN-Kubernetes clusters only)
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_ovn_dbs.py <must-gather-path>
   ```
   - Analyzes OVN Northbound/Southbound databases from network_logs
   - Shows logical switches, switch ports, ACLs, and routers per node
   - Provides pod network topology and access control configuration
   - **Prerequisites**: Requires `ovsdb-tool` (install openvswitch package)
   - **Note**: Only available if must-gather includes `network_logs/ovnk_database_store.tar.gz`

6. **Ingress and Routes**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_ingress.py <must-gather-path> --ingresscontrollers
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_ingress.py <must-gather-path> --routes --problems-only
   ```
   - Checks IngressController availability
   - Identifies routes not admitted
   - **Important**: Ingress issues affect external access

#### Phase 3: Workload Health (Pods & Storage)
These analyze application workloads and their dependencies.

7. **Pods**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pods.py <must-gather-path> --problems-only
   ```
   - Shows crashlooping, pending, or failed pods
   - **Cross-reference**: Match pod issues with node and operator problems
   - Note which namespaces have the most issues

8. **Storage**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pvs.py <must-gather-path>
   ```
   - Shows PersistentVolume and PersistentVolumeClaim status
   - Identifies pending or unbound volumes
   - **Important**: Storage issues can cause pod failures

9. **MachineConfigPools**
   ```bash
   python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_machineconfigpools.py <must-gather-path>
   ```
   - Shows node configuration rollout status
   - Identifies stuck node updates
   - **Critical during upgrades**: Degraded MCPs block cluster updates

#### Phase 4: Critical Components (etcd & Events)
These provide insights into cluster stability and specific events.

10. **etcd Cluster**
    ```bash
    python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_etcd.py <must-gather-path>
    ```
    - Checks etcd member health and quorum
    - **Critical**: etcd issues can cause API server instability
    - Shows leader status and database size

11. **Events**
    ```bash
    python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_events.py <must-gather-path> --type Warning --count 100
    ```
    - Shows warning events across the cluster
    - Helps identify recent problems and their timeline
    - **Tip**: Look for patterns in event messages

#### Phase 5: Detailed Diagnostics (Logs)
These provide detailed error patterns from various log sources.

12. **Service Logs** (Master Node Services)
    ```bash
    python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_servicelogs.py <must-gather-path> --errors-only
    ```
    - Analyzes kubelet and crio logs from systemd
    - **Note**: Only collected from master nodes in must-gather
    - Shows common error patterns with occurrence counts

13. **Pod Logs** (Container Application Logs)
    ```bash
    # Start with problem namespaces identified in Phase 3
    python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pod_logs.py <must-gather-path> --errors-only --top 5

    # Or analyze specific namespace
    # python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pod_logs.py <must-gather-path> --namespace <namespace> --top 10
    ```
    - Analyzes application container logs
    - Shows error patterns from failing components
    - **Cross-reference**: Match with pod failures from Phase 3

14. **Node Logs** (Kubelet Logs)
    ```bash
    python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_node_logs.py <must-gather-path> --log-type kubelet --errors-only --top 5
    ```
    - Analyzes kubelet logs from all nodes
    - **Note**: Kubelet logs are gzipped and extracted on-the-fly
    - Shows per-node kubelet error patterns
    - **Cross-reference**: Match with node issues from Phase 2

### 3. Generate Consolidated Report

After running all scripts, synthesize the findings into a structured report with the following sections:
- Executive summary
- Critical issues (prioritized)
- Warnings
- Root cause analysis
- Error pattern analysis
- Recommendations
- Detailed logs to review
- Metrics and statistics
- Next steps

### 4. Analysis Guidelines

**Cross-Reference Issues:**
- If an operator is degraded, check its pods in that namespace
- If pods are failing on a specific node, check node conditions
- If network is degraded, check OVN/SDN pods
- If etcd is unhealthy, check etcd pods and member logs

**Pattern Recognition:**
- Multiple pods failing = likely node or infrastructure issue
- Single namespace issues = likely application or config issue
- Cluster-wide patterns = likely control plane or network issue
- Time-based correlation = check events around that timestamp

**Prioritization:**
1. **Critical**: etcd unhealthy, API server down, quorum lost
2. **High**: Control plane operators degraded, multiple nodes down
3. **Medium**: Single operator degraded, some pods failing
4. **Low**: Transient errors, progressing updates, warnings

**Context Matters:**
- Kubernetes is eventually consistent - some errors are transient
- Look for persistent error patterns, not isolated occurrences
- Consider cluster version and update status
- Check if issues started during an upgrade or change

**Cross-Reference Events with Current State:**
- **CRITICAL**: Events show historical attempts, not necessarily current failures
- When FailedScheduling events appear:
  1. Check current pod status (Phase 3 output)
  2. If pod is Running/Succeeded → event shows resolved retry attempts (normal)
  3. If pod is Pending/Failed → event shows ongoing issue (action needed)
- Example: "Pod had 10 FailedScheduling retries but is now Running" = transient resource pressure (expected)
- Example: "Pod has FailedScheduling events and is still Pending" = persistent scheduling issue (investigate)

### 5. Report Generation Tips

**Be Concise:**
- Focus on actionable insights, not data dumps
- Summarize patterns rather than listing every error
- Highlight the "why" and "what to do", not just "what"

**Be Specific:**
- Include component names, namespaces, node names
- Reference specific error messages
- Provide file paths for detailed investigation

**Be Practical:**
- Prioritize issues by impact
- Suggest concrete next steps
- Distinguish between symptoms and root causes

## Return Value

The command outputs a comprehensive structured report to stdout:

```
================================================================================
MUST-GATHER COMPREHENSIVE ANALYSIS REPORT
================================================================================
Cluster: <cluster-id>
Version: <version>
Analysis Date: <date>

================================================================================
EXECUTIVE SUMMARY
================================================================================

Cluster Health: [Healthy / Degraded / Critical]
- X/Y operators healthy
- X/Y nodes ready
- X pods with issues across Y namespaces
- etcd: [Healthy / Degraded]
- Network: [Healthy / Degraded]

Overall Assessment:
[1-2 sentence summary of cluster state]

================================================================================
CRITICAL ISSUES (Immediate Attention Required)
================================================================================

Priority 1 - Control Plane Issues:
[List any issues affecting control plane components]
- Degraded operators: <list>
- etcd problems: <describe>
- API server issues: <describe>

Priority 2 - Infrastructure Issues:
[List any infrastructure problems]
- Node problems: <list nodes with issues>
- Network issues: <describe>
- Storage issues: <list pending PVCs>

Priority 3 - Workload Issues:
[List workload problems]
- CrashLooping pods: <count and namespaces>
- Pending pods: <count and reasons>
- Failed pods: <count and namespaces>

================================================================================
WARNINGS (Monitor and Plan)
================================================================================

- Progressing operators: <list>
- Nodes with pressure conditions: <list>
- High error rates in logs: <describe>
- Routes not admitted: <count>
- MachineConfigPools updating: <list>

================================================================================
ROOT CAUSE ANALYSIS
================================================================================

Primary Issues Identified:
1. [Issue 1]
   - Affected components: <list>
   - Error patterns: <summarize>
   - Likely cause: <hypothesis>

2. [Issue 2]
   - Affected components: <list>
   - Error patterns: <summarize>
   - Likely cause: <hypothesis>

Cascade Effects:
- [Describe how issues are related]
- [Map degraded operator → failing pods → node issues]

================================================================================
ERROR PATTERN ANALYSIS
================================================================================

Most Common Errors Across Cluster:

Service Logs (systemd):
- [Top 3 error patterns with counts]

Pod Logs (containers):
- [Top 3 error patterns with counts]

Node Logs (kubelet):
- [Top 3 error patterns with counts]

Events:
- [Top 3 warning event reasons]

================================================================================
RECOMMENDATIONS
================================================================================

Immediate Actions:
1. [Action for critical issue 1]
2. [Action for critical issue 2]
3. [Action for critical issue 3]

Short-term Actions:
1. [Monitoring or investigation needed]
2. [Configuration changes to consider]

Long-term Improvements:
1. [Capacity planning]
2. [Architecture recommendations]

================================================================================
DETAILED LOGS TO REVIEW
================================================================================

Based on findings, manually review these specific logs:

Control Plane Logs:
- namespaces/openshift-kube-apiserver/pods/<pod>/kube-apiserver/logs/
- namespaces/openshift-etcd/pods/<pod>/etcd/logs/

Problem Namespace Logs:
- namespaces/<namespace>/pods/<pod>/<container>/logs/

Node Logs:
- nodes/<node>/<node>_logs_kubelet.gz

Service Logs:
- host_service_logs/masters/<service>.log

Events:
- namespaces/<namespace>/core/events.yaml

================================================================================
METRICS AND STATISTICS
================================================================================

Cluster Resources:
- Total Nodes: X (Y masters, Z workers)
- Total Namespaces: X
- Total Pods: X (Y running, Z with issues)
- Total PVs/PVCs: X/Y

Error Counts:
- Service log errors: X
- Pod log errors: X
- Node log errors: X
- Warning events: X

Health Percentages:
- Operator health: X%
- Node health: X%
- Pod health: X%

================================================================================
NEXT STEPS
================================================================================

1. Address critical issues in priority order
2. Monitor cluster state after remediation
3. Review detailed logs for specific components
4. Consider filing bugs for unexpected behavior
5. Document lessons learned and preventive measures

================================================================================
```

## Examples

1. **Full comprehensive analysis**:
   ```
   /must-gather:comprehensive-analysis ./must-gather/registry-ci-openshift-org-origin-4-20-...-sha256-abc123/
   ```
   Runs all 14 analysis scripts in order and generates comprehensive report with executive summary, issues, and recommendations.

2. **Interactive comprehensive analysis**:
   ```
   /must-gather:comprehensive-analysis
   ```
   Asks for must-gather path, then runs full comprehensive analysis.

3. **Targeted investigation** (authentication operator degraded):
   ```
   User: "I see the authentication operator is degraded, help me investigate"
   ```
   - Run Phase 1 (operators) to confirm
   - Run Phase 3 (pods --namespace openshift-authentication)
   - Run Phase 5 (pod logs --namespace openshift-authentication)
   - Generate focused report on authentication subsystem

## Advanced Analysis Techniques

### Namespace-Focused Investigation

When a specific namespace has issues:

```bash
NAMESPACE="openshift-etcd"

# 1. Check pods in namespace
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pods.py <mg-path> --namespace $NAMESPACE

# 2. Check events in namespace
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_events.py <mg-path> --namespace $NAMESPACE

# 3. Analyze pod logs in namespace
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pod_logs.py <mg-path> --namespace $NAMESPACE --show-warnings

# 4. Check PVCs in namespace
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pvs.py <mg-path> --namespace $NAMESPACE
```

### Node-Focused Investigation

When a specific node has issues:

```bash
NODE="ip-10-0-45-79"

# 1. Check node status
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_nodes.py <mg-path>  # Look for the node

# 2. Check pods on that node
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pods.py <mg-path>  # Note which pods are on that node

# 3. Check node logs
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_node_logs.py <mg-path> --node $NODE --show-warnings

# 4. Check kubelet errors specifically
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_node_logs.py <mg-path> --node $NODE --log-type kubelet --top 15
```

### Update/Upgrade Investigation

When investigating update issues:

```bash
# 1. Check update status
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_clusterversion.py <mg-path>

# 2. Check MachineConfigPools (nodes updating?)
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_machineconfigpools.py <mg-path>

# 3. Check if operators progressing
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_clusteroperators.py <mg-path>

# 4. Check for update-related events
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_events.py <mg-path> --type Warning
```

### OVN Network Investigation (OVN-Kubernetes clusters)

When investigating OVN networking issues:

```bash
# 1. Check network operator status
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_network.py <mg-path>

# 2. Analyze OVN databases (all nodes)
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_ovn_dbs.py <mg-path>

# 3. Analyze specific node's OVN database
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_ovn_dbs.py <mg-path> --node <node-name>

# 4. Run custom OVSDB query
# Example: Find all ACLs with priority > 1000
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_ovn_dbs.py <mg-path> \
  --query '["OVN_Northbound", {"op":"select", "table":"ACL", "where":[["priority", ">", 1000]], "columns":["priority","match","action"]}]'

# 5. Check OVN pods
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pods.py <mg-path> --namespace openshift-ovn-kubernetes

# 6. Check OVN logs
python3 .claude-plugin/skills/must-gather-analyzer/scripts/analyze_pod_logs.py <mg-path> --namespace openshift-ovn-kubernetes --show-warnings
```

**Note**: OVN database analysis requires:
- `ovsdb-tool` installed (from openvswitch package)
- Must-gather includes `network_logs/ovnk_database_store.tar.gz`
- Only available for OVN-Kubernetes clusters (OpenShift 4.12+)

## Common Issue Patterns

### Pattern 1: Degraded Operator
```
Symptom: Operator shows Degraded=True
Investigation Path:
1. analyze_clusteroperators.py → identify operator
2. analyze_pods.py --namespace <operator-namespace> → check operator pods
3. analyze_pod_logs.py --namespace <operator-namespace> → check pod errors
4. analyze_events.py --namespace <operator-namespace> → check events
Result: Usually pod crashloop or missing dependency
```

### Pattern 2: Node NotReady
```
Symptom: Node shows NotReady status
Investigation Path:
1. analyze_nodes.py → identify node and conditions
2. analyze_pods.py → check which pods affected
3. analyze_node_logs.py --node <node> → check kubelet logs
4. analyze_servicelogs.py → check systemd services (if master)
Result: Usually disk pressure, network issue, or kubelet crash
```

### Pattern 3: Pod CrashLoopBackOff
```
Symptom: Pod continuously restarting
Investigation Path:
1. analyze_pods.py --problems-only → identify pod
2. analyze_pod_logs.py --pod <pod-name> → check application logs
3. analyze_events.py --namespace <namespace> → check events
4. analyze_pvs.py --namespace <namespace> → check storage (if applicable)
Result: Application error, missing config, or resource limits
```

### Pattern 4: Network Connectivity Issues
```
Symptom: Pods can't communicate or external access failing
Investigation Path:
1. analyze_network.py → check network operator
2. analyze_pods.py --namespace openshift-ovn-kubernetes → check OVN pods
3. analyze_ingress.py --routes --problems-only → check route admission
4. analyze_ovn_dbs.py → check OVN database state (logical switches, ACLs)
5. analyze_pod_logs.py --namespace openshift-ovn-kubernetes → check OVN errors
Result: OVN pod failure, misconfigured routes, network policy, or OVN DB inconsistency
```

### Pattern 5: etcd Issues
```
Symptom: API slowness, operator timeouts
Investigation Path:
1. analyze_etcd.py → check quorum and member health
2. analyze_pods.py --namespace openshift-etcd → check etcd pods
3. analyze_pod_logs.py --namespace openshift-etcd → check etcd logs
4. analyze_nodes.py → check etcd node health (masters)
Result: Quorum loss, disk latency, or network partitioning
```

### Pattern 6: FailedScheduling Events
```
Symptom: Events show FailedScheduling warnings
Investigation Path:
1. analyze_events.py --namespace <namespace> → see scheduling failures
2. analyze_pods.py --namespace <namespace> → CHECK CURRENT POD STATUS
   - If pod Running/Succeeded → Events show resolved retries (NORMAL)
   - If pod Pending → Active scheduling issue (INVESTIGATE)
3. If still Pending:
   a. Check event message for reason (Insufficient cpu, taints, etc.)
   b. analyze_nodes.py → verify node capacity/taints
   c. Check pod resource requests vs node allocatable
Result: Either resolved (normal retries) or active capacity/constraint issue
```

## Tips for Effective Analysis

### 1. Follow the Investigation Flow
```
Symptom (from Phase 1-2) → Component (Phase 3) → Logs (Phase 5)
```

Example:
- Symptom: "ingress operator degraded" (Phase 1)
- Component: Check ingress pods in openshift-ingress namespace (Phase 3)
- Logs: Analyze pod logs for router pods (Phase 5)

### 2. Look for Cascading Failures
```
Root Cause → Primary Effect → Secondary Effect
```

Example:
- Root: Node disk pressure (Phase 2)
- Primary: Pods evicted from node (Phase 3)
- Secondary: Operator degraded due to pod failure (Phase 1)

### 3. Time Correlation
- Use events (Phase 4) to establish timeline
- Check when issues first appeared
- Correlate with cluster updates or configuration changes

### 4. Error Pattern Deduplication
- Scripts show occurrence counts (e.g., [176x] Error syncing pod)
- High counts often indicate systematic issues
- Unique errors may indicate specific component problems

### 5. Kubernetes Context & Event Validation
Many errors are normal in Kubernetes:
- "Error syncing pod, skipping" - often transient
- "DeleteContainer returned error" - pods being terminated
- "failed to get version" - intermittent connectivity
- "FailedScheduling" - normal retry behavior before success

**CRITICAL: Always validate events against current state**
- FailedScheduling event + Pod Running = **Resolved** (scheduler retries succeeded)
- FailedScheduling event + Pod Pending = **Active Issue** (still failing)
- Events show retry history, not necessarily current failure
- Check Phase 3 (Pods) output to confirm current status before concluding failure

Focus on:
- Persistent high-count errors
- Errors correlated with degraded state
- Errors from critical components (etcd, API server)
- Events for pods that are STILL failing (not resolved)

## Script Output Reference

### Understanding Script Outputs

**Summary Lines:**
```
✅ All healthy
⚠️  Issues detected
❌ Critical problems
🔄 Progressing/Updating
```

**Emoji Indicators:**
- ✅ (Green check): Everything normal
- ⚠️ (Warning): Attention needed, not critical
- ❌ (Red X): Critical issue, immediate attention
- 🔄 (Arrows): Update or rollout in progress

**Problem Filtering:**
Most scripts support `--problems-only` to reduce noise and focus on issues.

**Pattern Format:**
```
[176x] Error message here
```
- Number in brackets = occurrence count
- Higher counts = more significant pattern
- Similar patterns are deduplicated

## Report Customization

Customize the report based on your audience:

### For SRE/Operations Team
Focus on:
- Immediate actions needed
- Service impact assessment
- Monitoring recommendations
- Runbook references

### For Development Team
Focus on:
- Application errors from pod logs
- Configuration issues
- Resource constraints
- Dependency failures

### For Management
Focus on:
- Executive summary only
- Business impact
- Timeline to resolution
- Prevention measures

## Limitations and Caveats

1. **Must-Gather Snapshot**: Data is point-in-time, cluster may have changed
2. **Redacted Data**: Some must-gathers have sensitive data removed
3. **Log Truncation**: Very large log files may be truncated in collection
4. **Master Node Bias**: Service logs typically only from master nodes
5. **Pattern Limitations**: Some error patterns may not be correctly extracted
6. **Transient Errors**: Many Kubernetes errors are normal and self-healing

## Best Practices

1. **Start Broad, Go Deep**: Begin with cluster-level health, drill into specifics
2. **Correlate Across Phases**: Cross-reference findings between different script outputs
3. **Focus on Persistence**: Distinguish transient from persistent issues
4. **Document Findings**: Keep notes as you investigate
5. **Verify Hypotheses**: Use multiple data sources to confirm root cause
6. **Consider Context**: Account for cluster state, version, and recent changes

## Notes

- **Must-Gather Path**: Always use the subdirectory containing `cluster-scoped-resources/` and `namespaces/`, not the parent directory
- **Script Dependencies**: Analysis scripts must be executable and have required Python dependencies installed
- **Systematic Approach**: The phased approach ensures comprehensive coverage and proper correlation of issues
- **Actionable Output**: The goal is not just to list problems, but to understand relationships between issues and provide a clear path to resolution
- **Cross-Referencing**: Always correlate findings across phases to identify root causes vs symptoms
- **Event Validation**: Events show historical attempts; always cross-reference with current component status

## Arguments

- **$1** (must-gather-path): Optional. Path to the must-gather directory (the subdirectory with the hash name). If not provided, the user will be asked.
