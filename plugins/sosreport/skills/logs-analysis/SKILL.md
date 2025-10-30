---
name: Logs Analysis
description: Analyze system and application log data from sosreport archives, extracting error patterns, kernel panics, OOM events, service failures, and application crashes from journald logs and traditional log files within the sosreport directory structure to identify root causes of system failures and issues
---

# Logs Analysis Skill

This skill provides detailed guidance for analyzing logs from sosreport archives, including journald logs, system logs, kernel messages, and application logs.

## When to Use This Skill

Use this skill when:
- Analyzing the `/sosreport:analyze` command's log analysis phase
- Investigating specific log-related errors or warnings in a sosreport
- Performing deep-dive analysis of system failures from logs
- Identifying patterns and root causes in system logs

## Prerequisites

- Sosreport archive must be extracted to a working directory
- Path to the sosreport root directory must be known
- Basic understanding of Linux log structure and journald

## Key Log Locations in Sosreport

Sosreports contain logs in several locations:

1. **Journald logs**: `sos_commands/logs/journalctl_*`
   - `journalctl_--no-pager_--boot` - Current boot logs
   - `journalctl_--no-pager` - All available logs
   - `journalctl_--no-pager_--priority_err` - Error priority logs

2. **Traditional system logs**: `var/log/`
   - `messages` - System-level messages
   - `dmesg` - Kernel ring buffer
   - `secure` - Authentication and security logs
   - `cron` - Cron job logs

3. **Application logs**: `var/log/` (varies by application)
   - `httpd/` - Apache logs
   - `nginx/` - Nginx logs
   - `audit/audit.log` - SELinux audit logs

## Implementation Steps

### Step 1: Identify Available Log Sources

1. **Check for journald logs**:
   ```bash
   ls -la sos_commands/logs/journalctl_* 2>/dev/null || echo "No journald logs found"
   ```

2. **Check for traditional system logs**:
   ```bash
   ls -la var/log/{messages,dmesg,secure} 2>/dev/null || echo "No traditional logs found"
   ```

3. **Identify application-specific logs**:
   ```bash
   find var/log/ -type f -name "*.log" 2>/dev/null | head -20
   ```

### Step 2: Analyze Journald Logs

1. **Parse journalctl output for error patterns**:
   ```bash
   # Look for common error indicators
   grep -iE "(error|failed|failure|critical|panic|segfault|oom)" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -100
   ```

2. **Identify OOM (Out of Memory) killer events**:
   ```bash
   grep -i "out of memory\|oom.*kill" sos_commands/logs/journalctl_--no-pager 2>/dev/null
   ```

3. **Find kernel panics**:
   ```bash
   grep -i "kernel panic\|bug:\|oops:" sos_commands/logs/journalctl_--no-pager 2>/dev/null
   ```

4. **Check for segmentation faults**:
   ```bash
   grep -i "segfault\|sigsegv\|core dump" sos_commands/logs/journalctl_--no-pager 2>/dev/null
   ```

5. **Extract service failures**:
   ```bash
   grep -i "failed to start\|failed with result" sos_commands/logs/journalctl_--no-pager 2>/dev/null
   ```

### Step 3: Analyze System Logs (var/log)

1. **Check messages for errors**:
   ```bash
   # If file exists and is readable
   if [ -f var/log/messages ]; then
     grep -iE "(error|failed|failure|critical)" var/log/messages | tail -100
   fi
   ```

2. **Check dmesg for hardware issues**:
   ```bash
   if [ -f var/log/dmesg ]; then
     grep -iE "(error|fail|warning|i/o error|bad sector)" var/log/dmesg
   fi
   ```

3. **Analyze authentication logs**:
   ```bash
   if [ -f var/log/secure ]; then
     grep -iE "(failed|failure|invalid|denied)" var/log/secure | tail -50
   fi
   ```

### Step 4: Count and Categorize Errors

1. **Count errors by severity**:
   ```bash
   # Critical errors
   grep -ic "critical\|panic\|fatal" sos_commands/logs/journalctl_--no-pager 2>/dev/null || echo "0"

   # Errors
   grep -ic "error" sos_commands/logs/journalctl_--no-pager 2>/dev/null || echo "0"

   # Warnings
   grep -ic "warning\|warn" sos_commands/logs/journalctl_--no-pager 2>/dev/null || echo "0"
   ```

2. **Find most frequent error messages**:
   ```bash
   grep -iE "(error|failed)" sos_commands/logs/journalctl_--no-pager 2>/dev/null | \
     sed 's/^.*\]: //' | \
     sort | uniq -c | sort -rn | head -10
   ```

3. **Extract timestamps for error timeline**:
   ```bash
   # Get first and last error timestamps
   grep -i "error" sos_commands/logs/journalctl_--no-pager 2>/dev/null | \
     head -1 | awk '{print $1, $2, $3}'
   grep -i "error" sos_commands/logs/journalctl_--no-pager 2>/dev/null | \
     tail -1 | awk '{print $1, $2, $3}'
   ```

### Step 5: Analyze Application-Specific Logs

1. **Identify application logs**:
   ```bash
   find var/log/ -type f \( -name "*.log" -o -name "*_log" \) 2>/dev/null
   ```

2. **Check for stack traces and exceptions**:
   ```bash
   # Python tracebacks
   grep -A 10 "Traceback (most recent call last)" var/log/*.log 2>/dev/null | head -50

   # Java exceptions
   grep -B 2 -A 10 "Exception\|Error:" var/log/*.log 2>/dev/null | head -50
   ```

3. **Look for common application errors**:
   ```bash
   # Database connection errors
   grep -i "connection.*refused\|connection.*timeout\|database.*error" var/log/*.log 2>/dev/null

   # HTTP/API errors
   grep -E "HTTP [45][0-9]{2}|status.*[45][0-9]{2}" var/log/*.log 2>/dev/null | head -20
   ```

### Step 6: Generate Log Analysis Summary

Create a structured summary with the following information:

1. **Error Statistics**:
   - Total critical errors
   - Total errors
   - Total warnings
   - Time range of errors (first to last)

2. **Critical Findings**:
   - Kernel panics (with timestamps)
   - OOM killer events (with victim processes)
   - Segmentation faults (with process names)
   - Service failures (with service names)

3. **Top Error Messages** (sorted by frequency):
   - Error message
   - Count
   - First occurrence timestamp
   - Affected component/service

4. **Application-Specific Issues**:
   - Stack traces found
   - Database errors
   - Network/connectivity errors
   - Authentication failures

5. **Log File Locations**:
   - Provide paths to specific log files for manual investigation
   - Indicate which logs contain the most relevant information

## Error Handling

1. **Missing log files**:
   - If journalctl logs are missing, fall back to var/log/* files
   - If traditional logs are missing, document this in the summary
   - Some sosreports may have limited logs due to collection parameters

2. **Large log files**:
   - For files larger than 100MB, sample the beginning and end
   - Use `head -n 10000` and `tail -n 10000` to avoid memory issues
   - Inform user that analysis is based on sampling

3. **Compressed logs**:
   - Check for `.gz` files in `var/log/`
   - Use `zgrep` instead of `grep` for compressed files
   - Example: `zgrep -i "error" var/log/messages*.gz`

4. **Binary log formats**:
   - Some logs may be in binary format (e.g., journald binary logs)
   - Rely on `sos_commands/logs/journalctl_*` text outputs
   - Do not attempt to parse binary files directly

## Output Format

The log analysis should produce:

```bash
LOG ANALYSIS SUMMARY
====================

Time Range: {first_log_entry} to {last_log_entry}

ERROR STATISTICS
----------------
Critical: {count}
Errors: {count}
Warnings: {count}

CRITICAL FINDINGS
-----------------
Kernel Panics: {count}
  - {timestamp}: {panic_message}

OOM Killer Events: {count}
  - {timestamp}: Killed {process_name} (PID: {pid})

Segmentation Faults: {count}
  - {timestamp}: {process_name} segfaulted

Service Failures: {count}
  - {service_name}: {failure_reason}

TOP ERROR MESSAGES
------------------
1. [{count}x] {error_message}
   First seen: {timestamp}
   Component: {component}

2. [{count}x] {error_message}
   First seen: {timestamp}
   Component: {component}

APPLICATION ERRORS
------------------
Stack Traces: {count} found in {log_files}
Database Errors: {count}
Network Errors: {count}
Auth Failures: {count}

LOG FILES FOR INVESTIGATION
---------------------------
- Primary: {sosreport_path}/sos_commands/logs/journalctl_--no-pager
- System: {sosreport_path}/var/log/messages
- Kernel: {sosreport_path}/var/log/dmesg
- Security: {sosreport_path}/var/log/secure
- Application: {sosreport_path}/var/log/{app_specific}

RECOMMENDATIONS
---------------
1. {actionable_recommendation_based_on_findings}
2. {actionable_recommendation_based_on_findings}
```

## Examples

### Example 1: OOM Killer Analysis

```bash
# Detect OOM events
grep -B 5 -A 15 "Out of memory" sos_commands/logs/journalctl_--no-pager

# Output interpretation:
# - Which process was killed
# - Memory state at the time
# - What triggered the OOM
```

### Example 2: Service Failure Pattern

```bash
# Find failed services
grep "failed to start\|Failed with result" sos_commands/logs/journalctl_--no-pager | \
  awk -F'[][]' '{print $2}' | sort | uniq -c | sort -rn

# This shows which services failed most frequently
```

### Example 3: Timeline of Errors

```bash
# Create error timeline
grep -i "error\|fail" sos_commands/logs/journalctl_--no-pager | \
  awk '{print $1, $2, $3}' | sort | uniq -c

# Shows error frequency over time
```

## Tips for Effective Analysis

1. **Start with critical errors**: Focus on panics, OOMs, and segfaults first
2. **Look for patterns**: Repeated errors often indicate systemic issues
3. **Check timestamps**: Correlate errors with the reported incident time
4. **Consider context**: Read surrounding log lines for context
5. **Cross-reference**: Correlate log findings with resource analysis
6. **Be thorough**: Check both journald and traditional logs
7. **Document findings**: Note file paths and line numbers for reference

## Common Log Patterns to Look For

1. **OOM Killer**: "Out of memory: Kill process" → Memory pressure issue
2. **Segfault**: "segfault at" → Application crash, possible bug
3. **I/O Error**: "I/O error" in dmesg → Hardware or filesystem issue
4. **Connection Refused**: "Connection refused" → Service not running or firewall
5. **Permission Denied**: "Permission denied" → SELinux, file permissions, or ACL issue
6. **Timeout**: "timeout" → Network or resource contention
7. **Failed to start**: "Failed to start" → Service configuration or dependency issue

## See Also

- Resource Analysis Skill: For correlating log errors with resource constraints
- System Configuration Analysis Skill: For investigating service failures
- Network Analysis Skill: For investigating connectivity errors
