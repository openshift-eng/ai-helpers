---
name: Advanced ETCD Performance Analyzer
description: Comprehensive ETCD performance analysis with AI-powered insights and bottleneck detection
---

# Advanced ETCD Performance Analyzer

This skill provides sophisticated ETCD performance analysis capabilities based on the OCP Performance Analyzer MCP project. It includes 15+ specialized analysis tools, comprehensive metrics collection, and AI-powered bottleneck detection.

## When to Use This Skill

Use this skill when implementing advanced ETCD performance analysis commands that require:

1. **Multi-dimensional performance analysis** across WAL, backend, network, and storage subsystems
2. **Statistical analysis** of performance metrics with percentile calculations
3. **Trend analysis** and performance degradation detection
4. **Executive reporting** with actionable recommendations
5. **Real-time monitoring** with intelligent alerting
6. **Root cause analysis** for complex performance issues

## Prerequisites

### Required Tools
- `oc` (OpenShift CLI) - cluster access and etcd pod management
- `jq` - JSON processing for metrics parsing
- `bc` - Mathematical calculations and threshold comparisons
- `awk`, `sed`, `grep` - Text processing for log analysis
- `tput` - Terminal formatting for real-time displays

### Required Permissions
- Cluster-admin or equivalent permissions
- Access to `openshift-etcd` namespace
- Ability to execute commands in etcd pods
- Log access for etcd containers

### Environment Setup
```bash
# Verify prerequisites
if ! command -v oc &> /dev/null; then
    echo "Error: oc CLI not found. Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
    exit 1
fi

for tool in jq bc awk sed grep tput; do
    if ! command -v "$tool" &> /dev/null; then
        echo "Error: $tool not found. Install required tools."
        exit 1
    fi
done

# Verify cluster access
if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to OpenShift cluster"
    exit 1
fi

# Check permissions
if ! oc auth can-i get pods -n openshift-etcd &> /dev/null; then
    echo "Error: Insufficient permissions to access etcd namespace"
    exit 1
fi
```

## Implementation Steps

### Step 1: ETCD Cluster Discovery and Validation

```bash
# Discover running etcd pods
get_etcd_pods() {
    oc get pods -n openshift-etcd -l app=etcd \
        --field-selector=status.phase=Running \
        -o jsonpath='{.items[*].metadata.name}'
}

# Validate cluster health
validate_cluster_health() {
    local pods=($1)
    
    if [ ${#pods[@]} -eq 0 ]; then
        echo "CRITICAL: No running etcd pods found"
        return 1
    fi
    
    echo "Found ${#pods[@]} running etcd pods:"
    for pod in "${pods[@]}"; do
        echo "  - $pod"
    done
    
    # Test connectivity to primary pod
    local primary_pod="${pods[0]}"
    if ! oc exec -n openshift-etcd "$primary_pod" -c etcdctl -- \
        etcdctl endpoint health --cluster &>/dev/null; then
        echo "WARNING: Cluster health check failed"
        return 1
    fi
    
    echo "Cluster connectivity validated"
    return 0
}
```

### Step 2: Performance Metrics Collection

```bash
# Collect comprehensive performance metrics
collect_performance_metrics() {
    local pod="$1"
    local duration="$2"
    local work_dir="$3"
    
    echo "Collecting performance metrics for ${duration}m window..."
    
    # Database status and fragmentation
    oc exec -n openshift-etcd "$pod" -c etcdctl -- \
        etcdctl endpoint status --cluster -w json > "$work_dir/db_status.json" 2>/dev/null
    
    # Member list and topology
    oc exec -n openshift-etcd "$pod" -c etcdctl -- \
        etcdctl member list -w json > "$work_dir/cluster_members.json" 2>/dev/null
    
    # Recent logs for analysis
    oc logs -n openshift-etcd "$pod" -c etcd \
        --since="${duration}m" > "$work_dir/etcd_logs.txt" 2>/dev/null
    
    # Performance-specific log patterns
    grep -iE "wal.*fsync|backend.*commit|apply.*took" "$work_dir/etcd_logs.txt" \
        > "$work_dir/performance_events.txt" 2>/dev/null || true
    
    grep -iE "leader.*changed|became.*leader|election" "$work_dir/etcd_logs.txt" \
        > "$work_dir/leadership_events.txt" 2>/dev/null || true
    
    grep -iE "compaction|defrag" "$work_dir/etcd_logs.txt" \
        > "$work_dir/maintenance_events.txt" 2>/dev/null || true
        
    echo "Metrics collection completed"
}
```

### Step 3: Statistical Performance Analysis

```bash
# Perform statistical analysis on performance metrics
analyze_performance_statistics() {
    local work_dir="$1"
    
    echo "Performing statistical analysis..."
    
    # WAL fsync latency analysis
    if [ -s "$work_dir/performance_events.txt" ]; then
        grep -i "wal.*fsync.*took" "$work_dir/performance_events.txt" | \
            grep -oE "[0-9]+\\.?[0-9]*ms" | \
            sed 's/ms//' | \
            sort -n > "$work_dir/wal_latencies.txt"
        
        if [ -s "$work_dir/wal_latencies.txt" ]; then
            calculate_percentiles "$work_dir/wal_latencies.txt" "WAL fsync" "ms"
        fi
        
        # Backend commit latency analysis
        grep -i "backend.*commit.*took" "$work_dir/performance_events.txt" | \
            grep -oE "[0-9]+\\.?[0-9]*ms" | \
            sed 's/ms//' | \
            sort -n > "$work_dir/backend_latencies.txt"
        
        if [ -s "$work_dir/backend_latencies.txt" ]; then
            calculate_percentiles "$work_dir/backend_latencies.txt" "Backend commit" "ms"
        fi
    fi
}

# Calculate percentile statistics
calculate_percentiles() {
    local data_file="$1"
    local metric_name="$2"
    local unit="$3"
    
    local count=$(wc -l < "$data_file")
    if [ $count -eq 0 ]; then
        return
    fi
    
    local p50_line=$((count / 2))
    local p95_line=$((count * 95 / 100))
    local p99_line=$((count * 99 / 100))
    
    local p50=$(sed -n "${p50_line}p" "$data_file")
    local p95=$(sed -n "${p95_line}p" "$data_file")
    local p99=$(sed -n "${p99_line}p" "$data_file")
    local max=$(tail -1 "$data_file")
    
    echo "$metric_name statistics (${count} samples):"
    echo "  P50: ${p50}${unit}"
    echo "  P95: ${p95}${unit}"
    echo "  P99: ${p99}${unit}"
    echo "  Max: ${max}${unit}"
    echo ""
}
```

### Step 4: Threshold-Based Analysis

```bash
# Analyze metrics against performance thresholds
analyze_thresholds() {
    local work_dir="$1"
    local alert_level="$2"  # critical, warning, info
    
    # Define thresholds based on OCP Performance Analyzer MCP standards
    case $alert_level in
        critical)
            local wal_threshold=20
            local backend_threshold=50
            local frag_threshold=60
            ;;
        warning)
            local wal_threshold=10
            local backend_threshold=25
            local frag_threshold=30
            ;;
        info)
            local wal_threshold=5
            local backend_threshold=15
            local frag_threshold=20
            ;;
    esac
    
    local violations=0
    local critical_issues=0
    
    echo "Threshold Analysis ($alert_level level):"
    echo "WAL fsync: <${wal_threshold}ms, Backend: <${backend_threshold}ms, Fragmentation: <${frag_threshold}%"
    echo ""
    
    # Database size and fragmentation analysis\n    if [ -s "$work_dir/db_status.json" ]; then\n        local max_db_size_mb=$(jq -r '[.[] | (.Status.dbSize / 1024 / 1024)] | max | floor' "$work_dir/db_status.json")\n        local max_fragmentation=$(jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max | floor' "$work_dir/db_status.json")\n        \n        echo "Database Analysis:"\n        echo "  Size: ${max_db_size_mb}MB"\n        echo "  Fragmentation: ${max_fragmentation}%"\n        \n        if [ "$max_fragmentation" -gt "$frag_threshold" ]; then\n            echo "  ⚠️ Fragmentation exceeds ${frag_threshold}% threshold"\n            violations=$((violations + 1))\n        else\n            echo "  ✅ Fragmentation within limits"\n        fi\n        \n        if [ "$max_db_size_mb" -gt 8192 ]; then  # 8GB limit\n            echo "  🔥 Database size exceeds 8GB limit"\n            critical_issues=$((critical_issues + 1))\n        else\n            echo "  ✅ Database size within limits"\n        fi\n        echo ""\n    fi\n    \n    # WAL performance analysis\n    if [ -s "$work_dir/wal_latencies.txt" ]; then\n        local wal_p99=$(tail -1 "$work_dir/wal_latencies.txt")\n        echo "WAL Performance:"\n        echo "  P99 latency: ${wal_p99}ms"\n        \n        if (( $(echo "$wal_p99 > $wal_threshold" | bc -l) )); then\n            if [ "$wal_threshold" -le 10 ]; then\n                echo "  🔥 Critical WAL performance issue"\n                critical_issues=$((critical_issues + 1))\n            else\n                echo "  ⚠️ WAL performance degradation"\n                violations=$((violations + 1))\n            fi\n        else\n            echo "  ✅ WAL performance acceptable"\n        fi\n        echo ""\n    fi\n    \n    # Backend performance analysis\n    if [ -s "$work_dir/backend_latencies.txt" ]; then\n        local backend_p99=$(tail -1 "$work_dir/backend_latencies.txt")\n        echo "Backend Performance:"\n        echo "  P99 latency: ${backend_p99}ms"\n        \n        if (( $(echo "$backend_p99 > $backend_threshold" | bc -l) )); then\n            if [ "$backend_threshold" -le 25 ]; then\n                echo "  🔥 Critical backend performance issue"\n                critical_issues=$((critical_issues + 1))\n            else\n                echo "  ⚠️ Backend performance degradation"\n                violations=$((violations + 1))\n            fi\n        else\n            echo "  ✅ Backend performance acceptable"\n        fi\n        echo ""\n    fi\n    \n    # Leader stability analysis\n    if [ -s "$work_dir/leadership_events.txt" ]; then\n        local leader_changes=$(wc -l < "$work_dir/leadership_events.txt")\n        echo "Leadership Stability:"\n        echo "  Leader changes: $leader_changes"\n        \n        if [ "$leader_changes" -gt 5 ]; then\n            echo "  ⚠️ Excessive leader changes detected"\n            violations=$((violations + 1))\n        else\n            echo "  ✅ Leader stability acceptable"\n        fi\n        echo ""\n    fi\n    \n    echo "Threshold Analysis Summary:"\n    echo "  Critical Issues: $critical_issues"\n    echo "  Warnings: $violations"\n    echo ""\n    \n    return $((critical_issues + violations))\n}\n```\n\n### Step 5: AI-Powered Bottleneck Detection\n\n```bash\n# Perform intelligent bottleneck detection\ndetect_bottlenecks() {\n    local work_dir="$1"\n    \n    echo "AI-Powered Bottleneck Detection:"\n    echo "=============================="\n    \n    local bottlenecks=()\n    \n    # Analyze patterns in performance events\n    if [ -s "$work_dir/performance_events.txt" ]; then\n        \n        # Disk I/O bottleneck detection\n        local disk_events=$(grep -iE "fsync|fdatasync|wal.*took" "$work_dir/performance_events.txt" | wc -l)\n        local slow_disk_events=$(grep -iE "fsync.*[5-9][0-9]ms|fsync.*[0-9]{3,}ms" "$work_dir/performance_events.txt" | wc -l)\n        \n        if [ "$slow_disk_events" -gt 0 ] && [ $((slow_disk_events * 100 / disk_events)) -gt 20 ]; then\n            bottlenecks+=("DISK_IO")\n            echo "🔍 Disk I/O Bottleneck Detected:"\n            echo "   - Slow disk operations: $slow_disk_events/$disk_events (>20%)"   \n            echo "   - Recommendation: Upgrade to SSD/NVMe storage"\n            echo "   - Check for storage contention and competing I/O"\n            echo ""\n        fi\n        \n        # Network bottleneck detection\n        local network_events=$(grep -iE "peer|network|sendMessage|recvMessage" "$work_dir/etcd_logs.txt" | \\\n            grep -iE "slow|timeout|failed" | wc -l)\n        \n        if [ "$network_events" -gt 5 ]; then\n            bottlenecks+=("NETWORK")\n            echo "🔍 Network Bottleneck Detected:"\n            echo "   - Network issues: $network_events events"\n            echo "   - Recommendation: Check network connectivity between etcd nodes"\n            echo "   - Verify network latency and packet loss"\n            echo ""\n        fi\n        \n        # Memory/CPU bottleneck detection\n        local apply_events=$(grep -i "apply.*took" "$work_dir/performance_events.txt" | wc -l)\n        local slow_apply=$(grep -iE "apply.*took.*[1-9][0-9]{2,}ms" "$work_dir/performance_events.txt" | wc -l)\n        \n        if [ "$slow_apply" -gt 0 ] && [ $((slow_apply * 100 / apply_events)) -gt 15 ]; then\n            bottlenecks+=("COMPUTE")\n            echo "🔍 Compute Resource Bottleneck Detected:"\n            echo "   - Slow apply operations: $slow_apply/$apply_events (>15%)"\n            echo "   - Recommendation: Check CPU and memory resources"\n            echo "   - Consider etcd resource limits and requests"\n            echo ""\n        fi\n        \n        # Workload bottleneck detection\n        local total_events=$(wc -l < "$work_dir/performance_events.txt")\n        if [ "$total_events" -gt 100 ]; then\n            bottlenecks+=("WORKLOAD")\n            echo "🔍 High Workload Detected:"\n            echo "   - Performance events: $total_events"\n            echo "   - Recommendation: Analyze application workload patterns"\n            echo "   - Consider request rate limiting and optimization"\n            echo ""\n        fi\n    fi\n    \n    # Database-specific bottlenecks\n    if [ -s "$work_dir/db_status.json" ]; then\n        local avg_db_size=$(jq -r '[.[] | .Status.dbSize] | add / length' "$work_dir/db_status.json")\n        local avg_db_size_gb=$(echo "scale=2; $avg_db_size / 1024 / 1024 / 1024" | bc)\n        \n        if (( $(echo "$avg_db_size_gb > 6" | bc -l) )); then\n            bottlenecks+=("DATABASE_SIZE")\n            echo "🔍 Database Size Bottleneck Detected:"\n            echo "   - Average database size: ${avg_db_size_gb}GB"\n            echo "   - Recommendation: Implement data retention policies"\n            echo "   - Schedule regular compaction and defragmentation"\n            echo ""\n        fi\n    fi\n    \n    # Maintenance bottleneck detection\n    if [ -s "$work_dir/maintenance_events.txt" ]; then\n        local compaction_count=$(grep -i "compaction" "$work_dir/maintenance_events.txt" | wc -l)\n        local slow_compactions=$(grep -iE "compaction.*took.*[5-9][0-9]{2,}ms" "$work_dir/maintenance_events.txt" | wc -l)\n        \n        if [ "$slow_compactions" -gt 0 ]; then\n            bottlenecks+=("MAINTENANCE")\n            echo "🔍 Maintenance Performance Bottleneck Detected:"\n            echo "   - Slow compactions: $slow_compactions/$compaction_count"\n            echo "   - Recommendation: Schedule compaction during low-traffic periods"\n            echo "   - Check for resource contention during maintenance"\n            echo ""\n        fi\n    fi\n    \n    # Summary\n    if [ ${#bottlenecks[@]} -eq 0 ]; then\n        echo "✅ No significant bottlenecks detected"\n        echo "   System appears to be performing within acceptable parameters"\n    else\n        echo "📊 Bottleneck Summary:"\n        echo "   Detected bottlenecks: ${#bottlenecks[@]}"\n        for bottleneck in "${bottlenecks[@]}"; do\n            echo "   - $bottleneck"\n        done\n        echo ""\n        echo "🔧 Priority Actions:"\n        if [[ " ${bottlenecks[*]} " =~ " DISK_IO " ]]; then\n            echo "   1. HIGH: Upgrade storage to SSD/NVMe"\n        fi\n        if [[ " ${bottlenecks[*]} " =~ " NETWORK " ]]; then\n            echo "   2. HIGH: Investigate network connectivity"\n        fi\n        if [[ " ${bottlenecks[*]} " =~ " DATABASE_SIZE " ]]; then\n            echo "   3. MEDIUM: Implement data retention policies"\n        fi\n        if [[ " ${bottlenecks[*]} " =~ " COMPUTE " ]]; then\n            echo "   4. MEDIUM: Review resource allocation"\n        fi\n    fi\n    \n    echo ""\n}\n```\n\n### Step 6: Executive Report Generation\n\n```bash\n# Generate executive-level performance report\ngenerate_executive_report() {\n    local work_dir="$1"\n    local analysis_duration="$2"\n    local critical_issues="$3"\n    local warnings="$4"\n    \n    local report_file="$work_dir/executive_performance_report.txt"\n    \n    cat > "$report_file" << EOF\nETCD PERFORMANCE ANALYSIS EXECUTIVE REPORT\n==========================================\nGenerated: $(date)\nAnalysis Duration: ${analysis_duration} minutes\nCluster: $(oc config current-context)\n\nEXECUTIVE SUMMARY\n-----------------\nEOF\n    \n    # Determine overall status\n    if [ "$critical_issues" -gt 0 ]; then\n        echo "Status: 🔥 CRITICAL - Immediate action required" >> "$report_file"\n        echo "Impact: High risk of cluster performance degradation" >> "$report_file"\n    elif [ "$warnings" -gt 0 ]; then\n        echo "Status: ⚠️ WARNING - Monitoring recommended" >> "$report_file"\n        echo "Impact: Moderate performance concerns detected" >> "$report_file"\n    else\n        echo "Status: ✅ HEALTHY - Performance within acceptable limits" >> "$report_file"\n        echo "Impact: No immediate performance risks identified" >> "$report_file"\n    fi\n    \n    cat >> "$report_file" << EOF\n\nIssues Identified: $critical_issues critical, $warnings warnings\nRecommended Actions: See detailed recommendations below\n\nKEY PERFORMANCE INDICATORS\n--------------------------\nEOF\n    \n    # Add KPIs from analysis\n    if [ -s "$work_dir/db_status.json" ]; then\n        local max_db_size_mb=$(jq -r '[.[] | (.Status.dbSize / 1024 / 1024)] | max | floor' "$work_dir/db_status.json")\n        local max_fragmentation=$(jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max | floor' "$work_dir/db_status.json")\n        \n        echo "Database Size: ${max_db_size_mb}MB (Target: <8GB)" >> "$report_file"\n        echo "Fragmentation: ${max_fragmentation}% (Target: <30%)" >> "$report_file"\n    fi\n    \n    if [ -s "$work_dir/wal_latencies.txt" ]; then\n        local wal_p99=$(tail -1 "$work_dir/wal_latencies.txt")\n        echo "WAL fsync P99: ${wal_p99}ms (Target: <10ms)" >> "$report_file"\n    fi\n    \n    if [ -s "$work_dir/backend_latencies.txt" ]; then\n        local backend_p99=$(tail -1 "$work_dir/backend_latencies.txt")\n        echo "Backend commit P99: ${backend_p99}ms (Target: <25ms)" >> "$report_file"\n    fi\n    \n    cat >> "$report_file" << EOF\n\nRECOMMENDATIONS\n---------------\nEOF\n    \n    # Add specific recommendations based on findings\n    if [ "$critical_issues" -gt 0 ]; then\n        echo "IMMEDIATE ACTIONS (Critical Priority):" >> "$report_file"\n        \n        if [ -s "$work_dir/wal_latencies.txt" ]; then\n            local wal_p99=$(tail -1 "$work_dir/wal_latencies.txt")\n            if (( $(echo "$wal_p99 > 10" | bc -l) )); then\n                echo "• Upgrade to SSD/NVMe storage for etcd data volumes" >> "$report_file"\n                echo "• Ensure dedicated disks for etcd (not shared with OS)" >> "$report_file"\n            fi\n        fi\n        \n        if [ -s "$work_dir/backend_latencies.txt" ]; then\n            local backend_p99=$(tail -1 "$work_dir/backend_latencies.txt")\n            if (( $(echo "$backend_p99 > 25" | bc -l) )); then\n                echo "• Investigate and optimize cluster workload patterns" >> "$report_file"\n                echo "• Review etcd resource allocation (CPU, memory)" >> "$report_file"\n            fi\n        fi\n        \n        echo "" >> "$report_file"\n    fi\n    \n    if [ "$warnings" -gt 0 ]; then\n        echo "MONITORING ACTIONS (High Priority):" >> "$report_file"\n        \n        if [ -s "$work_dir/db_status.json" ]; then\n            local max_fragmentation=$(jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max | floor' "$work_dir/db_status.json")\n            if [ "$max_fragmentation" -gt 30 ]; then\n                echo "• Schedule defragmentation during next maintenance window" >> "$report_file"\n                echo "• Monitor fragmentation trends and automate if possible" >> "$report_file"\n            fi\n        fi\n        \n        echo "" >> "$report_file"\n    fi\n    \n    cat >> "$report_file" << EOF\nOPTIMIZATION ACTIONS (Medium Priority):\n• Implement continuous monitoring with automated alerting\n• Review and optimize data retention policies\n• Consider etcd performance baseline establishment\n• Plan capacity based on observed growth trends\n\nNEXT STEPS\n----------\n1. Review and prioritize recommendations based on business impact\n2. Schedule maintenance windows for critical actions\n3. Implement monitoring for early warning of performance issues\n4. Plan follow-up analysis in 2-4 weeks to validate improvements\n\nDETAILED ANALYSIS DATA\n---------------------\nFull analysis data available in: $work_dir\n• Database metrics: db_status.json\n• Performance events: performance_events.txt\n• Leadership events: leadership_events.txt\n• Statistical analysis: *_latencies.txt\n\nEOF\n    \n    echo "Executive report generated: $report_file"\n}\n```\n\n### Step 7: Real-time Dashboard Implementation\n\n```bash\n# Create real-time monitoring dashboard\ncreate_realtime_dashboard() {\n    local interval="$1"\n    local alert_threshold="$2"\n    local work_dir="$3"\n    \n    # Setup terminal for real-time display\n    clear\n    tput civis  # Hide cursor\n    \n    # Trap for cleanup\n    trap 'tput cnorm; echo ""; echo "Real-time monitoring stopped"; exit 0' INT TERM\n    \n    local iteration=0\n    local alert_count=0\n    \n    while true; do\n        iteration=$((iteration + 1))\n        \n        # Clear screen and show header\n        tput cup 0 0\n        tput ed\n        \n        echo "ETCD REAL-TIME PERFORMANCE DASHBOARD"\n        echo "===================================="\n        echo "Iteration: $iteration | $(date) | Update: ${interval}s"\n        echo "Alert Threshold: $alert_threshold | Alerts: $alert_count"\n        echo ""\n        \n        # Collect current metrics\n        local etcd_pod=$(oc get pods -n openshift-etcd -l app=etcd \\\n            --field-selector=status.phase=Running \\\n            -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)\n        \n        if [ -z "$etcd_pod" ]; then\n            echo "❌ No running etcd pods found"\n            sleep $interval\n            continue\n        fi\n        \n        # Get current database status\n        local db_status=$(oc exec -n openshift-etcd "$etcd_pod" -c etcdctl -- \\\n            etcdctl endpoint status --cluster -w json 2>/dev/null)\n        \n        if [ -n "$db_status" ]; then\n            # Parse metrics\n            local db_size_mb=$(echo "$db_status" | jq -r '[.[] | (.Status.dbSize / 1024 / 1024)] | max | floor')\n            local fragmentation=$(echo "$db_status" | jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max | floor')\n            \n            # Display current status\n            echo "📊 CURRENT METRICS"\n            printf "   Database Size:    %8s MB\\n" "$db_size_mb"\n            printf "   Fragmentation:    %8s%%\\n" "$fragmentation"\n            \n            # Check for alerts\n            local alerts=""\n            if [ "$fragmentation" -gt 30 ]; then\n                alerts="${alerts}HIGH_FRAGMENTATION "\n                alert_count=$((alert_count + 1))\n            fi\n            \n            if [ -n "$alerts" ]; then\n                echo ""\n                echo "🚨 ACTIVE ALERTS"\n                if [[ "$alerts" == *"HIGH_FRAGMENTATION"* ]]; then\n                    echo "   • High fragmentation: ${fragmentation}%"\n                fi\n            else\n                echo "   ✅ All metrics within normal range"\n            fi\n        else\n            echo "❌ Failed to collect metrics"\n        fi\n        \n        echo ""\n        echo "Press Ctrl+C to stop monitoring..."\n        \n        sleep $interval\n    done\n}\n```\n\n## Error Handling\n\n### Common Issues and Solutions\n\n1. **No etcd pods found**\n   ```bash\n   if [ ${#etcd_pods[@]} -eq 0 ]; then\n       echo "ERROR: No running etcd pods found"\n       echo "Check cluster status with: oc get pods -n openshift-etcd"\n       exit 1\n   fi\n   ```\n\n2. **Permission denied errors**\n   ```bash\n   if ! oc auth can-i exec pods -n openshift-etcd; then\n       echo "ERROR: Insufficient permissions to execute commands in etcd pods"\n       echo "Required: cluster-admin or equivalent permissions"\n       exit 1\n   fi\n   ```\n\n3. **Metric collection failures**\n   ```bash\n   collect_metrics_with_retry() {\n       local pod="$1"\n       local retries=3\n       \n       for i in $(seq 1 $retries); do\n           if oc exec -n openshift-etcd "$pod" -c etcdctl -- \\\n               etcdctl endpoint status --cluster -w json &>/dev/null; then\n               return 0\n           fi\n           echo "Retry $i/$retries for metric collection..."\n           sleep 2\n       done\n       \n       echo "ERROR: Failed to collect metrics after $retries attempts"\n       return 1\n   }\n   ```\n\n4. **Invalid analysis data**\n   ```bash\n   validate_analysis_data() {\n       local work_dir="$1"\n       \n       if [ ! -s "$work_dir/db_status.json" ]; then\n           echo "WARNING: Database status data missing or empty"\n           return 1\n       fi\n       \n       if ! jq empty "$work_dir/db_status.json" 2>/dev/null; then\n           echo "ERROR: Invalid JSON in database status"\n           return 1\n       fi\n       \n       return 0\n   }\n   ```\n\n## Examples\n\n### Complete Deep Analysis Implementation\n```bash\n#!/bin/bash\n\n# Source the advanced analyzer skill\nsource "plugins/etcd/skills/advanced-etcd-analyzer/SKILL.md"\n\n# Parse arguments\nDURATION=15\nVERBOSE=false\nEXPORT_HTML=false\n\n# Process command line arguments...\n\n# Create workspace\nWORK_DIR=\".work/etcd-analysis/$(date +%Y%m%d_%H%M%S)\"\nmkdir -p "$WORK_DIR"\n\n# Execute analysis steps\necho "Starting advanced ETCD performance analysis..."\n\n# Step 1: Cluster discovery\nETCD_PODS=($(get_etcd_pods))\nvalidate_cluster_health "${ETCD_PODS[@]}" || exit 1\n\n# Step 2: Metrics collection\ncollect_performance_metrics "${ETCD_PODS[0]}" "$DURATION" "$WORK_DIR"\n\n# Step 3: Statistical analysis\nanalyze_performance_statistics "$WORK_DIR"\n\n# Step 4: Threshold analysis\nanalyze_thresholds "$WORK_DIR" "warning"\nTHRESHOLD_RESULT=$?\n\n# Step 5: Bottleneck detection\ndetect_bottlenecks "$WORK_DIR"\n\n# Step 6: Executive reporting\ngenerate_executive_report "$WORK_DIR" "$DURATION" "0" "$THRESHOLD_RESULT"\n\necho "Analysis complete. Results in: $WORK_DIR"\n```\n\n### Real-time Monitoring Implementation\n```bash\n#!/bin/bash\n\n# Source the advanced analyzer skill\nsource "plugins/etcd/skills/advanced-etcd-analyzer/SKILL.md"\n\n# Parse arguments for real-time monitoring\nINTERVAL=5\nALERT_THRESHOLD="warning"\nWORK_DIR=\".work/etcd-realtime/$(date +%Y%m%d_%H%M%S)\"\n\n# Process command line arguments...\n\n# Create workspace\nmkdir -p "$WORK_DIR"\n\n# Start real-time dashboard\necho "Starting real-time ETCD performance monitoring..."\ncreate_realtime_dashboard "$INTERVAL" "$ALERT_THRESHOLD" "$WORK_DIR"\n```\n\n## Integration Points\n\nThis skill integrates with:\n\n1. **OpenShift CLI tools** for cluster access and pod management\n2. **ETCD command-line tools** via etcdctl for metrics collection\n3. **System utilities** for log analysis and statistical calculations\n4. **Terminal formatting** for real-time dashboard display\n5. **JSON processing** for structured data analysis\n6. **External monitoring systems** via CSV export and structured logging\n\n## Performance Considerations\n\n- **Metrics collection impact**: Minimized through efficient etcdctl usage\n- **Log analysis optimization**: Uses grep patterns before detailed processing\n- **Memory usage**: Streams large log files rather than loading into memory\n- **Network impact**: Collects metrics from single pod when possible\n- **Storage requirements**: Organized workspace with automatic cleanup options\n\n## Security Notes\n\n- All operations require cluster-admin level permissions\n- Collected metrics may contain sensitive cluster operational data\n- Generated reports should be treated as confidential\n- Log data may expose internal cluster configuration details\n- Workspace directories should have appropriate access controls\n\n## Maintenance and Updates\n\nThis skill should be updated when:\n\n1. **ETCD version changes** require new metric collection methods\n2. **Performance thresholds** are revised based on operational experience\n3. **New bottleneck patterns** are identified in production environments\n4. **Monitoring requirements** evolve with cluster scale and complexity\n5. **Integration requirements** change with new tooling or processes\n