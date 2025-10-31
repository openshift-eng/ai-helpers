# Must-Gather Analyzer Plugin

Claude Code plugin for analyzing OpenShift must-gather diagnostic data.

## Overview

This plugin provides tools to analyze must-gather data collected from OpenShift clusters, displaying resource status in familiar `oc`-like format and identifying cluster issues.

## Features

### Skills

- **Must-Gather Analyzer** - Comprehensive analysis of cluster operators, pods, nodes, and network components
  - Parses YAML resources from must-gather dumps
  - Displays output similar to `oc get` commands
  - Identifies and categorizes issues
  - Provides actionable diagnostics

### Analysis Scripts

All scripts located in `plugins/must-gather/skills/must-gather-analyzer/scripts/`:

#### `analyze_clusterversion.py`
Analyzes cluster version, update status, and capabilities.

```bash
./analyze_clusterversion.py <must-gather-path>
```

Output format matches `oc get clusterversion`:
```
NAME       VERSION                                            AVAILABLE   PROGRESSING   SINCE   STATUS
version    4.20.0-0.okd-scos-2025-08-18-130459                            False         65d
```

Also provides detailed information:
- Cluster ID and version hash
- Current and desired versions
- Conditions (Available, Progressing, Failing, etc.)
- Update history
- Available updates
- Enabled capabilities

#### `analyze_clusteroperators.py`
Analyzes cluster operator status and health.

```bash
./analyze_clusteroperators.py <must-gather-path>
```

Output format matches `oc get clusteroperators`:
```
NAME                                       VERSION   AVAILABLE   PROGRESSING   DEGRADED   SINCE   MESSAGE
authentication                             4.18.26   True        False         False      149m
baremetal                                  4.18.26   True        False         False      169m
```

#### `analyze_pods.py`
Analyzes pod status across all namespaces.

```bash
# All pods in all namespaces
./analyze_pods.py <must-gather-path>

# Specific namespace
./analyze_pods.py <must-gather-path> --namespace openshift-etcd

# Only problematic pods
./analyze_pods.py <must-gather-path> --problems-only
```

Output format matches `oc get pods -A`:
```
NAMESPACE                              NAME                                    READY   STATUS             RESTARTS   AGE
openshift-kube-apiserver               kube-apiserver-master-0                 4/4     Running            0          5d
openshift-etcd                         etcd-master-1                           1/1     CrashLoopBackOff   15         2h
```

#### `analyze_nodes.py`
Analyzes node status and conditions.

```bash
# All nodes
./analyze_nodes.py <must-gather-path>

# Only nodes with issues
./analyze_nodes.py <must-gather-path> --problems-only
```

Output format matches `oc get nodes`:
```
NAME                                       STATUS                     ROLES          AGE     VERSION
master-0.example.com                       Ready                      master         10d     v1.27.0+1234
worker-1.example.com                       Ready,MemoryPressure       worker         10d     v1.27.0+1234
```

#### `analyze_network.py`
Analyzes network configuration and health.

```bash
./analyze_network.py <must-gather-path>
```

Shows:
- Network type (OVN-Kubernetes, OpenShift SDN)
- Network operator status
- OVN pod health
- PodNetworkConnectivityCheck results

#### `analyze_ovn_dbs.py`
Analyzes OVN Northbound and Southbound databases from clusters using `ovsdb-tool`.

```bash
# Standard analysis
./analyze_ovn_dbs.py <must-gather-path>

# Query mode (raw OVSDB queries)
./analyze_ovn_dbs.py <must-gather-path> --query '["OVN_Northbound", {...}]'
```

**Requirements:**
- `ovsdb-tool` must be installed (`openvswitch` package)
- Database files collected in `network_logs/ovnk_database_store.tar.gz`

**Output per node:**
```
================================================================================
Node: worker-node.internal
Pod:  ovnkube-node-79cbh
================================================================================
  Logical Switches:      4
  Logical Switch Ports:  55
  ACLs:                  7
  Logical Routers:       2

  POD LOGICAL SWITCH PORTS (43):
  NAMESPACE                                POD                                           IP
  ------------------------------------------------------------------------------------------------------------------------
  openshift-apiserver                      apiserver-7f4f77f688-s6t7b                    10.128.0.4
  openshift-authentication                 oauth-openshift-96688d9f8-v2l2j               10.128.0.6
  ...
```

**Features:**
- Automatically maps ovnkube pods to nodes by reading pod specifications
- Per-node logical network topology
- Filter analysis to specific nodes with `--node` flag
- **Query Mode**: Run custom OVSDB JSON queries for specific data extraction
- Claude can construct OVSDB queries based on natural language requests
- Logical switches and their ports
- Pod logical switch ports with namespace, pod name, and IP addresses
- Access Control Lists (ACLs) with priorities, directions, and match rules
- Logical routers and their ports

**Use Cases:**
- Verify pod network configuration and IP assignments
- Troubleshoot connectivity issues by reviewing ACL rules
- Understand logical network topology across zones
- Audit network policies translated to OVN ACLs

#### `analyze_events.py`
Analyzes cluster events sorted by last occurrence.

```bash
# Recent events (last 100)
./analyze_events.py <must-gather-path>

# Warning events only
./analyze_events.py <must-gather-path> --type Warning

# Events in specific namespace
./analyze_events.py <must-gather-path> --namespace openshift-etcd

# Show last 50 events
./analyze_events.py <must-gather-path> --count 50
```

Output format:
```
NAMESPACE                      LAST SEEN  TYPE       REASON                         OBJECT                                   MESSAGE
openshift-etcd                 64d        Warning    Unhealthy                      Pod/etcd-guard-ip-10-0-90-209            Readiness probe failed
openshift-kube-apiserver       64d        Normal     Started                        Pod/kube-apiserver-master-0              Started container
```

#### `analyze_etcd.py`
Analyzes etcd cluster health from etcd_info directory.

```bash
./analyze_etcd.py <must-gather-path>
```

Shows:
- Member health status
- Member list with IDs and URLs
- Endpoint status (leader, version, DB size)
- Quorum status and summary

Output includes:
```
ETCD CLUSTER SUMMARY
Total Members: 3
Healthy Members: 3/3
  ✅ All members healthy
  ✅ Quorum achieved (3/2)
```

#### `analyze_pvs.py`
Analyzes PersistentVolumes and PersistentVolumeClaims.

```bash
# All PVs and PVCs
./analyze_pvs.py <must-gather-path>

# PVCs in specific namespace
./analyze_pvs.py <must-gather-path> --namespace openshift-monitoring
```

Output format:
```
PERSISTENT VOLUMES
NAME                                               CAPACITY   ACCESS MODES         RECLAIM    STATUS     CLAIM
pvc-3d4a0119-b2f2-44fa-9b2f-b11c611c74f2           20Gi       ReadWriteOnce        Delete     Bound      openshift-monitoring/prometheus-data-pro

PERSISTENT VOLUME CLAIMS
NAMESPACE                      NAME                                STATUS     VOLUME                                         CAPACITY
openshift-monitoring           prometheus-data-prometheus-0        Bound      pvc-3d4a0119-b2f2-44fa-9b2f-b11c611c74f2       20Gi
```

### Slash Commands

#### `/must-gather:analyze [path] [component]`
Runs comprehensive analysis of must-gather data.

```
/must-gather:analyze ./must-gather.local.123456789
```

Executes all analysis scripts and provides:
- Executive summary of cluster health
- Critical issues and warnings
- Actionable recommendations
- Suggested logs to review

Can also analyze specific components:
```
/must-gather:analyze ./must-gather.local.123456789 ovn databases
```

#### `/must-gather:ovn-dbs [path] [--node <node-name>]`
Analyzes OVN databases from must-gather.

```
# Analyze all nodes
/must-gather:ovn-dbs ./must-gather.local.123456789

# Analyze specific node
/must-gather:ovn-dbs ./must-gather.local.123456789 --node ip-10-0-26-145

# Analyze worker nodes (partial match)
/must-gather:ovn-dbs ./must-gather.local.123456789 --node worker

# Run custom OVSDB query (Claude constructs the JSON)
/must-gather:ovn-dbs ./must-gather.local.123456789 --query '["OVN_Northbound", {"op":"select", "table":"ACL", "where":[["priority", ">", 1000]], "columns":["priority","match"]}]'
```

Provides detailed analysis of:
- Logical network topology per node (automatically mapped from pods)
- Pod logical switch ports with IPs
- ACL rules and priorities
- Logical routers and switches
- Node filtering with partial name matching

**Requirements:** `ovsdb-tool` installed

## Installation

### From Local Repository

If you're working in the must-gather repository:

1. The plugin is already available in `.claude-plugin/`
2. Claude Code will automatically detect project plugins

### Manual Installation

To use this plugin in other projects:

1. Copy the `.claude-plugin/` directory to your desired location
2. Add to Claude Code:
   ```bash
   /plugin marketplace add /path/to/.claude-plugin
   /plugin install must-gather-analyzer
   ```

## Usage Examples

### Analyzing Cluster Version

Ask Claude:
- "What version is this cluster running?"
- "Show me the cluster version"
- "What's the update status?"
- "What capabilities are enabled?"

### Analyzing Cluster Operators

Ask Claude:
- "Analyze the cluster operators in this must-gather"
- "Which operators are degraded?"
- "Show me operator status"

Claude will automatically use the Must-Gather Analyzer skill and run `analyze_clusteroperators.py`.

### Finding Pod Issues

Ask Claude:
- "What pods are failing in this must-gather?"
- "Show me crashlooping pods"
- "Analyze pods in openshift-etcd namespace"

### Analyzing Events

Ask Claude:
- "Show me warning events from this must-gather"
- "What events occurred in openshift-etcd namespace?"
- "Show me the last 50 events"

### Checking etcd Health

Ask Claude:
- "Check etcd cluster health"
- "What's the etcd member status?"
- "Is etcd quorum healthy?"

### Analyzing Storage

Ask Claude:
- "Show me PersistentVolumes and PVCs"
- "What storage resources exist?"
- "Are there any pending PVCs?"

### Complete Cluster Analysis

```
/analyze-mg ./must-gather.local.5464029130631179436
```

This runs all analysis scripts and provides comprehensive diagnostics.

## Requirements

- Python 3.6+
- PyYAML library (`pip install pyyaml`)

## Must-Gather Directory Structure

Expected directory structure from `oc adm must-gather` output:

```
must-gather.local.*/
├── cluster-scoped-resources/
│   ├── config.openshift.io/
│   │   └── clusteroperators/
│   └── core/
│       └── nodes/
├── namespaces/
│   └── <namespace>/
│       └── core/
│           └── pods/
└── network_logs/
```

## Development

### Adding New Analysis Scripts

1. Create script in `skills/must-gather-analyzer/scripts/`
2. Follow the output format pattern (matching `oc get` commands)
3. Update `SKILL.md` with usage instructions
4. Add to `/analyze-mg` command workflow

### Output Format Guidelines

All scripts should:
- Use tabular output matching `oc` command format
- Handle missing resources gracefully
- Print "No resources found." when appropriate
- Support common flags like `--namespace`, `--problems-only`

## Troubleshooting

### "No resources found"
- Verify must-gather path is correct
- Check that must-gather completed successfully
- Ensure directory structure matches expected format

### Scripts not executing
- Verify scripts are executable: `chmod +x scripts/*.py`
- Check Python 3 is available
- Install dependencies: `pip install pyyaml`

## Contributing

When adding new analysis capabilities:
1. Follow existing script patterns
2. Match `oc` command output format
3. Include error handling for missing data
4. Update this README with new features

## License

This plugin is part of the openshift/must-gather repository.
