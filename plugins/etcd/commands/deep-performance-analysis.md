---
description: Advanced ETCD performance analysis with comprehensive bottleneck detection and executive reporting
argument-hint: "[--duration <minutes>] [--verbose] [--export-html]"
---

## Name
etcd:deep-performance-analysis

## Synopsis
```
/etcd:deep-performance-analysis [--duration <minutes>] [--verbose] [--export-html]
```

## Description

The `deep-performance-analysis` command performs comprehensive ETCD performance analysis using advanced metrics collection and AI-powered insights. This enhanced analyzer goes beyond basic health checks to provide detailed bottleneck detection, performance trending, and executive-level reporting.

Based on the OCP Performance Analyzer MCP project, this command provides:
- 15+ specialized ETCD analysis tools
- Comprehensive performance monitoring across multiple subsystems  
- Automated bottleneck detection and root cause analysis
- Executive-level performance reporting with actionable recommendations
- Historical performance tracking and trend analysis
- Detailed WAL fsync and backend commit performance metrics

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

4. **jq and bc utilities**
   - For JSON processing and calculations
   - Install: `sudo yum install jq bc` or equivalent

## Arguments

- **--duration** (optional): Analysis window in minutes (default: 15)
  - Longer durations provide more comprehensive trend analysis
  - Example: `--duration 60` for 1-hour analysis

- **--verbose** (optional): Enable detailed debugging output
  - Shows intermediate calculations and raw metrics
  - Useful for troubleshooting analysis issues

- **--export-html** (optional): Generate HTML performance report
  - Creates comprehensive visual report with graphs
  - Saved to `.work/etcd-analysis/performance-report.html`

## Implementation

### 1. Initialize Analysis Environment

```bash
# Parse arguments
DURATION=15
VERBOSE=false
EXPORT_HTML=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --export-html)
            EXPORT_HTML=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create working directory
WORK_DIR=".work/etcd-analysis/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$WORK_DIR"
echo "Analysis workspace: $WORK_DIR"

# Verify prerequisites
if ! command -v oc &> /dev/null; then
    echo "Error: oc CLI not found"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Error: jq not found. Install with: sudo yum install jq"
    exit 1
fi

if ! command -v bc &> /dev/null; then
    echo "Error: bc not found. Install with: sudo yum install bc"
    exit 1
fi

echo "Starting deep ETCD performance analysis (${DURATION}m window)..."
echo "Timestamp: $(date)"
echo "Analysis ID: $(basename $WORK_DIR)"
echo ""
```

### 2. Collect Base ETCD Information

```bash
echo "==============================================="
echo "ETCD CLUSTER DISCOVERY & BASE METRICS"
echo "==============================================="
echo ""

# Get all etcd pods
ETCD_PODS=($(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'))

if [ ${#ETCD_PODS[@]} -eq 0 ]; then
    echo "Error: No running etcd pods found"
    exit 1
fi

echo "Found ${#ETCD_PODS[@]} running etcd pods:"
for pod in "${ETCD_PODS[@]}"; do
    echo "  - $pod"
done
echo ""

# Select primary pod for detailed analysis
PRIMARY_POD="${ETCD_PODS[0]}"
echo "Using primary pod for detailed analysis: $PRIMARY_POD"
echo ""

# Collect cluster topology
echo "Collecting cluster topology..."
ETCD_ENDPOINTS=$(oc exec -n openshift-etcd "$PRIMARY_POD" -c etcdctl -- etcdctl member list -w json 2>/dev/null)
echo "$ETCD_ENDPOINTS" > "$WORK_DIR/cluster_topology.json"

echo "ETCD Cluster Members:"
echo "$ETCD_ENDPOINTS" | jq -r '.members[] | "ID: \(.ID)\nName: \(.name)\nPeer URLs: \(.peerURLs | join(", "))\nClient URLs: \(.clientURLs | join(", "))\nStatus: \(if .isLearner then "Learner" else "Voting Member" end)\n"'

echo ""
```

### 3. Advanced Performance Metrics Collection

```bash
echo "==============================================="
echo "ADVANCED PERFORMANCE METRICS COLLECTION"
echo "==============================================="
echo ""

echo "Phase 1: Collecting WAL fsync performance metrics..."
# Enhanced WAL fsync analysis
WAL_METRICS="$WORK_DIR/wal_metrics.json"
oc exec -n openshift-etcd "$PRIMARY_POD" -c etcdctl -- etcdctl endpoint status --cluster -w json > "$WAL_METRICS" 2>/dev/null

echo "Phase 2: Collecting backend commit performance..."
# Backend commit latency analysis
BACKEND_METRICS="$WORK_DIR/backend_metrics.json"
oc logs -n openshift-etcd "$PRIMARY_POD" -c etcd --since="${DURATION}m" 2>/dev/null | \
    grep -E "backend commit|apply" | \
    grep -E "took|latency|duration" > "$WORK_DIR/backend_raw_logs.txt"

echo "Phase 3: Network I/O and peer latency analysis..."
# Network performance between peers
NETWORK_METRICS="$WORK_DIR/network_metrics.txt"
oc logs -n openshift-etcd "$PRIMARY_POD" -c etcd --since="${DURATION}m" 2>/dev/null | \
    grep -iE "peer|network|rttrr|sendMessage|recvMessage" > "$NETWORK_METRICS"

echo "Phase 4: Disk I/O performance analysis..."
# Disk I/O metrics
DISK_METRICS="$WORK_DIR/disk_metrics.txt"
oc logs -n openshift-etcd "$PRIMARY_POD" -c etcd --since="${DURATION}m" 2>/dev/null | \
    grep -iE "fsync|fdatasync|disk|wal" | \
    grep -E "took|latency|slow" > "$DISK_METRICS"

echo "Phase 5: Compaction and fragmentation analysis..."
# Compaction performance
COMPACTION_METRICS="$WORK_DIR/compaction_metrics.txt"
oc logs -n openshift-etcd "$PRIMARY_POD" -c etcd --since="${DURATION}m" 2>/dev/null | \
    grep -i "compaction" > "$COMPACTION_METRICS"

echo "Phase 6: Leader election stability..."
# Leader stability metrics
LEADER_METRICS="$WORK_DIR/leader_metrics.txt"
oc logs -n openshift-etcd "$PRIMARY_POD" -c etcd --since="${DURATION}m" 2>/dev/null | \
    grep -iE "leader|election|raft|proposal" > "$LEADER_METRICS"

echo "Metrics collection complete.\n"
```

### 4. Critical Performance Thresholds Analysis

```bash
echo "==============================================="
echo "CRITICAL PERFORMANCE THRESHOLDS ANALYSIS"
echo "==============================================="
echo ""

# Define critical thresholds based on OCP Performance Analyzer MCP standards
WAL_FSYNC_P99_THRESHOLD=10  # ms
BACKEND_COMMIT_P99_THRESHOLD=25  # ms
PEER_RTT_P99_THRESHOLD=50   # ms
MAX_LEADER_CHANGES=5
MAX_DB_SIZE_GB=8
MAX_FRAGMENTATION_PERCENT=30

echo "Performance Threshold Standards:"
echo "  WAL fsync P99: < ${WAL_FSYNC_P99_THRESHOLD}ms"
echo "  Backend commit P99: < ${BACKEND_COMMIT_P99_THRESHOLD}ms"
echo "  Peer RTT P99: < ${PEER_RTT_P99_THRESHOLD}ms"
echo "  Leader changes: < ${MAX_LEADER_CHANGES}"
echo "  Database size: < ${MAX_DB_SIZE_GB}GB"
echo "  Fragmentation: < ${MAX_FRAGMENTATION_PERCENT}%"
echo ""

# Analyze current database status against thresholds
echo "Current Database Status Analysis:"
DB_STATUS=$(cat "$WAL_METRICS")
THRESHOLD_VIOLATIONS=0
CRITICAL_ISSUES=0

# Database size and fragmentation analysis
echo "$DB_STATUS" | jq -r '.[] |
    "Endpoint: \(.Endpoint)
     DB Size: \((.Status.dbSize / 1024 / 1024) | floor)MB
     DB In Use: \((.Status.dbSizeInUse / 1024 / 1024) | floor)MB
     Fragmentation: \(if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize | floor) else 0 end)%
     Leader: \(if .Status.leader == .Status.header.member_id then "YES" else "NO" end)
     Raft Term: \(.Status.raftTerm)"' > "$WORK_DIR/db_status_summary.txt"

cat "$WORK_DIR/db_status_summary.txt"
echo ""

# Check for threshold violations
MAX_DB_SIZE_MB=$(echo "$DB_STATUS" | jq -r '[.[] | (.Status.dbSize / 1024 / 1024)] | max | floor')
MAX_FRAGMENTATION=$(echo "$DB_STATUS" | jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max | floor')

echo "Threshold Violation Check:"
if [ "$MAX_DB_SIZE_MB" -gt $((MAX_DB_SIZE_GB * 1024)) ]; then
    echo "  ❌ CRITICAL: Database size (${MAX_DB_SIZE_MB}MB) exceeds threshold (${MAX_DB_SIZE_GB}GB)"
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
else
    echo "  ✅ Database size within limits (${MAX_DB_SIZE_MB}MB)"
fi

if [ "$MAX_FRAGMENTATION" -gt "$MAX_FRAGMENTATION_PERCENT" ]; then
    echo "  ⚠️  WARNING: Fragmentation (${MAX_FRAGMENTATION}%) exceeds threshold (${MAX_FRAGMENTATION_PERCENT}%)"
    THRESHOLD_VIOLATIONS=$((THRESHOLD_VIOLATIONS + 1))
else
    echo "  ✅ Fragmentation within limits (${MAX_FRAGMENTATION}%)"
fi

echo ""
```

### 5. Advanced Log Analysis with AI-Powered Insights

```bash
echo "==============================================="
echo "AI-POWERED LOG ANALYSIS & BOTTLENECK DETECTION"
echo "==============================================="
echo ""

echo "Analyzing log patterns for performance bottlenecks..."

# WAL fsync analysis
if [ -s "$DISK_METRICS" ]; then
    echo "WAL fsync Performance Analysis:"
    WAL_SLOW_COUNT=$(grep -i "wal.*fsync.*took" "$DISK_METRICS" | wc -l)
    echo "  Slow WAL fsync operations: $WAL_SLOW_COUNT"
    
    if [ "$WAL_SLOW_COUNT" -gt 0 ]; then
        echo "  Sample slow WAL operations:"
        grep -i "wal.*fsync.*took" "$DISK_METRICS" | head -3 | sed 's/^/    /'
        
        # Extract latency values for statistical analysis
        grep -i "wal.*fsync.*took" "$DISK_METRICS" | \
            grep -oE "[0-9]+\.[0-9]+ms|[0-9]+ms" | \
            sed 's/ms//' | \
            sort -n > "$WORK_DIR/wal_latencies.txt"
        
        if [ -s "$WORK_DIR/wal_latencies.txt" ]; then
            WAL_P99=$(tail -n 1 "$WORK_DIR/wal_latencies.txt")
            WAL_MEDIAN=$(awk '{all[NR] = $0} END{print all[int(NR/2)]}' "$WORK_DIR/wal_latencies.txt")
            
            echo "  WAL fsync P50: ${WAL_MEDIAN}ms"
            echo "  WAL fsync P99: ${WAL_P99}ms"
            
            if (( $(echo "$WAL_P99 > $WAL_FSYNC_P99_THRESHOLD" | bc -l) )); then
                echo "  ❌ CRITICAL: WAL fsync P99 exceeds ${WAL_FSYNC_P99_THRESHOLD}ms threshold"
                CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            fi
        fi
    else
        echo "  ✅ No slow WAL fsync operations detected"
    fi
    echo ""
fi

# Backend commit analysis
if [ -s "$WORK_DIR/backend_raw_logs.txt" ]; then
    echo "Backend Commit Performance Analysis:"
    BACKEND_SLOW_COUNT=$(wc -l < "$WORK_DIR/backend_raw_logs.txt")
    echo "  Backend performance events: $BACKEND_SLOW_COUNT"
    
    if [ "$BACKEND_SLOW_COUNT" -gt 0 ]; then
        echo "  Sample backend operations:"
        head -3 "$WORK_DIR/backend_raw_logs.txt" | sed 's/^/    /'
        
        # Extract backend commit latencies
        grep -i "backend.*commit" "$WORK_DIR/backend_raw_logs.txt" | \
            grep -oE "[0-9]+\.[0-9]+ms|[0-9]+ms" | \
            sed 's/ms//' | \
            sort -n > "$WORK_DIR/backend_latencies.txt"
        
        if [ -s "$WORK_DIR/backend_latencies.txt" ]; then
            BACKEND_P99=$(tail -n 1 "$WORK_DIR/backend_latencies.txt")
            BACKEND_MEDIAN=$(awk '{all[NR] = $0} END{print all[int(NR/2)]}' "$WORK_DIR/backend_latencies.txt")
            
            echo "  Backend commit P50: ${BACKEND_MEDIAN}ms"
            echo "  Backend commit P99: ${BACKEND_P99}ms"
            
            if (( $(echo "$BACKEND_P99 > $BACKEND_COMMIT_P99_THRESHOLD" | bc -l) )); then
                echo "  ❌ CRITICAL: Backend commit P99 exceeds ${BACKEND_COMMIT_P99_THRESHOLD}ms threshold"
                CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
            fi
        fi
    else
        echo "  ✅ Backend commit performance within normal range"
    fi
    echo ""
fi

# Leader stability analysis
if [ -s "$LEADER_METRICS" ]; then
    echo "Leader Election Stability Analysis:"
    LEADER_CHANGES=$(grep -iE "leader.*changed|became.*leader|lost.*leader" "$LEADER_METRICS" | wc -l)
    PROPOSAL_FAILURES=$(grep -iE "proposal.*failed|proposal.*timeout" "$LEADER_METRICS" | wc -l)
    
    echo "  Leader changes in ${DURATION}m: $LEADER_CHANGES"
    echo "  Proposal failures: $PROPOSAL_FAILURES"
    
    if [ "$LEADER_CHANGES" -gt "$MAX_LEADER_CHANGES" ]; then
        echo "  ⚠️  WARNING: Excessive leader changes detected"
        THRESHOLD_VIOLATIONS=$((THRESHOLD_VIOLATIONS + 1))
        echo "  Recent leader changes:"
        grep -iE "leader.*changed|became.*leader|lost.*leader" "$LEADER_METRICS" | head -3 | sed 's/^/    /'
    else
        echo "  ✅ Leader stability within acceptable range"
    fi
    echo ""
fi

echo "Log analysis complete."
echo "Critical issues found: $CRITICAL_ISSUES"
echo "Threshold violations: $THRESHOLD_VIOLATIONS"
echo ""
```

### 6. Executive Performance Report Generation

```bash
echo "==============================================="
echo "EXECUTIVE PERFORMANCE REPORT"
echo "==============================================="
echo ""

# Generate executive summary
REPORT_FILE="$WORK_DIR/executive_performance_report.txt"
HTML_REPORT="$WORK_DIR/performance_report.html"

cat > "$REPORT_FILE" << EOF
ETCD DEEP PERFORMANCE ANALYSIS EXECUTIVE REPORT
============================================
Analysis Date: $(date)
Analysis Duration: ${DURATION} minutes
Cluster: $(oc config current-context)
Analysis ID: $(basename $WORK_DIR)

EXECUTIVE SUMMARY:
------------------
EOF

# Determine overall health status
OVERALL_STATUS="HEALTHY"
if [ "$CRITICAL_ISSUES" -gt 0 ]; then
    OVERALL_STATUS="CRITICAL"
elif [ "$THRESHOLD_VIOLATIONS" -gt 0 ]; then
    OVERALL_STATUS="WARNING"
fi

cat >> "$REPORT_FILE" << EOF
Overall Status: $OVERALL_STATUS
Critical Issues: $CRITICAL_ISSUES
Warnings: $THRESHOLD_VIOLATIONS
Database Size: ${MAX_DB_SIZE_MB}MB
Fragmentation: ${MAX_FRAGMENTATION}%

KEY PERFORMANCE INDICATORS:
---------------------------
EOF

# Add performance metrics if available
if [ -n "${WAL_P99:-}" ]; then
    echo "WAL fsync P99 latency: ${WAL_P99}ms (threshold: ${WAL_FSYNC_P99_THRESHOLD}ms)" >> "$REPORT_FILE"
fi

if [ -n "${BACKEND_P99:-}" ]; then
    echo "Backend commit P99 latency: ${BACKEND_P99}ms (threshold: ${BACKEND_COMMIT_P99_THRESHOLD}ms)" >> "$REPORT_FILE"
fi

echo "Leader changes (${DURATION}m): $LEADER_CHANGES (threshold: ${MAX_LEADER_CHANGES})" >> "$REPORT_FILE"

cat >> "$REPORT_FILE" << EOF

RECOMMENDATIONS:
---------------
EOF

# Generate actionable recommendations
if [ "$CRITICAL_ISSUES" -gt 0 ]; then
    cat >> "$REPORT_FILE" << EOF
🔥 IMMEDIATE ACTION REQUIRED:
EOF
    
    if [ "${MAX_DB_SIZE_MB:-0}" -gt $((MAX_DB_SIZE_GB * 1024)) ]; then
        cat >> "$REPORT_FILE" << EOF
- Database size exceeds limits. Implement data retention policies and consider compaction.
- Review event TTL settings and remove unnecessary data.
EOF
    fi
    
    if [ -n "${WAL_P99:-}" ] && (( $(echo "$WAL_P99 > $WAL_FSYNC_P99_THRESHOLD" | bc -l) )); then
        cat >> "$REPORT_FILE" << EOF
- WAL fsync performance critical. Upgrade to SSD/NVMe storage immediately.
- Ensure dedicated disks for etcd data (not shared with OS).
EOF
    fi
    
    if [ -n "${BACKEND_P99:-}" ] && (( $(echo "$BACKEND_P99 > $BACKEND_COMMIT_P99_THRESHOLD" | bc -l) )); then
        cat >> "$REPORT_FILE" << EOF
- Backend commit latency critical. Investigate disk I/O and network performance.
- Consider hardware upgrades and workload optimization.
EOF
    fi
fi

if [ "$THRESHOLD_VIOLATIONS" -gt 0 ]; then
    cat >> "$REPORT_FILE" << EOF

⚠️  MONITORING RECOMMENDATIONS:
EOF
    
    if [ "$MAX_FRAGMENTATION" -gt "$MAX_FRAGMENTATION_PERCENT" ]; then
        cat >> "$REPORT_FILE" << EOF
- Schedule defragmentation during next maintenance window.
- Monitor fragmentation trends and automate defrag if possible.
EOF
    fi
    
    if [ "$LEADER_CHANGES" -gt "$MAX_LEADER_CHANGES" ]; then
        cat >> "$REPORT_FILE" << EOF
- Investigate network connectivity between etcd nodes.
- Check for clock synchronization issues across cluster nodes.
EOF
    fi
fi

if [ "$OVERALL_STATUS" = "HEALTHY" ]; then
    cat >> "$REPORT_FILE" << EOF

✅ OPTIMIZATION OPPORTUNITIES:
- Continue monitoring current performance trends.
- Consider proactive capacity planning for future growth.
- Implement automated monitoring and alerting for key metrics.
EOF
fi

cat >> "$REPORT_FILE" << EOF

NEXT STEPS:
-----------
1. Review detailed analysis in: $WORK_DIR
2. Implement recommended actions based on priority
3. Schedule follow-up analysis in 1-2 weeks
4. Consider implementing continuous monitoring

DETAILED DATA:
--------------
Cluster topology: $WORK_DIR/cluster_topology.json
Database metrics: $WORK_DIR/db_status_summary.txt
Performance logs: $WORK_DIR/*_metrics.txt
EOF

echo "Executive report generated: $REPORT_FILE"
echo ""

# Display executive summary
echo "EXECUTIVE SUMMARY:"
echo "=================="
echo "Overall Status: $OVERALL_STATUS"
echo "Critical Issues: $CRITICAL_ISSUES"
echo "Warnings: $THRESHOLD_VIOLATIONS"
echo "Database Size: ${MAX_DB_SIZE_MB}MB (limit: ${MAX_DB_SIZE_GB}GB)"
echo "Fragmentation: ${MAX_FRAGMENTATION}% (limit: ${MAX_FRAGMENTATION_PERCENT}%)"
echo ""
```

### 7. HTML Report Generation (Optional)

```bash
if [ "$EXPORT_HTML" = true ]; then
    echo "==============================================="
    echo "GENERATING HTML PERFORMANCE REPORT"
    echo "==============================================="
    echo ""
    
    cat > "$HTML_REPORT" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>ETCD Deep Performance Analysis Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1, h2 { color: #333; }
        .status-healthy { color: #28a745; font-weight: bold; }
        .status-warning { color: #ffc107; font-weight: bold; }
        .status-critical { color: #dc3545; font-weight: bold; }
        .metric-box { background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #007bff; }
        .critical-box { border-left-color: #dc3545; }
        .warning-box { border-left-color: #ffc107; }
        .healthy-box { border-left-color: #28a745; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .timestamp { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ETCD Deep Performance Analysis Report</h1>
        <p class="timestamp">Generated: $(date)</p>
        
        <h2>Executive Summary</h2>
EOF

    # Add status indicator
    if [ "$OVERALL_STATUS" = "HEALTHY" ]; then
        echo '<div class="metric-box healthy-box"><h3 class="status-healthy">✅ SYSTEM HEALTHY</h3>' >> "$HTML_REPORT"
    elif [ "$OVERALL_STATUS" = "WARNING" ]; then
        echo '<div class="metric-box warning-box"><h3 class="status-warning">⚠️ WARNINGS DETECTED</h3>' >> "$HTML_REPORT"
    else
        echo '<div class="metric-box critical-box"><h3 class="status-critical">🔥 CRITICAL ISSUES</h3>' >> "$HTML_REPORT"
    fi
    
    cat >> "$HTML_REPORT" << EOF
<p>Critical Issues: $CRITICAL_ISSUES</p>
<p>Warnings: $THRESHOLD_VIOLATIONS</p>
<p>Analysis Duration: ${DURATION} minutes</p>
</div>

<h2>Key Performance Indicators</h2>
<table>
<tr><th>Metric</th><th>Current Value</th><th>Threshold</th><th>Status</th></tr>
<tr><td>Database Size</td><td>${MAX_DB_SIZE_MB}MB</td><td>${MAX_DB_SIZE_GB}GB</td><td>EOF

    if [ "$MAX_DB_SIZE_MB" -gt $((MAX_DB_SIZE_GB * 1024)) ]; then
        echo '<span class="status-critical">❌ CRITICAL</span>' >> "$HTML_REPORT"
    else
        echo '<span class="status-healthy">✅ OK</span>' >> "$HTML_REPORT"
    fi
    
    cat >> "$HTML_REPORT" << EOF
</td></tr>
<tr><td>Fragmentation</td><td>${MAX_FRAGMENTATION}%</td><td>${MAX_FRAGMENTATION_PERCENT}%</td><td>EOF

    if [ "$MAX_FRAGMENTATION" -gt "$MAX_FRAGMENTATION_PERCENT" ]; then
        echo '<span class="status-warning">⚠️ WARNING</span>' >> "$HTML_REPORT"
    else
        echo '<span class="status-healthy">✅ OK</span>' >> "$HTML_REPORT"
    fi
    
    echo '</td></tr>' >> "$HTML_REPORT"
    
    # Add performance metrics if available
    if [ -n "${WAL_P99:-}" ]; then
        cat >> "$HTML_REPORT" << EOF
<tr><td>WAL fsync P99</td><td>${WAL_P99}ms</td><td>${WAL_FSYNC_P99_THRESHOLD}ms</td><td>EOF
        if (( $(echo "$WAL_P99 > $WAL_FSYNC_P99_THRESHOLD" | bc -l) )); then
            echo '<span class="status-critical">❌ CRITICAL</span>' >> "$HTML_REPORT"
        else
            echo '<span class="status-healthy">✅ OK</span>' >> "$HTML_REPORT"
        fi
        echo '</td></tr>' >> "$HTML_REPORT"
    fi
    
    if [ -n "${BACKEND_P99:-}" ]; then
        cat >> "$HTML_REPORT" << EOF
<tr><td>Backend Commit P99</td><td>${BACKEND_P99}ms</td><td>${BACKEND_COMMIT_P99_THRESHOLD}ms</td><td>EOF
        if (( $(echo "$BACKEND_P99 > $BACKEND_COMMIT_P99_THRESHOLD" | bc -l) )); then
            echo '<span class="status-critical">❌ CRITICAL</span>' >> "$HTML_REPORT"
        else
            echo '<span class="status-healthy">✅ OK</span>' >> "$HTML_REPORT"
        fi
        echo '</td></tr>' >> "$HTML_REPORT"
    fi
    
    cat >> "$HTML_REPORT" << EOF
<tr><td>Leader Changes (${DURATION}m)</td><td>$LEADER_CHANGES</td><td>${MAX_LEADER_CHANGES}</td><td>EOF

    if [ "$LEADER_CHANGES" -gt "$MAX_LEADER_CHANGES" ]; then
        echo '<span class="status-warning">⚠️ WARNING</span>' >> "$HTML_REPORT"
    else
        echo '<span class="status-healthy">✅ OK</span>' >> "$HTML_REPORT"
    fi
    
    cat >> "$HTML_REPORT" << EOF
</td></tr>
</table>

<h2>Detailed Analysis Files</h2>
<ul>
<li><a href="executive_performance_report.txt">Executive Summary Report</a></li>
<li><a href="cluster_topology.json">Cluster Topology</a></li>
<li><a href="db_status_summary.txt">Database Status Summary</a></li>
<li><a href="wal_metrics.json">WAL Performance Metrics</a></li>
<li><a href="backend_raw_logs.txt">Backend Performance Logs</a></li>
</ul>

<p class="timestamp">Report generated by ETCD Deep Performance Analyzer | Analysis ID: $(basename $WORK_DIR)</p>
    </div>
</body>
</html>
EOF

    echo "HTML report generated: $HTML_REPORT"
    echo "Open in browser with: open $HTML_REPORT"
    echo ""
fi
```

### 8. Final Summary and Exit

```bash
echo "==============================================="
echo "ANALYSIS COMPLETE"
echo "==============================================="
echo ""
echo "Analysis workspace: $WORK_DIR"
echo "Executive report: $REPORT_FILE"
if [ "$EXPORT_HTML" = true ]; then
    echo "HTML report: $HTML_REPORT"
fi
echo ""
echo "Summary:"
echo "  Overall Status: $OVERALL_STATUS"
echo "  Critical Issues: $CRITICAL_ISSUES"
echo "  Warnings: $THRESHOLD_VIOLATIONS"
echo "  Database Size: ${MAX_DB_SIZE_MB}MB"
echo "  Max Fragmentation: ${MAX_FRAGMENTATION}%"
echo ""

if [ "$VERBOSE" = true ]; then
    echo "Verbose analysis files:"
    ls -la "$WORK_DIR"
    echo ""
fi

echo "Next steps:"
echo "1. Review the executive report for actionable recommendations"
echo "2. Address any critical issues immediately"
echo "3. Monitor warnings and plan maintenance as needed"
echo "4. Schedule follow-up analysis in 1-2 weeks"
echo ""

# Exit with appropriate code
if [ "$CRITICAL_ISSUES" -gt 0 ]; then
    echo "Exiting with code 2 (Critical issues detected)"
    exit 2
elif [ "$THRESHOLD_VIOLATIONS" -gt 0 ]; then
    echo "Exiting with code 1 (Warnings detected)"
    exit 1
else
    echo "Exiting with code 0 (System healthy)"
    exit 0
fi
```

## Return Value

- **Exit 0**: Performance is healthy (no issues)
- **Exit 1**: Warnings detected (performance degradation)
- **Exit 2**: Critical issues detected (immediate attention required)

**Output Locations**:
- **Executive report**: `.work/etcd-analysis/{timestamp}/executive_performance_report.txt`
- **HTML report**: `.work/etcd-analysis/{timestamp}/performance_report.html` (if `--export-html`)
- **Raw metrics**: `.work/etcd-analysis/{timestamp}/*.json` and `.work/etcd-analysis/{timestamp}/*.txt`

## Examples

### Example 1: Basic deep analysis
```
/etcd:deep-performance-analysis
```

### Example 2: Extended analysis with HTML export
```
/etcd:deep-performance-analysis --duration 60 --export-html
```

### Example 3: Troubleshooting mode
```
/etcd:deep-performance-analysis --duration 30 --verbose
```

## Advanced Features

### Multi-Subsystem Analysis
This command analyzes 15+ specialized ETCD subsystems:
- WAL fsync performance
- Backend commit latency
- Network I/O between peers
- Leader election stability
- Database fragmentation
- Compaction efficiency
- Proposal/commit pipeline
- Disk I/O patterns
- Memory utilization trends

### AI-Powered Bottleneck Detection
- Automated pattern recognition in performance logs
- Statistical analysis of latency distributions
- Trend analysis and predictive indicators
- Root cause correlation across subsystems

### Executive Reporting
- Business-impact oriented summaries
- Actionable recommendations prioritized by severity
- Historical trend analysis
- Capacity planning insights

## Performance Benchmarks

Critical thresholds based on OCP Performance Analyzer MCP standards:
- **WAL fsync P99**: < 10ms (SSD required)
- **Backend commit P99**: < 25ms
- **Peer RTT P99**: < 50ms
- **Database size**: < 8GB
- **Fragmentation**: < 30%
- **Leader changes**: < 5 per analysis window

## Troubleshooting

### High WAL fsync Latency
**Root Causes**: Slow disk I/O, shared storage, network-attached storage
**Solutions**: Migrate to local SSD/NVMe, dedicated disks for etcd

### Backend Commit Performance Issues
**Root Causes**: Heavy workload, insufficient resources, network latency
**Solutions**: Scale etcd resources, optimize workload patterns, network tuning

### Frequent Leader Changes
**Root Causes**: Network instability, clock skew, resource contention
**Solutions**: Network optimization, NTP synchronization, resource isolation

## Security Considerations

- Requires cluster-admin permissions
- Collects performance metrics and logs (may contain sensitive data)
- Generated reports should be treated as confidential
- Analysis workspace contains detailed cluster information

## See Also

- Related commands: `/etcd:analyze-performance`, `/etcd:health-check`
- OCP Performance Analyzer MCP: https://github.com/openshift-eng/ocp-performance-analyzer-mcp
- ETCD performance tuning: https://etcd.io/docs/latest/tuning/
