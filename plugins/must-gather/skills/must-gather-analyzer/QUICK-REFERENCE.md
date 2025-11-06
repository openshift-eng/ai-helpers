# Must-Gather Analyzer - Quick Reference

## All Available Scripts

### Cluster-Level Analysis
```bash
# Cluster version and update status
./analyze_clusterversion.py <must-gather-path>

# Cluster operator health
./analyze_clusteroperators.py <must-gather-path>
```

### Infrastructure Analysis
```bash
# Node status and conditions
./analyze_nodes.py <must-gather-path>
./analyze_nodes.py <must-gather-path> --problems-only

# Network health (OVN/SDN)
./analyze_network.py <must-gather-path>

# OVN database analysis (requires ovsdb-tool)
./analyze_ovn_dbs.py <must-gather-path>
./analyze_ovn_dbs.py <must-gather-path> --node <node-name>
./analyze_ovn_dbs.py <must-gather-path> --query '<ovsdb-json-query>'

# Ingress and routes
./analyze_ingress.py <must-gather-path> --ingresscontrollers
./analyze_ingress.py <must-gather-path> --routes
./analyze_ingress.py <must-gather-path> --routes --problems-only
```

### Workload Analysis
```bash
# Pod status
./analyze_pods.py <must-gather-path>
./analyze_pods.py <must-gather-path> --namespace <namespace>
./analyze_pods.py <must-gather-path> --problems-only

# Storage (PVs/PVCs)
./analyze_pvs.py <must-gather-path>
./analyze_pvs.py <must-gather-path> --namespace <namespace>

# MachineConfigPools (node updates)
./analyze_machineconfigpools.py <must-gather-path>
./analyze_machineconfigpools.py <must-gather-path> --problems-only
```

### Critical Components
```bash
# etcd cluster health
./analyze_etcd.py <must-gather-path>

# Cluster events
./analyze_events.py <must-gather-path>
./analyze_events.py <must-gather-path> --type Warning
./analyze_events.py <must-gather-path> --namespace <namespace>
./analyze_events.py <must-gather-path> --count 50
```

### Log Analysis
```bash
# Service logs (systemd - masters only)
./analyze_servicelogs.py <must-gather-path>
./analyze_servicelogs.py <must-gather-path> --service kubelet
./analyze_servicelogs.py <must-gather-path> --errors-only

# Pod logs (container logs)
./analyze_pod_logs.py <must-gather-path>
./analyze_pod_logs.py <must-gather-path> --namespace <namespace>
./analyze_pod_logs.py <must-gather-path> --pod <pod-name>
./analyze_pod_logs.py <must-gather-path> --errors-only --top 5

# Node logs (kubelet, sysinfo, dmesg)
./analyze_node_logs.py <must-gather-path>
./analyze_node_logs.py <must-gather-path> --node <node-name>
./analyze_node_logs.py <must-gather-path> --log-type kubelet
./analyze_node_logs.py <must-gather-path> --skip-kubelet
./analyze_node_logs.py <must-gather-path> --errors-only --top 5
```

### Comprehensive Analysis
```bash
# Run all scripts and generate report
./run-comprehensive-analysis.sh <must-gather-path>
./run-comprehensive-analysis.sh <must-gather-path> my-report.txt
```

### Specialized Tools
```bash
# CAMGI - Cluster Autoscaler Must-Gather Inspector (Web UI)
./run-camgi.sh <must-gather-path>     # Start CAMGI web interface
./run-camgi.sh stop                    # Stop CAMGI containers
```

## Common Flags

- `--problems-only` - Show only resources with issues
- `--errors-only` - Show only logs/resources with errors
- `--namespace <ns>` - Filter by namespace
- `--show-warnings` - Include warning patterns in output
- `--top N` - Show top N error patterns (default: 10)
- `--count N` - Limit number of results

## Quick Investigation Workflows

### "Cluster is degraded"
```bash
./analyze_clusteroperators.py <mg-path>           # Find degraded operator
./analyze_pods.py <mg-path> --namespace <ns>      # Check operator pods
./analyze_pod_logs.py <mg-path> --namespace <ns>  # Check logs
./analyze_events.py <mg-path> --namespace <ns>    # Check events
```

### "Pods are failing"
```bash
./analyze_pods.py <mg-path> --problems-only       # Find failing pods
./analyze_nodes.py <mg-path>                       # Check node health
./analyze_pod_logs.py <mg-path> --errors-only     # Check pod logs
./analyze_events.py <mg-path> --type Warning      # Check events
```

### "Node issues"
```bash
./analyze_nodes.py <mg-path> --problems-only      # Find problem nodes
./analyze_pods.py <mg-path>                        # See affected pods
./analyze_node_logs.py <mg-path> --node <node>   # Check kubelet logs
./analyze_servicelogs.py <mg-path> --errors-only  # Check systemd logs
```

### "Network problems"
```bash
./analyze_network.py <mg-path>                    # Check network operator
./analyze_pods.py <mg-path> --namespace openshift-ovn-kubernetes
./analyze_pod_logs.py <mg-path> --namespace openshift-ovn-kubernetes
./analyze_ingress.py <mg-path> --routes --problems-only
./analyze_ovn_dbs.py <mg-path> --node <node>      # Deep OVN database analysis
```

### "etcd issues"
```bash
./analyze_etcd.py <mg-path>                       # Check etcd health
./analyze_pods.py <mg-path> --namespace openshift-etcd
./analyze_pod_logs.py <mg-path> --namespace openshift-etcd
./analyze_nodes.py <mg-path>                       # Check master nodes
```

### "Update/upgrade stuck"
```bash
./analyze_clusterversion.py <mg-path>             # Check update status
./analyze_machineconfigpools.py <mg-path>        # Check node rollout
./analyze_clusteroperators.py <mg-path>           # Check progressing
./analyze_events.py <mg-path> --type Warning     # Check events
```

### "Cluster autoscaler issues"
```bash
./run-camgi.sh <mg-path>                          # Launch CAMGI web UI
# Or use slash command:
/must-gather:camgi <path>                         # Interactive autoscaler analysis
```

## Slash Commands (Claude Code)

```
/must-gather:analyze <path>                 # Quick comprehensive analysis
/must-gather:comprehensive-analysis <path>  # Detailed report generation
/must-gather:camgi <path>                   # Launch CAMGI web interface for cluster autoscaler analysis
/must-gather:camgi stop                     # Stop CAMGI containers
/must-gather:ovn-dbs <path>                 # Analyze OVN databases (requires ovsdb-tool)
/must-gather:ovn-dbs <path> --node <name>   # Analyze OVN database for specific node
```

## Output Format Guide

### Emoji Indicators
- ✅ Healthy / Normal
- ⚠️  Warning / Issues detected
- ❌ Critical / Failed
- 🔄 Progressing / Updating

### Pattern Format
```
[176x] Error message here
```
- Number = occurrence count
- Higher count = more significant

### Summary Format
```
SUMMARY: X/Y resources healthy
  ⚠️  N resources with issues
  ❌ M critical problems
```

## Tips

1. **Start broad, go deep**: Cluster → Infrastructure → Workloads → Logs
2. **Cross-reference**: Match issues across scripts (degraded operator → failing pod → node issue)
3. **Focus on patterns**: High occurrence counts indicate systematic issues
4. **Check timing**: Use events to establish timeline
5. **Context matters**: Many errors are transient in Kubernetes
6. **Use --problems-only**: Reduce noise and focus on issues
7. **Top N patterns**: Use --top 5 for quick overview of most common errors

## Script Locations

All scripts located in:
```
.claude-plugin/skills/must-gather-analyzer/scripts/
```

## Documentation

- Full guide: `.claude-plugin/README.md`
- Skill details: `.claude-plugin/skills/must-gather-analyzer/SKILL.md`
- Comprehensive analysis: `.claude-plugin/commands/comprehensive-analysis.md`
- This reference: `.claude-plugin/skills/must-gather-analyzer/QUICK-REFERENCE.md`
