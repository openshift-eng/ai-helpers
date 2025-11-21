---
description: Generate and visualize OVN-Kubernetes network topology diagram
argument-hint:
---

## Name

openshift:visualize-ovn-topology

## Synopsis

```
/openshift:visualize-ovn-topology
```

## Description

The `openshift:visualize-ovn-topology` command generates a comprehensive Mermaid diagram of the OVN-Kubernetes network topology for a running cluster. The diagram shows:

- Logical switches and routers
- Switch and router ports with MAC/IP addresses
- Pod connectivity
- External network connections
- Per-node component placement (interconnect mode) or centralized components (default mode)

The command automatically detects the cluster architecture (interconnect vs default mode) and creates an accurate topology diagram based on real data from the OVN databases.

## Implementation

This command invokes the `generating-ovn-topology` skill which implements a data-driven architecture discovery approach:

1. **Cluster Detection**: Automatically finds and connects to an OVN-Kubernetes cluster
2. **Permission Check**: Verifies Kubernetes access level and warns if write permissions detected
   - If you have cluster admin permissions, you'll be asked to confirm before proceeding
   - The command only performs read-only operations regardless of your permission level
   - This check ensures informed consent when using admin credentials
3. **Architecture Discovery**: Analyzes UUID patterns across node databases to determine component placement (per-node vs cluster-wide)
4. **Data Collection**: Queries OVN northbound databases for topology information
5. **Diagram Generation**: Creates a Mermaid graph with proper component placement
6. **Output**: Saves diagram to `ovn-topology-diagram.md` (or timestamped/custom path if file exists)

**Key Features:**
- **Data-driven**: Never generates synthetic data - always queries real cluster
- **Architecture-aware**: Correctly handles both interconnect and default deployment modes
- **Complete topology**: Shows all logical switches, routers, and ports
- **Visual clarity**: Uses color-coded components and node subgraphs for organization

**Skill Reference:**
- Implementation details: `plugins/openshift/skills/generating-ovn-topology/SKILL.md`
- Helper scripts: `plugins/openshift/skills/generating-ovn-topology/scripts/`

## Return Value

- **Format**: Mermaid diagram saved to file
- **Location**: `./ovn-topology-diagram.md` (current directory) or custom path if specified
- **Output**: Summary statistics and preview of the generated diagram

## Examples

1. **Basic usage** (generates topology for detected cluster):
   ```shell
   /openshift:visualize-ovn-topology
   ```

   Output:
   ```text
   ✓ Successfully generated OVN-Kubernetes topology diagram

   📄 Diagram saved to: ovn-topology-diagram.md

   Summary:
   - 3 nodes (ovn-control-plane, ovn-worker, ovn-worker2)
   - 10 logical switches, 4 logical routers
   - 27 logical switch ports, 13 logical router ports
   - 9 running pods
   - Mode: Interconnect (distributed control plane)

   💡 Open the file in your IDE to view the full rendered Mermaid diagram!
   ```

2. **With existing file** (prompts for action):
   ```shell
   /openshift:visualize-ovn-topology
   ```

   You'll be asked:
   ```text
   File ovn-topology-diagram.md already exists. Would you like to:
   (1) Overwrite it
   (2) Save to a different location
   (3) Append timestamp to filename
   (4) Cancel
   ```

## Prerequisites

- **kubectl**: Must be installed and configured with access to an OVN-Kubernetes cluster
- **Cluster**: A running Kubernetes cluster with OVN-Kubernetes CNI deployed
- **Access**: Permission to exec into pods in the OVN namespace (e.g., `ovn-kubernetes` or `openshift-ovn-kubernetes`)

## Security & Safety

**This command performs ONLY read-only operations:**
- ✅ `kubectl get` - Query pods and nodes
- ✅ `kubectl exec` - Run read-only `ovn-nbctl list` commands
- ✅ Local file writes - Save topology diagram

**Operations NEVER performed:**
- ❌ No `kubectl create/delete/patch/apply`
- ❌ No `ovn-nbctl` modifications
- ❌ No cluster state changes

**Permission Check:**
If you have cluster admin permissions, you'll receive a warning message before the command proceeds. This is for transparency - you'll be informed about your access level and asked to confirm. The command will still only perform read-only operations.

## Notes

- The command is cluster-agnostic and works with any OVN-Kubernetes deployment
- For KIND clusters created via `/openshift:create-cluster`, the kubeconfig is automatically detected
- The diagram uses bottom-to-top layout (graph BT) following network topology conventions
- All component placement is determined by UUID analysis, not hardcoded assumptions
