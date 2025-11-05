# OLM Plugin

A comprehensive plugin for managing and debugging Operator Lifecycle Manager (OLM) in OpenShift clusters.

## Overview

This plugin provides comprehensive OLM capabilities:

- **Operator Discovery**: Search and discover operators across all catalog sources
- **Lifecycle Management**: Install, upgrade, and uninstall operators with intelligent defaults
- **Health Monitoring**: List and check detailed operator health status
- **Update Management**: Check for and install operator updates with approval workflows
- **Troubleshooting**: Diagnose and fix common OLM issues automatically
- **Catalog Management**: Add, remove, and manage custom catalog sources
- **Advanced Debugging**: Troubleshoot OLM issues by correlating must-gather logs with source code and known bugs in Jira
- **Safety Features**: Orphaned resource cleanup, stuck namespace detection, and confirmation prompts
- **Context-Aware**: Automatic channel discovery, namespace auto-detection, and smart recommendations

The plugin supports both OLMv0 (traditional OLM) and OLMv1 (next-generation) architectures.

## Prerequisites

- Claude Code installed
- OpenShift CLI (`oc`) installed and configured
- Access to an OpenShift cluster with cluster-admin or sufficient RBAC permissions
- `git` (required for debug command)
- Network access to GitHub and Jira (for debug command)

## Commands

### Operator Management Commands

#### `/olm:search` - Search for Operators

Search for available operators in OperatorHub catalogs.

**Usage:**
```bash
/olm:search cert-manager                              # Search by keyword
/olm:search                                           # List all operators
/olm:search prometheus --catalog community-operators  # Search specific catalog
/olm:search external-secrets-operator --exact         # Exact name match
```

**What it does:**
- Searches across all catalog sources or specific catalogs
- Shows operator details (versions, channels, descriptions)
- Groups results by catalog source
- Provides install commands for each operator

**Arguments:**
- `query` (optional): Search term for filtering operators
- `--catalog <name>` (optional): Limit search to specific catalog
- `--exact` (optional): Only show exact name matches

See [commands/search.md](commands/search.md) for full documentation.

---

#### `/olm:install` - Install Operators

Install operators from OperatorHub with smart defaults and verification.

**Usage:**
```bash
/olm:install openshift-cert-manager-operator                           # Basic install
/olm:install openshift-cert-manager-operator my-namespace              # Custom namespace
/olm:install openshift-cert-manager-operator ns stable-v1              # Specific channel
/olm:install prometheus ns stable community-operators --approval=Manual # Manual approval mode
```

**What it does:**
- Creates namespace and OperatorGroup automatically
- Auto-discovers default channel if not specified
- Creates Subscription with configurable approval mode
- Monitors installation progress and verifies CSV status
- Reports deployment and pod status

**Arguments:**
- `operator-name` (required): Name of the operator
- `namespace` (optional): Target namespace (defaults to operator name)
- `channel` (optional): Subscription channel (auto-discovered if not provided)
- `source` (optional): CatalogSource name (defaults to "redhat-operators")
- `--approval=Automatic|Manual` (optional): InstallPlan approval mode (default: Automatic)

See [commands/install.md](commands/install.md) for full documentation.

---

#### `/olm:list` - List Installed Operators

View all operators installed in the cluster with health status.

**Usage:**
```bash
/olm:list                           # List all operators
/olm:list cert-manager-operator     # List in specific namespace
/olm:list --all-namespaces          # Explicit cluster-wide view
```

**What it does:**
- Shows operator status, versions, and channels
- Identifies operators requiring attention (failed, upgrading, etc.)
- Provides summary statistics by status and catalog
- Suggests troubleshooting commands for problematic operators

**Arguments:**
- `namespace` (optional): Target namespace
- `--all-namespaces` or `-A` (optional): List cluster-wide

See [commands/list.md](commands/list.md) for full documentation.

---

#### `/olm:status` - Check Operator Status

Get comprehensive health and status information for a specific operator.

**Usage:**
```bash
/olm:status openshift-cert-manager-operator           # Auto-discover namespace
/olm:status external-secrets-operator my-namespace    # Specific namespace
```

**What it does:**
- Shows CSV, Subscription, and InstallPlan status
- Displays available updates and upgrade information
- Lists deployments and pods with health information
- Shows recent events and warnings
- Checks for pending manual approvals
- Provides context-aware troubleshooting recommendations

**Arguments:**
- `operator-name` (required): Name of the operator
- `namespace` (optional): Namespace (auto-discovered if not provided)

See [commands/status.md](commands/status.md) for full documentation.

---

#### `/olm:upgrade` - Update Operators

Update operators to the latest version or switch channels.

**Usage:**
```bash
/olm:upgrade openshift-cert-manager-operator                      # Upgrade to latest
/olm:upgrade cert-manager ns --channel=tech-preview               # Switch channel
/olm:upgrade prometheus ns --approve                               # Approve pending upgrade
```

**What it does:**
- Checks for available updates in current or different channels
- Switches operator to different channel if requested
- Approves pending InstallPlans for manual approval mode
- Monitors upgrade progress with detailed feedback
- Verifies upgrade success and reports any issues

**Arguments:**
- `operator-name` (required): Name of the operator to upgrade
- `namespace` (optional): Namespace (auto-discovered if not provided)
- `--channel=<channel>` (optional): Switch to specified channel
- `--approve` (optional): Auto-approve pending InstallPlan

See [commands/upgrade.md](commands/upgrade.md) for full documentation.

---

#### `/olm:approve` - Approve InstallPlans

Approve pending InstallPlans for operators with manual approval mode.

**Usage:**
```bash
/olm:approve openshift-cert-manager-operator                      # Approve pending plan
/olm:approve external-secrets-operator eso-operator               # Specific namespace
/olm:approve cert-manager ns --all                                # Approve all pending
```

**What it does:**
- Finds pending InstallPlans requiring manual approval
- Shows what will be installed/upgraded before approval
- Approves InstallPlans after user confirmation
- Monitors installation/upgrade execution
- Reports completion status

**Arguments:**
- `operator-name` (required): Name of the operator
- `namespace` (optional): Namespace (auto-discovered if not provided)
- `--all` (optional): Approve all pending InstallPlans

See [commands/approve.md](commands/approve.md) for full documentation.

---

#### `/olm:uninstall` - Uninstall Operators

Safely uninstall operators with optional resource cleanup.

**Usage:**
```bash
/olm:uninstall openshift-cert-manager-operator                    # Basic uninstall
/olm:uninstall operator-name my-namespace                          # Custom namespace
/olm:uninstall operator-name ns --remove-crds                      # Include CRDs
/olm:uninstall operator-name ns --remove-crds --remove-namespace   # Full cleanup
```

**What it does:**
- Removes Subscription and CSV
- Checks for and handles orphaned custom resources
- Removes operator deployments
- Optionally removes CRDs (with cluster-wide impact warning)
- Optionally removes namespace
- Detects and handles stuck Terminating namespaces
- Provides detailed uninstallation summary
- Post-uninstall verification

**Arguments:**
- `operator-name` (required): Name of the operator
- `namespace` (optional): Target namespace (defaults to operator name)
- `--remove-crds` (optional): Remove CRDs - **CAUTION: affects entire cluster**
- `--remove-namespace` (optional): Remove namespace
- `--force` (optional): Skip confirmation prompts

See [commands/uninstall.md](commands/uninstall.md) for full documentation.

---

#### `/olm:diagnose` - Diagnose and Fix Issues

Diagnose common OLM and operator issues with optional auto-fix.

**Usage:**
```bash
/olm:diagnose                                           # Cluster-wide health check
/olm:diagnose openshift-cert-manager-operator           # Check specific operator
/olm:diagnose "" stuck-namespace --fix                  # Fix stuck namespace
/olm:diagnose --cluster --fix                           # Full scan and fix
```

**What it does:**
- Scans for orphaned CRDs from deleted operators
- Detects namespaces stuck in Terminating state
- Identifies failed operator installations
- Checks for conflicting OperatorGroups
- Verifies catalog source health
- Detects Subscription/CSV mismatches
- Lists pending manual approvals
- Generates comprehensive troubleshooting report
- Optionally attempts to fix detected issues

**Arguments:**
- `operator-name` (optional): Specific operator to diagnose
- `namespace` (optional): Specific namespace to check
- `--fix` (optional): Attempt automatic fixes with confirmation
- `--cluster` (optional): Run cluster-wide diagnostics

See [commands/diagnose.md](commands/diagnose.md) for full documentation.

---

#### `/olm:catalog` - Manage Catalog Sources

Manage catalog sources for operator discovery and installation.

**Usage:**
```bash
/olm:catalog list                                     # List all catalogs
/olm:catalog add my-catalog registry.io/catalog:v1    # Add custom catalog
/olm:catalog remove my-catalog                        # Remove catalog
/olm:catalog refresh redhat-operators                 # Refresh catalog
/olm:catalog status custom-catalog                    # Check catalog health
```

**What it does:**
- Lists all catalog sources with health status
- Adds custom or private catalog sources
- Removes catalog sources (with operator usage warnings)
- Refreshes catalogs to get latest operator updates
- Checks catalog source health and connectivity
- Shows catalog pod status and troubleshooting info

**Subcommands:**
- `list`: Show all catalog sources
- `add <name> <image>`: Add new catalog source
- `remove <name>`: Remove catalog source
- `refresh <name>`: Force catalog refresh
- `status <name>`: Check catalog health

See [commands/catalog.md](commands/catalog.md) for full documentation.

---

### Debugging Commands

#### `/olm:debug` - Debug OLM Issues

Debug OLM issues using must-gather logs and source code analysis.

**Usage:**
```
/olm:debug <issue-description> <must-gather-path> [olm-version]
```

**Arguments:**
- `issue-description`: Brief description of the OLM issue being investigated
- `must-gather-path`: Path to the must-gather log directory
- `olm-version`: (Optional) Either `olmv0` (default) or `olmv1`

**Examples:**

1. Debug a CSV stuck in pending state (OLMv0):
   ```
   /olm:debug "CSV stuck in pending state" /path/to/must-gather
   ```

2. Debug OLMv1 ClusterExtension issue:
   ```
   /olm:debug "ClusterExtension installation failing" /path/to/must-gather olmv1
   ```

3. Debug operator upgrade issue:
   ```
   /olm:debug "Operator upgrade from v1.0 to v2.0 fails with dependency resolution error" ~/Downloads/must-gather.local.123456 olmv0
   ```

**How it works:**

1. **Extracts OCP version** from the must-gather logs
2. **Clones appropriate repositories**:
   - OLMv0: `operator-framework-olm`
   - OLMv1: `operator-framework-operator-controller` and `cluster-olm-operator`
3. **Checks out the correct branch** matching the OCP version (e.g., `release-4.14`)
4. **Analyzes logs** to identify errors, warnings, and failed reconciliations
5. **Queries Jira** for known bugs in OCPBUGS project (OLM component) matching the OCP version
6. **Matches errors** with known bugs based on error messages and symptoms
7. **Correlates errors with source code** to identify root causes
8. **Generates a comprehensive analysis report** with recommendations and links to related Jira issues

**Output:**

The command creates a working directory at `.work/olm-debug/<timestamp>/` containing:

- `analysis.md`: Comprehensive analysis report with known bugs section
- `relevant-logs.txt`: Extracted relevant log entries
- `code-references.md`: Links to relevant source code
- `known-bugs.md`: List of potentially related Jira bugs with match confidence and workarounds
- `repos/`: Cloned repository directories

See [commands/debug.md](commands/debug.md) for full documentation.

---

## Example Workflows

### Quick Start - Install and Monitor

```bash
# Search for operator
/olm:search cert-manager

# Install operator
/olm:install openshift-cert-manager-operator

# Check status
/olm:status openshift-cert-manager-operator

# List all operators
/olm:list
```

### Production Workflow - Manual Approval

```bash
# Install with manual approval for better control
/olm:install external-secrets-operator eso-operator stable-v0.10 redhat-operators --approval=Manual

# Check for updates
/olm:status external-secrets-operator eso-operator

# Upgrade when ready
/olm:upgrade external-secrets-operator eso-operator

# Approve the upgrade
/olm:approve external-secrets-operator eso-operator
```

### Troubleshooting Workflow

```bash
# Operator not working properly
/olm:status problematic-operator

# Run diagnostics
/olm:diagnose problematic-operator

# If issues found, attempt fixes
/olm:diagnose problematic-operator namespace --fix
```

### Clean Uninstall Workflow

```bash
# Check operator status before uninstalling
/olm:status openshift-cert-manager-operator

# Uninstall with full cleanup
/olm:uninstall openshift-cert-manager-operator cert-manager-operator --remove-crds --remove-namespace

# Verify cleanup
/olm:diagnose --cluster
```

### Catalog Management Workflow

```bash
# List available catalogs
/olm:catalog list

# Add custom catalog
/olm:catalog add my-operators registry.internal.com/operators:v1.0

# Search for operators in new catalog
/olm:search --catalog my-operators

# Check catalog health
/olm:catalog status my-operators
```

### Advanced Debugging Workflow

```bash
# Debug OLM issues using must-gather logs
/olm:debug "CSV stuck in pending" /path/to/must-gather
```

## OLM Version Support

### OLMv0
- Used in OpenShift 4.x (traditional OLM)
- Repository: [operator-framework-olm](https://github.com/openshift/operator-framework-olm)
- Key resources: CSV, Subscription, InstallPlan, OperatorGroup

### OLMv1
- Next-generation OLM architecture
- Repositories:
  - [operator-framework-operator-controller](https://github.com/openshift/operator-framework-operator-controller)
  - [cluster-olm-operator](https://github.com/openshift/cluster-olm-operator)
- Key resources: ClusterExtension, Catalog

## Troubleshooting

### Operator Not Found
```bash
/olm:search <operator-name>                           # Search for operator
oc get packagemanifests -n openshift-marketplace      # List manually
/olm:catalog list                                     # Check catalog sources
```

### Installation Issues
```bash
/olm:status <operator-name>                           # Check detailed status
/olm:diagnose <operator-name>                         # Run diagnostics
oc get csv -n <namespace>                             # Check CSV manually
oc describe csv <csv-name> -n <namespace>             # Detailed CSV info
```

### Upgrade Issues
```bash
/olm:status <operator-name>                           # Check for pending upgrades
/olm:approve <operator-name>                          # Approve if manual mode
/olm:diagnose <operator-name> --fix                   # Fix issues
```

### Uninstallation Issues
```bash
# CSV won't delete
oc get csv <csv-name> -n <namespace> -o yaml | grep finalizers

# Namespace stuck in Terminating
/olm:diagnose "" <namespace> --fix

# Orphaned resources
/olm:diagnose --cluster
```

### Catalog Source Issues
```bash
/olm:catalog status <catalog-name>                    # Check catalog health
/olm:catalog refresh <catalog-name>                   # Refresh catalog
oc logs -n openshift-marketplace <catalog-pod>        # Check logs
```

### Debugging Issues

**Cannot determine OCP version from must-gather:**
- **Solution**: Manually specify the OCP version when prompted, or check that the must-gather is complete

**Repository clone fails:**
- **Solution**: Check network connectivity and GitHub access. You can manually clone the repositories and point the command to them.

**Branch not found for OCP version:**
- **Solution**: The command will fall back to the `main` branch. Be aware that there may be version differences.

**Jira access fails or returns no results:**
- **Solution**: Check network connectivity to https://issues.redhat.com/. The command will continue with analysis even if Jira is unavailable.

**Too many potential bug matches returned:**
- **Solution**: Review the `known-bugs.md` file and focus on high-confidence matches. Verify each match by reading the full bug description in Jira.

## Resources

- [Red Hat OpenShift: Operators Documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/)
- [Red Hat OpenShift: Administrator Tasks](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks)
- [Red Hat OpenShift: Troubleshooting Operators](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-troubleshooting-operator-issues)
- [Operator Lifecycle Manager Documentation](https://olm.operatorframework.io/)
- [OperatorHub.io](https://operatorhub.io/) - Browse operators online
- [Must-gather Documentation](https://docs.openshift.com/container-platform/latest/support/gathering-cluster-data.html)
- [OCPBUGS Jira Project](https://issues.redhat.com/projects/OCPBUGS/)

## Contributing

To add new commands to this plugin:

1. Create a new `.md` file in `plugins/olm/commands/`
2. Follow the command definition format in existing commands
3. Update this README with the new command documentation
4. Run `make lint` to validate the plugin structure

## Support

For issues or feature requests, please file an issue at:
https://github.com/openshift-eng/ai-helpers/issues
