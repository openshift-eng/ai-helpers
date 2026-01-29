# Agent-Gather Plugin

Claude Code plugin for collecting and analyzing diagnostic data from OpenShift agent-based installer deployments.

## Overview

This plugin provides tools to collect and analyze agent-gather data from OpenShift clusters deployed using the agent-based installer. It helps troubleshoot installation failures that occur before API services are available.

- `/agent-gather:collect`: collect diagnostic data from agent-based installer nodes
- `/agent-gather:decode-journal`: decode journal export files to human-readable format
- `/agent-gather:analyze`: analyze agent-gather archives for common issues

## Features

### What is agent-gather?

Agent-gather is a diagnostic data collection tool specifically designed for agent-based installer deployments. Unlike `must-gather` which requires a running cluster with API access, agent-gather works during the installation phase before the cluster API is available.

### When to Use

Use agent-gather when experiencing:
- Bootstrap failures during agent-based installation
- Installation hanging or not progressing
- Node registration issues
- Pre-API installation errors
- Agent-based installer troubleshooting

### Data Collected

Agent-gather collects:
- System journal logs (in export format)
- Assisted-service logs and database data
- Agent-tui logs
- Host and cluster validation information
- Certificate data
- Installation configuration details

**Security**: Pull secrets and platform passwords are automatically redacted.

## Slash Commands

### `/agent-gather:collect <node-ip> [--output path] [--all-nodes]`
Collects diagnostic data from agent-based installer nodes.

```
# Collect from rendezvous host
/agent-gather:collect 192.168.1.100

# Collect from multiple nodes
/agent-gather:collect 192.168.1.100 --all-nodes

# Specify output location
/agent-gather:collect 192.168.1.100 --output /tmp/diagnostics/
```

Collects diagnostic information including:
- System journals
- Installation logs
- Service status
- Configuration files

Requires:
- SSH access to the node(s)
- SSH key or credentials for `core` user
- Network connectivity to node IP addresses

Output is saved to `agent-gather.tar.xz` by default. After collection, you can use `/agent-gather:decode-journal` to extract readable logs.

### `/agent-gather:decode-journal [path] [--service name] [--priority level]`
Decodes systemd journal export files to human-readable format.

```
# Decode journal from current directory
/agent-gather:decode-journal

# Decode journal from specific path
/agent-gather:decode-journal /tmp/agent-gather/journal.export

# Decode and filter by service
/agent-gather:decode-journal --service assisted-service

# Filter by log priority
/agent-gather:decode-journal --priority err
```

Converts binary journal export format to readable text logs using `systemd-journal-remote` and `journalctl`.

Requires:
- `systemd-journal-remote` package installed (Linux only)
- Extracted agent-gather archive
- For macOS/Windows: Uses container-based workflow

### `/agent-gather:analyze [path] [--component name] [--attach-logs]`
Analyzes agent-gather archives for common installation issues.

```
# Analyze current directory
/agent-gather:analyze

# Analyze specific archive
/agent-gather:analyze /tmp/agent-gather.tar.xz

# Analyze with focus on specific component
/agent-gather:analyze --component network

# Provide logs directly
/agent-gather:analyze --attach-logs
```

Searches for:
- Common error patterns
- Validation failures
- Service crashes
- Configuration issues
- Network problems

## Workflow

### 1. Monitor Installation

First, monitor your agent-based installation:

```bash
./openshift-install --dir <installation_directory> agent wait-for bootstrap-complete --log-level=debug
```

### 2. Collect Diagnostic Data

If installation fails or stalls, use the plugin to collect data:

```
/agent-gather:collect 192.168.1.100
```

The plugin will:
- Verify SSH connectivity
- Run `ssh core@192.168.1.100 agent-gather -O > agent-gather.tar.xz`
- Extract the archive
- Display summary of collected data

### 3. Decode Journal Logs

Convert binary journal logs to readable format:

```
/agent-gather:decode-journal
```

This generates `jnl.log` with human-readable journal entries.

### 4. Analyze Issues

Run analysis to identify common problems:

```
/agent-gather:analyze
```

The plugin searches for error patterns and provides troubleshooting suggestions.

## Prerequisites

### For Collecting Data
- SSH access to agent-based installer nodes
- SSH key configured for `core` user
- Network connectivity to node IPs

### For Decoding Journals
- Linux system with systemd (or container environment)
- `systemd-journal-remote` package:

**RHEL/CentOS/Fedora:**
```bash
sudo dnf install systemd-journal-remote
```

**Ubuntu/Debian:**
```bash
sudo apt-get install systemd-journal-remote
```

**macOS/Windows:**
Use a container:
```bash
podman run -it --rm -v $(pwd):/data:Z registry.access.redhat.com/ubi9/ubi bash -c \
  "dnf install -y systemd-journal-remote && cd /data && \
   cat journal.export | systemd-journal-remote -o node-0.journal - && \
   journalctl --file node-0.journal > jnl.log"
```

## Key Differences: agent-gather vs must-gather

| Feature | agent-gather | must-gather |
|---------|-------------|-------------|
| **When to use** | Before cluster API is available | After cluster is running |
| **Access method** | SSH to rendezvous host | `oc adm must-gather` |
| **Use case** | Agent-based installer failures | Running cluster diagnostics |
| **Data collected** | Pre-installation logs, journals | Cluster resources, pod logs |
| **Installer type** | Agent-based installer only | Any OpenShift installation |

## Common Issues and Solutions

### Issue: SSH Connection Failed
```
Error: Connection refused to 192.168.1.100
```
**Solution**:
- Verify node IP address
- Check network connectivity: `ping 192.168.1.100`
- Ensure SSH key is configured
- Try: `ssh -v core@192.168.1.100` to debug

### Issue: agent-gather Command Not Found
```
Error: bash: agent-gather: command not found
```
**Solution**:
- Verify you're connected to the rendezvous host (not a worker node)
- Check OpenShift version (4.12+ required)
- Ensure node is running RHCOS with agent-based installer

### Issue: systemd-journal-remote Not Installed
```
Error: systemd-journal-remote: command not found
```
**Solution**:
- Install package: `sudo dnf install systemd-journal-remote`
- Or use container-based workflow (see Prerequisites)

## Examples

### Example 1: Complete Troubleshooting Workflow

```
# 1. Installation monitoring shows failure
./openshift-install --dir ~/ocp-install agent wait-for bootstrap-complete --log-level=debug
# Output: Error: Bootstrap failed to complete

# 2. Collect diagnostic data
/agent-gather:collect 192.168.1.100

# 3. Decode journal logs
/agent-gather:decode-journal

# 4. Analyze for issues
/agent-gather:analyze

# 5. Review specific service logs
Can you show me the assisted-service logs from the journal?
```

### Example 2: Multi-Node Collection

```
# Collect from all control plane nodes
/agent-gather:collect 192.168.1.100 --all-nodes

# The plugin will prompt for additional node IPs
# Then collect from each node and organize the data
```

### Example 3: Targeted Analysis

```
# Analyze network-related issues
/agent-gather:analyze --component network

# Analyze storage issues
/agent-gather:analyze --component storage

# Search for specific error patterns
Can you search the agent-gather logs for "validation failed"?
```

### Example 4: Analyzing Provided Logs

```
# Upload or paste logs directly
/agent-gather:analyze --attach-logs

# Or paste logs in conversation
Can you analyze these logs?
<paste agent-gather log content>
```

## Version Compatibility

- **OpenShift 4.12+**: agent-gather available with basic functionality
- **OpenShift 4.17+**: Enhanced logging with debug mode in assisted-service
- **OpenShift 4.18**: Current stable version with full agent-gather support

## Resources

- [OpenShift Agent-based Installer Documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/installing_an_on-premise_cluster_with_the_agent-based_installer/)
- [Systemd Journal Export Formats](https://systemd.io/JOURNAL_EXPORT_FORMATS/)
- [OpenShift Installer GitHub](https://github.com/openshift/installer)
- [Must-Gather Plugin](../must-gather/README.md) - For running cluster diagnostics

## See Also

- `/must-gather:generate` - For collecting data from running clusters
- `/must-gather:analyze` - For analyzing running cluster issues
- OpenShift troubleshooting documentation
