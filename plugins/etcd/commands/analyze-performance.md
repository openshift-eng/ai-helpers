---
description: Analyze etcd performance metrics, latency, and identify bottlenecks
argument-hint: "[--duration <minutes>]"
---

## Name
etcd:analyze-performance

## Synopsis
```
/etcd:analyze-performance [--duration <minutes>]
```

## Description

The `analyze-performance` command analyzes etcd performance metrics to identify latency issues, slow operations, and potential bottlenecks. It examines disk performance, commit latency, network latency, and provides recommendations for optimization.

Etcd performance is critical for cluster responsiveness. Slow etcd operations can cause:
- API server timeouts
- Slow pod creation and updates
- Controller delays
- Overall cluster sluggishness

This command is useful for:
- Diagnosing slow cluster operations
- Identifying disk I/O bottlenecks
- Detecting network latency issues
- Capacity planning
- Performance tuning

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (oc)**
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Verify with: `oc version`

2. **Active cluster connection**
   - Must be connected to an OpenShift cluster
   - Verify with: `oc whoami`

3. **Cluster admin permissions**
   - Required to access etcd pods and metrics
   - Verify with: `oc auth can-i get pods -n openshift-etcd`

4. **Running etcd pods**
   - At least one etcd pod must be running
   - Check with: `oc get pods -n openshift-etcd -l app=etcd`

## Arguments

- **--duration** (optional): Duration in minutes to analyze logs (default: 5)
  - Analyzes recent logs for the specified duration
  - Longer durations provide more comprehensive analysis
  - Example: `--duration 15` for 15-minute window

## Implementation

The command performs the following analysis:

### 1. Verify Prerequisites

```bash
if ! command -v oc &> /dev/null; then
    echo "Error: oc CLI not found"
    exit 1
fi

if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to cluster"
    exit 1
fi

# Parse duration argument (default: 5 minutes)
DURATION=5
if [[ "$1" == "--duration" ]] && [[ -n "$2" ]]; then
    DURATION=$2
fi

echo "Analyzing etcd performance (last $DURATION minutes)..."
```

### 2. Get Running Etcd Pod

```bash
ETCD_POD=$(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

if [ -z "$ETCD_POD" ]; then
    echo "Error: No running etcd pod found"
    exit 1
fi

echo "Using etcd pod: $ETCD_POD"
echo ""
```

### 3. Analyze Database Performance

Get database statistics using etcdctl:

```bash
echo "==============================================="
echo "DATABASE PERFORMANCE ANALYSIS"
echo "==============================================="
echo ""
echo "Fetching database statistics..."

# Get database sizes from endpoint status
DB_STATUS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint status --cluster -w json 2>/dev/null)

echo "Database Statistics:"
echo "$DB_STATUS" | jq -r '.[] |
    "Endpoint: \(.Endpoint)
  Version: \(.Status.version)
  DB Size: \(.Status.dbSize) bytes (\((.Status.dbSize / 1024 / 1024) | floor)MB)
  DB In Use: \(.Status.dbSizeInUse) bytes (\((.Status.dbSizeInUse / 1024 / 1024) | floor)MB)
  Keys: \(.Status.header.revision)
  Raft Index: \(.Status.raftIndex)
  Raft Term: \(.Status.raftTerm)
  Leader: \(if .Status.leader == .Status.header.member_id then "YES" else "NO" end)
"'

echo ""
echo "Fragmentation Analysis:"
echo "$DB_STATUS" | jq -r '.[] |
    if .Status.dbSize > 0 then
        ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) as $frag |
        "Endpoint: \(.Endpoint)
  Fragmentation: \($frag | floor)%" +
        if $frag > 50 then
            " - WARNING: High fragmentation detected, consider defragmentation"
        elif $frag > 30 then
            " - NOTICE: Moderate fragmentation"
        else
            " - OK"
        end
    else
        "Endpoint: \(.Endpoint)
  Fragmentation: N/A"
    end'
```

### 4. Check Cluster Health

Verify etcd cluster health:

```bash
echo ""
echo "==============================================="
echo "CLUSTER HEALTH"
echo "==============================================="
echo ""
oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint health --cluster 2>/dev/null || echo "Health check failed"
```

### 5. Analyze Logs for Performance Issues

Parse etcd logs for performance warnings:

```bash
echo ""
echo "==============================================="
echo "LOG ANALYSIS (Last $DURATION minutes)"
echo "==============================================="
echo ""
echo "Searching for performance-related warnings..."

# Get recent logs
LOGS=$(oc logs -n openshift-etcd "$ETCD_POD" -c etcd --since="${DURATION}m" 2>/dev/null)

# Count slow operations
SLOW_OPS=$(echo "$LOGS" | grep -i "slow" | wc -l)
echo "Slow operations logged: $SLOW_OPS"

if [ "$SLOW_OPS" -gt 0 ]; then
    echo ""
    echo "Recent slow operations (last 10):"
    echo "$LOGS" | grep -i "slow" | tail -10
fi

echo ""

# Check for disk warnings
DISK_WARNINGS=$(echo "$LOGS" | grep -iE "disk|fdatasync|fsync" | grep -iE "slow|took|latency" | wc -l)
echo "Disk-related warnings: $DISK_WARNINGS"

if [ "$DISK_WARNINGS" -gt 0 ]; then
    echo ""
    echo "Disk performance warnings:"
    echo "$LOGS" | grep -iE "disk|fdatasync|fsync" | grep -iE "slow|took|latency" | tail -5
fi

echo ""

# Check for apply warnings
APPLY_WARNINGS=$(echo "$LOGS" | grep -iE "apply.*took|slow.*apply" | wc -l)
echo "Apply operation warnings: $APPLY_WARNINGS"

if [ "$APPLY_WARNINGS" -gt 0 ]; then
    echo ""
    echo "Apply warnings:"
    echo "$LOGS" | grep -iE "apply.*took|slow.*apply" | tail -5
fi

echo ""

# Check for compaction info
echo "Recent compaction operations:"
echo "$LOGS" | grep "finished scheduled compaction" | tail -3
if [ $(echo "$LOGS" | grep "finished scheduled compaction" | wc -l) -eq 0 ]; then
    echo "  No compaction operations in this time window"
fi

echo ""

# Check for snapshot operations
echo "Snapshot operations:"
SNAPSHOTS=$(echo "$LOGS" | grep -i "snapshot" | wc -l)
echo "Snapshot events: $SNAPSHOTS"
if [ "$SNAPSHOTS" -gt 0 ]; then
    echo "$LOGS" | grep -i "snapshot" | tail -3
fi
```

### 6. Analyze Leader Stability

Check for leader changes and stability issues:

```bash
echo ""
echo "==============================================="
echo "LEADER STABILITY ANALYSIS"
echo "==============================================="
echo ""

LEADER_CHANGES=$(echo "$LOGS" | grep -i "leader.*changed\|became leader\|lost leader" | wc -l)
echo "Leader change events: $LEADER_CHANGES"

if [ "$LEADER_CHANGES" -gt 0 ]; then
    echo ""
    echo "Leader change events:"
    echo "$LOGS" | grep -i "leader.*changed\|became leader\|lost leader"
fi

# Check for proposal/commit issues
echo ""
echo "Proposal and commit operations:"
PROPOSAL_LOGS=$(echo "$LOGS" | grep -iE "proposal|commit" | grep -iE "slow|took|failed" | wc -l)
echo "Slow proposal/commit operations: $PROPOSAL_LOGS"

if [ "$PROPOSAL_LOGS" -gt 0 ]; then
    echo ""
    echo "Sample slow operations:"
    echo "$LOGS" | grep -iE "proposal|commit" | grep -iE "slow|took|failed" | tail -5
fi
```

### 7. Analyze Network Performance

Check for network-related issues:

```bash
echo ""
echo "==============================================="
echo "NETWORK ANALYSIS"
echo "==============================================="
echo ""

NETWORK_ISSUES=$(echo "$LOGS" | grep -iE "network|connection|timeout|peer" | grep -iE "error|fail|slow" | wc -l)
echo "Network-related issues: $NETWORK_ISSUES"

if [ "$NETWORK_ISSUES" -gt 0 ]; then
    echo ""
    echo "Network issues:"
    echo "$LOGS" | grep -iE "network|connection|timeout|peer" | grep -iE "error|fail|slow" | tail -5
fi
```

### 8. Generate Performance Summary

Create summary with recommendations:

```bash
echo ""
echo "==============================================="
echo "PERFORMANCE SUMMARY & RECOMMENDATIONS"
echo "==============================================="
echo ""

ISSUES=0
WARNINGS=0

# Check fragmentation from DB status
MAX_FRAG=$(echo "$DB_STATUS" | jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max')

if (( $(echo "$MAX_FRAG > 50" | bc -l 2>/dev/null || echo 0) )); then
    echo "ISSUE: High database fragmentation (${MAX_FRAG}%)"
    echo "  Recommendation: Run defragmentation on all etcd members"
    echo "  Command: oc exec -n openshift-etcd <pod> -c etcdctl -- etcdctl defrag"
    echo ""
    ISSUES=$((ISSUES + 1))
elif (( $(echo "$MAX_FRAG > 30" | bc -l 2>/dev/null || echo 0) )); then
    echo "WARNING: Moderate database fragmentation (${MAX_FRAG}%)"
    echo "  Recommendation: Monitor and consider defragmentation if performance degrades"
    echo ""
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$LEADER_CHANGES" -gt 5 ]; then
    echo "WARNING: Frequent leader changes ($LEADER_CHANGES in last ${DURATION}m)"
    echo "  Recommendation: Check network stability between etcd nodes"
    echo "  - Verify network latency between control plane nodes"
    echo "  - Check for packet loss or network congestion"
    echo ""
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$SLOW_OPS" -gt 10 ]; then
    echo "WARNING: High number of slow operations ($SLOW_OPS in last ${DURATION}m)"
    echo "  Recommendation: Investigate disk I/O and workload patterns"
    echo "  - Check disk performance with 'fio' benchmarks"
    echo "  - Review etcd workload and consider optimization"
    echo ""
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$DISK_WARNINGS" -gt 5 ]; then
    echo "WARNING: Multiple disk performance warnings ($DISK_WARNINGS in last ${DURATION}m)"
    echo "  Recommendation: Investigate disk I/O performance"
    echo "  - Ensure etcd is using SSD/NVMe storage"
    echo "  - Check for disk saturation or competing I/O"
    echo "  - Verify disk benchmarks meet etcd requirements (> 50 sequential IOPS)"
    echo ""
    WARNINGS=$((WARNINGS + 1))
fi

# Get average DB size
AVG_DB_SIZE=$(echo "$DB_STATUS" | jq -r '[.[] | .Status.dbSize] | add / length')
AVG_DB_SIZE_MB=$(echo "scale=0; $AVG_DB_SIZE / 1024 / 1024" | bc)

if [ "$AVG_DB_SIZE_MB" -gt 8000 ]; then
    echo "WARNING: Large database size (${AVG_DB_SIZE_MB}MB)"
    echo "  Recommendation: Review data retention and compaction policies"
    echo "  - Check event retention policies"
    echo "  - Consider more frequent compaction"
    echo ""
    WARNINGS=$((WARNINGS + 1))
fi

echo "Performance Metrics Summary:"
echo "  - Database size: ${AVG_DB_SIZE_MB}MB (recommended: < 8GB)"
echo "  - Fragmentation: ${MAX_FRAG}% (recommended: < 30%)"
echo "  - Slow operations (${DURATION}m): $SLOW_OPS (recommended: < 10)"
echo "  - Leader changes (${DURATION}m): $LEADER_CHANGES (recommended: < 5)"
echo ""

if [ "$ISSUES" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo "Status: ✓ HEALTHY - Performance within acceptable ranges"
    exit 0
elif [ "$ISSUES" -gt 0 ]; then
    echo "Status: ✗ CRITICAL - Found $ISSUES performance issues requiring attention"
    exit 1
else
    echo "Status: ⚠ WARNING - Found $WARNINGS performance warnings"
    exit 0
fi
```

## Return Value

- **Exit 0**: Performance is acceptable (may have warnings)
- **Exit 1**: Critical performance issues detected

**Output Format**:
- Structured sections for different performance aspects
- Metrics with percentile values (P50, P99)
- Warnings for values exceeding thresholds
- Recommendations for remediation

## Examples

### Example 1: Basic performance analysis
```
/etcd:analyze-performance
```

Output:
```
===============================================
ETCD PERFORMANCE ANALYSIS
===============================================
Analyzing etcd performance (last 5 minutes)...
Using etcd pod: etcd-dis016-p6vvv-master-0.us-central1-a.c.openshift-qe.internal

===============================================
DATABASE PERFORMANCE ANALYSIS
===============================================

Fetching database statistics...
Database Statistics:
Endpoint: https://10.0.0.5:2379
  Version: 3.5.24
  DB Size: 94941184 bytes (90MB)
  DB In Use: 51789824 bytes (49MB)
  Keys: 50240
  Raft Index: 57097
  Raft Term: 8
  Leader: YES

Endpoint: https://10.0.0.3:2379
  Version: 3.5.24
  DB Size: 95363072 bytes (90MB)
  DB In Use: 51789824 bytes (49MB)
  Keys: 50240
  Raft Index: 57097
  Raft Term: 8
  Leader: NO

Endpoint: https://10.0.0.6:2379
  Version: 3.5.24
  DB Size: 94613504 bytes (90MB)
  DB In Use: 51834880 bytes (49MB)
  Keys: 50240
  Raft Index: 57097
  Raft Term: 8
  Leader: NO

Fragmentation Analysis:
Endpoint: https://10.0.0.5:2379
  Fragmentation: 45% - NOTICE: Moderate fragmentation
Endpoint: https://10.0.0.3:2379
  Fragmentation: 45% - NOTICE: Moderate fragmentation
Endpoint: https://10.0.0.6:2379
  Fragmentation: 45% - NOTICE: Moderate fragmentation

===============================================
CLUSTER HEALTH
===============================================

https://10.0.0.5:2379 is healthy: successfully committed proposal: took = 9.848973ms
https://10.0.0.3:2379 is healthy: successfully committed proposal: took = 14.309216ms
https://10.0.0.6:2379 is healthy: successfully committed proposal: took = 14.829731ms

===============================================
LOG ANALYSIS (Last 5 minutes)
===============================================

Searching for performance-related warnings...
Slow operations logged: 0
Disk-related warnings: 0
Apply operation warnings: 0

Recent compaction operations:
{"level":"info","ts":"2025-11-19T06:15:10.136401Z","caller":"mvcc/kvstore_compaction.go:72","msg":"finished scheduled compaction","compact-revision":48026,"took":"175.577699ms","hash":1330697744}

===============================================
LEADER STABILITY ANALYSIS
===============================================

Leader change events: 0

===============================================
NETWORK ANALYSIS
===============================================

Network-related issues: 0

===============================================
PERFORMANCE SUMMARY & RECOMMENDATIONS
===============================================

WARNING: Moderate database fragmentation (45%)
  Recommendation: Monitor and consider defragmentation if performance degrades

Performance Metrics Summary:
  - Database size: 90MB (recommended: < 8GB)
  - Fragmentation: 45% (recommended: < 30%)
  - Slow operations (5m): 0 (recommended: < 10)
  - Leader changes (5m): 0 (recommended: < 5)

Status: ⚠ WARNING - Found 1 performance warnings
```

### Example 2: Extended analysis window
```
/etcd:analyze-performance --duration 30
```

## Common Performance Issues

### High Database Fragmentation

**Symptoms**: Database size significantly larger than in-use size (>30% fragmentation)

**Investigation**:
```bash
# Check current fragmentation
oc exec -n openshift-etcd <pod> -c etcdctl -- etcdctl endpoint status --cluster -w json | jq
```

**Remediation**:
```bash
# Defragment each etcd member (run one at a time)
oc exec -n openshift-etcd <pod> -c etcdctl -- etcdctl defrag --cluster
```

**Recommendations**:
- Schedule regular defragmentation during maintenance windows
- Monitor fragmentation trends over time
- Consider defragmentation when >30% fragmented

### Slow Disk I/O

**Symptoms**:
- Disk-related warnings in logs (fsync, fdatasync)
- Slow apply operations
- High compaction times (>500ms)

**Investigation**:
```bash
# Check disk performance on etcd nodes
oc debug node/<node-name> -- chroot /host fio --name=test --rw=write --bs=4k --size=1G --direct=1
```

**Recommendations**:
- Use SSD or NVMe storage for etcd
- Ensure dedicated disks for etcd (not shared with OS)
- Check for disk saturation or competing I/O
- Verify disk benchmarks meet etcd requirements (> 50 sequential IOPS)

### Frequent Leader Changes

**Symptoms**: Multiple leader change events in logs

**Investigation**:
```bash
# Test network latency between control plane nodes
oc debug node/<node1> -- ping <node2-ip>

# Check for network packet loss
oc debug node/<node1> -- ping -c 100 <node2-ip>
```

**Recommendations**:
- Ensure etcd nodes are in same datacenter/availability zone
- Check for network congestion or packet loss
- Verify MTU settings across cluster network
- Review network firewall rules and QoS settings

### Large Database Size

**Symptoms**:
- Database size >8GB
- Slow operations
- High memory usage

**Investigation**:
```bash
# Check database size across cluster
oc exec -n openshift-etcd <pod> -c etcdctl -- etcdctl endpoint status --cluster -w table
```

**Remediation**:
```bash
# Check event retention settings
oc get kubeapiserver cluster -o yaml | grep -A5 eventTTL

# Review compaction settings
oc logs -n openshift-etcd <pod> -c etcd | grep compaction
```

**Recommendations**:
- Review event retention policies
- Consider more frequent compaction
- Check for key churn and unnecessary data
- Monitor database growth trends

## Security Considerations

- Metrics may expose cluster operational details
- Requires cluster-admin permissions
- Log analysis may contain sensitive data
- Performance data should be treated as confidential

## See Also

- Etcd performance guide: https://etcd.io/docs/latest/tuning/
- OpenShift etcd docs: https://docs.openshift.com/container-platform/latest/scalability_and_performance/recommended-performance-scale-practices/
- Related commands: `/etcd:health-check`

## Notes

- This command uses `etcdctl` and log analysis rather than direct metrics endpoint access
- Performance thresholds are based on etcd upstream recommendations
- Disk benchmarks should show > 50 sequential IOPS for etcd
- Network latency < 50ms recommended between members
- Analysis is point-in-time; trends require repeated checks over time
- Compatible with etcd 3.5+ (OpenShift 4.x)
- Log analysis window can be adjusted with `--duration` parameter
- For production clusters, consider running during low-traffic periods
- Health check latency is measured by actual proposal commits to the cluster
