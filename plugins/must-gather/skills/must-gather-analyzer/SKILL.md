---
name: Must-Gather Analyzer
description: |
  Analyze OpenShift must-gather diagnostic data including cluster operators, pods, nodes,
  and network components. Use this skill when the user asks about cluster health, operator status,
  pod issues, node conditions, or wants diagnostic insights from must-gather data.

  Triggers: "analyze must-gather", "check cluster health", "operator status", "pod issues",
  "node status", "failing pods", "degraded operators", "cluster problems", "crashlooping",
  "network issues", "etcd health", "analyze clusteroperators", "analyze pods", "analyze nodes"
---

# Must-Gather Analyzer Skill

Comprehensive analysis of OpenShift must-gather diagnostic data with helper scripts that parse YAML and display output in `oc`-like format.

## Overview

This skill provides analysis for:
- **ClusterVersion**: Current version, update status, and capabilities
- **Cluster Operators**: Status, degradation, and availability
- **Pods**: Health, restarts, crashes, and failures across namespaces
- **Nodes**: Conditions, capacity, and readiness
- **Network**: OVN/SDN diagnostics and connectivity
- **Events**: Warning and error events across namespaces
- **etcd**: Cluster health, member status, and quorum
- **Storage**: PersistentVolumes and PersistentVolumeClaims status

## Must-Gather Directory Structure

**Important**: Must-gather data is contained in a subdirectory with a long hash name:
```
must-gather/
└── registry-ci-openshift-org-origin-...-sha256-<hash>/
    ├── cluster-scoped-resources/
    │   ├── config.openshift.io/clusteroperators/
    │   └── core/nodes/
    ├── namespaces/
    │   └── <namespace>/
    │       └── pods/
    │           └── <pod-name>/
    │               └── <pod-name>.yaml
    └── network_logs/
```

The analysis scripts expect the path to the **subdirectory** (the one with the hash), not the root must-gather folder.

## Instructions

### 1. Get Must-Gather Path
Ask the user for the must-gather directory path if not already provided.
- If they provide the root directory, look for the subdirectory with the hash name
- The correct path contains `cluster-scoped-resources/` and `namespaces/` directories

### 2. Choose Analysis Type

Based on user's request, run the appropriate helper script:

#### ClusterVersion Analysis
```bash
./scripts/analyze_clusterversion.py <must-gather-path>
```

Shows cluster version information similar to `oc get clusterversion`:
- Current version and update status
- Progressing state
- Available updates
- Version conditions
- Enabled capabilities
- Update history

#### Cluster Operators Analysis
```bash
./scripts/analyze_clusteroperators.py <must-gather-path>
```

Shows cluster operator status similar to `oc get clusteroperators`:
- Available, Progressing, Degraded conditions
- Version information
- Time since condition change
- Detailed messages for operators with issues

#### Pods Analysis
```bash
# All namespaces
./scripts/analyze_pods.py <must-gather-path>

# Specific namespace
./scripts/analyze_pods.py <must-gather-path> --namespace <namespace>

# Show only problematic pods
./scripts/analyze_pods.py <must-gather-path> --problems-only
```

Shows pod status similar to `oc get pods -A`:
- Ready/Total containers
- Status (Running, Pending, CrashLoopBackOff, etc.)
- Restart counts
- Age
- Categorized issues (crashlooping, pending, failed)

#### Nodes Analysis
```bash
./scripts/analyze_nodes.py <must-gather-path>

# Show only nodes with issues
./scripts/analyze_nodes.py <must-gather-path> --problems-only
```

Shows node status similar to `oc get nodes`:
- Ready status
- Roles (master, worker)
- Age
- Kubernetes version
- Node conditions (DiskPressure, MemoryPressure, etc.)
- Capacity and allocatable resources

#### Network Analysis
```bash
./scripts/analyze_network.py <must-gather-path>
```

Shows network health:
- Network type (OVN-Kubernetes, OpenShift SDN)
- Network operator status
- OVN pod health
- PodNetworkConnectivityCheck results
- Network-related issues

#### Events Analysis
```bash
# Recent events (last 100)
./scripts/analyze_events.py <must-gather-path>

# Warning events only
./scripts/analyze_events.py <must-gather-path> --type Warning

# Events in specific namespace
./scripts/analyze_events.py <must-gather-path> --namespace openshift-etcd

# Show last 50 events
./scripts/analyze_events.py <must-gather-path> --count 50
```

Shows cluster events:
- Event type (Warning, Normal)
- Last seen timestamp
- Reason and message
- Affected object
- Event count

#### etcd Analysis
```bash
./scripts/analyze_etcd.py <must-gather-path>
```

Shows etcd cluster health:
- Member health status
- Member list with IDs and URLs
- Endpoint status (leader, version, DB size)
- Quorum status
- Cluster summary

#### Storage Analysis
```bash
# All PVs and PVCs
./scripts/analyze_pvs.py <must-gather-path>

# PVCs in specific namespace
./scripts/analyze_pvs.py <must-gather-path> --namespace openshift-monitoring
```

Shows storage resources:
- PersistentVolumes (capacity, status, claims)
- PersistentVolumeClaims (binding, capacity)
- Storage classes
- Pending/unbound volumes

#### Monitoring Analysis
```bash
# All alerts.
./scripts/analyze_prometheus.py <must-gather-path>

# Alerts in specific namespace
./scripts/analyze_prometheus.py <must-gather-path> --namespace openshift-monitoring
```

Shows monitoring information:
- Alerts (state, namespace, name, active since, labels)
- Total of pending/firing alerts

### 3. Interpret and Report

After running the scripts:
1. Review the summary statistics
2. Focus on items flagged with issues
3. Provide actionable insights and next steps
4. Suggest log analysis for specific components if needed
5. Cross-reference issues (e.g., degraded operator → failing pods → node issues)

## Output Format

All scripts provide:
- **Summary Section**: High-level statistics with emoji indicators
- **Table View**: `oc`-like formatted output
- **Issues Section**: Detailed breakdown of problems

Example summary format:
```
================================================================================
SUMMARY: 25/28 operators healthy
  ⚠️  3 operators with issues
  🔄 1 progressing
  ❌ 2 degraded
================================================================================
```

## Helper Scripts Reference

### scripts/analyze_clusterversion.py
Parses: `cluster-scoped-resources/config.openshift.io/clusterversions/version.yaml`
Output: ClusterVersion table with detailed version info, conditions, and capabilities

### scripts/analyze_clusteroperators.py
Parses: `cluster-scoped-resources/config.openshift.io/clusteroperators/`
Output: ClusterOperator status table with conditions

### scripts/analyze_pods.py
Parses: `namespaces/*/pods/*/*.yaml` (individual pod directories)
Output: Pod status table with issues categorized

### scripts/analyze_nodes.py
Parses: `cluster-scoped-resources/core/nodes/`
Output: Node status table with conditions and capacity

### scripts/analyze_network.py
Parses: `network_logs/`, network operator, OVN resources
Output: Network health summary and diagnostics

### scripts/analyze_events.py
Parses: `namespaces/*/core/events.yaml`
Output: Event table sorted by last occurrence

### scripts/analyze_etcd.py
Parses: `etcd_info/` (endpoint_health.json, member_list.json, endpoint_status.json)
Output: etcd cluster health and member status

### scripts/analyze_pvs.py
Parses: `cluster-scoped-resources/core/persistentvolumes/`, `namespaces/*/core/persistentvolumeclaims.yaml`
Output: PV and PVC status tables

## Tips for Analysis

1. **Start with Cluster Operators**: They often reveal system-wide issues
2. **Check Timing**: Look at "SINCE" columns to understand when issues started
3. **Follow Dependencies**: Degraded operator → check its namespace pods → check hosting nodes
4. **Look for Patterns**: Multiple pods failing on same node suggests node issue
5. **Cross-reference**: Use multiple scripts together for complete picture

## Common Scenarios

### "Why is my cluster degraded?"
1. Run `analyze_clusteroperators.py` - identify degraded operators
2. Run `analyze_pods.py --namespace <operator-namespace>` - check operator pods
3. Run `analyze_nodes.py` - verify node health

### "Pods keep crashing"
1. Run `analyze_pods.py --problems-only` - find crashlooping pods
2. Check which nodes they're on
3. Run `analyze_nodes.py` - verify node conditions
4. Suggest checking pod logs in must-gather data

### "Network connectivity issues"
1. Run `analyze_network.py` - check network health
2. Run `analyze_pods.py --namespace openshift-ovn-kubernetes`
3. Check PodNetworkConnectivityCheck results

## Next Steps After Analysis

Based on findings, suggest:
- Examining specific pod logs in `namespaces/<ns>/pods/<pod>/<container>/logs/`
- Reviewing events in `namespaces/<ns>/core/events.yaml`
- Checking audit logs in `audit_logs/`
- Analyzing metrics data if available
- Looking at host service logs in `host_service_logs/`
