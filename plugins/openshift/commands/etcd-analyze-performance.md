---
description: Analyze etcd performance metrics, latency, and identify bottlenecks
argument-hint: "[--duration <minutes>]"
---

## Name
openshift:etcd-analyze-performance

## Synopsis
```
/openshift:etcd-analyze-performance [--duration <minutes>]
```

## Description

The `etcd-analyze-performance` command analyzes etcd performance metrics to identify latency issues, slow operations, and potential bottlenecks. It examines disk performance, commit latency, network latency, and provides recommendations for optimization.

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

### 3. Collect Etcd Metrics

Fetch current metrics from etcd:

```bash
echo "Collecting etcd metrics..."

METRICS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcd -- curl -s http://localhost:2379/metrics 2>/dev/null)

if [ -z "$METRICS" ]; then
    echo "Error: Unable to fetch etcd metrics"
    exit 1
fi
```

### 4. Analyze Disk Performance

Parse disk-related metrics:

```bash
echo "==============================================="
echo "DISK PERFORMANCE ANALYSIS"
echo "==============================================="

# Backend commit duration (time to commit to disk)
echo "Backend Commit Duration (seconds):"
echo "$METRICS" | grep "etcd_disk_backend_commit_duration_seconds_bucket" | grep -v "#" | tail -5

COMMIT_P50=$(echo "$METRICS" | grep 'etcd_disk_backend_commit_duration_seconds{quantile="0.5"}' | awk '{print $2}')
COMMIT_P99=$(echo "$METRICS" | grep 'etcd_disk_backend_commit_duration_seconds{quantile="0.99"}' | awk '{print $2}')

echo ""
echo "  - P50 (median): ${COMMIT_P50}s"
echo "  - P99: ${COMMIT_P99}s"

# Evaluate commit latency
if (( $(echo "$COMMIT_P99 > 0.1" | bc -l) )); then
    echo "  WARNING: High commit latency detected (P99 > 100ms)"
    echo "  This indicates slow disk I/O performance"
fi

echo ""

# WAL fsync duration (write-ahead log sync)
echo "WAL Fsync Duration (seconds):"
FSYNC_P50=$(echo "$METRICS" | grep 'etcd_disk_wal_fsync_duration_seconds{quantile="0.5"}' | awk '{print $2}')
FSYNC_P99=$(echo "$METRICS" | grep 'etcd_disk_wal_fsync_duration_seconds{quantile="0.9}' | awk '{print $2}')

echo "  - P50 (median): ${FSYNC_P50}s"
echo "  - P99: ${FSYNC_P99}s"

if (( $(echo "$FSYNC_P99 > 0.01" | bc -l) )); then
    echo "  WARNING: High fsync latency detected (P99 > 10ms)"
    echo "  This may indicate disk saturation or slow storage"
fi

echo ""

# Snapshot save duration
echo "Snapshot Save Duration:"
SNAPSHOT_DURATION=$(echo "$METRICS" | grep "etcd_debugging_snap_save_total_duration_seconds" | grep "quantile=\"0.99\"" | awk '{print $2}')
echo "  - P99: ${SNAPSHOT_DURATION}s"
```

### 5. Analyze Network Performance

Parse network and RPC metrics:

```bash
echo ""
echo "==============================================="
echo "NETWORK PERFORMANCE ANALYSIS"
echo "==============================================="

# gRPC message size
echo "gRPC Message Sizes:"
GRPC_SENT=$(echo "$METRICS" | grep "etcd_network_client_grpc_sent_bytes_total" | awk '{print $2}')
GRPC_RECEIVED=$(echo "$METRICS" | grep "etcd_network_client_grpc_received_bytes_total" | awk '{print $2}')

echo "  - Total sent: ${GRPC_SENT} bytes"
echo "  - Total received: ${GRPC_RECEIVED} bytes"

echo ""

# Peer network latency
echo "Peer Round-Trip Time (RTT):"
echo "$METRICS" | grep "etcd_network_peer_round_trip_time_seconds" | grep "quantile" | while read line; do
    echo "  $line"
done

# Check for high peer latency
PEER_RTT_P99=$(echo "$METRICS" | grep 'etcd_network_peer_round_trip_time_seconds{quantile="0.99"' | awk '{print $2}')

if [ -n "$PEER_RTT_P99" ] && (( $(echo "$PEER_RTT_P99 > 0.05" | bc -l) )); then
    echo "  WARNING: High peer network latency (P99 > 50ms)"
    echo "  Check network connectivity between etcd members"
fi
```

### 6. Analyze Request Performance

Examine API request latencies:

```bash
echo ""
echo "==============================================="
echo "REQUEST PERFORMANCE ANALYSIS"
echo "==============================================="

# Request duration by type
echo "Request Duration by Operation:"

for op in put get delete txn; do
    DURATION=$(echo "$METRICS" | grep "etcd_request_duration_seconds.*type=\"$op\"" | grep "quantile=\"0.99\"" | awk '{print $2}')
    if [ -n "$DURATION" ]; then
        echo "  - $op (P99): ${DURATION}s"
    fi
done

echo ""

# Slow operations
echo "Slow Apply Operations:"
SLOW_APPLY=$(echo "$METRICS" | grep "etcd_server_slow_apply_total" | awk '{print $2}')
echo "  - Total slow applies: ${SLOW_APPLY}"

if [ -n "$SLOW_APPLY" ] && [ "$SLOW_APPLY" -gt 0 ]; then
    echo "  WARNING: Detected $SLOW_APPLY slow apply operations"
fi

echo ""

# Slow reads
echo "Slow Read Operations:"
SLOW_READ=$(echo "$METRICS" | grep "etcd_server_slow_read_indexes_total" | awk '{print $2}')
echo "  - Total slow reads: ${SLOW_READ}"
```

### 7. Analyze Leader Performance

Check leader-specific metrics:

```bash
echo ""
echo "==============================================="
echo "LEADER PERFORMANCE ANALYSIS"
echo "==============================================="

# Leader changes
LEADER_CHANGES=$(echo "$METRICS" | grep "etcd_server_leader_changes_seen_total" | awk '{print $2}')
echo "Leader Changes: $LEADER_CHANGES"

if [ -n "$LEADER_CHANGES" ] && [ "$LEADER_CHANGES" -gt 5 ]; then
    echo "  WARNING: High number of leader changes detected"
    echo "  This indicates cluster instability"
fi

echo ""

# Proposals
PROPOSALS_COMMITTED=$(echo "$METRICS" | grep "etcd_server_proposals_committed_total" | awk '{print $2}')
PROPOSALS_APPLIED=$(echo "$METRICS" | grep "etcd_server_proposals_applied_total" | awk '{print $2}')
PROPOSALS_PENDING=$(echo "$METRICS" | grep "etcd_server_proposals_pending" | awk '{print $2}')
PROPOSALS_FAILED=$(echo "$METRICS" | grep "etcd_server_proposals_failed_total" | awk '{print $2}')

echo "Proposal Statistics:"
echo "  - Committed: $PROPOSALS_COMMITTED"
echo "  - Applied: $PROPOSALS_APPLIED"
echo "  - Pending: $PROPOSALS_PENDING"
echo "  - Failed: $PROPOSALS_FAILED"

if [ -n "$PROPOSALS_PENDING" ] && [ "$PROPOSALS_PENDING" -gt 100 ]; then
    echo "  WARNING: High number of pending proposals"
fi
```

### 8. Analyze Database Performance

Check database size and operations:

```bash
echo ""
echo "==============================================="
echo "DATABASE PERFORMANCE ANALYSIS"
echo "==============================================="

# Get database sizes from endpoint status
DB_STATUS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint status --cluster -w json 2>/dev/null)

echo "Database Statistics:"
echo "$DB_STATUS" | jq -r '.[] | "Endpoint: \(.Endpoint)\n  DB Size: \(.Status.dbSize) bytes (\(.Status.dbSize / 1024 / 1024 | floor)MB)\n  DB In Use: \(.Status.dbSizeInUse) bytes (\(.Status.dbSizeInUse / 1024 / 1024 | floor)MB)\n  Keys: \(.Status.keys)\n  Raft Index: \(.Status.raftIndex)\n  Raft Term: \(.Status.raftTerm)"'

echo ""

# Check for high fragmentation
echo "$DB_STATUS" | jq -r '.[] |
    if .Status.dbSize > 0 then
        ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) as $frag |
        "Fragmentation: \($frag | floor)%" +
        if $frag > 50 then
            " - WARNING: High fragmentation detected, consider defragmentation"
        else
            ""
        end
    else
        "Fragmentation: N/A"
    end'
```

### 9. Analyze Recent Logs for Performance Issues

Parse etcd logs for performance warnings:

```bash
echo ""
echo "==============================================="
echo "LOG ANALYSIS (Last $DURATION minutes)"
echo "==============================================="

# Calculate timestamp for log filtering
SINCE_TIME="${DURATION}m"

echo "Searching for performance-related warnings..."

# Get recent logs
LOGS=$(oc logs -n openshift-etcd "$ETCD_POD" -c etcd --since="$SINCE_TIME" 2>/dev/null)

# Count slow operations
SLOW_OPS=$(echo "$LOGS" | grep -i "slow" | wc -l)
echo "Slow operations logged: $SLOW_OPS"

if [ "$SLOW_OPS" -gt 0 ]; then
    echo ""
    echo "Sample slow operations (last 5):"
    echo "$LOGS" | grep -i "slow" | tail -5
fi

echo ""

# Check for disk warnings
DISK_WARNINGS=$(echo "$LOGS" | grep -i "disk\|fdatasync\|fsync" | grep -i "slow\|took" | wc -l)
echo "Disk-related warnings: $DISK_WARNINGS"

if [ "$DISK_WARNINGS" -gt 0 ]; then
    echo "Sample disk warnings:"
    echo "$LOGS" | grep -i "disk\|fdatasync\|fsync" | grep -i "slow\|took" | tail -3
fi

echo ""

# Check for apply warnings
APPLY_WARNINGS=$(echo "$LOGS" | grep -i "apply.*took\|slow.*apply" | wc -l)
echo "Apply operation warnings: $APPLY_WARNINGS"
```

### 10. Generate Performance Report

Create summary with recommendations:

```bash
echo ""
echo "==============================================="
echo "PERFORMANCE SUMMARY & RECOMMENDATIONS"
echo "==============================================="

ISSUES=0
WARNINGS=0

# Evaluate overall health
if (( $(echo "$COMMIT_P99 > 0.1" | bc -l) )); then
    echo "ISSUE: High backend commit latency (${COMMIT_P99}s)"
    echo "  Recommendation: Check disk I/O performance, consider faster storage"
    ISSUES=$((ISSUES + 1))
fi

if (( $(echo "$FSYNC_P99 > 0.01" | bc -l) )); then
    echo "ISSUE: High WAL fsync latency (${FSYNC_P99}s)"
    echo "  Recommendation: Investigate disk saturation, check fio benchmarks"
    ISSUES=$((ISSUES + 1))
fi

if [ -n "$LEADER_CHANGES" ] && [ "$LEADER_CHANGES" -gt 5 ]; then
    echo "WARNING: Frequent leader changes ($LEADER_CHANGES)"
    echo "  Recommendation: Check network stability between etcd nodes"
    WARNINGS=$((WARNINGS + 1))
fi

if [ "$SLOW_OPS" -gt 10 ]; then
    echo "WARNING: High number of slow operations ($SLOW_OPS in last ${DURATION}m)"
    echo "  Recommendation: Investigate workload patterns and consider scaling"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "Performance Benchmarks (Recommended):"
echo "  - Backend commit P99: < 100ms (Current: ${COMMIT_P99}s)"
echo "  - WAL fsync P99: < 10ms (Current: ${FSYNC_P99}s)"
echo "  - Peer RTT P99: < 50ms"
echo "  - Leader changes: < 5"
echo ""

if [ "$ISSUES" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo "Status: HEALTHY - Performance within acceptable ranges"
    exit 0
elif [ "$ISSUES" -gt 0 ]; then
    echo "Status: CRITICAL - Found $ISSUES performance issues requiring attention"
    exit 1
else
    echo "Status: WARNING - Found $WARNINGS performance warnings"
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
/openshift:etcd-analyze-performance
```

Output:
```
Analyzing etcd performance (last 5 minutes)...
Using etcd pod: etcd-ip-10-0-21-125.us-east-2.compute.internal

===============================================
DISK PERFORMANCE ANALYSIS
===============================================
Backend Commit Duration (seconds):
  - P50 (median): 0.002s
  - P99: 0.025s

WAL Fsync Duration (seconds):
  - P50 (median): 0.001s
  - P99: 0.004s

===============================================
NETWORK PERFORMANCE ANALYSIS
===============================================
Peer Round-Trip Time (RTT):
  - P99: 0.015s

===============================================
Performance Summary
===============================================
Status: HEALTHY - Performance within acceptable ranges
```

### Example 2: Extended analysis window
```
/openshift:etcd-analyze-performance --duration 30
```

## Common Performance Issues

### Slow Disk I/O

**Symptoms**: High backend commit or fsync latency

**Investigation**:
```bash
# Check disk performance on etcd nodes
oc debug node/<node-name> -- chroot /host fio --name=test --rw=write --bs=4k --size=1G --direct=1
```

**Recommendations**:
- Use SSD or NVMe storage for etcd
- Ensure dedicated disks for etcd (not shared with OS)
- Check for disk saturation or competing I/O

### High Network Latency

**Symptoms**: High peer RTT, frequent leader changes

**Investigation**:
```bash
# Test network latency between nodes
oc debug node/<node1> -- ping <node2-ip>
```

**Recommendations**:
- Ensure etcd nodes are in same datacenter/availability zone
- Check for network congestion or packet loss
- Verify MTU settings

### Large Database Size

**Symptoms**: Slow operations, high memory usage

**Remediation**:
- Run defragmentation: `/openshift:etcd-defrag`
- Review event retention policies
- Check for key churn

## Security Considerations

- Metrics may expose cluster operational details
- Requires cluster-admin permissions
- Log analysis may contain sensitive data
- Performance data should be treated as confidential

## See Also

- Etcd performance guide: https://etcd.io/docs/latest/tuning/
- OpenShift etcd docs: https://docs.openshift.com/container-platform/latest/scalability_and_performance/recommended-performance-scale-practices/
- Related commands: `/openshift:etcd-check-health`, `/openshift:etcd-defrag`, `/openshift:cluster-health-check`

## Notes

- Performance thresholds are based on etcd upstream recommendations
- Disk benchmarks should show > 50 sequential IOPS for etcd
- Network latency < 50ms recommended between members
- Analysis is point-in-time; trends require repeated checks
- Some metrics require etcd v3.4+ features
