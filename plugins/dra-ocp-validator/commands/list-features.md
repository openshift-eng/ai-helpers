---
description: List all DRA features with metadata, graduation status, and requirements
argument-hint: "<kubeconfig-path> [--detailed]"
---

## Name
dra-ocp-validator:list-features

## Synopsis
```
/dra-ocp-validator:list-features <kubeconfig-path> [--detailed]
```

## Description

The `list-features` command displays comprehensive information about all Dynamic Resource Allocation (DRA) features supported by the plugin, including:

- Feature graduation levels (Alpha/Beta/GA) for the current cluster
- Kubernetes version requirements
- Feature gate requirements and status
- Setup prerequisites and enablement commands
- Test coverage information

This command helps answer:
- What DRA features are available on my cluster?
- Which features require feature gates to be enabled?
- What is the graduation status of each feature?
- Which features are testable on my K8s version?

## Arguments

- `<kubeconfig-path>` (required): Path to kubeconfig file for the target cluster
  - Supports tilde expansion (e.g., `~/.kube/config`)
  - Can be relative or absolute path

- `[--detailed]` (optional): Display detailed information for each feature including:
  - Full descriptions
  - Feature gate names and enablement commands
  - Setup flags required
  - Associated test scripts

## Implementation

This command executes a bash script from the plugin's `tools/` directory to analyze and display DRA feature information for the target cluster.

### Steps

1. **Parse Arguments**:
   - Extract kubeconfig path from `$1` (required)
   - Check for `--detailed` flag in `$2` (optional)
   - Expand tilde (`~`) to `$HOME` if present in the path

2. **Validate Kubeconfig**:
   - Verify kubeconfig path is provided (error if missing)
   - Verify kubeconfig file exists at the path (error if not found)

3. **Execute Feature List Script**:
   
   Use the Bash tool to run the plugin's list-features script:
   
   ```bash
   # Build the command with the plugin root path
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
   SCRIPT="${PLUGIN_ROOT}/tools/list-features.sh"
   
   # Pass through arguments
   ${SCRIPT} "$1" "${2:-}"
   ```
   
   The script will:
   - Connect to the cluster using the provided kubeconfig
   - Detect cluster version (K8s 1.32-1.36)
   - Check if DRA driver is installed
   - List all features with their graduation status for this K8s version
   - Show feature gate status (enabled/disabled/not applicable)
   - Display detailed information if `--detailed` flag provided

4. **Present Output**:
   
   The script outputs formatted tables showing:
   - Cluster information (OCP version, K8s version, DRA driver status)
   - Feature table (name, graduation level, min K8s version, gate status, description)
   - Summary (count of Alpha/Beta/GA features available)
   - Next step commands
   
   Present this output directly to the user. If the script fails, show the error message.

## Return Value

- **Success**: Formatted tables showing all DRA features with their status
- **Error**: 
  - Missing or invalid kubeconfig path
  - Cluster connectivity issues (falls back to offline mode)
  - Missing required tools (`oc`, `jq`)

## Examples

### Basic List (Summary View)

```
/dra-ocp-validator:list-features ~/.kube/cluster-bot-config
```

**Output:**
```
==========================================
DRA Features - Cluster Analysis
==========================================

Cluster: OCP 4.21.18, Kubernetes v1.34.8

DRA Driver: ✓ Installed (gpu.example.com)

==========================================
Available DRA Features
==========================================

FEATURE              GRADUATION   MIN K8S    GATE STATUS     DESCRIPTION
-------              ----------   -------    -----------     -----------
partitionable        Alpha        1.34       ✗ Not enabled   Support for GPU partition...
admin-access         Beta         1.34       N/A             Namespace-based admin ac...
prioritized-list     Beta         1.34       N/A             Scheduler preference ord...
```

### Detailed View

```
/dra-ocp-validator:list-features ~/.kube/cluster-bot-config --detailed
```

**Output:**
```
==========================================
Detailed Feature Information
==========================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Feature: partitionable
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name:        Partitionable Devices
Description: Support for GPU partitioning via SharedCounters (e.g., NVIDIA MIG)
Min K8s:     1.34
Graduation:  alpha (on K8s 1.34)
Feature Gate: DRAPartitionableDevices
Gate Status:  ✗ Not enabled (Alpha - requires enablement)

To enable:
  oc patch featuregate cluster --type=merge \
    -p '{"spec":{"customNoUpgrade":{"enabled":["DRAPartitionableDevices"]}}}'

Setup Flags:  --enable-dynamic-mig
Test Script:  test-dra-partitionable.sh
```

## Prerequisites

**Required Tools:**
- `oc` CLI (OpenShift client)
- `jq` (JSON processor)
- `kubectl` (Kubernetes CLI)

**Cluster Requirements:**
- Kubeconfig with valid cluster credentials
- Network connectivity to cluster (optional - falls back to offline mode if unavailable)

## Notes

- **Offline Mode**: If cluster is unreachable, the command displays feature metadata for K8s 1.36 without cluster-specific information
- **Graduation Levels**: Automatically determined based on the cluster's Kubernetes version
- **Feature Gates**: Command checks actual cluster configuration to determine if gates are enabled
- **Beta Features**: Some beta features don't require explicit feature gate enablement
- **Alpha Features**: Always require feature gate enablement via `customNoUpgrade`

## See Also

- `/dra-ocp-validator:setup` - Install DRA driver with required features
- `/dra-ocp-validator:test` - Run DRA feature tests
- `/dra-ocp-validator:validate` - Full validation workflow
