# Node Plugin

Kubernetes and OpenShift node health monitoring and diagnostics.

## Overview

The Node plugin provides comprehensive health checking and diagnostic capabilities for Kubernetes and OpenShift cluster nodes. It automates the inspection of node-level components including kubelet, CRI-O container runtime, system resources, and node conditions to ensure nodes are functioning properly. It also provides network packet capture capabilities for troubleshooting connectivity and performance issues.

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

### `/node:tcpdump`

SSH into OpenShift node and capture network traffic using tcpdump on specified or all interfaces.

**Usage:**
```bash
/node:tcpdump <node-name> [--interface <interface>] [--filter <tcpdump-filter>] [--duration <seconds>] [--count <packets>] [--tcpdump-options <options>] [--output <filename>]
```

**Arguments:**
- `<node-name>` (required): The name of the OpenShift node to capture traffic from
- `--interface <interface>` (optional): Network interface to capture packets from. Default: `any` (all interfaces)
- `--filter <tcpdump-filter>` (optional): tcpdump filter expression for targeted capture. Default: no filter
- `--duration <seconds>` (optional): Capture duration in seconds. Default: 60
- `--count <packets>` (optional): Maximum number of packets to capture. Default: unlimited
- `--tcpdump-options <options>` (optional): Additional tcpdump options like `"-n -s 0"` (no name resolution, full packets)
- `--output <filename>` (optional): Output filename for the capture file. Default: auto-generated

**Examples:**

Capture all traffic on all interfaces for 60 seconds:
```bash
/node:tcpdump ip-10-0-143-232.ec2.internal
```

Capture HTTPS traffic to API server for 2 minutes:
```bash
/node:tcpdump worker-0 --filter "tcp port 6443" --duration 120
```

Capture DNS queries:
```bash
/node:tcpdump worker-0 --filter "udp port 53" --count 100
```

Capture traffic on specific interface:
```bash
/node:tcpdump worker-0 --interface eth0 --duration 300
```

Capture pod network traffic:
```bash
/node:tcpdump worker-0 --filter "net 10.128.0.0/14" --interface ovn-k8s-mp0
```

Capture with full packet size and no name resolution:
```bash
/node:tcpdump worker-0 --tcpdump-options "-n -s 0" --filter "port 443"
```

**What it captures:**

- Network packets on node interfaces (eth0, br-ex, ovn-k8s-mp0, any, etc.)
- Filtered traffic based on IP, port, protocol, or custom tcpdump filters
- Saves capture to local .pcap file for analysis with Wireshark or tcpdump

**Common use cases:**

- Debug pod-to-pod networking issues
- Analyze traffic between nodes and external services
- Troubleshoot DNS resolution problems
- Investigate network performance bottlenecks
- Debug load balancer or ingress connectivity
- Analyze CNI plugin behavior (OVN-Kubernetes, etc.)

**Output:**

The command creates a `.pcap` file at `.work/node-tcpdump/<output-filename>.pcap` that can be analyzed with:
- Wireshark (GUI): `wireshark .work/node-tcpdump/<file>.pcap`
- tcpdump (CLI): `tcpdump -r .work/node-tcpdump/<file>.pcap`

See [commands/tcpdump.md](commands/tcpdump.md) for detailed documentation.

## Prerequisites

- **Kubernetes/OpenShift CLI**: Either `oc` or `kubectl` must be installed
- **Active cluster connection**: Must be connected to a running cluster
- **Sufficient permissions**: Read access to nodes and pods, ability to create debug pods for node-level inspection

## Use Cases

- **Pre-deployment validation**: Verify node health before deploying applications
- **Troubleshooting**: Diagnose node-related issues affecting workload performance
- **Network debugging**: Capture and analyze network traffic for connectivity issues
- **Capacity planning**: Understand resource utilization across nodes
- **Proactive monitoring**: Regular health checks to catch issues early
- **Post-upgrade validation**: Verify node health after cluster upgrades
- **Security analysis**: Capture network traffic for security investigation
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
