---
name: Resource Analysis
description: Analyze system resource usage data from sosreport archives, extracting memory statistics, CPU load averages, disk space utilization, and process information from the sosreport directory structure to diagnose resource exhaustion, performance bottlenecks, and capacity issues
---

# Resource Analysis Skill

This skill provides detailed guidance for analyzing system resource usage from sosreport archives, including memory, CPU, disk space, and process information.

## When to Use This Skill

Use this skill when:
- Analyzing the `/sosreport:analyze` command's resource analysis phase
- Investigating performance issues or resource bottlenecks
- Identifying resource exhaustion problems
- Correlating resource usage with system failures

## Prerequisites

- Sosreport archive must be extracted to a working directory
- Path to the sosreport root directory must be known
- Understanding of Linux resource management

## Key Resource Data Locations in Sosreport

1. **Memory Information**:
   - `sos_commands/memory/free` - Memory usage snapshot
   - `proc/meminfo` - Detailed memory statistics
   - `sos_commands/memory/swapon_-s` - Swap usage
   - `proc/buddyinfo` - Memory fragmentation

2. **CPU Information**:
   - `sos_commands/processor/lscpu` - CPU architecture and features
   - `proc/cpuinfo` - Detailed CPU information
   - `sos_commands/processor/turbostat` - CPU frequency and power states (if available)
   - `uptime` - Load averages

3. **Disk Information**:
   - `sos_commands/filesys/df_-al` - Filesystem usage
   - `sos_commands/block/lsblk` - Block device information
   - `sos_commands/filesys/mount` - Mounted filesystems
   - `proc/diskstats` - Disk I/O statistics

4. **Process Information**:
   - `sos_commands/process/ps_auxwww` - Process list with details
   - `sos_commands/process/top` - Process snapshot (if available)
   - `proc/[pid]/` - Per-process information

## Implementation Steps

### Step 1: Analyze Memory Usage

1. **Parse free command output**:
   ```bash
   # Check if free output exists
   if [ -f sos_commands/memory/free ]; then
     cat sos_commands/memory/free
   fi
   ```

2. **Extract memory metrics**:
   ```bash
   # Parse /proc/meminfo for detailed stats
   if [ -f proc/meminfo ]; then
     grep -E "^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|Dirty|Slab):" proc/meminfo
   fi
   ```

3. **Calculate memory usage percentage**:
   - Total memory = MemTotal
   - Used memory = MemTotal - MemAvailable
   - Usage percentage = (Used / Total) * 100
   - Parse from `free` output or calculate from `meminfo`

4. **Check for memory pressure indicators**:
   ```bash
   # Look for OOM events in logs
   grep -i "out of memory\|oom killer" sos_commands/logs/journalctl_--no-pager 2>/dev/null

   # Check swap usage
   if [ -f sos_commands/memory/swapon_-s ]; then
     cat sos_commands/memory/swapon_-s
   fi
   ```

5. **Identify memory issues**:
   - Memory usage > 90% → Critical
   - Memory usage > 80% → Warning
   - Heavy swap usage (>50% swap used) → Performance issue
   - OOM killer events → Critical memory exhaustion

### Step 2: Analyze CPU Usage

1. **Extract CPU information**:
   ```bash
   # Get CPU count and model
   if [ -f sos_commands/processor/lscpu ]; then
     grep -E "^(CPU\(s\)|Model name|Thread|Core|Socket|CPU MHz):" sos_commands/processor/lscpu
   fi
   ```

2. **Check load averages**:
   ```bash
   # Parse uptime for load averages
   if [ -f uptime ]; then
     cat uptime
   fi

   # Or from proc/loadavg
   if [ -f proc/loadavg ]; then
     cat proc/loadavg
   fi
   ```

3. **Interpret load averages**:
   - Load average format: 1-min, 5-min, 15-min
   - Compare with CPU count from lscpu
   - Load > CPU count → System overloaded
   - Load >> CPU count (2x or more) → Critical overload

4. **Check for CPU throttling**:
   ```bash
   # Look for thermal throttling in logs
   grep -i "throttl\|temperature\|thermal" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20
   ```

5. **Identify CPU issues**:
   - 1-min load > 2x CPU count → Critical
   - 5-min load > CPU count → Warning
   - Thermal throttling present → Hardware/cooling issue

### Step 3: Analyze Disk Usage

1. **Parse df output for filesystem usage**:
   ```bash
   if [ -f sos_commands/filesys/df_-al ]; then
     # Skip header and special filesystems, show only regular filesystems
     grep -v "^Filesystem\|tmpfs\|devtmpfs\|overlay" sos_commands/filesys/df_-al | grep -v "^$"
   fi
   ```

2. **Identify full or nearly-full filesystems**:
   ```bash
   # Extract filesystems with usage > 85%
   if [ -f sos_commands/filesys/df_-al ]; then
     awk 'NR>1 && $5+0 >= 85 {print $5, $6, $1}' sos_commands/filesys/df_-al | grep -v "tmpfs\|devtmpfs"
   fi
   ```

3. **Check disk I/O errors**:
   ```bash
   # Look for I/O errors in logs
   grep -i "i/o error\|read error\|write error\|bad sector" var/log/dmesg 2>/dev/null
   grep -i "i/o error\|read error\|write error" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20
   ```

4. **Analyze block devices**:
   ```bash
   if [ -f sos_commands/block/lsblk ]; then
     cat sos_commands/block/lsblk
   fi
   ```

5. **Identify disk issues**:
   - Filesystem > 95% full → Critical
   - Filesystem > 85% full → Warning
   - I/O errors present → Hardware issue
   - Root filesystem full → System stability risk

### Step 4: Analyze Process Information

1. **Parse ps output**:
   ```bash
   if [ -f sos_commands/process/ps_auxwww ]; then
     # Show header
     head -1 sos_commands/process/ps_auxwww
   fi
   ```

2. **Find top CPU consumers**:
   ```bash
   # Sort by CPU usage (column 3), show top 10
   if [ -f sos_commands/process/ps_auxwww ]; then
     tail -n +2 sos_commands/process/ps_auxwww | sort -k3 -rn | head -10
   fi
   ```

3. **Find top memory consumers**:
   ```bash
   # Sort by memory usage (column 4), show top 10
   if [ -f sos_commands/process/ps_auxwww ]; then
     tail -n +2 sos_commands/process/ps_auxwww | sort -k4 -rn | head -10
   fi
   ```

4. **Check for zombie processes**:
   ```bash
   # Look for processes in Z state
   if [ -f sos_commands/process/ps_auxwww ]; then
     grep " Z " sos_commands/process/ps_auxwww || echo "No zombie processes found"
   fi
   ```

5. **Count processes by state**:
   ```bash
   # Count processes by state (R=running, S=sleeping, D=uninterruptible, Z=zombie, T=stopped)
   if [ -f sos_commands/process/ps_auxwww ]; then
     tail -n +2 sos_commands/process/ps_auxwww | awk '{print $8}' | cut -c1 | sort | uniq -c
   fi
   ```

6. **Identify process issues**:
   - Zombie processes present → Parent process not reaping children
   - Many processes in D state → I/O bottleneck
   - Single process using >80% memory → Memory leak or expected behavior
   - Many processes using high CPU → CPU contention

### Step 5: Correlate Resource Usage with Issues

1. **Cross-reference with logs**:
   - If high memory usage, check for OOM events in logs
   - If high disk usage, check for disk full errors
   - If high load, check for performance-related errors

2. **Identify resource exhaustion patterns**:
   - Memory exhaustion → OOM killer → Service crashes
   - Disk full → Write failures → Application errors
   - CPU overload → Timeouts → Request failures

3. **Build timeline**:
   - When did resource issues start?
   - Correlate with log timestamps
   - Identify triggering event if possible

### Step 6: Generate Resource Analysis Summary

Create a structured summary with the following sections:

1. **Memory Summary**:
   - Total memory
   - Used memory (GB and %)
   - Available memory
   - Swap usage (GB and %)
   - Memory pressure indicators (OOM events)

2. **CPU Summary**:
   - CPU count and model
   - Load averages (1-min, 5-min, 15-min)
   - Load per CPU
   - CPU issues (throttling, overload)

3. **Disk Summary**:
   - Filesystems and usage percentages
   - Full or nearly-full filesystems
   - I/O errors count
   - Most full filesystem

4. **Process Summary**:
   - Total process count
   - Top CPU consumers (top 5)
   - Top memory consumers (top 5)
   - Zombie process count
   - Processes in uninterruptible sleep (D state)

5. **Critical Resource Issues**:
   - List issues by severity
   - Provide evidence (file paths, metrics)
   - Suggest remediation

## Error Handling

1. **Missing resource files**:
   - If `free` is missing, parse `proc/meminfo` directly
   - If `ps` is missing, check `proc/` for process information
   - Document missing data in summary

2. **Parsing errors**:
   - Handle different output formats (free -h vs free -m)
   - Account for locale differences in number formats
   - Validate data before calculations

3. **Incomplete data**:
   - Some sosreports may not include all resource files
   - Indicate which metrics are unavailable
   - Work with available data only

## Output Format

The resource analysis should produce:

```bash
RESOURCE USAGE SUMMARY
======================

MEMORY
------
Total:      {total_gb} GB
Used:       {used_gb} GB ({used_pct}%)
Available:  {available_gb} GB ({available_pct}%)
Buffers:    {buffers_gb} GB
Cached:     {cached_gb} GB
Swap Total: {swap_total_gb} GB
Swap Used:  {swap_used_gb} GB ({swap_used_pct}%)

Status: {OK|WARNING|CRITICAL}
Issues:
  - {memory_issue_description}

CPU
---
Model:        {cpu_model}
CPU Count:    {cpu_count}
Threads/Core: {threads_per_core}

Load Averages: {load_1m}, {load_5m}, {load_15m}
Load per CPU:  {load_1m_per_cpu}, {load_5m_per_cpu}, {load_15m_per_cpu}

Status: {OK|WARNING|CRITICAL}
Issues:
  - {cpu_issue_description}

DISK USAGE
----------
Filesystem                    Size  Used  Avail  Use%  Mounted on
{filesystem}                 {size} {used} {avail} {pct}% {mount}

Nearly Full Filesystems (>85%):
  - {mount}: {pct}% full ({available} available)

I/O Errors: {count} errors found in logs

Status: {OK|WARNING|CRITICAL}
Issues:
  - {disk_issue_description}

PROCESSES
---------
Total Processes: {total}
Running:         {running}
Sleeping:        {sleeping}
Zombie:          {zombie}
Uninterruptible: {uninterruptible}

Top CPU Consumers:
  1. {process_name} (PID {pid}): {cpu}% CPU, {mem}% MEM
  2. {process_name} (PID {pid}): {cpu}% CPU, {mem}% MEM
  3. {process_name} (PID {pid}): {cpu}% CPU, {mem}% MEM

Top Memory Consumers:
  1. {process_name} (PID {pid}): {mem}% MEM, {cpu}% CPU
  2. {process_name} (PID {pid}): {mem}% MEM, {cpu}% CPU
  3. {process_name} (PID {pid}): {mem}% MEM, {cpu}% CPU

Status: {OK|WARNING|CRITICAL}
Issues:
  - {process_issue_description}

CRITICAL RESOURCE ISSUES
------------------------
{severity}: {issue_description}
  Evidence: {file_path}
  Impact: {impact_description}
  Recommendation: {remediation_action}

RECOMMENDATIONS
---------------
1. {actionable_recommendation}
2. {actionable_recommendation}

DATA SOURCES
------------
- Memory: {sosreport_path}/sos_commands/memory/free
- Memory: {sosreport_path}/proc/meminfo
- CPU: {sosreport_path}/sos_commands/processor/lscpu
- Load: {sosreport_path}/uptime
- Disk: {sosreport_path}/sos_commands/filesys/df_-al
- Processes: {sosreport_path}/sos_commands/process/ps_auxwww
```

## Examples

### Example 1: Memory Analysis

```bash
# Parse free command output
$ cat sos_commands/memory/free
              total        used        free      shared  buff/cache   available
Mem:       16277396     8123456     2145678      123456     6008262     7654321
Swap:       8388604      512000     7876604

# Interpretation:
# - Total RAM: ~16 GB
# - Used: ~8 GB (50%)
# - Available: ~7.6 GB (47%)
# - Swap used: ~500 MB (6%)
# Status: OK - healthy memory usage
```

### Example 2: Disk Full Detection

```bash
# Find filesystems > 85% full
$ awk 'NR>1 && $5+0 >= 85' sos_commands/filesys/df_-al
/dev/sda1      50G   45G   5G   90%  /
/dev/sdb1      100G  96G   4G   96%  /var/log

# Critical: Root filesystem at 90%, /var/log at 96%
# Action required: Clean up disk space
```

### Example 3: High Load Investigation

```bash
# Check load averages
$ cat uptime
14:23:45 up 10 days, 3:42, 2 users, load average: 8.45, 7.23, 6.12

# With lscpu showing 4 CPUs:
# Load per CPU: 2.1, 1.8, 1.5
# System is overloaded (load > 2x CPU count)
```

## Tips for Effective Analysis

1. **Context matters**: High resource usage isn't always bad - consider the workload
2. **Look for trends**: Compare 1-min, 5-min, 15-min loads to see if issues are growing
3. **Correlate metrics**: High load + high memory + disk full = multiple issues
4. **Check ratios**: Usage percentages are more meaningful than absolute values
5. **Validate findings**: Cross-reference with log analysis for confirmation
6. **Consider capacity**: Is the system appropriately sized for its workload?

## Common Resource Patterns

1. **Memory leak**: Steadily increasing memory usage, eventual OOM
2. **Disk full**: Application writes failing, log rotation issues
3. **CPU spike**: Load average spike, potentially from runaway process
4. **I/O bottleneck**: High load but low CPU usage, many D-state processes
5. **Swap thrashing**: High swap usage, poor performance
6. **Zombie accumulation**: Parent process bug not reaping children

## Severity Classification

| Metric | OK | Warning | Critical |
|--------|----|---------| ---------|
| Memory Usage | < 80% | 80-90% | > 90% |
| Swap Usage | < 20% | 20-50% | > 50% |
| Disk Usage | < 85% | 85-95% | > 95% |
| Load (per CPU) | < 1.0 | 1.0-2.0 | > 2.0 |
| Root FS Usage | < 80% | 80-90% | > 90% |

## See Also

- Logs Analysis Skill: For finding resource-related errors in logs
- System Configuration Analysis Skill: For investigating service resource limits
- Network Analysis Skill: For network-related performance issues
