# Node Plugin

Kubernetes and OpenShift node health monitoring and diagnostics.

## Overview

The Node plugin provides comprehensive health checking and diagnostic capabilities for Kubernetes and OpenShift cluster nodes. It automates the inspection of node-level components including kubelet, CRI-O container runtime, system resources, and node conditions to ensure nodes are functioning properly.

## Commands

### `/node:cluster-node-health-check`

Perform comprehensive health check on cluster nodes and report kubelet, CRI-O, and node-level issues.

**Usage:**
```bash
/node:cluster-node-health-check [--node <node-name>] [--verbose] [--output-format json|text]
```

**Arguments:**
- `--node <node-name>` (optional): Name of a specific node to check. If not provided, checks all nodes in the cluster.
- `--verbose` (optional): Enable detailed output with additional context, including resource-level details, warning conditions, and remediation suggestions.
- `--output-format` (optional): Output format for results (`text` or `json`). Defaults to `text`.

**Examples:**

Check all nodes in the cluster:
```bash
/node:cluster-node-health-check
```

Check a specific node:
```bash
/node:cluster-node-health-check --node worker-1
```

Verbose output with detailed diagnostics:
```bash
/node:cluster-node-health-check --verbose
```

JSON output for automation:
```bash
/node:cluster-node-health-check --output-format json
```

**What it checks:**

1. **Node Status and Conditions**
   - Ready status
   - MemoryPressure, DiskPressure, PIDPressure
   - NetworkUnavailable condition
   - Node taints and scheduling constraints

2. **Kubelet Service Health**
   - Service status and restart counts
   - Certificate validity
   - Configuration issues

3. **CRI-O Container Runtime**
   - Runtime service status
   - Container operation errors
   - Version compatibility

4. **Resource Utilization**
   - CPU and memory allocation
   - Disk space usage
   - Pod count vs capacity
   - Ephemeral storage

5. **System Services**
   - Critical daemon status (kubelet, crio)
   - Failed systemd units

6. **Kernel Parameters**
   - Key sysctl settings for Kubernetes
   - SELinux status

7. **Pod Health on Nodes**
   - Running, pending, and failed pods
   - High restart counts
   - Resource pressure impact

8. **Recent Events**
   - Warning events for nodes
   - Pod events on nodes

**Output:**

The command provides:
- Overall health status (Healthy ✅ / Warning ⚠️ / Critical ❌)
- Detailed findings for each node
- Specific issues with severity levels
- Impact assessment
- Recommended remediation actions
- Diagnostic commands for further investigation

See [commands/cluster-node-health-check.md](commands/cluster-node-health-check.md) for detailed documentation.

## Prerequisites

- **Kubernetes/OpenShift CLI**: Either `oc` or `kubectl` must be installed
- **Active cluster connection**: Must be connected to a running cluster
- **Sufficient permissions**: Read access to nodes and pods, ability to create debug pods for node-level inspection

## Use Cases

- **Pre-deployment validation**: Verify node health before deploying applications
- **Troubleshooting**: Diagnose node-related issues affecting workload performance
- **Capacity planning**: Understand resource utilization across nodes
- **Proactive monitoring**: Regular health checks to catch issues early
- **Post-upgrade validation**: Verify node health after cluster upgrades
- **CI/CD integration**: Automated node health verification in pipelines

## Common Issues Detected

The plugin can detect and report:

- Nodes in NotReady state
- Kubelet service failures or frequent restarts
- CRI-O runtime errors
- Memory or disk pressure conditions
- Network unavailability
- High pod restart counts
- Resource exhaustion (CPU, memory, disk)
- Failed system services
- Certificate expiration warnings
- Scheduling constraints (taints, labels)

## Installation

### From Marketplace

```bash
# Add the ai-helpers marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the node plugin
/plugin install node@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Link to Claude Code plugins directory
ln -s $(pwd)/ai-helpers/plugins/node ~/.claude/plugins/node
```

## Contributing

Contributions are welcome! Please see the main [CLAUDE.md](../../CLAUDE.md) for plugin development guidelines.

## License

Apache License 2.0 - See [LICENSE](../../LICENSE) for details.
