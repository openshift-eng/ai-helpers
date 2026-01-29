---
description: Analyze agent-gather data for common installation issues
argument-hint: [path] [--component name] [--attach-logs]
---

## Name
agent-gather:analyze

## Synopsis
```
/agent-gather:analyze [path] [--component name] [--attach-logs]
```

## Description
The `agent-gather:analyze` command analyzes agent-gather archives or decoded logs to identify common installation issues, error patterns, and validation failures. It can work with either compressed archives or already-extracted/decoded logs.

## Arguments
- `path` (optional): Path to agent-gather archive (.tar.xz), extracted directory, or decoded log file. Defaults to current directory
- `--component` (optional): Focus analysis on specific component (network, storage, validation, assisted-service, kubelet, etc.)
- `--attach-logs` (optional): User provides logs directly via file upload or paste

## Implementation

1. **Detect Input Type**
   - Check if path is:
     - Compressed archive (`.tar.xz` or `.tar.gz`)
     - Extracted directory (contains `journal.export` or log files)
     - Decoded log file (`.log` file, typically `jnl.log`)
     - If `--attach-logs`, prompt user to upload/paste logs
   - Handle each type appropriately

2. **Process Archive** (if compressed)
   - Extract archive: `tar -xf <archive> -C agent-gather-temp/`
   - Check for journal.export
   - If found, run `/agent-gather:decode-journal` automatically
   - Proceed to analysis with decoded logs

3. **Process Directory** (if extracted but not decoded)
   - Look for `journal.export` file
   - If found, run `/agent-gather:decode-journal` automatically
   - Look for other log files (`assisted-service.log`, `agent-tui.log`, etc.)
   - Proceed to analysis with all available logs

4. **Process Log Files** (if already decoded or provided)
   - If `jnl.log` exists, use it as primary source
   - Also scan for:
     - `assisted-service.log`
     - `agent-tui.log`
     - Service-specific logs
   - If `--attach-logs`, read from provided file or stdin

5. **Analyze Common Error Patterns**

   Search for common issues:

   **Installation Failures:**
   - "bootstrap failed"
   - "installation failed"
   - "cluster installation timeout"
   - "no agent found matching config"

   **Validation Failures:**
   - "validation failed"
   - "insufficient resources"
   - "host validation failed"
   - "cluster validation failed"

   **Network Issues:**
   - "connection refused"
   - "network unreachable"
   - "DNS resolution failed"
   - "timeout connecting"

   **Service Crashes:**
   - "service failed"
   - "panic"
   - "segmentation fault"
   - "exit code"

   **Configuration Errors:**
   - "invalid configuration"
   - "missing required field"
   - "parsing error"

6. **Component-Specific Analysis** (if `--component` specified)

   **Network:**
   - DNS configuration
   - Network interface status
   - Routing issues
   - Firewall blocks

   **Storage:**
   - Disk space issues
   - Mount failures
   - Storage validation failures

   **Validation:**
   - Host validation details
   - Cluster validation details
   - Resource requirements

   **Services:**
   - assisted-service errors
   - kubelet issues
   - container runtime problems

7. **Generate Report**
   - Summary of findings
   - Critical errors (priority: emerg, alert, crit, err)
   - Warnings (priority: warning)
   - Timeline of key events
   - Suggested remediation steps
   - Relevant log excerpts with context

8. **Interactive Follow-up**
   - Offer to show full logs for specific errors
   - Suggest next troubleshooting steps
   - Provide relevant documentation links
   - Offer to search for specific patterns

## Return Value

- **Success**: Analysis report with findings and recommendations
- **Failure**: Error message indicating what went wrong

## Examples

1. **Analyze agent-gather archive**:
   ```
   /agent-gather:analyze agent-gather.tar.xz
   ```
   Output:
   ```
   Analyzing agent-gather.tar.xz...
   Extracting archive...
   Decoding journal logs...

   === Agent-Gather Analysis Report ===

   Critical Issues Found: 2
   Warnings: 5

   [CRITICAL] Bootstrap failure detected
   Time: 2025-12-24 10:45:23
   Service: assisted-service
   Message: "Cluster installation failed: validation failure on control-plane-0"

   [CRITICAL] Host validation failed
   Time: 2025-12-24 10:42:15
   Service: assisted-service
   Message: "Host validation failed: insufficient memory (16GB required, 8GB available)"

   [WARNING] DNS resolution slow
   Time: 2025-12-24 10:30:12
   Service: NetworkManager
   Message: "DNS query timeout for api.cluster.example.com"

   Recommendations:
   1. Increase memory on control-plane-0 to at least 16GB
   2. Verify DNS server configuration and connectivity
   3. Check network connectivity to all required endpoints

   Next steps:
   - Run /agent-gather:analyze --component validation for detailed validation info
   - Check host resources: memory, CPU, disk space
   - Verify DNS configuration in install-config.yaml
   ```

2. **Analyze with component focus**:
   ```
   /agent-gather:analyze --component network
   ```
   Searches specifically for network-related issues

3. **Analyze decoded logs**:
   ```
   /agent-gather:analyze jnl.log
   ```
   Analyzes an already-decoded journal log file

4. **Analyze with attached logs**:
   ```
   /agent-gather:analyze --attach-logs
   ```
   Prompts:
   ```
   Please provide the agent-gather logs:
   - Upload a file, or
   - Paste log contents below (Ctrl+D when done)
   ```

5. **Analyze extracted directory**:
   ```
   /agent-gather:analyze ./agent-gather-extracted-192.168.1.100/
   ```
   Analyzes logs in an extracted directory

6. **Quick error summary**:
   ```
   /agent-gather:analyze agent-gather.tar.xz --component validation
   ```
   Focus only on validation failures

## Analysis Components

### Network Analysis (`--component network`)
- Network interface configuration
- DNS resolution issues
- Connectivity to required endpoints
- Firewall or routing problems
- NTP/time synchronization issues

### Storage Analysis (`--component storage`)
- Disk space availability
- Mount point issues
- Storage performance problems
- Disk I/O errors

### Validation Analysis (`--component validation`)
- Host validation failures
- Cluster validation failures
- Resource requirements not met
- Configuration issues

### Service Analysis (`--component assisted-service|kubelet|crio`)
- Service-specific errors
- Crash dumps
- Configuration issues
- Performance problems

## Error Patterns Detected

The analysis searches for these common patterns:

### Critical Patterns
```
- "panic:"
- "fatal error"
- "segmentation fault"
- "out of memory"
- "no space left on device"
- "validation failed"
- "installation failed"
- "bootstrap failed"
```

### Warning Patterns
```
- "timeout"
- "connection refused"
- "retrying"
- "slow"
- "degraded"
- "warning:"
```

### Info Patterns
```
- "starting"
- "completed"
- "success"
- "ready"
```

## Timeline Generation

The analysis creates a timeline of key events:

```
Timeline of Installation Events:
10:15:23 - assisted-service started
10:16:45 - Host discovery initiated
10:18:12 - control-plane-0 registered
10:18:45 - control-plane-1 registered
10:19:32 - control-plane-2 registered
10:20:15 - Cluster validation started
10:22:30 - [ERROR] Host validation failed on control-plane-0
10:25:00 - Installation aborted
```

## Providing Logs Directly

### Option 1: Upload File
When using `--attach-logs`:
```
/agent-gather:analyze --attach-logs
```

The plugin will prompt for file upload or allow pasting content directly.

### Option 2: Specify File Path
```
/agent-gather:analyze /path/to/my-logs.txt
```

### Option 3: Paste in Chat
User can also just paste logs directly in the conversation:
```
User: Can you analyze these agent-gather logs?

<paste logs here>

Dec 24 10:15:23 node-0 systemd[1]: Starting assisted-service...
Dec 24 10:15:24 node-0 assisted-service[1234]: ERROR: validation failed
...
```

## Validation Failure Details

When validation failures are detected, the analysis provides:

1. **Host Validation Failures**:
   - Which host failed
   - Specific validation checks that failed
   - Required vs. actual resources
   - Remediation steps

2. **Cluster Validation Failures**:
   - Cluster-level checks that failed
   - Network connectivity issues
   - DNS/API reachability
   - Configuration problems

Example output:
```
=== Validation Failures ===

Host: control-plane-0 (192.168.1.100)
Status: Insufficient

Failed Checks:
✗ Memory: Required 16GB, Available 8GB
✗ CPU: Required 4 cores, Available 2 cores
✓ Disk: Required 120GB, Available 500GB
✓ Network: All connectivity checks passed

Remediation:
1. Shutdown the node
2. Increase RAM to at least 16GB
3. Increase vCPU count to at least 4
4. Restart the node and re-run installation
```

## Troubleshooting

### No Errors Found
If analysis doesn't find obvious errors:
- Check if logs are complete (not truncated)
- Look for warnings that might indicate issues
- Review timeline for unexpected gaps
- Search for specific error messages manually

### Analysis Takes Too Long
For very large log files:
- Use `--component` to focus on specific areas
- Pre-filter logs before analysis
- Decode only specific services: `/agent-gather:decode-journal --service assisted-service`

### Ambiguous Results
If multiple issues found:
- Prioritize by severity (critical > error > warning)
- Follow chronological order (first error often root cause)
- Use component-specific analysis to drill down

## Report Sections

A complete analysis report includes:

1. **Executive Summary**
   - Number of critical issues
   - Number of warnings
   - Installation outcome

2. **Critical Issues**
   - Detailed error messages
   - Timestamps
   - Affected components
   - Log excerpts

3. **Warnings**
   - Non-critical issues
   - Performance concerns
   - Configuration recommendations

4. **Timeline**
   - Chronological event sequence
   - Key milestones
   - Error occurrences

5. **Recommendations**
   - Specific remediation steps
   - Configuration changes needed
   - Resource adjustments required

6. **Next Steps**
   - Suggested actions
   - Additional analysis needed
   - Documentation links

## Notes

- Analysis can work with compressed archives, extracted directories, or decoded logs
- Automatic journal decoding if needed (requires systemd-journal-remote)
- Pattern matching uses both regex and keyword search
- Timestamps are preserved from original system
- Analysis is read-only and doesn't modify source files
- Multiple log sources are combined for comprehensive analysis

## See Also

- `/agent-gather:collect` - Collect agent-gather data from nodes
- `/agent-gather:decode-journal` - Decode journal export files
- [Agent-based Installer Troubleshooting](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/installing_an_on-premise_cluster_with_the_agent-based_installer/installing-with-agent-based-installer#troubleshooting)
- [Common Installation Issues](https://access.redhat.com/solutions/7012958)
