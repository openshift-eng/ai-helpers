# OLM v1 Plugin

Manage Kubernetes cluster extensions using Operator Lifecycle Manager v1 (operator-controller).

## Overview

OLM v1 provides a simpler, more flexible approach to managing Kubernetes extensions including Operators, Helm charts, and other cluster extensions. This plugin helps you discover, install, upgrade, and manage extensions in your cluster.

## Prerequisites

- `kubectl` or `oc` CLI configured with cluster access
- OLM v1 (operator-controller) installed in the cluster
- Appropriate RBAC permissions for managing ClusterExtensions and ClusterCatalogs

## Key Concepts

- **ClusterCatalog**: A catalog of available extensions
- **ClusterExtension**: An installed extension in the cluster
- **Channels**: Release channels for extensions (stable, candidate, etc.)
- **Version Constraints**: Semver-based version management
- **ServiceAccount & RBAC**: Each extension requires a ServiceAccount with sufficient permissions to install and operate

## Important: RBAC Requirements in OLM v1

**CRITICAL DIFFERENCE FROM OLM v0**: In OLM v1, YOU (the cluster admin) must provide a ServiceAccount with all necessary RBAC permissions for each extension. OLM v1 does NOT have cluster-admin privileges like OLM v0.

### ServiceAccount Requirements

Every ClusterExtension installation requires:
1. A ServiceAccount in the target namespace
2. RBAC permissions (ClusterRole/Role) granting the ServiceAccount rights to:
   - Create and manage the extension's resources (Deployments, Services, ConfigMaps, etc.)
   - Create Custom Resource Definitions (CRDs)
   - Create RBAC resources (if the extension creates its own Roles/RoleBindings)
   - Any additional permissions the extension needs to operate

### PreflightPermissions Feature Gate

When the `PreflightPermissions` feature gate is enabled in operator-controller:
- OLM performs a **preflight check** before installation
- Missing RBAC permissions are identified and reported in the ClusterExtension status conditions
- Installation fails fast with clear error messages listing exactly which permissions are missing
- This helps you iteratively fix RBAC issues without trial and error

The `/olmv1:install` command automatically creates baseline RBAC permissions and can iteratively fix missing permissions when preflight checks fail.

### Webhook Feature Gates

Many operators include admission webhooks (mutating or validating webhook configurations). OLM v1 requires a feature gate to be enabled for webhook support:

**WebhookProviderCertManager** (recommended):
- Enables webhook support using cert-manager to provision certificates
- Requires cert-manager to be installed in the cluster
- Enable with:
  ```bash
  kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \
    -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-",
    "value": "--feature-gates=WebhookProviderCertManager=true"}]'
  ```

**WebhookProviderOpenshiftServiceCA**:
- Enables webhook support using OpenShift's service CA for certificate provisioning
- Only available on OpenShift clusters
- Enable similarly with `--feature-gates=WebhookProviderOpenshiftServiceCA=true`

**What happens without webhook support:**
- Operators with webhooks will fail to install with error: "unsupported bundle: webhookDefinitions are not supported"
- The `/olmv1:install` and `/olmv1:status` commands will detect this and suggest enabling the appropriate feature gate
- If cert-manager is installed, the commands may automatically enable WebhookProviderCertManager

**Additional RBAC for webhooks:**
When webhooks are enabled via cert-manager, your ServiceAccount also needs permissions for cert-manager resources:
```yaml
- apiGroups: ["cert-manager.io"]
  resources: ["certificates", "issuers", "certificaterequests"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

## Commands

### Catalog Management

#### `/olmv1:catalog-add <catalog-name> <image-ref> [--poll-interval <duration>]`
Add a new catalog source to the cluster.

**Example:**
```bash
/olmv1:catalog-add operatorhubio quay.io/operatorhubio/catalog:latest
/olmv1:catalog-add my-catalog registry.example.com/catalog:v1 --poll-interval 1h
```

#### `/olmv1:catalog-list`
List all available catalogs and their status.

**Example:**
```bash
/olmv1:catalog-list
```

### Extension Discovery

#### `/olmv1:search <keyword> [--catalog <catalog-name>]`
Search for available extensions across catalogs.

**Example:**
```bash
/olmv1:search cert-manager
/olmv1:search prometheus --catalog operatorhubio
```

### Extension Installation

#### `/olmv1:install <extension-name> [--version <version>] [--channel <channel>] [--catalog <catalog-name>] [--namespace <namespace>]`
Install an extension with optional version or channel constraints.

**Parameters:**
- `extension-name`: Name of the extension to install (required)
- `--version`: Specific version or version range (e.g., "1.14.5", ">=1.14.0 <1.15.0")
- `--channel`: Channel to track (e.g., "stable", "candidate")
- `--catalog`: Catalog source to use
- `--namespace`: Target namespace for namespaced extensions

**Examples:**
```bash
# Install latest from stable channel
/olmv1:install cert-manager --channel stable

# Install specific version
/olmv1:install argocd-operator --version 0.11.0

# Install with version range
/olmv1:install prometheus-operator --version ">=0.68.0 <0.69.0"

# Install from specific catalog
/olmv1:install my-extension --catalog my-catalog
```

### Extension Management

#### `/olmv1:list [--all-namespaces]`
List all installed extensions with their status.

**Example:**
```bash
/olmv1:list
/olmv1:list --all-namespaces
```

#### `/olmv1:status <extension-name>`
Get detailed status and health information for an installed extension.

**Shows:**
- Installation status and conditions
- Resolved version and channel
- ServiceAccount and RBAC configuration
- Associated resources (CRDs, deployments, services)
- Recent events and issues
- **RBAC/preflight permission errors** (if present)

**Example:**
```bash
/olmv1:status cert-manager
```

#### `/olmv1:fix-rbac <extension-name>`
Analyze and fix RBAC permission issues for a ClusterExtension that failed preflight checks.

**What it does:**
- Detects pre-authorization failures in the ClusterExtension status
- Parses the missing RBAC permissions from error messages
- Identifies the current ServiceAccount and ClusterRole
- Offers to automatically update the ClusterRole with missing permissions
- Or displays the required RBAC YAML for manual application

**When to use:**
- Extension installation is stuck in "Progressing" state
- Status shows "pre-authorization failed" errors
- You see RBAC-related error messages

**Example:**
```bash
/olmv1:fix-rbac postgres-operator
```

**Note:** Requires the `PreflightPermissions` feature gate to be enabled in operator-controller for detailed permission analysis.

### Extension Upgrades

#### `/olmv1:upgrade <extension-name> [--version <version>] [--channel <channel>]`
Upgrade an extension using different strategies.

**Strategies:**
- Channel-based: Track a specific channel for automatic updates
- Version pinning: Upgrade to a specific version
- Version range: Allow upgrades within a version range
- Z-stream: Stay within the same minor version

**Examples:**
```bash
# Upgrade to latest in stable channel
/olmv1:upgrade cert-manager --channel stable

# Upgrade to specific version
/olmv1:upgrade argocd-operator --version 0.12.0

# Upgrade within version range (z-stream)
/olmv1:upgrade prometheus-operator --version "~0.68.0"
```

### Extension Removal

#### `/olmv1:uninstall <extension-name>`
Safely uninstall an extension from the cluster.

**Example:**
```bash
/olmv1:uninstall cert-manager
```

## Typical Workflows

### Installing a New Extension
```bash
# 1. Search for the extension
/olmv1:search postgres-operator

# 2. Install with desired version/channel
# This automatically creates:
#   - Namespace
#   - ServiceAccount
#   - ClusterRole with baseline permissions
#   - ClusterRoleBinding
#   - ClusterExtension
/olmv1:install postgres-operator --channel stable --namespace postgres-operator

# 3. If installation fails due to RBAC issues:
/olmv1:status postgres-operator
# Will show missing permissions

# 4. Fix RBAC automatically
/olmv1:fix-rbac postgres-operator

# 5. Verify installation succeeded
/olmv1:status postgres-operator

# 6. List all installed extensions
/olmv1:list
```

### Managing Upgrades
```bash
# Check current status
/olmv1:status my-extension

# Upgrade to latest in channel
/olmv1:upgrade my-extension --channel stable

# Or pin to specific version
/olmv1:upgrade my-extension --version 2.0.0

# Verify upgrade
/olmv1:status my-extension
```

### Troubleshooting
```bash
# Check extension status and conditions (including RBAC issues)
/olmv1:status <extension-name>

# Fix RBAC permission issues
/olmv1:fix-rbac <extension-name>

# Check catalog availability
/olmv1:catalog-list

# View all extensions and their health
/olmv1:list
```

## Differences from OLM v0

- **Simpler API**: Uses ClusterExtension and ClusterCatalog instead of Subscription/CSV/InstallPlan
- **Flexible versioning**: Supports semver ranges and version constraints
- **Broader scope**: Manages any Kubernetes extension, not just Operators
- **No automatic upgrades**: Explicit upgrade commands for better control
- **GitOps friendly**: Declarative extension management
- **⚠️ USER-MANAGED RBAC**: You must provide ServiceAccounts with proper RBAC permissions (OLM v0 had cluster-admin but best practices are to avoid this whenever possible)

## Troubleshooting

Common issues and solutions:

1. **Extension stuck in progressing state with RBAC errors**:
   - Run `/olmv1:status <extension-name>` to see missing permissions
   - Use `/olmv1:fix-rbac <extension-name>` to automatically fix RBAC issues
   - Requires `PreflightPermissions` feature gate enabled for detailed error messages

2. **Pre-authorization failed errors**:
   - These indicate the ServiceAccount lacks required RBAC permissions
   - Error messages show exactly which permissions are missing in format:
     ```
     Namespace:"" APIGroups:[apps] Resources:[deployments] Verbs:[create,update]
     ```
   - Use `/olmv1:fix-rbac` to parse and apply missing permissions automatically

3. **Catalog not available**:
   - Verify catalog image and network connectivity
   - Run `/olmv1:catalog-list` to check catalog status

4. **Version conflicts**:
   - Use `/olmv1:status` to see resolved dependencies
   - Check for conflicting version constraints

5. **ServiceAccount doesn't exist**:
   - The `/olmv1:install` command creates ServiceAccounts automatically
   - Ensure the namespace exists and you have permissions to create ServiceAccounts

6. **PreflightPermissions feature gate not enabled**:
   - Without this gate, RBAC errors won't be caught early
   - Installation will fail with less helpful error messages
   - Consider enabling it in operator-controller for better RBAC feedback

## Resources

- [OLM v1 Documentation](https://operator-framework.github.io/operator-controller/)
- [OLM v1 GitHub Repository](https://github.com/operator-framework/operator-controller)
- [Migration from OLM v0](https://operator-framework.github.io/operator-controller/concepts/olmv0-to-olmv1/)
- [RBAC Permissions Checking Guide](https://github.com/operator-framework/operator-controller/blob/main/docs/draft/howto/rbac-permissions-checking.md)
