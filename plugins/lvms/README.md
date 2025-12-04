# LVMS Plugin

Comprehensive troubleshooting and debugging plugin for LVMS (Logical Volume Manager Storage).

## Overview

The LVMS plugin provides powerful commands for diagnosing and troubleshooting storage issues in OpenShift clusters using LVMS. It analyzes LVMCluster resources, volume groups, PVCs, TopoLVM CSI driver, and node-level storage configuration to identify root causes of storage failures.

## Commands

### `/lvms:analyze`

Comprehensive LVMS troubleshooting that analyzes cluster health, storage resources, and identifies common issues.

**Works with:**
- Live OpenShift clusters (via `oc` CLI)
- LVMS must-gather data (offline analysis)

**Features:**
- LVMCluster health and readiness analysis
- Volume group status across all nodes
- PVC/PV binding issues and pending volumes
- LVMS operator and TopoLVM CSI driver health
- Node-level device availability and configuration (live clusters)
- Thin pool capacity and usage
- Pod log analysis with error deduplication
- Root cause analysis with specific remediation steps

**Usage Examples:**

```bash
# Analyze live cluster
/lvms:analyze --live

# Analyze must-gather data
/lvms:analyze ./must-gather/registry-ci-openshift-org-origin-4-18.../

# Focus on specific component
/lvms:analyze --live --component storage
/lvms:analyze ./must-gather/... check pending PVCs

# Analyze pod logs only
/lvms:analyze --live --component logs
/lvms:analyze ./must-gather/... --component logs
```

## Common Use Cases

### 1. PVCs Stuck in Pending State

When PVCs using LVMS storage classes are not binding:

```bash
/lvms:analyze --live check pending PVCs
```

The command will:
- Identify which PVCs are pending
- Check volume group free space
- Verify TopoLVM CSI driver is running
- Check for node affinity issues
- Provide specific remediation steps

### 2. LVMCluster Not Ready

When LVMCluster resource is not reaching Ready state:

```bash
/lvms:analyze --live analyze operator
```

The command will:
- Check LVMCluster status and conditions
- Identify which nodes have volume group issues
- Verify device availability and configuration
- Check for conflicting filesystems on devices
- Provide steps to clean devices and recreate VGs

### 3. Volume Group Creation Failures

When volume groups are not being created on nodes:

```bash
/lvms:analyze --live --component volumes
```

The command will:
- Show volume group status per node
- Identify missing or failed volume groups
- Check device selector configuration
- Detect devices already in use
- Provide commands to wipe devices and retry

### 4. Must-Gather Analysis

When analyzing a must-gather from a failed cluster:

```bash
/lvms:analyze ./must-gather/path/
```

The command will:
- Perform offline analysis of all LVMS resources
- Generate comprehensive health report
- Identify critical issues and warnings
- Provide prioritized remediation recommendations
- Suggest which logs to review

## Installation

### From Marketplace

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install LVMS plugin
/plugin install lvms@ai-helpers

# Use the command
/lvms:analyze --live
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Link to Claude Code plugins directory
ln -s $(pwd)/ai-helpers/plugins/lvms ~/.claude/plugins/lvms
```

## Prerequisites

**For Live Cluster Analysis:**
- `oc` CLI installed and configured
- Active cluster connection
- Read access to `openshift-lvm-storage` or older `openshift-storage` namespace
- Ability to read cluster-scoped resources

**For Must-Gather Analysis:**
- Python 3.6+ (for analysis script)
- PyYAML library: `pip install pyyaml`

## What the Plugin Checks

### LVMCluster Resources
- Overall state (Ready, Progressing, Failed, Degraded)
- Status conditions (ResourcesAvailable, VolumeGroupsReady)
- Device class configurations
- Node coverage and readiness

### Volume Groups
- Volume group creation status per node
- Physical volume availability
- Free space and capacity
- Thin pool configuration and usage
- Missing or failed volume groups

### Storage (PVCs/PVs)
- PVC binding status
- Pending volume provisioning failures
- Storage class configuration
- Capacity issues
- Node affinity constraints

### Operator Health
- LVMS operator deployment status
- TopoLVM controller readiness
- TopoLVM node daemonset coverage
- VG-manager daemonset status
- Pod crashes and restarts

### Node Devices
- Block device availability
- Existing filesystems on devices
- Device selector matches
- Disk capacity and usage

### Pod Logs
- Error and warning messages from vg-manager pods
- Error and warning messages from lvms-operator pod
- Deduplication of repeated errors from reconciliation loops
- JSON log parsing with timestamps and context

## Output Format

The plugin provides structured, color-coded output:

- ✓ Green checkmarks for healthy components
- ⚠ Yellow warnings for non-critical issues
- ❌ Red errors for critical problems
- ℹ Blue info for additional context

Reports include:
- Component-by-component health status
- Root cause analysis
- Prioritized recommendations
- Specific remediation commands
- Links to relevant documentation

## Troubleshooting the Plugin

**Script not found:**
```bash
# Verify script exists
ls plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py

# Make executable
chmod +x plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py
```

**Cannot connect to cluster:**
```bash
# Verify oc is configured
oc whoami
oc cluster-info

# Check LVMS namespace
oc get namespace openshift-lvm-storage
```

**Must-gather path errors:**
```bash
# Use the correct subdirectory (the one with the hash)
ls must-gather/registry-ci-*/namespaces/openshift-lvm-storage

# Not the parent directory
```

## Related Resources

- [LVMS GitHub Repository](https://github.com/openshift/lvm-operator)
- [LVMS Troubleshooting Guide](https://github.com/openshift/lvm-operator/blob/main/docs/troubleshooting.md)
- [TopoLVM Documentation](https://github.com/topolvm/topolvm)
- [OpenShift Storage Documentation](https://docs.openshift.com/container-platform/latest/storage/index.html)

## Contributing

Contributions are welcome! Please see the main repository's [CLAUDE.md](../../CLAUDE.md) for guidelines on:
- Adding new commands
- Extending analysis capabilities
- Improving diagnostic checks
- Adding helper scripts

## Support

For issues or feature requests:
- GitHub Issues: https://github.com/openshift-eng/ai-helpers/issues
- Repository: https://github.com/openshift-eng/ai-helpers
