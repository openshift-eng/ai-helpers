# Must-Gather Analyzer Plugin

Claude Code plugin for analyzing OpenShift must-gather diagnostic data.

## Overview

This plugin provides tools to analyze must-gather data collected from OpenShift clusters, displaying resource status in familiar `oc`-like format and identifying cluster issues.

**Quick Start**: See [QUICK-REFERENCE.md](skills/must-gather-analyzer/QUICK-REFERENCE.md) for a command cheat sheet.

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

#### `analyze_ingress.py`
Analyzes IngressControllers and Routes.

```bash
# Analyze IngressControllers
./analyze_ingress.py <must-gather-path> --ingresscontrollers

# Analyze Routes (all namespaces)
./analyze_ingress.py <must-gather-path> --routes

# Routes in specific namespace
./analyze_ingress.py <must-gather-path> --routes --namespace openshift-console

# Only routes with problems
./analyze_ingress.py <must-gather-path> --routes --problems-only
```

Output format:
```
NAME                 DOMAIN                                                       REPLICAS   AVAILABLE   PROGRESSING   DEGRADED   TYPE
default              apps.ci-op-54xcy53v-3c4c5.example.com                        2/2        True        False         False      LoadBalancerService

NAMESPACE                      NAME                                     HOST                                                                             ADMITTED   AGE
openshift-console              console                                  console-openshift-console.apps.example.com                                       True       1d
openshift-authentication       oauth-openshift                          oauth-openshift.apps.example.com                                                 True       1d
```

#### `analyze_servicelogs.py`
Analyzes host service logs from systemd services.

**Note**: Host service logs (systemd) are typically collected only from master nodes in must-gather data.

```bash
# All service logs
./analyze_servicelogs.py <must-gather-path>

# Filter by service name
./analyze_servicelogs.py <must-gather-path> --service kubelet

# Only services with errors
./analyze_servicelogs.py <must-gather-path> --errors-only

# Show warnings in addition to errors
./analyze_servicelogs.py <must-gather-path> --show-warnings
```

Output format:
```
SERVICE                                  ERRORS     WARNINGS   STATUS
======================================================================
kubelet (masters)                        9271       14         ⚠️  HAS ERRORS
crio (masters)                           21         656        ⚠️  HAS ERRORS

ERROR PATTERNS (9271 total occurrences):
1. [712x] DeleteContainer returned error
2. [550x] Error syncing pod, skipping
3. [512x] ContainerStatus from runtime service failed
```

#### `analyze_machineconfigpools.py`
Analyzes MachineConfigPools to identify node update and rollout issues.

```bash
# Show all MachineConfigPools
./analyze_machineconfigpools.py <must-gather-path>

# Show only pools with problems
./analyze_machineconfigpools.py <must-gather-path> --problems-only
```

Output format:
```
NAME                 CONFIG                                             UPDATED   UPDATING   DEGRADED   MACHINECOUNT   READYMACHINECOUNT   UPDATEDMACHINECOUNT
master               rendered-master-abc123                             True      False      False      3              3                   3
worker               rendered-worker-def456                             True      False      False      3              3                   3
```

#### `analyze_pod_logs.py`
Analyzes pod/container logs to identify error patterns.

```bash
# Analyze all pod logs with errors
./analyze_pod_logs.py <must-gather-path>

# Analyze logs for a specific namespace
./analyze_pod_logs.py <must-gather-path> --namespace openshift-etcd

# Analyze logs for a specific pod
./analyze_pod_logs.py <must-gather-path> --pod etcd

# Show top 5 error patterns
./analyze_pod_logs.py <must-gather-path> --top 5
```

Output format:
```
NAMESPACE                      POD                                                CONTAINER                                ERRORS     WARNINGS   LINES
openshift-etcd                 etcd-ip-10-0-45-79.us-west-1.compute.internal      etcd                                     76         0          346

ERROR PATTERNS (76 total occurrences):
1. [44x] error
2. [15x] failed to reach the peer URL
3. [15x] failed to get version
```

#### `analyze_node_logs.py`
Analyzes node logs including kubelet, sysinfo, and dmesg logs.

**Note**: Kubelet logs are gzipped and will be extracted on-the-fly.

```bash
# Analyze all node logs
./analyze_node_logs.py <must-gather-path>

# Analyze logs for a specific node
./analyze_node_logs.py <must-gather-path> --node ip-10-0-45-79

# Analyze only kubelet logs
./analyze_node_logs.py <must-gather-path> --log-type kubelet

# Skip kubelet logs (avoids extracting gzipped files)
./analyze_node_logs.py <must-gather-path> --skip-kubelet

# Show top 5 error patterns
./analyze_node_logs.py <must-gather-path> --top 5

# Show warnings in addition to errors
./analyze_node_logs.py <must-gather-path> --show-warnings

# Show only nodes with errors
./analyze_node_logs.py <must-gather-path> --errors-only
```

Output format:
```
NODE                                          LOG TYPE        ERRORS     WARNINGS   LINES
ip-10-0-45-79.us-west-1.compute.internal      kubelet         755        17         11755
ip-10-0-45-79.us-west-1.compute.internal      sysinfo         1          1          3357

ERROR PATTERNS (755 total occurrences):
1. [176x] Error syncing pod, skipping
2. [112x] Error getting the current node from lister
3. [90x] DeleteContainer returned error
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

#### `/comprehensive-analysis [path]`
Performs detailed comprehensive analysis with full report generation.

```
/comprehensive-analysis ./must-gather.local.123456789
```

Executes a systematic 5-phase analysis:
- **Phase 1**: Cluster-level health (version, operators)
- **Phase 2**: Infrastructure health (nodes, network, ingress)
- **Phase 3**: Workload health (pods, storage, MachineConfigPools)
- **Phase 4**: Critical components (etcd, events)
- **Phase 5**: Detailed diagnostics (service logs, pod logs, node logs)

Generates a comprehensive report with:
- Executive summary with health assessment
- Critical issues prioritized by impact
- Root cause analysis
- Error pattern analysis across all log sources
- Detailed recommendations
- Cross-referenced findings

See `/home/psundara/ws/src/github.com/openshift/must-gather/.claude-plugin/commands/comprehensive-analysis.md` for full details.

#### Automation Script

You can also run the automated analysis script directly:

```bash
./scripts/run-comprehensive-analysis.sh <must-gather-path> [output-file]
```

This generates a timestamped report file with complete analysis output.

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

### Analyzing Ingress and Routes

Ask Claude:
- "Check the IngressController status"
- "Show me all routes in the cluster"
- "Are there any routes not admitted?"
- "What's the ingress configuration?"

### Analyzing Service Logs

Ask Claude:
- "Show me error patterns in the service logs"
- "Check kubelet logs for errors"
- "What service errors occurred on the masters?"
- "Analyze systemd service logs"

### Analyzing MachineConfigPools

Ask Claude:
- "Check the MachineConfigPool status"
- "Are there any stuck node updates?"
- "Show me the machine config pool rollout status"
- "Check if nodes are updating properly"

### Analyzing Pod Logs

Ask Claude:
- "Analyze pod logs for errors"
- "Check etcd pod logs"
- "Show error patterns in openshift-apiserver pods"
- "What errors are in the container logs?"
- "Show me pod log errors in openshift-etcd namespace"

### Analyzing Node Logs

Ask Claude:
- "Analyze node logs for errors"
- "Check kubelet logs on all nodes"
- "Show error patterns in node logs"
- "What kubelet errors occurred?"
- "Analyze node logs for ip-10-0-45-79"

### Complete Cluster Analysis

For a quick overview:
```
/analyze-mg ./must-gather.local.5464029130631179436
```

For detailed comprehensive analysis with full report:
```
/comprehensive-analysis ./must-gather.local.5464029130631179436
```

Or use the automation script:
```bash
cd .claude-plugin/skills/must-gather-analyzer/scripts
./run-comprehensive-analysis.sh /path/to/must-gather
```

This runs all 13 analysis scripts in systematic order and generates a detailed report with:
- Executive summary and health assessment
- Critical issues prioritized by severity
- Root cause analysis with cross-referenced findings
- Error pattern analysis from all log sources
- Actionable recommendations for remediation
- Suggested logs for detailed investigation

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
