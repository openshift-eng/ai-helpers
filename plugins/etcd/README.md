# Etcd Plugin

A Claude Code plugin for monitoring etcd cluster health and analyzing performance in OpenShift environments.

## Overview

This plugin provides commands to help diagnose and troubleshoot etcd-related issues in OpenShift clusters. Etcd is the critical distributed key-value store that holds all cluster state for Kubernetes/OpenShift, and maintaining its health and performance is essential for cluster stability.

## Commands

### `/etcd:health-check`

Performs a comprehensive health check of the etcd cluster, examining:
- Etcd pod status and availability
- Cluster health and member status
- Leadership election status
- Database size and fragmentation
- Disk space utilization
- Recent error logs
- Performance metrics (with `--verbose` flag)

**Usage:**
```
/etcd:health-check [--verbose]
```

**Example:**
```
/etcd:health-check
/etcd:health-check --verbose
```

### `/etcd:analyze-performance`

Analyzes etcd performance metrics to identify latency issues and bottlenecks, including:
- Disk I/O performance (commit latency, fsync duration)
- Network latency between etcd peers
- Request/response performance by operation type
- Leader stability and proposal metrics
- Database size and fragmentation
- Performance warnings from logs

**Usage:**
```
/etcd:analyze-performance [--duration <minutes>]
```

**Example:**
```
/etcd:analyze-performance
/etcd:analyze-performance --duration 15
```

## Prerequisites

All commands require:

1. **OpenShift CLI (oc)** - Install from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
2. **Active cluster connection** - Must be authenticated to an OpenShift cluster
3. **Cluster admin permissions** - Required to access etcd pods and metrics
4. **Running etcd pods** - At least one etcd pod must be running

## Installation

### From Marketplace

```bash
# Add the marketplace (if not already added)
/plugin marketplace add openshift-eng/ai-helpers

# Install the etcd plugin
/plugin install etcd@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Link to your Claude Code plugins directory
ln -s $(pwd)/ai-helpers/plugins/etcd ~/.claude/plugins/etcd
```

## Use Cases

### Troubleshooting Cluster Issues

When experiencing cluster-wide problems:
1. Run `/etcd:health-check` to verify etcd cluster status
2. If issues are found, run `/etcd:analyze-performance` to identify bottlenecks
3. Follow the recommendations provided in the output

### Performance Tuning

For proactive performance monitoring:
1. Run `/etcd:analyze-performance --duration 30` for comprehensive analysis
2. Review disk I/O and network latency metrics
3. Compare against recommended thresholds
4. Implement suggested optimizations

### Capacity Planning

Before scaling operations:
1. Check current database size with `/etcd:health-check`
2. Analyze performance trends with `/etcd:analyze-performance`
3. Identify if hardware upgrades are needed

## Common Issues and Solutions

### High Disk Latency

**Problem:** Backend commit P99 > 100ms or WAL fsync P99 > 10ms

**Solutions:**
- Migrate to SSD or NVMe storage
- Use dedicated disks for etcd (not shared with OS)
- Check for competing I/O workloads

### Frequent Leader Changes

**Problem:** Leader changes > 5

**Solutions:**
- Check network connectivity between etcd nodes
- Ensure nodes are in same datacenter/availability zone
- Verify no clock skew between nodes

### Large Database Size

**Problem:** Database size > 8GB or high fragmentation

**Solutions:**
- Run etcd defragmentation
- Review event retention policies
- Check for excessive key creation

## Performance Benchmarks

Recommended thresholds for healthy etcd:
- **Backend commit P99:** < 100ms
- **WAL fsync P99:** < 10ms
- **Peer RTT P99:** < 50ms
- **Leader changes:** < 5 total
- **Database size:** < 8GB
- **Disk usage:** < 80%

## Security Considerations

- Commands require cluster-admin or equivalent permissions
- Access to etcd allows viewing all cluster secrets
- Metrics and logs may contain sensitive information
- Performance data should be treated as confidential

## Resources

- **Etcd Documentation:** https://etcd.io/docs/
- **OpenShift Etcd Docs:** https://docs.openshift.com/container-platform/latest/backup_and_restore/control_plane_backup_and_restore/
- **Performance Tuning:** https://etcd.io/docs/latest/tuning/

## Contributing

To contribute improvements or report issues:
1. Visit https://github.com/openshift-eng/ai-helpers
2. Open an issue or pull request
3. Follow the contribution guidelines in the repository

## License

This plugin is part of the ai-helpers project and follows the same license terms.
