---
name: HyperShift Azure Provider
description: Use this skill when you need to deploy HyperShift clusters on Microsoft Azure with proper identity configuration and resource management
---

# HyperShift Azure Provider

This skill provides implementation guidance for creating HyperShift clusters on Azure, focusing on self-managed control plane configuration, resource group management, and Azure identity integration.

## When to Use This Skill

This skill is automatically invoked by the `/hcp:generate azure` command to guide the Azure provider cluster creation process.

## Prerequisites

- Azure CLI configured with appropriate credentials
- Azure subscription with sufficient quotas
- HyperShift operator installed and configured
- Pull secret for accessing OpenShift images

## Azure Provider Overview

### Azure Provider Peculiarities

- **Self-managed control plane only:** For ARO HCP use ARO CLI instead
- **Resource groups:** Auto-created during cluster creation
- **Limited region availability:** Not all Azure regions support all features
- **Azure identity required:** Service principal or managed identity configuration
- **Virtual network integration:** Requires proper VNet configuration
- **Control plane runs on Azure VMs:** Managed by HyperShift operator

### Identity Configuration Options

Choose one of three identity methods:

1. **Managed + Data Plane Identities:** Use `--managed-identities-file` AND `--data-plane-identities-file`
2. **Workload Identities:** Use `--workload-identities-file`
3. **OIDC Integration:** Use `--oidc-issuer-url`

## Implementation Steps

### Step 1: Parse Environment Requirements

**Environment Detection:**
- **Development:** "dev", "testing", "demo" → Standard_D4s_v3, SingleReplica
- **Production:** "prod", "enterprise" → Standard_D8s_v3+, HighlyAvailable

### Step 2: Interactive Parameter Collection

**Required Parameters:**

1. **Cluster Name & Location**
   ```
   🔹 **Cluster Name**: What would you like to name your cluster?
   🔹 **Azure Location**: Which Azure region? [default: eastus]
   ```

2. **Identity Configuration Method**
   ```
   🔹 **Identity Method**: Choose Azure identity configuration:
      1. Managed + Data Plane Identities (recommended)
      2. Workload Identities
      3. OIDC Integration
   ```

3. **Resource Group Configuration**
   ```
   🔹 **Resource Group**: Name for the resource group?
      [default: {cluster-name}-rg]
   ```

### Step 3: Generate Command

**Development Configuration:**
```bash
hypershift create cluster azure \
  --name dev-cluster \
  --namespace dev-cluster-ns \
  --location eastus \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --resource-group-name dev-cluster-rg \
  --base-domain example.com \
  --managed-identities-file /path/to/managed-identities.json \
  --data-plane-identities-file /path/to/data-plane-identities.json
```

**Production Configuration:**
```bash
hypershift create cluster azure \
  --name production-cluster \
  --namespace production-cluster-ns \
  --location eastus \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --resource-group-name production-cluster-rg \
  --base-domain clusters.company.com \
  --managed-identities-file /path/to/managed-identities.json \
  --data-plane-identities-file /path/to/data-plane-identities.json \
  --control-plane-availability-policy HighlyAvailable
```

## Error Handling

### Identity Configuration Issues
```
Azure identity files not found or invalid.

Required files for managed identity method:
1. managed-identities.json
2. data-plane-identities.json

Generate using Azure CLI:
  az identity create --name hypershift-managed-identity
```

### Resource Group Conflicts
```
Resource group "cluster-rg" already exists.

Options:
1. Use existing resource group (ensure proper permissions)
2. Choose different name
3. Delete existing resource group (if safe)
```

## See Also

- [HyperShift Azure Provider Documentation](https://hypershift.openshift.io/how-to/azure/)
- [Azure Resource Manager Documentation](https://docs.microsoft.com/en-us/azure/azure-resource-manager/)