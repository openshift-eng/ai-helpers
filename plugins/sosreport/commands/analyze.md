---
description: Analyze sosreport archive for system diagnostics and issues
argument-hint: <path-to-sosreport> [--only <areas>] [--skip <areas>]
---

## Name
sosreport:analyze

## Synopsis
```
/sosreport:analyze <path-to-sosreport> [--only <areas>] [--skip <areas>]
```

**Analysis Areas:**

- **`logs`**: Analyze system and application logs (journald, syslog, dmesg, application logs)
  - Identifies errors, warnings, critical messages
  - Detects OOM killer events, kernel panics, segfaults
  - Counts and categorizes errors by severity
  - Provides timeline of critical events

- **`resources`**: Analyze system resource usage (memory, CPU, disk, processes)
  - Memory usage, swap, and pressure indicators
  - CPU information and load averages
  - Disk usage and filesystem capacity
  - Top resource consumers and zombie processes

- **`network`**: Analyze network configuration and connectivity
  - Network interface status and IP addresses
  - Routing table and default gateway
  - Active connections and listening services
  - Firewall rules (firewalld/iptables)
  - DNS configuration and hostname resolution

- **`system-config`**: Analyze system configuration (packages, services, security)
  - OS version and kernel information
  - Installed package versions
  - Systemd service status and failures
  - SELinux/AppArmor configuration and denials
  - Kernel parameters and resource limits

## Description
The `sosreport:analyze` command performs comprehensive analysis of a sosreport archive (from <https://github.com/sosreport/sos>) to identify system issues, configuration problems, and potential causes of failures. It examines system logs, resource usage, network configuration, installed packages, and other diagnostic data collected by sosreport.

By default, all analysis areas are executed. Use `--only` to run specific areas or `--skip` to exclude areas from analysis.

## Arguments
- `$1` (required): Path to the sosreport archive file (`.tar.gz` or `.tar.xz`) or extracted directory
- `--only <areas>` (optional): Comma-separated list of analysis areas to run. Valid areas: `logs`, `resources`, `network`, `system-config`. If not specified, all areas are analyzed.
- `--skip <areas>` (optional): Comma-separated list of analysis areas to skip. Valid areas: `logs`, `resources`, `network`, `system-config`. Cannot be used with `--only`.

## Implementation

The sosreport analysis is organized into several specialized phases, each with detailed implementation guidance in separate skill documents. The command supports selective analysis through optional arguments.

### 1. Parse Arguments and Determine Analysis Scope

1. **Parse command-line arguments**
   - Extract the sosreport path (required first argument)
   - Check for `--only` flag and parse comma-separated areas
   - Check for `--skip` flag and parse comma-separated areas
   - Validate that `--only` and `--skip` are not used together

2. **Validate analysis areas**
   - Valid areas: `logs`, `resources`, `network`, `system-config`
   - If invalid area specified, return error with list of valid areas
   - Normalize area names (case-insensitive, accept variations like `system` for `system-config`)

3. **Determine which skills to run**
   - If no flags specified: Run all skills (default comprehensive analysis)
   - If `--only` specified: Run only the specified skills
   - If `--skip` specified: Run all skills except the specified ones
   - Store the list of skills to execute for later phases

4. **Example argument parsing**:
   ```bash
   # Parse: /sosreport:analyze /path/sos.tar.gz --only logs,network
   # Result: Run only logs-analysis and network-analysis skills

   # Parse: /sosreport:analyze /path/sos.tar.gz --skip resources
   # Result: Run logs, network, and system-config (skip resources)

   # Parse: /sosreport:analyze /path/sos.tar.gz
   # Result: Run all skills (comprehensive analysis)
   ```

### 2. Extract and Validate Sosreport

1. **Check if path exists**
   - Verify the provided path points to a valid file or directory
   - If file doesn't exist, return error with helpful message

2. **Extract archive if needed**
   - If path is a `.tar.gz` or `.tar.xz` file:
     - Create extraction directory: `.work/sosreport-analyze/{timestamp}/`
     - Extract archive: `tar -xf <path> -C .work/sosreport-analyze/{timestamp}/`
     - Store extracted directory path for analysis
   - If path is already a directory:
     - Verify it's a valid sosreport directory (check for `sos_commands/`, `sos_logs/`, etc.)
     - Use the directory directly

3. **Identify sosreport structure**
   - Locate the root directory (usually has format `sosreport-{hostname}-{date}/`)
   - Verify expected directories exist: `sos_commands/`, `sos_logs/`, `sos_reports/`

### 3. Analyze System Logs

**Run condition**: Only if `logs` area is selected (or no filters specified)
**Detailed implementation**: See `plugins/sosreport/skills/logs-analysis/SKILL.md`

Perform comprehensive log analysis including:
- Journald logs (journalctl output)
- System logs (messages, dmesg, secure)
- Application-specific logs
- Error counting and categorization
- Timeline of critical events
- OOM killer events, kernel panics, segfaults

**Key outputs**:
- Error statistics by severity
- Top error messages by frequency
- Critical findings with timestamps
- Log file locations for investigation

### 4. Analyze Resource Usage

**Run condition**: Only if `resources` area is selected (or no filters specified)
**Detailed implementation**: See `plugins/sosreport/skills/resource-analysis/SKILL.md`

Perform resource analysis including:
- Memory usage and pressure indicators
- CPU information and load averages
- Disk usage and I/O errors
- Process analysis (top consumers, zombies)
- Resource exhaustion patterns

**Key outputs**:
- Memory usage metrics and swap status
- CPU count and load per CPU
- Filesystems near capacity
- Top CPU and memory-consuming processes
- Resource-related issues and recommendations

### 5. Analyze Network Configuration

**Run condition**: Only if `network` area is selected (or no filters specified)
**Detailed implementation**: See `plugins/sosreport/skills/network-analysis/SKILL.md`

Perform network analysis including:
- Network interface configuration and status
- Routing table and default gateway
- Active connections and listening services
- Firewall rules (firewalld/iptables)
- DNS configuration and hostname resolution
- Network errors from logs

**Key outputs**:
- Interface status with IP addresses
- Routing configuration
- Connection statistics by state
- Firewall configuration summary
- DNS and hostname settings
- Network-related errors and issues

### 6. Analyze Installed Packages and System Configuration

**Run condition**: Only if `system-config` area is selected (or no filters specified)
**Detailed implementation**: See `plugins/sosreport/skills/system-config-analysis/SKILL.md`

Perform system configuration analysis including:
- OS version and kernel information
- Installed package versions
- Systemd service status
- Failed services with reasons
- SELinux/AppArmor configuration and denials
- Kernel parameters and resource limits

**Key outputs**:
- System information summary
- Key package versions
- Failed services with failure reasons
- SELinux status and denial count
- Configuration issues and recommendations

### 7. Generate Interactive Summary

1. **Create findings structure**
   - Organize findings by category (Critical, High, Medium, Low, Info)
   - Include only findings from the selected analysis areas
   - For each finding, include:
     - Severity level
     - Category (logs, resources, network, packages, config)
     - Description of the issue
     - Evidence (file paths, log snippets, metrics)
     - Recommended actions

2. **Display summary in terminal**
   - Show executive summary with key statistics
   - List critical and high-severity findings
   - Provide file paths for detailed investigation
   - Include timeline of significant events
   - Suggest next steps for troubleshooting

3. **Format output**
   ```bash
   SOSREPORT ANALYSIS SUMMARY
   ==========================

   System: {hostname}
   Report Date: {date}
   OS: {os_version}
   Kernel: {kernel_version}

   CRITICAL ISSUES (count)
   -----------------------
   - [Issue description with file reference]

   HIGH PRIORITY (count)
   ---------------------
   - [Issue description with file reference]

   MEDIUM PRIORITY (count)
   -----------------------
   - [Issue description with file reference]

   RESOURCE SUMMARY
   ----------------
   - Memory: X GB used / Y GB total (Z% used)
   - Disk: Most full filesystem at X%
   - Load Average: X.XX, X.XX, X.XX

   TOP ERRORS IN LOGS
   ------------------
   1. [Error message] (count occurrences)
   2. [Error message] (count occurrences)

   FAILED SERVICES
   ---------------
   - [service name]: [reason]

   RECOMMENDATIONS
   ---------------
   1. [Actionable recommendation]
   2. [Actionable recommendation]

   ANALYSIS LOCATION
   -----------------
   Extracted to: {extraction_path}
   ```

4. **Interactive drill-down**
   - Offer to explore specific areas in more detail
   - Allow user to ask follow-up questions about findings
   - Provide file paths for manual investigation

## Return Value

- **Format**: Interactive summary displayed in terminal with categorized findings
- **Exit code**:
  - 0 if analysis completes successfully
  - 1 if sosreport path is invalid
  - 2 if sosreport structure is malformed

## Examples

1. **Comprehensive analysis (default)**:
   ```bash
   /sosreport:analyze /tmp/sosreport-server01-2024-01-15.tar.xz
   ```

   Extracts archive to `.work/sosreport-analyze/{timestamp}/` and performs comprehensive analysis using all skills (logs, resources, network, system-config).

2. **Analyze only logs and network**:
   ```bash
   /sosreport:analyze /tmp/sosreport-server01-2024-01-15.tar.xz --only logs,network
   ```

   Performs only log analysis and network analysis. Useful when investigating connectivity or service issues without needing full resource analysis.

3. **Skip resource analysis**:
   ```bash
   /sosreport:analyze /tmp/sosreport.tar.gz --skip resources
   ```

   Performs all analysis except resource analysis. Useful when you already know resource metrics and want to focus on configuration and logs.

4. **Quick log-only analysis**:
   ```bash
   /sosreport:analyze /tmp/sosreport.tar.xz --only logs
   ```

   Performs only log analysis. Fastest option for quickly identifying errors and critical events without analyzing configuration or resources.

5. **Analyze extracted sosreport directory**:
   ```bash
   /sosreport:analyze /tmp/sosreport-server01-2024-01-15/
   ```

   Analyzes an already extracted sosreport directory with comprehensive analysis.

6. **Selective analysis on extracted directory**:
   ```bash
   /sosreport:analyze /tmp/sosreport-server01-2024-01-15/ --only system-config,network
   ```

   Analyzes only system configuration and network from an already extracted directory.

7. **Follow-up investigation**:
   ```bash
   User: /sosreport:analyze /tmp/sosreport.tar.gz --only logs
   Agent: [Shows log analysis summary]
   User: Can you now analyze the resources as well?
   Agent: /sosreport:analyze /tmp/sosreport.tar.gz --only resources
   Agent: [Shows resource analysis]
   ```

## Notes

- Sosreport structure varies by OS version and sosreport version
- Command handles both compressed archives and extracted directories
- Analysis focuses on common issues but can be extended for specific use cases
- For OpenShift/Kubernetes sosreports, additional pod/container analysis may be relevant
- Large sosreports (>1GB) may take several minutes to analyze
- **Selective analysis**: Use `--only` or `--skip` to run specific analysis areas for faster results
- **Performance**: Running only needed analysis areas reduces analysis time significantly
- **Valid areas**: `logs`, `resources`, `network`, `system-config`

## Prerequisites

1. **tar utility**: Required for extracting compressed sosreports
   - Check: `which tar`
   - Usually pre-installed on Linux/macOS

2. **Sufficient disk space**: Extracted sosreports can be large
   - Check available space: `df -h .work/`
   - Recommend at least 2x the compressed archive size

## See Also

### Analysis Skills
- **Logs Analysis**: `plugins/sosreport/skills/logs-analysis/SKILL.md` - Detailed guidance for analyzing system and application logs
- **Resource Analysis**: `plugins/sosreport/skills/resource-analysis/SKILL.md` - Detailed guidance for analyzing memory, CPU, disk, and processes
- **Network Analysis**: `plugins/sosreport/skills/network-analysis/SKILL.md` - Detailed guidance for analyzing network configuration and connectivity
- **System Configuration Analysis**: `plugins/sosreport/skills/system-config-analysis/SKILL.md` - Detailed guidance for analyzing packages, services, and security settings

### External Resources
- Sosreport documentation: <https://github.com/sosreport/sos>
- Red Hat sosreport guide: <https://access.redhat.com/solutions/3592>
