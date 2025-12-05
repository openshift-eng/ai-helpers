# Must-Gather Plugin

A comprehensive plugin for analyzing OpenShift must-gather data, providing detailed reports on cluster health, networking, and component status.

## Commands

### `/must-gather:analyze`
General must-gather analysis command that provides an overview of cluster health and common issues.

### `/must-gather:ovn-dbs`
Analyze OVN Northbound and Southbound databases from must-gather data. Shows logical network topology, switches, ports, ACLs, and routers per node.

**Usage:**
```
/must-gather:ovn-dbs [must-gather-path] [--node <node-name>] [--query <json>]
```

### `/must-gather:multus`
Analyze Multus CNI configuration and multi-networked pods from must-gather data. Generates a comprehensive HTML report and failure analysis.

**Usage:**
```
/must-gather:multus [must-gather-path] [output-html-path]
```

**Features:**
- Cluster information and health analysis
- Multus infrastructure status (DaemonSets, Deployments, Pods)
- NetworkAttachmentDefinition (NAD) analysis
- Multi-networked pod detection and analysis
- CNI configuration details
- Visual HTML report with tabs for easy navigation
- Separate failure analysis output

**Example:**
```
/must-gather:multus /path/to/must-gather.tar /path/to/output/report.html
```

**Output:**
1. **HTML Report**: Comprehensive visual report with cluster info, Multus status, NADs, and multi-networked pods
2. **Failure Analysis**: Text file listing detected issues with severity and recommendations

## Prerequisites

- Python 3.6 or later
- `pyyaml` module: `pip3 install pyyaml`
- `ovsdb-tool` (for ovn-dbs command): `sudo dnf install openvswitch`

## Skills

The plugin includes several helper scripts in `skills/must-gather-analyzer/scripts/`:

- `analyze_clusteroperators.py` - Analyze cluster operator status
- `analyze_clusterversion.py` - Analyze cluster version information
- `analyze_etcd.py` - Analyze etcd health and performance
- `analyze_events.py` - Analyze cluster events
- `analyze_network.py` - Analyze network configuration
- `analyze_nodes.py` - Analyze node health
- `analyze_ovn_dbs.py` - Analyze OVN databases
- `analyze_pods.py` - Analyze pod status
- `analyze_prometheus.py` - Analyze Prometheus metrics
- `analyze_pvs.py` - Analyze persistent volumes
- `analyze_multus.py` - Analyze Multus CNI configuration

## Use Cases

1. **Post-Mortem Analysis**: Analyze must-gather data from failed CI jobs or production incidents
2. **Health Checks**: Verify cluster and component health status
3. **Network Troubleshooting**: Diagnose Multus CNI and OVN networking issues
4. **Documentation**: Generate comprehensive reports for sharing with team members
5. **Audit**: Review NetworkAttachmentDefinitions and multi-networked pod configurations

## Examples

### Analyze Multus from Prow CI Job
```
/must-gather:multus /path/to/prow-job/gather-must-gather/artifacts/ /path/to/multus-report.html
```

### Analyze OVN Databases for Specific Node
```
/must-gather:ovn-dbs /path/to/must-gather/ --node master-0
```

### General Must-Gather Analysis
```
/must-gather:analyze /path/to/must-gather/
```

## Output Examples

### Multus HTML Report Sections
1. **Cluster Information**: Version, nodes, network configuration
2. **Cluster Health**: Operator status and overall health
3. **Multus CNI Summary**: DaemonSets, Deployments, and pod status
4. **Network Attachment Definitions**: NAD configurations by namespace
5. **Multi-Networked Pods**: Pods with additional network interfaces

### Failure Analysis Output
```
Multus CNI Failure Analysis
================================================================================

Found 2 issue(s):

1. WARNING: DaemonSet 'multus' has 5/6 pods ready
2. ERROR: Multus pod 'multus-abc123' is in CrashLoopBackOff state

================================================================================
Analysis completed: 2025-12-04 11:29:27
```

## Contributing

When adding new analysis capabilities:

1. Create a new command file in `commands/`
2. Add helper scripts to `skills/must-gather-analyzer/scripts/`
3. Follow the existing command structure and documentation format
4. Include comprehensive error handling
5. Test with real must-gather data

## Support

For issues or feature requests, please refer to the main ai-helpers repository.
