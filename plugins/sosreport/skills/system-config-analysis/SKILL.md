---
name: System Configuration Analysis
description: Analyze system configuration data from sosreport archives, extracting OS details, installed packages, systemd service status, SELinux/AppArmor policies, and kernel parameters from the sosreport directory structure to diagnose configuration-related system issues
---

# System Configuration Analysis Skill

This skill provides detailed guidance for analyzing system configuration from sosreport archives, including OS information, installed packages, systemd services, and SELinux/AppArmor settings.

## When to Use This Skill

Use this skill when:
- Analyzing the `/sosreport:analyze` command's system configuration phase
- Investigating service failures or misconfigurations
- Verifying package versions and updates
- Checking security policy settings (SELinux/AppArmor)
- Understanding system state and configuration

## Prerequisites

- Sosreport archive must be extracted to a working directory
- Path to the sosreport root directory must be known
- Understanding of Linux system administration

## Key Configuration Data Locations in Sosreport

1. **System Information**:
   - `uname` - Kernel version
   - `etc/os-release` - OS distribution and version
   - `uptime` - System uptime
   - `proc/uptime` - Uptime in seconds
   - `sos_commands/release/` - Release information

2. **Package Information**:
   - `installed-rpms` - RPM packages (RHEL/Fedora/CentOS)
   - `installed-debs` - DEB packages (Debian/Ubuntu)
   - `sos_commands/yum/` - Yum/DNF information
   - `sos_commands/rpm/` - RPM database queries

3. **Service Status**:
   - `sos_commands/systemd/systemctl_list-units` - All units
   - `sos_commands/systemd/systemctl_list-units_--failed` - Failed units
   - `sos_commands/systemd/systemctl_status_--all` - Detailed service status
   - `sos_commands/systemd/systemctl_list-unit-files` - Unit files

4. **SELinux**:
   - `sos_commands/selinux/sestatus` - SELinux status
   - `sos_commands/selinux/getenforce` - Current enforcement mode
   - `sos_commands/selinux/selinux-policy` - Policy information
   - `var/log/audit/audit.log` - SELinux denials

5. **AppArmor** (if applicable):
   - `sos_commands/apparmor/` - AppArmor configuration
   - `etc/apparmor.d/` - AppArmor profiles

6. **System Configuration Files**:
   - `etc/` - System-wide configuration
   - `etc/sysctl.conf` or `etc/sysctl.d/` - Kernel parameters
   - `etc/security/limits.conf` - Resource limits

## Implementation Steps

### Step 1: Analyze System Information

1. **Check OS version and distribution**:
   ```bash
   if [ -f etc/os-release ]; then
     cat etc/os-release
   fi
   ```

2. **Get kernel version**:
   ```bash
   if [ -f uname ]; then
     cat uname
   elif [ -f proc/version ]; then
     cat proc/version
   fi
   ```

3. **Check system uptime**:
   ```bash
   if [ -f uptime ]; then
     cat uptime
   elif [ -f proc/uptime ]; then
     # Parse uptime from proc/uptime (seconds)
     awk '{printf "%.2f days\n", $1/86400}' proc/uptime
   fi
   ```

4. **Extract key system details**:
   - OS name and version
   - Kernel version
   - System architecture (x86_64, aarch64, etc.)
   - Uptime (days)

5. **Check for outdated kernel or OS**:
   - Compare kernel version with current stable
   - Note if system hasn't been rebooted in a very long time (>365 days)
   - Identify if OS version is EOL

### Step 2: Analyze Installed Packages

1. **List installed packages**:
   ```bash
   # For RPM-based systems
   if [ -f installed-rpms ]; then
     cat installed-rpms
   fi

   # For DEB-based systems
   if [ -f installed-debs ]; then
     cat installed-debs
   fi
   ```

2. **Extract key package versions**:
   ```bash
   # Important system packages
   grep -E "^(kernel|systemd|glibc|openssh|openssl)" installed-rpms 2>/dev/null

   # Or use awk to parse package name and version
   awk '{print $1}' installed-rpms | head -20
   ```

3. **Check for known problematic versions**:
   - Security vulnerabilities (if known CVEs)
   - Buggy package versions
   - Compatibility issues

4. **Identify package manager issues**:
   ```bash
   # Check yum/dnf logs for errors
   if [ -d sos_commands/yum ]; then
     grep -i "error\|fail" sos_commands/yum/* 2>/dev/null
   fi
   ```

5. **Count packages and categorize**:
   - Total packages installed
   - Key package versions (kernel, systemd, glibc, etc.)
   - Recently updated packages (if timestamps available)

### Step 3: Analyze Service Status

1. **List all systemd units**:
   ```bash
   if [ -f sos_commands/systemd/systemctl_list-units ]; then
     cat sos_commands/systemd/systemctl_list-units
   fi
   ```

2. **Identify failed services**:
   ```bash
   if [ -f sos_commands/systemd/systemctl_list-units_--failed ]; then
     cat sos_commands/systemd/systemctl_list-units_--failed
   elif [ -f sos_commands/systemd/systemctl_list-units ]; then
     grep "failed" sos_commands/systemd/systemctl_list-units
   fi
   ```

3. **Check service details**:
   ```bash
   # Parse detailed status for failed services
   if [ -f sos_commands/systemd/systemctl_status_--all ]; then
     # Extract service names and their status
     grep -E "●|Active:" sos_commands/systemd/systemctl_status_--all | head -50
   fi
   ```

4. **Count services by state**:
   ```bash
   # Count running, failed, inactive services
   if [ -f sos_commands/systemd/systemctl_list-units ]; then
     awk '{print $4}' sos_commands/systemd/systemctl_list-units | sort | uniq -c
   fi
   ```

5. **Identify critical service failures**:
   - System services (systemd-*, dbus, NetworkManager)
   - Application services (httpd, nginx, postgresql, etc.)
   - Custom services

6. **Extract failure reasons from logs**:
   ```bash
   # For each failed service, find related log entries
   grep -i "failed to start\|service.*failed" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20
   ```

### Step 4: Analyze SELinux Configuration

1. **Check SELinux status**:
   ```bash
   if [ -f sos_commands/selinux/sestatus ]; then
     cat sos_commands/selinux/sestatus
   fi
   ```

2. **Get SELinux mode**:
   ```bash
   if [ -f sos_commands/selinux/getenforce ]; then
     cat sos_commands/selinux/getenforce
   fi
   ```

3. **Check for SELinux denials**:
   ```bash
   # Look for AVC denials in audit log
   if [ -f var/log/audit/audit.log ]; then
     grep "avc.*denied" var/log/audit/audit.log | head -50
   fi

   # Or in journald logs
   grep -i "selinux.*denied\|avc.*denied" sos_commands/logs/journalctl_--no-pager 2>/dev/null | head -20
   ```

4. **Parse denial information**:
   - Extract denied operations (read, write, execute, etc.)
   - Identify source and target contexts
   - Note which services are affected

5. **Check for SELinux booleans**:
   ```bash
   if [ -f sos_commands/selinux/getsebool_-a ]; then
     cat sos_commands/selinux/getsebool_-a
   fi
   ```

6. **Identify SELinux issues**:
   - SELinux in permissive mode (may hide errors)
   - SELinux disabled (security concern)
   - Frequent AVC denials (policy may need adjustment)
   - Context mismatches

### Step 5: Check System Configuration

1. **Review kernel parameters**:
   ```bash
   # Check sysctl settings
   if [ -f sos_commands/kernel/sysctl_-a ]; then
     cat sos_commands/kernel/sysctl_-a
   elif [ -d etc/sysctl.d ]; then
     cat etc/sysctl.d/*.conf 2>/dev/null
   fi
   ```

2. **Check resource limits**:
   ```bash
   if [ -f etc/security/limits.conf ]; then
     grep -v "^#\|^$" etc/security/limits.conf
   fi

   # Check limits.d directory
   if [ -d etc/security/limits.d ]; then
     cat etc/security/limits.d/*.conf 2>/dev/null
   fi
   ```

3. **Review boot parameters**:
   ```bash
   if [ -f sos_commands/boot/grub2-editenv_list ]; then
     cat sos_commands/boot/grub2-editenv_list
   elif [ -f proc/cmdline ]; then
     cat proc/cmdline
   fi
   ```

4. **Check systemd configuration**:
   ```bash
   # Look for systemd configuration overrides
   if [ -d etc/systemd/system ]; then
     find etc/systemd/system -name "*.conf" 2>/dev/null
   fi
   ```

### Step 6: Generate System Configuration Summary

Create a structured summary with the following sections:

1. **System Information**:
   - OS name and version
   - Kernel version
   - Architecture
   - System uptime
   - Last boot time

2. **Package Summary**:
   - Total packages installed
   - Key package versions (kernel, systemd, glibc, openssl, openssh)
   - Known problematic packages (if any)
   - Package manager issues

3. **Service Status**:
   - Total services
   - Running services count
   - Failed services count
   - List of failed services with reasons
   - Critical service status

4. **SELinux/AppArmor**:
   - SELinux status (enabled/disabled)
   - SELinux mode (enforcing/permissive)
   - Denial count
   - Top denied operations
   - Policy recommendations

5. **Configuration Issues**:
   - Kernel parameter anomalies
   - Resource limit issues
   - Boot parameter problems
   - Configuration file errors

## Error Handling

1. **Missing configuration files**:
   - Different distributions have different file locations
   - Some files may not be collected based on sosreport options
   - Document missing data in summary

2. **Package manager variations**:
   - Handle both RPM and DEB systems
   - Account for different package naming conventions
   - Support multiple package managers (yum, dnf, apt)

3. **SELinux vs AppArmor**:
   - Check which MAC system is in use
   - Analyze accordingly
   - Note if both or neither are present

4. **Systemd vs init**:
   - Older systems may use init instead of systemd
   - Check for both service management systems
   - Adapt analysis based on what's present

## Output Format

The system configuration analysis should produce:

```bash
SYSTEM CONFIGURATION SUMMARY
============================

SYSTEM INFORMATION
------------------
OS: {os_name} {os_version}
Kernel: {kernel_version}
Architecture: {arch}
Uptime: {uptime_days} days ({last_boot_time})

Status: {OK|WARNING|CRITICAL}
Notes:
  - {system_info_note}

INSTALLED PACKAGES
------------------
Total Packages: {count}

Key Package Versions:
  kernel: {version}
  systemd: {version}
  glibc: {version}
  openssl: {version}
  openssh-server: {version}

Status: {OK|WARNING|CRITICAL}
Issues:
  - {package_issue_description}

SYSTEMD SERVICES
----------------
Total Units: {total}
Active: {active_count}
Failed: {failed_count}
Inactive: {inactive_count}

Failed Services:
  ● {service_name}.service - {description}
    Reason: {failure_reason}
    Last Failed: {timestamp}

  ● {service_name}.service - {description}
    Reason: {failure_reason}
    Last Failed: {timestamp}

Status: {OK|WARNING|CRITICAL}
Recommendations:
  - {service_recommendation}

SELINUX
-------
Status: {enabled|disabled}
Mode: {enforcing|permissive|disabled}
Policy: {policy_name}

AVC Denials: {count} denials found

Top Denied Operations:
  [{count}x] {operation} on {target} by {source}
  [{count}x] {operation} on {target} by {source}

SELinux Booleans: {count} custom settings

Status: {OK|WARNING|CRITICAL}
Issues:
  - {selinux_issue_description}

Recommendations:
  - {selinux_recommendation}

KERNEL PARAMETERS
-----------------
Key sysctl Settings:
  vm.swappiness: {value}
  net.ipv4.ip_forward: {value}
  kernel.panic: {value}

Custom Parameters: {count} custom settings found

Status: {OK|WARNING|CRITICAL}
Notes:
  - {kernel_param_note}

RESOURCE LIMITS
---------------
Custom Limits Found: {count}

{user_or_group}  {type}  {item}  {value}

Status: {OK|WARNING}
Notes:
  - {limits_note}

CRITICAL CONFIGURATION ISSUES
-----------------------------
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
- OS Info: {sosreport_path}/etc/os-release
- Kernel: {sosreport_path}/uname
- Packages: {sosreport_path}/installed-rpms
- Services: {sosreport_path}/sos_commands/systemd/systemctl_list-units
- SELinux: {sosreport_path}/sos_commands/selinux/sestatus
- Audit Log: {sosreport_path}/var/log/audit/audit.log
```

## Examples

### Example 1: Failed Service Analysis

```bash
# List failed services
$ cat sos_commands/systemd/systemctl_list-units_--failed
  UNIT                    LOAD   ACTIVE SUB    DESCRIPTION
● httpd.service          loaded failed failed Apache Web Server
● postgresql.service     loaded failed failed PostgreSQL database

# Find failure reason in logs
$ grep "httpd.service" sos_commands/logs/journalctl_--no-pager | grep -i "failed\|error"
Jan 15 10:23:45 server systemd[1]: httpd.service: Main process exited, code=exited, status=1/FAILURE
Jan 15 10:23:45 server systemd[1]: httpd.service: Failed with result 'exit-code'
Jan 15 10:23:45 server httpd[12345]: (98)Address already in use: AH00072: make_sock: could not bind to address [::]:80

# Interpretation: httpd failed because port 80 is already in use
```

### Example 2: SELinux Denial Analysis

```bash
# Check for AVC denials
$ grep "avc.*denied" var/log/audit/audit.log | head -5
type=AVC msg=audit(1705320245.123:456): avc: denied { write } for pid=1234 comm="httpd" name="index.html" dev="sda1" ino=789012 scontext=system_u:system_r:httpd_t:s0 tcontext=system_u:object_r:user_home_t:s0 tclass=file permissive=0

# Interpretation:
# - httpd (web server) was denied write access
# - Target file: index.html with context user_home_t
# - Issue: Web server trying to write to user home directory
# - Solution: Fix file context or move file to proper location
```

### Example 3: Package Version Check

```bash
# Check for specific package versions
$ grep "^openssl" installed-rpms
openssl-1.1.1k-7.el8_6.x86_64
openssl-libs-1.1.1k-7.el8_6.x86_64

$ grep "^kernel" installed-rpms
kernel-4.18.0-425.el8.x86_64
kernel-4.18.0-477.el8.x86_64
kernel-core-4.18.0-425.el8.x86_64
kernel-core-4.18.0-477.el8.x86_64

# Interpretation:
# - OpenSSL version 1.1.1k (check for known CVEs)
# - Multiple kernels installed (good for rollback)
# - Current kernel is 4.18.0-477 (from uname)
```

## Tips for Effective Analysis

1. **Check service dependencies**: Failed service may be due to dependency failure
2. **Correlate with logs**: Service failures often have detailed errors in logs
3. **Verify configurations**: Check service config files for syntax errors
4. **Consider timing**: When did service fail? Correlate with system events
5. **SELinux context matters**: File contexts must match policy expectations
6. **Package versions**: Compare with known good/bad versions
7. **Uptime significance**: Very long uptime may mean missed security updates

## Common Configuration Patterns and Issues

1. **Service dependency failure**: ServiceB fails because ServiceA is not running
2. **Port conflict**: Service fails to bind - port already in use
3. **Permission denied**: Service can't access required files/directories
4. **SELinux blocking**: Service denied access by SELinux policy
5. **Missing dependencies**: Required package not installed
6. **Configuration error**: Syntax error in config file
7. **Resource limits**: Service hits ulimit (open files, processes, etc.)
8. **Outdated kernel**: Running kernel doesn't match installed packages

## Configuration Issue Severity Classification

| Issue Type | Severity | Impact |
|------------|----------|--------|
| Critical service failed | High | Core functionality unavailable |
| Optional service failed | Low | Non-essential feature unavailable |
| SELinux in permissive | Warning | Reduced security, hiding issues |
| SELinux disabled | Critical | No mandatory access control |
| Kernel very outdated | High | Missing security fixes |
| EOL OS version | Critical | No security updates |
| Many AVC denials | Warning | Policy may need tuning |

## See Also

- Logs Analysis Skill: For detailed service failure log analysis
- Resource Analysis Skill: For resource limit issues
- Network Analysis Skill: For network service configuration
