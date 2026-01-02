---
description: Analyze Windows node logs and issues in must-gather data
argument-hint: "[must-gather-path] [--component COMPONENT]"
---

## Name
must-gather:windows

## Synopsis
```
/must-gather:windows [must-gather-path] [--component COMPONENT] [--errors-only]
```

## Description

The `must-gather:windows` command analyzes Windows-specific logs collected during must-gather from Windows nodes in OpenShift clusters. It parses logs from Windows-specific components and identifies common Windows node issues.

This command analyzes logs from:
- **kube-proxy** - Windows networking service
- **hybrid-overlay** - OVN-Kubernetes hybrid networking (Linux-Windows pod communication)
- **kubelet** - Windows node agent
- **containerd** - Container runtime for Windows
- **WICD** - Windows Instance Config Daemon (node configuration)
- **csi-proxy** - Storage plugin for Windows

Use this command when:
- Troubleshooting Windows node issues
- Investigating Windows pod failures
- Analyzing Windows container runtime problems
- Debugging hybrid-overlay networking issues
- Reviewing HNS (Host Network Service) failures

## Prerequisites

**Windows Node Logs Collection:**

Windows node logs must be collected during must-gather. This requires:
1. The cluster has Windows nodes (labeled with `kubernetes.io/os=windows`)
2. Must-gather was run with Windows log collection enabled

**Expected Directory Structure:**
```
must-gather/
└── host_service_logs/
    └── windows/
        └── log_files/
            ├── kube-proxy/kube-proxy.log
            ├── hybrid-overlay/hybrid-overlay.log
            ├── kubelet/kubelet.log
            ├── containerd/containerd.log
            ├── wicd/
            │   ├── windows-instance-config-daemon.exe.INFO
            │   ├── windows-instance-config-daemon.exe.ERROR
            │   └── windows-instance-config-daemon.exe.WARNING
            └── csi-proxy/csi-proxy.log
```

## Implementation

1. **Locate Windows logs**:
   - Check for `host_service_logs/windows/log_files/` directory
   - If not found, inform user that cluster may not have Windows nodes or logs weren't collected

2. **Run Windows log analyzer**:
   ```bash
   python3 plugins/must-gather/skills/must-gather-analyzer/scripts/analyze_windows_logs.py \
     <must-gather-path>
   ```

3. **Parse logs for errors and warnings**:
   - Search for error patterns specific to each component
   - Categorize errors (HNS, Containerd, Hybrid-Overlay, etc.)
   - Count occurrences and identify trends

4. **Detect common Windows issues**:
   - **HNS failures** - Pods stuck in ContainerCreating
   - **Containerd errors** - Container runtime failures
   - **Hybrid-overlay issues** - Linux-Windows connectivity problems
   - **Kubelet failures** - Pod scheduling and management issues
   - **WICD errors** - Node configuration problems
   - **CSI-Proxy failures** - Storage mount issues

5. **Generate report with**:
   - Component status summary
   - Error and warning counts
   - Detected issues with severity (CRITICAL, HIGH, etc.)
   - Recommendations for remediation
   - Detailed error messages categorized by type

## Return Value

The command outputs:

```
================================================================================
WINDOWS NODE LOGS ANALYSIS
================================================================================
Log directory: <path>

Components analyzed: 6/8
Total log lines:     125,432
Total errors found:  23
Total warnings:      15

COMPONENT STATUS:
COMPONENT                 LINES      ERRORS     WARNINGS   STATUS
--------------------------------------------------------------------------------
kube-proxy                15,234     0          2          ✅ OK
hybrid-overlay            8,912      5          3          ❌ ERRORS
kubelet                   45,123     12         5          ❌ ERRORS
containerd                32,456     6          4          ❌ ERRORS
wicd-info                 12,345     0          1          ✅ OK
wicd-error                234        0          0          ✅ OK
wicd-warning              456        0          0          ✅ OK
csi-proxy                 10,672     0          0          ✅ OK

================================================================================
DETECTED ISSUES
================================================================================

1. [CRITICAL] HNS (Host Network Service) Failures Detected
   Found 5 HNS-related errors. This typically causes pods to fail in ContainerCreating state.
   → Check Windows node networking configuration. May need to restart HNS service or reboot node.

2. [CRITICAL] Container Runtime Failures
   Found 6 containerd errors. Containers may fail to start.
   → Check containerd service status on Windows node. Review container image compatibility.

================================================================================
DETAILED ERRORS BY CATEGORY
================================================================================

HNS ERRORS (5):
--------------------------------------------------------------------------------
  [hybrid-overlay:1234] failed to create HNS endpoint for pod default/test-pod
  [hybrid-overlay:2345] HNS network attach failed: endpoint not found
  ...

CONTAINERD ERRORS (6):
--------------------------------------------------------------------------------
  [containerd:567] failed to start container: runtime error
  [kubelet:890] failed to create pod sandbox: containerd timeout
  ...
```

## Examples

1. **Analyze all Windows logs**:
   ```
   /must-gather:windows ./must-gather.local.123456789
   ```
   Analyzes all Windows component logs and provides comprehensive report.

2. **Analyze specific component**:
   ```
   /must-gather:windows ./must-gather.local.123456789 --component kubelet
   ```
   Analyzes only kubelet logs from Windows nodes.

3. **Summary only (skip detailed errors)**:
   ```
   /must-gather:windows ./must-gather.local.123456789 --errors-only
   ```
   Shows component status and detected issues without detailed error listing.

4. **Analyze hybrid-overlay networking**:
   ```
   /must-gather:windows ./must-gather.local.123456789 --component hybrid-overlay
   ```
   Focuses on hybrid-overlay logs to troubleshoot Linux-Windows pod connectivity.

5. **Analyze containerd runtime**:
   ```
   /must-gather:windows ./must-gather.local.123456789 --component containerd
   ```
   Reviews container runtime logs for Windows container failures.

## Common Windows Issues Detected

### HNS (Host Network Service) Failures
**Symptoms:**
- Pods stuck in `ContainerCreating`
- `failed to create HNS endpoint` errors
- Network attach failures

**Recommendations:**
- Restart HNS service: `Restart-Service hns`
- Check Windows Firewall rules
- Verify network adapter configuration
- Consider node reboot if HNS is unresponsive

### Containerd Runtime Errors
**Symptoms:**
- Containers fail to start
- `runtime error` messages
- Image pull failures

**Recommendations:**
- Verify image OS matches (Windows vs Linux)
- Check containerd service status
- Review image platform compatibility
- Inspect containerd configuration

### Hybrid-Overlay Networking Issues
**Symptoms:**
- Linux pods cannot reach Windows pods
- Tunnel setup failures
- OVN errors

**Recommendations:**
- Verify OVN-Kubernetes hybrid-overlay configuration
- Check tunnel connectivity between nodes
- Review network policies
- Validate VXLAN configuration

### Kubelet Issues
**Symptoms:**
- Pods not scheduling to Windows nodes
- Pod sandbox creation failures
- Runtime not ready errors

**Recommendations:**
- Check kubelet service status
- Review node conditions
- Verify container runtime connectivity
- Check pod node selectors

### WICD Configuration Errors
**Symptoms:**
- Node configuration failures
- Instance config daemon errors

**Recommendations:**
- Review WICD error logs
- Check node bootstrap configuration
- Verify cloud provider integration

## Notes

- **No Windows Nodes**: If the command reports no Windows logs found, the cluster either has no Windows nodes or the logs weren't collected during must-gather
- **Log Location**: Windows logs are collected from nodes labeled `kubernetes.io/os=windows`
- **Collection Script**: Windows logs are gathered by the `gather_windows_nodes` script in the must-gather collection phase
- **Error Patterns**: The analyzer uses regex patterns specific to each Windows component
- **Max Errors**: By default, shows first 50 errors per log file; use `--max-errors` to adjust
- **Cross-Reference**: Combine with `/must-gather:analyze` for full cluster analysis including Windows resources

## Arguments

- **$1** (must-gather-path): Optional. Path to must-gather directory. If not provided, user will be prompted.
- **--component COMPONENT**: Optional. Analyze only a specific component (kubelet, containerd, hybrid-overlay, kube-proxy, wicd, csi-proxy).
- **--errors-only**: Optional. Show summary and detected issues only, skip detailed error listings.
- **--max-errors N**: Optional. Maximum number of errors to collect per log file (default: 50).
