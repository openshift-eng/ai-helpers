# Sosreport Plugin

Automate sosreport analysis for system diagnostics and troubleshooting.

## Overview

The sosreport plugin provides AI-powered analysis of sosreport archives, which are diagnostic data collections from Linux systems. It automatically examines logs, resource usage, network configuration, and system state to identify issues and provide actionable recommendations.

## What is sosreport?

[sosreport](https://github.com/sosreport/sos) is a diagnostic data collection tool used primarily in Red Hat Enterprise Linux and related distributions. It gathers system configuration, logs, and diagnostic information into a single archive for troubleshooting purposes.

## Commands

### `/sosreport:analyze`

Performs comprehensive analysis of a sosreport archive with support for selective analysis.

**Usage:**
```bash
/sosreport:analyze <path-to-sosreport> [--only <areas>] [--skip <areas>]
```

**Arguments:**
- `<path-to-sosreport>`: Path to the sosreport archive (`.tar.gz`, `.tar.xz`) or extracted directory
- `--only <areas>`: (Optional) Run only specific analysis areas (comma-separated)
- `--skip <areas>`: (Optional) Skip specific analysis areas (comma-separated)

**Analysis Areas:**

The analysis is organized into four specialized areas, each with detailed implementation guidance:

1. **`logs`** - System and Application Logs Analysis
   - Analyzes journald logs, syslog, dmesg, and application logs
   - Identifies errors, warnings, and critical messages
   - Detects OOM killer events, kernel panics, segfaults
   - Counts and categorizes errors by severity
   - Provides timeline of critical events
   - **Skill**: [`skills/logs-analysis/SKILL.md`](skills/logs-analysis/SKILL.md)

2. **`resources`** - System Resource Usage Analysis
   - Memory usage, swap, and pressure indicators
   - CPU information and load averages
   - Disk usage and filesystem capacity
   - Process analysis (top consumers, zombies)
   - Resource exhaustion patterns
   - **Skill**: [`skills/resource-analysis/SKILL.md`](skills/resource-analysis/SKILL.md)

3. **`network`** - Network Configuration and Connectivity
   - Network interface status and IP addresses
   - Routing table and default gateway
   - Active connections and listening services
   - Firewall rules (firewalld/iptables/nftables)
   - DNS configuration and hostname resolution
   - Network error detection
   - **Skill**: [`skills/network-analysis/SKILL.md`](skills/network-analysis/SKILL.md)

4. **`system-config`** - System Configuration and Security
   - OS version and kernel information
   - Installed package versions
   - Systemd service status and failures
   - SELinux/AppArmor configuration and denials
   - Kernel parameters and resource limits
   - **Skill**: [`skills/system-config-analysis/SKILL.md`](skills/system-config-analysis/SKILL.md)

**Output:**
- Interactive summary categorized by severity (Critical, High, Medium, Low)
- Resource utilization metrics (when `resources` is selected)
- Top errors and their frequency (when `logs` is selected)
- Failed services (when `system-config` is selected)
- Network configuration status (when `network` is selected)
- Actionable recommendations
- File paths for detailed investigation

**Examples:**

```bash
# Comprehensive analysis (all areas)
/sosreport:analyze /tmp/sosreport-server01-2024-01-15.tar.xz

# Analyze only logs and network
/sosreport:analyze /tmp/sosreport.tar.xz --only logs,network

# Skip resource analysis
/sosreport:analyze /tmp/sosreport.tar.xz --skip resources

# Quick log-only analysis
/sosreport:analyze /tmp/sosreport.tar.xz --only logs

# Analyze extracted directory
/sosreport:analyze /tmp/sosreport-server01-2024-01-15/ --only system-config
```

The command automatically extracts compressed archives to `.work/sosreport-analyze/` and performs the selected analysis.

## Analysis Skills

The sosreport plugin uses specialized analysis skills for each area. Each skill contains detailed implementation guidance with bash commands, parsing logic, error handling, and output formats.

| Skill | Description | Documentation |
|-------|-------------|---------------|
| **Logs Analysis** | Analyzes system logs, journald, dmesg, and application logs. Identifies errors, OOM events, kernel panics, and segfaults. | [`skills/logs-analysis/SKILL.md`](skills/logs-analysis/SKILL.md) |
| **Resource Analysis** | Analyzes memory, CPU, disk usage, and processes. Identifies resource exhaustion and performance bottlenecks. | [`skills/resource-analysis/SKILL.md`](skills/resource-analysis/SKILL.md) |
| **Network Analysis** | Analyzes network interfaces, routing, connections, firewall rules, and DNS configuration. | [`skills/network-analysis/SKILL.md`](skills/network-analysis/SKILL.md) |
| **System Config Analysis** | Analyzes OS info, packages, systemd services, SELinux/AppArmor, and kernel parameters. | [`skills/system-config-analysis/SKILL.md`](skills/system-config-analysis/SKILL.md) |

Each skill document includes:
- Step-by-step implementation instructions
- Bash command examples with actual sosreport file paths
- Error handling guidance
- Output format templates
- Common patterns and severity classifications
- Tips for effective analysis

## Installation

### From Marketplace

```bash
# Add the ai-helpers marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the sosreport plugin
/plugin install sosreport@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/openshift-eng/ai-helpers.git

# Add the ai-helpers marketplace from cloned directory
/plugin marketplace add $(pwd)/ai-helpers

# Install the sosreport plugin
/plugin install sosreport@ai-helpers
```

## Typical Workflows

### Full Comprehensive Analysis

1. **Obtain sosreport**: Get a sosreport archive from a system (usually generated with `sosreport` or `sos report` command)

2. **Run comprehensive analysis**:
   ```bash
   /sosreport:analyze /path/to/sosreport.tar.xz
   ```

3. **Review findings**: Examine the interactive summary for critical issues and recommendations across all areas

4. **Deep dive**: Ask follow-up questions about specific findings:
   ```
   Can you show me more details about the OOM killer events?
   What caused the httpd service to fail?
   ```

5. **Take action**: Use the recommendations to troubleshoot and resolve issues

### Targeted Investigation Workflow

1. **Quick log scan** (fastest):
   ```bash
   /sosreport:analyze /path/to/sosreport.tar.xz --only logs
   ```
   Quickly identify error patterns and critical events

2. **Follow-up based on findings**:
   - If memory issues found: Run `--only resources`
   - If network errors found: Run `--only network`
   - If service failures found: Run `--only system-config`

3. **Example iterative investigation**:
   ```bash
   # Start with logs to identify the problem area
   /sosreport:analyze /tmp/sos.tar.xz --only logs

   # Found network timeouts, analyze network configuration
   /sosreport:analyze /tmp/sos.tar.xz --only network

   # Network looks fine, check if it's a resource issue
   /sosreport:analyze /tmp/sos.tar.xz --only resources
   ```

### Performance-Focused Workflow

When you know what you're looking for:

```bash
# Only interested in service configuration
/sosreport:analyze /path/to/sos.tar.xz --only system-config

# Need logs and network, skip the rest
/sosreport:analyze /path/to/sos.tar.xz --only logs,network

# Full analysis but skip time-consuming resource analysis
/sosreport:analyze /path/to/sos.tar.xz --skip resources
```

## Use Cases

- **Incident response**: Quickly identify root causes of system failures
  - Start with `--only logs` for fastest initial assessment
  - Follow up with targeted analysis based on log findings

- **Performance troubleshooting**: Find resource bottlenecks and optimization opportunities
  - Use `--only resources` to focus on memory, CPU, and disk metrics
  - Combine with `--only logs` to correlate resource issues with errors

- **Configuration review**: Verify system configuration and identify misconfigurations
  - Use `--only system-config` to audit packages, services, and security settings
  - Add `--only network` to validate network configuration

- **Network troubleshooting**: Diagnose connectivity and firewall issues
  - Use `--only network,logs` to see network config and related errors
  - Skip resource-intensive analysis for faster results

- **Proactive monitoring**: Regular analysis of production system sosreports
  - Run comprehensive analysis for periodic health checks
  - Use selective analysis for quick daily checks

- **Knowledge transfer**: Let AI explain complex system issues to team members
  - Use selective analysis to focus on specific areas for learning
  - Each skill provides detailed documentation for understanding

## Prerequisites

- **tar**: For extracting compressed archives (usually pre-installed)
- **Disk space**: At least 2x the size of the compressed sosreport

## Tips

- **Selective analysis**: Use `--only` or `--skip` to run specific analysis areas for faster results
  - `--only logs` is the fastest option for initial investigation
  - Combine multiple areas: `--only logs,network`
  - Valid areas: `logs`, `resources`, `network`, `system-config`

- **Archive handling**: The command works with both compressed archives (`.tar.gz`, `.tar.xz`) and extracted directories

- **Performance**: For large sosreports (>1GB)
  - Comprehensive analysis may take several minutes
  - Use selective analysis to reduce analysis time
  - Start with `--only logs` then add more areas as needed

- **Interactive investigation**: You can ask follow-up questions to drill deeper into specific findings
  - "Show me more details about the OOM killer events"
  - "What caused the httpd service to fail?"
  - "Analyze the network timeouts in more detail"

- **Workspace**: The extracted sosreport is preserved in `.work/sosreport-analyze/` for manual investigation

- **Skills documentation**: Each analysis area has detailed implementation guidance
  - See `skills/logs-analysis/SKILL.md` for log analysis details
  - See `skills/resource-analysis/SKILL.md` for resource analysis details
  - See `skills/network-analysis/SKILL.md` for network analysis details
  - See `skills/system-config-analysis/SKILL.md` for system config details

## Contributing

See the main [CLAUDE.md](../../CLAUDE.md) guide for information on contributing to this plugin.

## Resources

- [sosreport GitHub](https://github.com/sosreport/sos)
- [Red Hat sosreport guide](https://access.redhat.com/solutions/3592)
- [AI Helpers Repository](https://github.com/openshift-eng/ai-helpers)
