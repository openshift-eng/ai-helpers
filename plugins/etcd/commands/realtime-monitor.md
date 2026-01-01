---
description: Real-time ETCD performance monitoring with live metrics and alerting
argument-hint: "[--interval <seconds>] [--duration <minutes>] [--alert-threshold <level>]"
---

## Name
etcd:realtime-monitor

## Synopsis
```
/etcd:realtime-monitor [--interval <seconds>] [--duration <minutes>] [--alert-threshold <level>]
```

## Description

The `realtime-monitor` command provides continuous real-time monitoring of ETCD performance with live metrics display, threshold alerting, and trend analysis. This command is designed for active monitoring scenarios, troubleshooting sessions, and performance validation during cluster operations.

Key capabilities:
- Live performance metrics with configurable refresh intervals
- Real-time threshold alerting and notification
- Trend analysis and performance degradation detection
- Interactive monitoring dashboard in terminal
- Automated alert logging and notification
- Performance baseline establishment and deviation detection

This command complements the deep-performance-analysis by providing ongoing monitoring capabilities rather than point-in-time analysis.

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

4. **Terminal utilities**
   - `watch`, `tput`, `jq`, `bc` for display formatting
   - Most are available by default on Linux systems

## Arguments

- **--interval** (optional): Refresh interval in seconds (default: 5)
  - How frequently to collect and display metrics
  - Range: 1-300 seconds
  - Example: `--interval 10` for 10-second updates

- **--duration** (optional): Total monitoring duration in minutes (default: continuous)
  - Automatic stop after specified duration
  - Use 0 for continuous monitoring (manual stop with Ctrl+C)
  - Example: `--duration 30` for 30-minute monitoring session

- **--alert-threshold** (optional): Alert sensitivity level (default: warning)
  - **critical**: Alert only on critical performance issues
  - **warning**: Alert on warning-level and critical issues
  - **info**: Alert on all performance deviations
  - Example: `--alert-threshold critical`

## Implementation

### 1. Initialize Monitoring Environment

```bash
# Parse arguments with defaults
INTERVAL=5
DURATION=0  # 0 = continuous
ALERT_THRESHOLD="warning"
WORK_DIR=".work/etcd-realtime/$(date +%Y%m%d_%H%M%S)"

while [[ $# -gt 0 ]]; do
    case $1 in
        --interval)
            INTERVAL="$2"
            if [[ $INTERVAL -lt 1 || $INTERVAL -gt 300 ]]; then
                echo "Error: Interval must be between 1 and 300 seconds"
                exit 1
            fi
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --alert-threshold)
            ALERT_THRESHOLD="$2"
            if [[ ! "$ALERT_THRESHOLD" =~ ^(critical|warning|info)$ ]]; then
                echo "Error: Alert threshold must be 'critical', 'warning', or 'info'"
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create monitoring workspace
mkdir -p "$WORK_DIR"
LOG_FILE="$WORK_DIR/monitoring.log"
ALERTS_FILE="$WORK_DIR/alerts.log"
METRICS_FILE="$WORK_DIR/metrics.csv"

# Verify prerequisites
if ! command -v oc &> /dev/null; then
    echo "Error: oc CLI not found"
    exit 1
fi

for tool in jq bc tput; do
    if ! command -v "$tool" &> /dev/null; then
        echo "Error: $tool not found. Please install required tools."
        exit 1
    fi
done

# Initialize CSV header
echo "timestamp,db_size_mb,fragmentation_pct,leader_changes,slow_ops,wal_latency_ms,backend_latency_ms,status" > "$METRICS_FILE"

# Set up terminal
clear
tput civis  # Hide cursor

# Trap for cleanup on exit
trap 'tput cnorm; echo ""; echo "Monitoring stopped. Logs saved to: $WORK_DIR"; exit 0' INT TERM

echo "ETCD Real-time Performance Monitor"
echo "================================="
echo "Started: $(date)"
echo "Interval: ${INTERVAL}s | Duration: $([ $DURATION -eq 0 ] && echo "Continuous" || echo "${DURATION}m")"
echo "Alert Threshold: $ALERT_THRESHOLD"
echo "Workspace: $WORK_DIR"
echo ""
echo "Press Ctrl+C to stop monitoring"
echo ""

# Define thresholds based on alert level
case $ALERT_THRESHOLD in
    critical)
        WAL_ALERT_THRESHOLD=20
        BACKEND_ALERT_THRESHOLD=50
        FRAG_ALERT_THRESHOLD=60
        ;;
    warning)
        WAL_ALERT_THRESHOLD=10
        BACKEND_ALERT_THRESHOLD=25
        FRAG_ALERT_THRESHOLD=30
        ;;
    info)
        WAL_ALERT_THRESHOLD=5
        BACKEND_ALERT_THRESHOLD=15
        FRAG_ALERT_THRESHOLD=20
        ;;
esac

echo "Alert thresholds: WAL=${WAL_ALERT_THRESHOLD}ms, Backend=${BACKEND_ALERT_THRESHOLD}ms, Fragmentation=${FRAG_ALERT_THRESHOLD}%"
echo ""
```

### 2. Main Monitoring Loop

```bash
# Initialize monitoring variables
START_TIME=$(date +%s)
ITERATION=0
LAST_LEADER_COUNT=0
ALERT_COUNT=0

while true; do
    ITERATION=$((ITERATION + 1))
    CURRENT_TIME=$(date +%s)
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Check duration limit
    if [ $DURATION -gt 0 ]; then
        ELAPSED_MINUTES=$(( (CURRENT_TIME - START_TIME) / 60 ))
        if [ $ELAPSED_MINUTES -ge $DURATION ]; then
            echo ""
            echo "Monitoring duration completed (${DURATION}m)"
            break
        fi
    fi
    
    # Get primary etcd pod
    ETCD_POD=$(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$ETCD_POD" ]; then
        echo "$(date): ERROR - No running etcd pod found" | tee -a "$ALERTS_FILE"
        sleep $INTERVAL
        continue
    fi
    
    # Clear previous display (keep header)
    tput cup 10 0
    tput ed
    
    echo "Iteration: $ITERATION | Pod: $ETCD_POD | $(date)"
    echo "───────────────────────────────────────────────────────────────────────────"
    
    # Collect real-time metrics
    DB_STATUS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint status --cluster -w json 2>/dev/null)
    
    if [ -z "$DB_STATUS" ]; then
        echo "❌ Failed to collect etcd metrics"
        sleep $INTERVAL
        continue
    fi
    
    # Parse metrics
    MAX_DB_SIZE_MB=$(echo "$DB_STATUS" | jq -r '[.[] | (.Status.dbSize / 1024 / 1024)] | max | floor' 2>/dev/null || echo "0")\n    MAX_FRAGMENTATION=$(echo "$DB_STATUS" | jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] | max | floor' 2>/dev/null || echo "0")\n    \n    # Get recent performance logs for latency analysis\n    RECENT_LOGS=$(oc logs -n openshift-etcd "$ETCD_POD" -c etcd --since="${INTERVAL}s" 2>/dev/null)\n    \n    # Analyze WAL fsync performance\n    WAL_LATENCY="N/A"\n    WAL_SLOW_OPS=$(echo "$RECENT_LOGS" | grep -i "wal.*fsync.*took" | wc -l)\n    if [ "$WAL_SLOW_OPS" -gt 0 ]; then\n        WAL_LATENCY=$(echo "$RECENT_LOGS" | grep -i "wal.*fsync.*took" | \\\n            grep -oE "[0-9]+\\.[0-9]+ms|[0-9]+ms" | \\\n            sed 's/ms//' | sort -n | tail -1)\n        WAL_LATENCY="${WAL_LATENCY}ms"\n    fi\n    \n    # Analyze backend commit performance\n    BACKEND_LATENCY="N/A"\n    BACKEND_SLOW_OPS=$(echo "$RECENT_LOGS" | grep -i "backend.*commit" | grep "took" | wc -l)\n    if [ "$BACKEND_SLOW_OPS" -gt 0 ]; then\n        BACKEND_LATENCY=$(echo "$RECENT_LOGS" | grep -i "backend.*commit" | grep "took" | \\\n            grep -oE "[0-9]+\\.[0-9]+ms|[0-9]+ms" | \\\n            sed 's/ms//' | sort -n | tail -1)\n        BACKEND_LATENCY="${BACKEND_LATENCY}ms"\n    fi\n    \n    # Count leader changes in this interval\n    LEADER_CHANGES=$(echo "$RECENT_LOGS" | grep -iE "leader.*changed|became.*leader|lost.*leader" | wc -l)\n    TOTAL_SLOW_OPS=$((WAL_SLOW_OPS + BACKEND_SLOW_OPS))\n    \n    # Display current metrics\n    echo "📊 CURRENT METRICS"\n    printf "   Database Size:    %6s MB\\n" "$MAX_DB_SIZE_MB"\n    printf "   Fragmentation:    %6s%%\\n" "$MAX_FRAGMENTATION"\n    printf "   WAL Latency:      %8s\\n" "$WAL_LATENCY"\n    printf "   Backend Latency:  %8s\\n" "$BACKEND_LATENCY"\n    printf "   Slow Operations:  %6s (${INTERVAL}s)\\n" "$TOTAL_SLOW_OPS"\n    printf "   Leader Changes:   %6s (${INTERVAL}s)\\n" "$LEADER_CHANGES"\n    echo ""\n    \n    # Determine status and alerts\n    STATUS="HEALTHY"\n    CURRENT_ALERTS=""\n    \n    # Check for alerts based on threshold\n    WAL_ALERT=false\n    BACKEND_ALERT=false\n    FRAG_ALERT=false\n    \n    if [ "$WAL_LATENCY" != "N/A" ]; then\n        WAL_VALUE=$(echo "$WAL_LATENCY" | sed 's/ms//')\n        if (( $(echo "$WAL_VALUE > $WAL_ALERT_THRESHOLD" | bc -l) )); then\n            WAL_ALERT=true\n            STATUS="ALERT"\n            CURRENT_ALERTS="${CURRENT_ALERTS}WAL_FSYNC_SLOW "\n        fi\n    fi\n    \n    if [ "$BACKEND_LATENCY" != "N/A" ]; then\n        BACKEND_VALUE=$(echo "$BACKEND_LATENCY" | sed 's/ms//')\n        if (( $(echo "$BACKEND_VALUE > $BACKEND_ALERT_THRESHOLD" | bc -l) )); then\n            BACKEND_ALERT=true\n            STATUS="ALERT"\n            CURRENT_ALERTS="${CURRENT_ALERTS}BACKEND_COMMIT_SLOW "\n        fi\n    fi\n    \n    if [ "$MAX_FRAGMENTATION" -gt "$FRAG_ALERT_THRESHOLD" ]; then\n        FRAG_ALERT=true\n        STATUS="WARNING"\n        CURRENT_ALERTS="${CURRENT_ALERTS}HIGH_FRAGMENTATION "\n    fi\n    \n    if [ "$LEADER_CHANGES" -gt 2 ]; then\n        STATUS="WARNING"\n        CURRENT_ALERTS="${CURRENT_ALERTS}LEADER_INSTABILITY "\n    fi\n    \n    # Display status with color coding\n    echo "🚦 STATUS"\n    case $STATUS in\n        "HEALTHY")\n            echo "   ✅ All systems performing within acceptable limits"\n            ;;\n        "WARNING")\n            echo "   ⚠️  Performance warnings detected"\n            ;;\n        "ALERT")\n            echo "   🔥 Critical performance issues detected"\n            ;;\n    esac\n    \n    # Display active alerts\n    if [ -n "$CURRENT_ALERTS" ]; then\n        echo ""\n        echo "🚨 ACTIVE ALERTS"\n        if [[ "$CURRENT_ALERTS" == *"WAL_FSYNC_SLOW"* ]]; then\n            echo "   • WAL fsync latency: $WAL_LATENCY (threshold: ${WAL_ALERT_THRESHOLD}ms)"\n        fi\n        if [[ "$CURRENT_ALERTS" == *"BACKEND_COMMIT_SLOW"* ]]; then\n            echo "   • Backend commit latency: $BACKEND_LATENCY (threshold: ${BACKEND_ALERT_THRESHOLD}ms)"\n        fi\n        if [[ "$CURRENT_ALERTS" == *"HIGH_FRAGMENTATION"* ]]; then\n            echo "   • High fragmentation: ${MAX_FRAGMENTATION}% (threshold: ${FRAG_ALERT_THRESHOLD}%)"\n        fi\n        if [[ "$CURRENT_ALERTS" == *"LEADER_INSTABILITY"* ]]; then\n            echo "   • Leader instability: $LEADER_CHANGES changes in ${INTERVAL}s"\n        fi\n        \n        # Log alerts\n        echo "$TIMESTAMP: $STATUS - $CURRENT_ALERTS" >> "$ALERTS_FILE"\n        ALERT_COUNT=$((ALERT_COUNT + 1))\n    fi\n    \n    # Log metrics to CSV\n    WAL_CSV=$([ "$WAL_LATENCY" = "N/A" ] && echo "" || echo "$WAL_LATENCY" | sed 's/ms//')\n    BACKEND_CSV=$([ "$BACKEND_LATENCY" = "N/A" ] && echo "" || echo "$BACKEND_LATENCY" | sed 's/ms//')\n    echo "$TIMESTAMP,$MAX_DB_SIZE_MB,$MAX_FRAGMENTATION,$LEADER_CHANGES,$TOTAL_SLOW_OPS,$WAL_CSV,$BACKEND_CSV,$STATUS" >> "$METRICS_FILE"\n    \n    # Display trend analysis (every 10 iterations)\n    if [ $((ITERATION % 10)) -eq 0 ] && [ $ITERATION -gt 10 ]; then\n        echo ""\n        echo "📈 TREND ANALYSIS (last 10 samples)"\n        \n        # Analyze fragmentation trend\n        FRAG_TREND=$(tail -10 "$METRICS_FILE" | cut -d',' -f3 | grep -v fragmentation_pct | \\\n            awk '{sum+=$1; count++} END {if(count>0) print sum/count}' | bc -l | cut -d'.' -f1)\n        \n        if [ -n "$FRAG_TREND" ]; then\n            FRAG_CHANGE=$((MAX_FRAGMENTATION - FRAG_TREND))\n            if [ $FRAG_CHANGE -gt 5 ]; then\n                echo "   • Fragmentation increasing rapidly (+${FRAG_CHANGE}%)" \n            elif [ $FRAG_CHANGE -lt -5 ]; then\n                echo "   • Fragmentation decreasing (-${FRAG_CHANGE}%)"\n            else\n                echo "   • Fragmentation stable (~${MAX_FRAGMENTATION}%)"\n            fi\n        fi\n        \n        # Analyze alert frequency\n        RECENT_ALERTS=$(tail -10 "$METRICS_FILE" | grep -c "ALERT\\|WARNING")\n        if [ $RECENT_ALERTS -gt 5 ]; then\n            echo "   • ⚠️  High alert frequency: $RECENT_ALERTS/10 samples"\n        elif [ $RECENT_ALERTS -eq 0 ]; then\n            echo "   • ✅ Stable performance: No recent alerts"\n        else\n            echo "   • 📊 Moderate alerts: $RECENT_ALERTS/10 samples"\n        fi\n    fi\n    \n    echo ""\n    echo "📋 SESSION SUMMARY"\n    printf "   Monitoring time:  %6s minutes\\n" "$(( (CURRENT_TIME - START_TIME) / 60 ))"\n    printf "   Total iterations: %6s\\n" "$ITERATION"\n    printf "   Total alerts:     %6s\\n" "$ALERT_COUNT"\n    echo ""\n    echo "Press Ctrl+C to stop monitoring | Next update in ${INTERVAL}s..."\n    \n    # Wait for next iteration\n    sleep $INTERVAL\ndone\n```\n\n### 3. Cleanup and Summary\n\n```bash\n# Restore cursor\ntput cnorm\n\necho ""\necho "==============================================="\necho "MONITORING SESSION COMPLETE"\necho "==============================================="\necho ""\necho "Session Summary:"\necho "  Duration: $(( ($(date +%s) - START_TIME) / 60 )) minutes"\necho "  Iterations: $ITERATION"\necho "  Total alerts: $ALERT_COUNT"\necho ""\necho "Generated files:"\necho "  Metrics log: $METRICS_FILE"\necho "  Alerts log: $ALERTS_FILE"\necho "  Session log: $LOG_FILE"\necho ""\n\nif [ $ALERT_COUNT -gt 0 ]; then\n    echo "Recent alerts:"\n    tail -5 "$ALERTS_FILE"\n    echo ""\nfi\n\necho "To analyze historical data:"\necho "  sort $METRICS_FILE | head -20"\necho "  grep ALERT $ALERTS_FILE"\necho ""\n\n# Exit with status based on final state\nif [ "$STATUS" = "ALERT" ]; then\n    exit 2\nelif [ "$STATUS" = "WARNING" ]; then\n    exit 1\nelse\n    exit 0\nfi\n```\n\n## Return Value\n\n- **Exit 0**: Session completed successfully (healthy status)\n- **Exit 1**: Session completed with warnings detected\n- **Exit 2**: Session completed with critical issues detected\n\n**Output Locations**:\n- **Metrics CSV**: `.work/etcd-realtime/{timestamp}/metrics.csv`\n- **Alerts log**: `.work/etcd-realtime/{timestamp}/alerts.log`\n- **Session log**: `.work/etcd-realtime/{timestamp}/monitoring.log`\n\n## Examples\n\n### Example 1: Basic real-time monitoring\n```\n/etcd:realtime-monitor\n```\nStarts continuous monitoring with 5-second intervals and warning-level alerts.\n\n### Example 2: High-frequency monitoring during troubleshooting\n```\n/etcd:realtime-monitor --interval 2 --duration 15 --alert-threshold info\n```\nMonitors for 15 minutes with 2-second updates, alerting on all performance deviations.\n\n### Example 3: Critical-only monitoring during maintenance\n```\n/etcd:realtime-monitor --interval 10 --alert-threshold critical\n```\nContinuous monitoring with 10-second intervals, alerting only on critical issues.\n\n## Use Cases\n\n### Troubleshooting Active Performance Issues\n1. Start real-time monitoring with high frequency\n2. Observe live metrics during problem reproduction\n3. Correlate performance degradation with cluster operations\n4. Use alerts to identify exact timing of issues\n\n### Maintenance Window Monitoring\n1. Begin monitoring before maintenance starts\n2. Set critical alert threshold to catch severe issues\n3. Monitor throughout maintenance operations\n4. Validate performance recovery after completion\n\n### Capacity Planning and Baseline Establishment\n1. Run extended monitoring sessions (2-4 hours)\n2. Collect performance baselines during normal operations\n3. Analyze trends and peak usage patterns\n4. Plan resource scaling based on observed metrics\n\n### Performance Validation After Changes\n1. Start monitoring before implementing changes\n2. Continue monitoring during and after changes\n3. Compare before/after performance metrics\n4. Validate that changes don't introduce regressions\n\n## Advanced Features\n\n### Real-time Terminal Dashboard\n- Live updating metrics display\n- Color-coded status indicators\n- Historical trend analysis\n- Interactive monitoring experience\n\n### Intelligent Alerting\n- Configurable threshold sensitivity\n- Alert frequency tracking\n- Trend-based anomaly detection\n- Automated alert logging\n\n### Data Collection and Export\n- Structured CSV metrics export\n- Timestamped alert logging\n- Historical data analysis capabilities\n- Integration with external monitoring systems\n\n## Integration with Deep Analysis\n\nThis command is designed to work alongside `/etcd:deep-performance-analysis`:\n\n1. **Start real-time monitoring** to establish baseline\n2. **Run deep analysis** when alerts are triggered\n3. **Continue monitoring** to validate remediation\n4. **Use historical data** from monitoring for trend analysis\n\n## Performance Impact\n\nThis monitoring command is designed to be lightweight:\n- Minimal resource consumption\n- Non-intrusive metric collection\n- Configurable update intervals to balance detail vs. impact\n- Uses existing etcd monitoring interfaces\n\n## Security Considerations\n\n- Requires cluster-admin permissions\n- Collects real-time performance data\n- Generates logs that may contain operational details\n- Monitor data should be treated as confidential\n\n## See Also\n\n- Related commands: `/etcd:deep-performance-analysis`, `/etcd:health-check`\n- OCP Performance Analyzer MCP: https://github.com/openshift-eng/ocp-performance-analyzer-mcp\n- ETCD monitoring best practices: https://etcd.io/docs/latest/op-guide/monitoring/\n