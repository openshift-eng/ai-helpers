# ETCD Performance Plugin - Testing Guide

> **Enhanced ETCD performance analysis with AI-powered insights and real-time monitoring**

This guide provides complete instructions for testing the enhanced ETCD performance analysis plugin that integrates capabilities from the [OCP Performance Analyzer MCP](https://github.com/openshift-eng/ocp-performance-analyzer-mcp) project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Available Tests](#available-tests)
- [Understanding Results](#understanding-results)
- [Generated Reports](#generated-reports)
- [Troubleshooting](#troubleshooting)
- [Use Cases](#use-cases)
- [Advanced Testing](#advanced-testing)

## Prerequisites

### Required Tools

Verify you have the required tools installed:

```bash
# OpenShift CLI
oc version
# Should show: Client Version and Server Version

# JSON processor
jq --version
# Should show: jq-1.6 or higher

# Basic calculator (usually pre-installed)
bc --version
# Should show: bc version info
```

**Install missing tools:**

```bash
# RHEL/CentOS/Fedora
sudo dnf install jq bc -y

# Ubuntu/Debian
sudo apt install jq bc -y

# macOS
brew install jq
```

### Required Cluster Access

Verify your cluster access and permissions:

```bash
# Cluster connection
export KUBECONFIG=/path/to/your/kubeconfig
oc whoami
oc cluster-info

# Node access
oc get nodes

# ETCD access
oc get pods -n openshift-etcd -l app=etcd
oc auth can-i get pods -n openshift-etcd
oc auth can-i exec pods -n openshift-etcd
```

**Expected results:**
- `oc whoami` shows your username
- `oc get pods -n openshift-etcd -l app=etcd` shows 3 running etcd pods
- Both auth commands return "yes"

> **⚠️ Important:** If any verification fails, contact your cluster administrator for proper permissions.

## Installation

### Option 1: From GitHub Repository (Recommended)

```bash
# Clone the enhanced repository
git clone https://github.com/SachinNinganure/ai-helpers.git
cd ai-helpers

# Switch to the enhanced branch
git checkout etcd-performance-analyzer

# Verify enhanced ETCD plugin structure
ls -la plugins/etcd/
ls -la plugins/etcd/commands/
```

**Expected structure:**
```
plugins/etcd/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── analyze-performance.md
│   ├── deep-performance-analysis.md    # NEW
│   ├── health-check.md
│   └── realtime-monitor.md             # NEW
├── skills/
│   └── advanced-etcd-analyzer/         # NEW
│       └── SKILL.md
└── README.md
```

### Option 2: Direct Test Scripts

For standalone testing without the full plugin:

```bash
# Create test directory
mkdir etcd-performance-tests
cd etcd-performance-tests

# Download test scripts
curl -o test_etcd_analysis.sh https://raw.githubusercontent.com/SachinNinganure/ai-helpers/etcd-performance-analyzer/test_etcd_analysis.sh
curl -o test_etcd_realtime.sh https://raw.githubusercontent.com/SachinNinganure/ai-helpers/etcd-performance-analyzer/test_etcd_realtime.sh

# Make executable
chmod +x test_etcd_*.sh
```

## Quick Start

### 5-Minute Performance Check

```bash
# Set your cluster config
export KUBECONFIG=/path/to/your/kubeconfig

# Run comprehensive analysis
./test_etcd_analysis.sh --duration 5 --verbose

# Expected output:
# ✅ Found 3 running etcd pods
# ✅ Database size: 68MB (healthy)
# ✅ Fragmentation: 24% (good)
# ✅ Commit latency: 6-11ms (excellent)
# ✅ Status: HEALTHY
```

### 1-Minute Real-time Monitoring

```bash
# Monitor live performance
./test_etcd_realtime.sh 3

# Expected output:
# 📊 Live dashboard updating every 3 seconds
# 📊 Database Size: 68MB | Fragmentation: 24%
# 📊 Commit Latency: 6.3ms | Status: HEALTHY
```

## Available Tests

### Test 1: Comprehensive Performance Analysis

**Purpose:** Deep analysis of ETCD performance with AI-powered insights

```bash
# Basic analysis (5-minute window)
./test_etcd_analysis.sh

# Extended analysis (30-minute window)
./test_etcd_analysis.sh --duration 30

# Verbose mode with detailed output
./test_etcd_analysis.sh --duration 15 --verbose

# Generate HTML report (if supported)
./test_etcd_analysis.sh --duration 20 --export-html
```

**What it analyzes:**
- Database size and fragmentation
- WAL fsync and backend commit performance
- Leader election stability
- Network latency between peers
- AI-powered bottleneck detection
- Historical trend analysis

### Test 2: Real-time Performance Monitoring

**Purpose:** Live monitoring dashboard with intelligent alerting

```bash
# Default monitoring (5-second updates, 60-second test)
./test_etcd_realtime.sh

# High-frequency monitoring (2-second updates)
./test_etcd_realtime.sh 2

# Low-frequency monitoring (10-second updates)
./test_etcd_realtime.sh 10

# With custom alert threshold
./test_etcd_realtime.sh 5 --alert-threshold warning
```

**What it monitors:**
- Live database metrics
- Real-time fragmentation tracking
- Commit latency trends
- Threshold-based alerting
- Performance degradation detection

### Test 3: Claude Code Integration (Advanced)

If you have Claude Code installed with the plugin:

```bash
# Deep performance analysis
/etcd:deep-performance-analysis

# Extended analysis with HTML export
/etcd:deep-performance-analysis --duration 60 --export-html

# Real-time monitoring dashboard
/etcd:realtime-monitor --interval 5 --duration 15

# High-sensitivity alerting
/etcd:realtime-monitor --interval 3 --alert-threshold info
```

## Understanding Results

### Performance Thresholds

| Metric | Target | Warning | Critical | Your Result Example |
|--------|--------|---------|----------|-------------------|
| **Database Size** | < 4GB | 4-8GB | > 8GB | 68MB ✅ |
| **Fragmentation** | < 20% | 20-30% | > 30% | 24% ⚠️ |
| **WAL fsync P99** | < 5ms | 5-10ms | > 10ms | - |
| **Backend Commit P99** | < 15ms | 15-25ms | > 25ms | 6-11ms ✅ |
| **Slow Operations** | 0 | 1-5/5min | > 5/5min | 0 ✅ |
| **Leader Changes** | 0 | 1-3 | > 3 | - |

### Status Indicators

#### ✅ HEALTHY Status
```
Database Size:     68MB
Fragmentation:     24%
Commit Latency:    6.3ms
Slow Operations:   0
Status:            HEALTHY
✅ All metrics within normal range
```

#### ⚠️ WARNING Status
```
Database Size:     156MB
Fragmentation:     35%
Commit Latency:    18ms
Slow Operations:   3
Status:            WARNING
⚠️ Performance degradation detected
```

#### 🔥 CRITICAL Status
```
Database Size:     9.2GB
Fragmentation:     55%
Commit Latency:    45ms
Slow Operations:   25
Status:            CRITICAL
🔥 Immediate action required
```

### Performance Impact Translation

| Technical Metric | User Experience |
|-----------------|-----------------|
| **Low commit latency (< 10ms)** | Fast pod creation, quick API responses |
| **High commit latency (> 25ms)** | Slow deployments, timeouts in kubectl |
| **Low fragmentation (< 30%)** | Efficient storage, good performance |
| **High fragmentation (> 50%)** | Slow operations, degraded performance |
| **No slow operations** | Responsive cluster operations |
| **Many slow operations** | Cluster slowness, potential outages |

## Generated Reports

### Analysis Report Files

```bash
# List generated analysis reports
ls -la .work/etcd-analysis/*/

# View executive summary
cat .work/etcd-analysis/*/executive_performance_report.txt

# Example executive report:
# ETCD PERFORMANCE ANALYSIS EXECUTIVE REPORT
# ==========================================
# Overall Status: HEALTHY
# Critical Issues: 0
# Warnings: 0
# Database Size: 68MB
# Fragmentation: 24%
#
# RECOMMENDATIONS:
# ✅ Continue monitoring current trends
# ✅ Performance within acceptable limits
```

### Real-time Monitoring Data

```bash
# View CSV metrics file
cat .work/etcd-realtime-*/metrics.csv

# Example CSV content:
timestamp,db_size_mb,fragmentation_pct,commit_latency_ms,status
2026-01-01 14:02:10,68,24,6.329522,HEALTHY
2026-01-01 14:02:25,68,21,6.13943,HEALTHY
2026-01-01 14:02:35,68,21,6.716706,HEALTHY
```

### HTML Reports (If Generated)

```bash
# Open HTML report in browser
open .work/etcd-analysis/*/performance_report.html

# Or view file location
ls -la .work/etcd-analysis/*/performance_report.html
```

## Troubleshooting

### Common Issues and Solutions

#### 1. No ETCD Pods Found

**Error:** `Error: No running etcd pods found`

**Diagnosis:**
```bash
oc get pods -n openshift-etcd
oc get co etcd
```

**Solutions:**
- If no pods exist: Check cluster operator status
- If pods are pending: Check node resources and storage
- If pods are failing: Check etcd logs

#### 2. Permission Denied

**Error:** `Error: Insufficient permissions to access etcd pods`

**Diagnosis:**
```bash
oc auth can-i exec pods -n openshift-etcd
oc auth can-i get pods -n openshift-etcd
```

**Solutions:**
- Request cluster-admin role from administrator
- Request specific RBAC permissions for etcd namespace
- Use a service account with appropriate permissions

#### 3. Missing Dependencies

**Error:** `jq: command not found` or `bc: command not found`

**Solutions:**
```bash
# RHEL/CentOS/Fedora
sudo dnf install jq bc -y

# Ubuntu/Debian
sudo apt install jq bc -y

# macOS
brew install jq
# bc is usually pre-installed on macOS
```

#### 4. Cluster Connection Issues

**Error:** `Error: Not connected to cluster`

**Diagnosis:**
```bash
oc cluster-info
oc whoami
echo $KUBECONFIG
```

**Solutions:**
```bash
# Set correct kubeconfig
export KUBECONFIG=/path/to/your/kubeconfig

# Login to cluster
oc login <cluster-url> -u <username>

# Verify connection
oc get nodes
```

#### 5. Metric Collection Failures

**Error:** `Failed to collect etcd metrics`

**Diagnosis:**
```bash
# Check etcd pod health
oc describe pod <etcd-pod-name> -n openshift-etcd

# Check etcd container status
oc get pods -n openshift-etcd -o wide

# Check etcd logs
oc logs <etcd-pod-name> -n openshift-etcd -c etcd --tail=20
```

**Solutions:**
- Wait for etcd pods to become ready
- Check if etcd cluster is forming properly
- Verify network connectivity between etcd nodes

## Use Cases

### 1. Daily Health Monitoring

Create automated daily health checks:

```bash
#!/bin/bash
# daily_etcd_check.sh

DATE=$(date +%Y%m%d)
REPORT_DIR="daily_reports"
mkdir -p "$REPORT_DIR"

echo "Running daily ETCD health check..."
./test_etcd_analysis.sh --duration 10 > "$REPORT_DIR/etcd_health_$DATE.txt"

# Email or alert if issues found
if grep -q "CRITICAL\|WARNING" "$REPORT_DIR/etcd_health_$DATE.txt"; then
    echo "⚠️ ETCD performance issues detected - check report"
    # Add alerting logic here
fi
```

### 2. Troubleshooting Cluster Performance

When users report slow cluster performance:

```bash
# Start high-frequency monitoring
./test_etcd_realtime.sh 2 > troubleshooting_$(date +%Y%m%d_%H%M).log &

# Run comprehensive analysis
./test_etcd_analysis.sh --duration 30 --verbose

# Correlate with cluster activity
oc get events --sort-by='.lastTimestamp' | tail -20
```

### 3. Pre-Maintenance Validation

Before cluster maintenance activities:

```bash
# Establish performance baseline
echo "Pre-maintenance ETCD baseline:"
./test_etcd_analysis.sh --duration 15 > pre_maintenance_baseline.txt

# Monitor during maintenance
echo "Starting maintenance monitoring..."
./test_etcd_realtime.sh 5 > maintenance_monitoring.log &

# Post-maintenance validation
echo "Post-maintenance ETCD validation:"
./test_etcd_analysis.sh --duration 10 > post_maintenance_validation.txt
```

### 4. Capacity Planning

Weekly performance trending for capacity planning:

```bash
#!/bin/bash
# weekly_etcd_trend.sh

WEEK=$(date +%Y_week_%V)
TREND_DIR="capacity_planning"
mkdir -p "$TREND_DIR"

echo "Collecting weekly ETCD performance trends..."
./test_etcd_analysis.sh --duration 60 > "$TREND_DIR/etcd_trend_$WEEK.txt"

# Analyze growth patterns
echo "Database size trend:"
grep "DB Size:" "$TREND_DIR"/etcd_trend_*.txt | tail -10
```

## Advanced Testing

### Stress Testing (Optional)

Test ETCD performance under load:

```bash
# Terminal 1: Start continuous monitoring
./test_etcd_realtime.sh 2 > stress_test_monitoring.log &

# Terminal 2: Generate cluster activity
for i in {1..100}; do
    oc create namespace stress-test-$i
    oc run stress-pod-$i --image=nginx -n stress-test-$i
    oc create configmap stress-cm-$i --from-literal=key=value -n stress-test-$i
    sleep 0.5
done

# Observe performance impact in monitoring

# Cleanup
for i in {1..100}; do 
    oc delete namespace stress-test-$i --timeout=10s
done
```

### Long-term Monitoring

Extended monitoring for trend analysis:

```bash
# Start long-term monitoring (4 hours)
nohup ./test_etcd_realtime.sh 60 > long_term_monitor_$(date +%Y%m%d).log 2>&1 &

# Check progress
tail -f long_term_monitor_$(date +%Y%m%d).log

# Stop monitoring
kill %1  # or find PID with ps aux | grep test_etcd_realtime
```

### Integration Testing

Test with CI/CD pipeline integration:

```bash
#!/bin/bash
# ci_etcd_health_gate.sh

echo "ETCD health gate for CI/CD pipeline"

# Run quick health check
./test_etcd_analysis.sh --duration 5 > ci_etcd_check.txt

# Check results
if grep -q "CRITICAL" ci_etcd_check.txt; then
    echo "❌ ETCD health gate FAILED - critical issues detected"
    exit 2
elif grep -q "WARNING" ci_etcd_check.txt; then
    echo "⚠️ ETCD health gate PASSED with warnings"
    exit 1
else
    echo "✅ ETCD health gate PASSED"
    exit 0
fi
```

## Performance Tuning Recommendations

Based on test results, here are common optimization recommendations:

### For High Fragmentation (>30%)

```bash
# Schedule defragmentation (during maintenance window)
oc exec -n openshift-etcd <etcd-pod> -c etcdctl -- etcdctl defrag --cluster

# Monitor fragmentation improvement
./test_etcd_realtime.sh 5
```

### For High Database Size (>4GB)

```bash
# Check event retention settings
oc get kubeapiserver cluster -o yaml | grep -A5 eventTTL

# Review large objects
oc exec -n openshift-etcd <etcd-pod> -c etcdctl -- etcdctl get --prefix=true --keys-only | head -20
```

### For High Commit Latency (>25ms)

```bash
# Check storage performance
oc debug node/<node-name> -- chroot /host fio --name=etcd-test --rw=write --bs=4k --size=100M --direct=1

# Check for resource contention
oc top nodes
oc describe node <etcd-node>
```

## Getting Help

### Documentation Resources

1. **Enhanced Plugin README**: `cat plugins/etcd/README.md`
2. **Deep Analysis Command**: `cat plugins/etcd/commands/deep-performance-analysis.md`
3. **Real-time Monitor Command**: `cat plugins/etcd/commands/realtime-monitor.md`
4. **Implementation Guide**: `cat plugins/etcd/skills/advanced-etcd-analyzer/SKILL.md`

### Support Channels

1. **GitHub Issues**: [https://github.com/SachinNinganure/ai-helpers/issues](https://github.com/SachinNinganure/ai-helpers/issues)
2. **Original Project**: [OCP Performance Analyzer MCP](https://github.com/openshift-eng/ocp-performance-analyzer-mcp)
3. **OpenShift Documentation**: [ETCD Performance Tuning](https://docs.openshift.com/container-platform/latest/scalability_and_performance/recommended-performance-scale-practices/)

### Reporting Issues

When reporting issues, include:

1. **Environment details**:
   ```bash
   oc version
   oc get nodes
   oc get pods -n openshift-etcd
   ```

2. **Error messages** and full command output

3. **Test results** from basic health check:
   ```bash
   ./test_etcd_analysis.sh --duration 5 > debug_output.txt
   ```

## Success Criteria

Your testing is successful when you achieve:

- ✅ Commands execute without permission errors
- ✅ Performance metrics are collected and displayed accurately
- ✅ Status indicators reflect actual cluster health
- ✅ CSV/text reports are generated in `.work/` directories
- ✅ Real-time monitoring updates correctly every interval
- ✅ Threshold-based alerting triggers appropriately
- ✅ Generated reports contain actionable insights

## Summary

This enhanced ETCD performance plugin provides:

- **Comprehensive analysis** with 15+ specialized tools
- **AI-powered insights** for bottleneck detection
- **Real-time monitoring** with intelligent alerting
- **Executive reporting** with actionable recommendations
- **Integration capabilities** with existing monitoring systems

The plugin helps prevent cluster outages, optimize performance, reduce troubleshooting time, and provide data-driven insights for capacity planning.

**Happy monitoring!** 🚀

---

> **Note**: This plugin integrates advanced capabilities from the [OCP Performance Analyzer MCP](https://github.com/openshift-eng/ocp-performance-analyzer-mcp) project, bringing enterprise-grade ETCD performance analysis to Claude Code users.