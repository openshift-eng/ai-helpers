---
description: Generate and visualize Kubernetes Gateway API topology diagram
argument-hint:
---

## Name

openshift:visualize-gateway-topology

## Synopsis

```
/openshift:visualize-gateway-topology
```

## Description

The `openshift:visualize-gateway-topology` command generates a comprehensive Mermaid diagram of the Kubernetes Gateway API topology for a running cluster. The diagram shows:

- GatewayClasses with their controllers and status
- Gateways with listeners and addresses
- Routes (HTTPRoute, GRPCRoute, TCPRoute, TLSRoute) with hostnames
- Backend Services referenced by routes
- ReferenceGrants for cross-namespace access
- Relationships between all resources

The command automatically detects Gateway API resources and creates an accurate topology diagram based on real data from your cluster.

## Implementation

This command invokes the `generating-gateway-topology` skill which implements a data-driven topology discovery approach:

1. **Cluster Detection**: Automatically finds clusters with Gateway API CRDs installed
2. **Permission Check**: Verifies Kubernetes access level and warns if write permissions detected
   - If you have cluster admin permissions, you'll be asked to confirm before proceeding
   - The command only performs read-only operations regardless of your permission level
   - This check ensures informed consent when using admin credentials
3. **Data Collection**: Queries all Gateway API resources (GatewayClasses, Gateways, Routes, Services)
4. **Topology Analysis**: Builds relationship graph between resources
5. **Diagram Generation**: Creates a Mermaid graph with proper hierarchy and styling
6. **Output**: Saves diagram to `gateway-topology-diagram.md` (or timestamped/custom path if file exists)

**Key Features:**
- **Data-driven**: Never generates synthetic data - always queries real cluster
- **Comprehensive**: Collects all Gateway API resource types
- **gwctl support**: Uses gwctl if available for enhanced data collection
- **Visual clarity**: Uses color-coded components and layered subgraphs for organization

**Skill Reference:**
- Implementation details: `plugins/openshift/skills/generating-gateway-topology/SKILL.md`
- Helper scripts: `plugins/openshift/skills/generating-gateway-topology/scripts/`

## Return Value

- **Format**: Mermaid diagram saved to file
- **Location**: `./gateway-topology-diagram.md` (current directory) or custom path if specified
- **Output**: Summary statistics and preview of the generated diagram

## Examples

1. **Basic usage** (generates topology for detected cluster):
   ```shell
   /openshift:visualize-gateway-topology
   ```

   Output:
   ```text
   ✅ Successfully generated Gateway API topology diagram

   📄 Diagram saved to: gateway-topology-diagram.md

   Summary:
   - 2 GatewayClasses (istio, nginx)
   - 3 Gateways
   - 8 HTTPRoutes, 2 GRPCRoutes
   - 12 Backend Services
   - 1 ReferenceGrant

   💡 Open the file in your IDE to view the full rendered Mermaid diagram!
   ```

2. **With existing file** (prompts for action):
   ```shell
   /openshift:visualize-gateway-topology
   ```

   You'll be asked:
   ```text
   File gateway-topology-diagram.md already exists. Would you like to:
   (1) Overwrite it
   (2) Save to a different location
   (3) Append timestamp to filename
   (4) Cancel
   ```

## Prerequisites

- **kubectl**: Must be installed and configured with access to a Kubernetes cluster
- **Gateway API**: CRDs must be installed in the cluster
- **Optional**: gwctl for enhanced data collection

To install Gateway API CRDs:
```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml
```

## Security & Safety

**This command performs ONLY read-only operations:**
- ✅ `kubectl get` - Query Gateway API resources
- ✅ `gwctl get/describe` - Query resources if available
- ✅ Local file writes - Save topology diagram

**Operations NEVER performed:**
- ❌ No `kubectl create/delete/patch/apply`
- ❌ No `gwctl apply/delete`
- ❌ No cluster state changes

**Permission Check:**
If you have cluster admin permissions, you'll receive a warning message before the command proceeds. This is for transparency - you'll be informed about your access level and asked to confirm. The command will still only perform read-only operations.

## Notes

- The command works with any Gateway API implementation (Istio, Nginx, Envoy, Kong, etc.)
- gwctl is auto-detected and used when available for richer data
- The diagram uses top-to-bottom layout (graph TB) following the Gateway API hierarchy
- Cross-namespace references are shown with ReferenceGrant relationships
