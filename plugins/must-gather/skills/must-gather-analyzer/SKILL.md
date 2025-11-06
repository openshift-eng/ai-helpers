---
name: Must-Gather Analyzer
description: |
  Analyze OpenShift must-gather diagnostic data including cluster operators, pods, nodes,
  and network components. Use this skill when the user asks about cluster health, operator status,
  pod issues, node conditions, or wants diagnostic insights from must-gather data.

  Triggers: "analyze must-gather", "check cluster health", "operator status", "pod issues",
  "node status", "failing pods", "degraded operators", "cluster problems", "crashlooping",
  "network issues", "etcd health", "analyze clusteroperators", "analyze pods", "analyze nodes",
  "generate report", "comprehensive analysis", "cluster report"
---

# Must-Gather Analyzer Skill

Comprehensive analysis of OpenShift must-gather diagnostic data with helper scripts that parse YAML and display output in `oc`-like format.

## Analysis Modes

### Quick Analysis
Run individual scripts to analyze specific components (operators, pods, nodes, etc.).

### Comprehensive Analysis
Use `/comprehensive-analysis` command or automation script for complete cluster health report:
- Runs all 13 analysis scripts in systematic 5-phase order
- Generates detailed report with executive summary
- Cross-references issues across components
- Provides root cause analysis and recommendations
- See `.claude-plugin/commands/comprehensive-analysis.md` for details

## Overview

This skill provides analysis for:
- **ClusterVersion**: Current version, update status, and capabilities
- **Cluster Operators**: Status, degradation, and availability
- **Pods**: Health, restarts, crashes, and failures across namespaces
- **Nodes**: Conditions, capacity, and readiness
- **Network**: OVN/SDN diagnostics and connectivity
- **OVN Databases**: Deep OVN database analysis (logical switches, ports, ACLs, routers) using ovsdb-tool
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

#### Ingress and Routes Analysis
```bash
# Analyze IngressControllers
./scripts/analyze_ingress.py <must-gather-path> --ingresscontrollers

# Analyze Routes (all namespaces)
./scripts/analyze_ingress.py <must-gather-path> --routes

# Routes in specific namespace
./scripts/analyze_ingress.py <must-gather-path> --routes --namespace openshift-console

# Only routes with problems
./scripts/analyze_ingress.py <must-gather-path> --routes --problems-only
```

Shows ingress configuration and route status:
- IngressController health (available, progressing, degraded)
- DNS and LoadBalancer status
- Route admission status
- Route hostnames and TLS configuration

#### Service Logs Analysis
```bash
# Analyze all service logs
./scripts/analyze_servicelogs.py <must-gather-path>

# Filter by service name
./scripts/analyze_servicelogs.py <must-gather-path> --service kubelet

# Show only services with errors
./scripts/analyze_servicelogs.py <must-gather-path> --errors-only

# Show warnings in addition to errors
./scripts/analyze_servicelogs.py <must-gather-path> --show-warnings
```

Shows host service logs from systemd:
- ERROR and WARN pattern summaries with occurrence counts
- Service-specific error pattern analysis
- Aggregated view of common issues
- NOTE: Host service logs (systemd) are typically only collected from master nodes in must-gather

#### MachineConfigPools Analysis
```bash
# Show all MachineConfigPools
./scripts/analyze_machineconfigpools.py <must-gather-path>

# Show only pools with problems
./scripts/analyze_machineconfigpools.py <must-gather-path> --problems-only
```

Shows MachineConfigPool status:
- Pool update status (Updated, Updating, Degraded)
- Machine counts (ready, updated, degraded)
- Current configuration being applied
- Identifies stuck node updates and rollout issues

#### Pod Logs Analysis
```bash
# Analyze all pod logs with errors
./scripts/analyze_pod_logs.py <must-gather-path>

# Analyze logs for a specific namespace
./scripts/analyze_pod_logs.py <must-gather-path> --namespace openshift-etcd

# Analyze logs for a specific pod (partial name match)
./scripts/analyze_pod_logs.py <must-gather-path> --pod etcd

# Analyze specific container logs
./scripts/analyze_pod_logs.py <must-gather-path> --namespace openshift-etcd --container etcd

# Show top 5 error patterns
./scripts/analyze_pod_logs.py <must-gather-path> --top 5

# Show warnings in addition to errors
./scripts/analyze_pod_logs.py <must-gather-path> --show-warnings
```

Shows pod/container log analysis:
- ERROR and WARN pattern summaries with occurrence counts
- Per-container error pattern analysis
- Filters by namespace, pod, or container name
- Identifies common error patterns across pod logs

#### Node Logs Analysis
```bash
# Analyze all node logs (kubelet, sysinfo, dmesg)
./scripts/analyze_node_logs.py <must-gather-path>

# Analyze logs for a specific node
./scripts/analyze_node_logs.py <must-gather-path> --node ip-10-0-45-79

# Analyze only kubelet logs
./scripts/analyze_node_logs.py <must-gather-path> --log-type kubelet

# Skip kubelet logs (avoids extracting gzipped files)
./scripts/analyze_node_logs.py <must-gather-path> --skip-kubelet

# Show top 5 error patterns
./scripts/analyze_node_logs.py <must-gather-path> --top 5

# Show warnings in addition to errors
./scripts/analyze_node_logs.py <must-gather-path> --show-warnings
```

Shows node log analysis:
- Kubelet logs (gzipped, extracted on-the-fly)
- System information logs (sysinfo.log)
- Kernel messages (dmesg)
- ERROR and WARN pattern summaries with occurrence counts
- Per-node error pattern analysis
- Identifies common kubelet errors across nodes

#### OVN Database Analysis
```bash
# Analyze all nodes
./scripts/analyze_ovn_dbs.py <must-gather-path>

# Analyze specific node (supports partial name matching)
./scripts/analyze_ovn_dbs.py <must-gather-path> --node ip-10-0-26-145

# Run custom OVSDB query
./scripts/analyze_ovn_dbs.py <must-gather-path> --query '["OVN_Northbound", {...}]'

# Or use slash command
/must-gather:ovn-dbs <must-gather-path>
/must-gather:ovn-dbs <must-gather-path> --node <node-name>
```

Deep OVN database analysis using ovsdb-tool:
- **Per-node analysis**: Each node has its own Northbound and Southbound databases
- **Logical Switches**: Network switches and their port counts
- **Pod Logical Switch Ports**: Pod network configuration with namespace, pod name, and IP
- **Access Control Lists (ACLs)**: Network policy rules with priorities and match conditions
- **Logical Routers**: Router configuration and port counts
- **Custom Queries**: Run raw OVSDB JSON queries for specific data extraction
- **Prerequisites**: Requires `ovsdb-tool` (install: `sudo dnf install openvswitch`)

#### CAMGI - Cluster Autoscaler Inspector
```bash
# Start CAMGI web interface
./scripts/run-camgi.sh <must-gather-path>

# Stop CAMGI containers
./scripts/run-camgi.sh stop

# Or use slash command
/must-gather:camgi <must-gather-path>
/must-gather:camgi stop
```

Interactive web-based analysis for cluster autoscaler:
- Examines cluster autoscaler configuration and behavior
- Provides visual interface for investigating autoscaler decisions
- Reviews scaling events and node group status
- Helps debug autoscaler-related issues
- Automatically handles permissions and browser launching
- Runs on http://127.0.0.1:8080
- See `scripts/README-CAMGI.md` for detailed documentation

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
Parses: `etcd_info/` (member_health.json, member_list.json, endpoint_status.json)
Output: etcd cluster health and member status

### scripts/analyze_pvs.py
Parses: `cluster-scoped-resources/core/persistentvolumes/`, `namespaces/*/core/persistentvolumeclaims.yaml`
Output: PV and PVC status tables

### scripts/analyze_ingress.py
Parses: `namespaces/openshift-ingress-operator/operator.openshift.io/ingresscontrollers/`, `namespaces/*/route.openshift.io/routes.yaml`
Output: IngressController status and Route tables

### scripts/analyze_servicelogs.py
Parses: `host_service_logs/masters/`, `host_service_logs/workers/`
Output: Systemd service log pattern summaries with occurrence counts

### scripts/analyze_machineconfigpools.py
Parses: `cluster-scoped-resources/machineconfiguration.openshift.io/machineconfigpools/`
Output: MachineConfigPool status table with update progress and degradation info

### scripts/analyze_pod_logs.py
Parses: `namespaces/*/pods/*/*/*/logs/current.log`
Output: Pod/container log pattern summaries with error and warning occurrence counts

### scripts/analyze_node_logs.py
Parses: `nodes/*/` (kubelet logs gzipped, sysinfo.log, dmesg)
Output: Node log pattern summaries with error and warning occurrence counts
Note: Kubelet logs are gzipped and extracted on-the-fly

### scripts/analyze_ovn_dbs.py
Parses: `network_logs/ovnk_database_store.tar.gz` (binary OVSDB files)
Output: Per-node OVN database analysis with logical switches, ports, ACLs, and routers
Prerequisites: `ovsdb-tool` from openvswitch package
Features: Standard analysis mode and custom query mode with OVSDB JSON queries

### scripts/run-camgi.sh
Launches: CAMGI (Cluster Autoscaler Must-Gather Inspector) web interface
Output: Interactive web UI at http://127.0.0.1:8080 for autoscaler analysis
Prerequisites: Podman/Docker (containerized) or `pip3 install okd-camgi` (local)
See: `scripts/README-CAMGI.md` for detailed documentation

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

### "Cluster autoscaler problems"
1. Run `run-camgi.sh <must-gather-path>` - launch interactive autoscaler inspector
2. Use CAMGI web UI to examine autoscaler configuration and scaling events
3. Review autoscaler decisions and node group status

### "Pod not getting IP address / OVN network issues"
1. Run `analyze_ovn_dbs.py <must-gather-path>` - check if pod exists in OVN
2. Search output for pod name to verify it has a logical switch port entry
3. Run `analyze_ovn_dbs.py --node <node>` - examine ACL rules on specific node
4. Check if ACLs are blocking traffic with unexpected match conditions

## Next Steps After Analysis

Based on findings, suggest:
- Examining specific pod logs in `namespaces/<ns>/pods/<pod>/<container>/logs/`
- Reviewing events in `namespaces/<ns>/core/events.yaml`
- Checking audit logs in `audit_logs/`
- Analyzing metrics data if available
- Looking at host service logs in `host_service_logs/`
