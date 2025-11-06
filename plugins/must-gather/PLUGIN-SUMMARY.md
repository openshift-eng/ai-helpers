# Must-Gather Analyzer Plugin - Complete Summary

## What We Built

A comprehensive Claude Code plugin for analyzing OpenShift must-gather diagnostic data with 13 Python analysis scripts, automation tooling, and detailed documentation.

## Analysis Scripts (14 Total)

### 1. Cluster-Level Scripts (2)
- **analyze_clusterversion.py** - Cluster version, update status, capabilities
- **analyze_clusteroperators.py** - Operator health (Available, Progressing, Degraded)

### 2. Infrastructure Scripts (5)
- **analyze_nodes.py** - Node conditions, capacity, readiness
- **analyze_network.py** - Network operator, OVN/SDN health, connectivity checks
- **analyze_ingress.py** - IngressControllers and Routes status
- **analyze_machineconfigpools.py** - Node configuration rollout and update status
- **analyze_ovn_dbs.py** - OVN database analysis using ovsdb-tool (logical switches, pods, ACLs, routers)

### 3. Workload Scripts (2)
- **analyze_pods.py** - Pod health, restarts, crashes across namespaces
- **analyze_pvs.py** - PersistentVolumes and PersistentVolumeClaims

### 4. Critical Component Scripts (2)
- **analyze_etcd.py** - etcd cluster health, member status, quorum
- **analyze_events.py** - Cluster events with filtering and sorting

### 5. Log Analysis Scripts (3)
- **analyze_servicelogs.py** - Systemd service logs (kubelet, crio) with pattern analysis
- **analyze_pod_logs.py** - Container application logs with error pattern extraction
- **analyze_node_logs.py** - Node logs (kubelet, sysinfo, dmesg) with gzip support

## Key Features

### Pattern-Based Log Analysis
All log analysis scripts use intelligent pattern extraction and deduplication:
- Error patterns with occurrence counts: `[176x] Error syncing pod, skipping`
- Distinguishes between transient and persistent issues
- Top N pattern display to focus on most common problems
- Separate error and warning analysis

### oc-Like Output Format
All scripts mimic OpenShift CLI output:
```
NAME                 VERSION   AVAILABLE   PROGRESSING   DEGRADED
authentication       4.18.26   True        False         False
```

### Problem Filtering
Most scripts support `--problems-only` to reduce noise and focus on issues.

### Cross-Component Analysis
Scripts designed to work together for root cause investigation:
- Degraded operator → failing pods → node issues
- Network problems → OVN pods → ingress routes
- etcd issues → API slowness → operator timeouts

## Automation & Reporting

### Comprehensive Analysis Command
`.claude-plugin/commands/comprehensive-analysis.md`
- Systematic 5-phase analysis workflow
- Report generation template
- Cross-referencing guidelines
- Common issue patterns and investigation paths

### Automation Scripts
`scripts/run-comprehensive-analysis.sh`
- Runs all 14 scripts in systematic order
- Generates timestamped report file
- Color-coded output for readability
- Error handling and validation

`scripts/run-camgi.sh`
- Launches CAMGI (Cluster Autoscaler Must-Gather Inspector)
- Web-based interactive tool for autoscaler analysis
- Containerized execution with automatic browser opening
- Available via `/must-gather:camgi` slash command

## Documentation

### User Documentation
1. **README.md** - Main plugin documentation with all script descriptions
2. **QUICK-REFERENCE.md** - Command cheat sheet and common workflows
3. **SKILL.md** - Claude Code skill definition with usage instructions
4. **comprehensive-analysis.md** - Detailed analysis workflow and report template

### Integration
- **analyze-mg.md** - Slash command for quick analysis
- **comprehensive-analysis.md** - Command for detailed report generation
- **camgi.md** - Slash command for launching CAMGI web interface

## Usage Modes

### Mode 1: Individual Script Analysis
```bash
./analyze_clusteroperators.py /path/to/must-gather
./analyze_pods.py /path/to/must-gather --problems-only
./analyze_pod_logs.py /path/to/must-gather --namespace openshift-etcd
```

### Mode 2: Slash Commands (Claude Code)
```
/must-gather:analyze /path/to/must-gather
/must-gather:comprehensive-analysis /path/to/must-gather
/must-gather:camgi /path/to/must-gather
```

### Mode 3: Automation Script
```bash
./run-comprehensive-analysis.sh /path/to/must-gather report.txt
```

## Analysis Workflow (5 Phases)

### Phase 1: Cluster-Level Health
Foundation - identify system-wide issues
- Cluster version and update status
- Cluster operator health

### Phase 2: Infrastructure Health
Compute and network - underlying infrastructure
- Node conditions and capacity
- Network operator and connectivity
- Ingress and routing

### Phase 3: Workload Health
Applications and dependencies
- Pod status and failures
- Storage (PVs/PVCs)
- MachineConfigPool rollout

### Phase 4: Critical Components
Stability and events
- etcd cluster health
- Cluster events and timeline

### Phase 5: Detailed Diagnostics
Log analysis for root cause
- Service logs (systemd)
- Pod logs (containers)
- Node logs (kubelet)

## Report Structure

Generated reports include:
1. **Executive Summary** - Overall health assessment
2. **Critical Issues** - Prioritized by impact (P1, P2, P3)
3. **Warnings** - Items to monitor
4. **Root Cause Analysis** - Cross-referenced findings
5. **Error Pattern Analysis** - Across all log sources
6. **Recommendations** - Immediate, short-term, long-term actions
7. **Detailed Logs to Review** - Specific file paths
8. **Metrics and Statistics** - Resource counts and health percentages
9. **Next Steps** - Action items

## Design Principles

### 1. Pattern Over Volume
Focus on error patterns with occurrence counts rather than overwhelming users with thousands of individual log lines.

### 2. Kubernetes Context
Many errors are normal in eventually consistent systems - distinguish transient from persistent issues.

### 3. Cross-Reference Everything
Issues rarely exist in isolation - map relationships between operators, pods, nodes, and logs.

### 4. Actionable Insights
Provide "why" and "what to do", not just "what happened".

### 5. Familiar Format
Use oc-like output so OpenShift users immediately understand the data.

## Technical Highlights

### Gzip Handling
Node logs (kubelet) are gzipped - scripts extract on-the-fly without requiring manual decompression.

### Robust Parsing
- Handles redacted must-gather data gracefully
- Supports multiple must-gather directory structures
- Error handling for missing or corrupted files

### Pattern Extraction
Sophisticated regex-based error pattern extraction:
- Removes timestamps and noise
- Extracts meaningful error messages
- Deduplicates similar errors
- Counts occurrences

### Filtering Capabilities
- By namespace, pod name, node name
- By problem type (errors vs warnings)
- By resource state (problems only)
- By log type (kubelet, sysinfo, dmesg)

## Common Investigation Patterns

### Pattern 1: Degraded Operator
```
analyze_clusteroperators.py → analyze_pods.py --namespace →
analyze_pod_logs.py --namespace → analyze_events.py --namespace
```

### Pattern 2: Node NotReady
```
analyze_nodes.py → analyze_pods.py →
analyze_node_logs.py --node → analyze_servicelogs.py
```

### Pattern 3: Pod CrashLoopBackOff
```
analyze_pods.py --problems-only → analyze_pod_logs.py --pod →
analyze_events.py --namespace → analyze_pvs.py --namespace
```

### Pattern 4: Network Issues
```
analyze_network.py → analyze_pods.py --namespace openshift-ovn-kubernetes →
analyze_pod_logs.py --namespace openshift-ovn-kubernetes →
analyze_ingress.py --routes --problems-only →
analyze_ovn_dbs.py --node <node>  # Deep OVN database analysis
```

### Pattern 5: etcd Problems
```
analyze_etcd.py → analyze_pods.py --namespace openshift-etcd →
analyze_pod_logs.py --namespace openshift-etcd → analyze_nodes.py
```

## Files Created/Modified

### Analysis Scripts (14)
```
skills/must-gather-analyzer/scripts/
├── analyze_clusterversion.py
├── analyze_clusteroperators.py
├── analyze_pods.py
├── analyze_nodes.py
├── analyze_network.py
├── analyze_events.py
├── analyze_etcd.py
├── analyze_pvs.py
├── analyze_ingress.py
├── analyze_servicelogs.py
├── analyze_machineconfigpools.py
├── analyze_pod_logs.py
├── analyze_node_logs.py
└── analyze_ovn_dbs.py
```

### Automation
```
skills/must-gather-analyzer/scripts/
└── run-comprehensive-analysis.sh
```

### Commands
```
commands/
├── analyze-mg.md
├── comprehensive-analysis.md
├── camgi.md
└── ovn-dbs.md
```

### Documentation
```
.
├── README.md (updated)
├── PLUGIN-SUMMARY.md (this file)
skills/must-gather-analyzer/
├── SKILL.md (updated)
└── QUICK-REFERENCE.md
```

## Example Output

### Script Output
```
================================================================================
SUMMARY: 25/28 operators healthy
  ⚠️  3 operators with issues
  🔄 1 progressing
  ❌ 2 degraded
================================================================================

NAME                           VERSION   AVAILABLE   PROGRESSING   DEGRADED
authentication                 4.18.26   True        False         False
ingress                        4.18.26   True        False         True
```

### Pattern Analysis
```
ERROR PATTERNS (755 total occurrences):
1. [176x] Error syncing pod, skipping
2. [112x] Error getting the current node from lister
3. [90x] DeleteContainer returned error
4. [75x] ContainerStatus from runtime service failed
... and 253 more patterns (286 occurrences)
```

## Script Statistics

- **Total Scripts**: 14 analysis scripts + 2 automation scripts (run-comprehensive-analysis.sh, run-camgi.sh)
- **Total Lines of Code**: ~5,000 lines of Python
- **Documentation Pages**: 5 comprehensive documents
- **Supported Filters**: 15+ command-line options across scripts
- **Error Pattern Extraction**: Sophisticated regex-based analysis
- **Data Sources**: YAML, JSON, plain text logs, gzipped logs, binary OVSDB files

## Dependencies

- Python 3.6+
- PyYAML library
- Standard Python libraries (pathlib, argparse, re, gzip, etc.)
- ovsdb-tool (from openvswitch package) - required for analyze_ovn_dbs.py

## Future Enhancements

Potential additions:
1. JSON/HTML report output formats
2. Historical comparison (compare multiple must-gathers)
3. Automated remediation suggestions
4. Integration with Red Hat support case systems
5. Prometheus metrics analysis (if included in must-gather)
6. Advanced root cause correlation using ML
7. Interactive web UI for report browsing

## Summary

This plugin represents a comprehensive solution for OpenShift must-gather analysis, providing:
- **Systematic workflow** from high-level to detailed diagnostics
- **Pattern-based insights** that filter noise and highlight issues
- **Cross-component correlation** to identify root causes
- **Familiar output format** matching OpenShift CLI tools
- **Flexible usage modes** from individual scripts to full automation
- **Detailed documentation** for both users and developers

The plugin transforms must-gather analysis from manual log digging into a structured, efficient diagnostic process that produces actionable insights and clear recommendations.
