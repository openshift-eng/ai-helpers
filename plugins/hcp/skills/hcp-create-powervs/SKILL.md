---
name: HyperShift PowerVS Provider
description: Use this skill when you need to deploy HyperShift clusters on IBM Cloud PowerVS with proper processor configuration and resource management
---

# HyperShift PowerVS Provider

This skill provides implementation guidance for creating HyperShift clusters on IBM Cloud PowerVS, handling PowerVS-specific requirements including IBM Cloud API keys, processor types, and resource group management.

## When to Use This Skill

This skill is automatically invoked by the `/hcp:generate powervs` command to guide the PowerVS provider cluster creation process.

## Prerequisites

- IBM Cloud CLI configured with API key
- PowerVS service instance configured
- IBM Cloud resource group access
- HyperShift operator installed and configured

## PowerVS Provider Overview

### PowerVS Provider Peculiarities

- **IBM Cloud specific:** Requires IBM Cloud API key and resource group
- **Different regions have different capabilities:** Service availability varies by region
- **Limited instance types:** Fewer processor types compared to other clouds
- **Network setup complex:** Requires careful network planning
- **Processor type selection:** Shared, dedicated, or capped options

## Implementation Steps

### Step 1: Interactive Parameter Collection

**Required Parameters:**

1. **IBM Cloud Authentication**
   ```
   🔹 **IBM Cloud API Key**: Configure IBM Cloud authentication
      - Set IBMCLOUD_API_KEY environment variable, OR
      - Provide IBMCLOUD_CREDENTIALS file path
   ```

2. **Resource Group**
   ```
   🔹 **Resource Group**: IBM Cloud resource group name?
      - Must exist in your IBM Cloud account
      - Example: default, hypershift-rg
   ```

3. **Region Configuration**
   ```
   🔹 **Region**: IBM Cloud region?
      [default: us-south]
   🔹 **Zone**: Availability zone?
      [default: us-south]
   ```

4. **Processor Configuration**
   ```
   🔹 **Memory**: Memory allocation per instance?
      [default: 32GB]
   🔹 **Processors**: Number of processors?
      [default: 0.5]
   🔹 **Processor Type**: Processor type?
      - shared (default) - Shared processor pool
      - dedicated - Dedicated processors
      - capped - Capped shared processors
   ```

### Step 2: Generate Command

**Standard Configuration:**
```bash
hypershift create cluster powervs \
  --name powervs-cluster \
  --namespace powervs-cluster-ns \
  --region us-south \
  --zone us-south \
  --resource-group default \
  --base-domain example.com \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --memory 32GB \
  --processors 0.5 \
  --proc-type shared \
  --sys-type s922 \
  --vpc-region us-south
```

**High-Performance Configuration:**
```bash
hypershift create cluster powervs \
  --name powervs-prod \
  --namespace powervs-prod-ns \
  --region us-south \
  --zone us-south \
  --resource-group production-rg \
  --base-domain clusters.company.com \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --memory 64GB \
  --processors 2.0 \
  --proc-type dedicated \
  --sys-type s922 \
  --vpc-region us-south
```

## Error Handling

### API Key Issues
```
IBM Cloud API key not configured or invalid.

Configure authentication:
  export IBMCLOUD_API_KEY="your-api-key"

Or verify existing configuration:
  ibmcloud auth list
```

### Resource Group Not Found
```
Resource group "hypershift-rg" not found.

List available resource groups:
  ibmcloud resource groups

Create new resource group:
  ibmcloud resource group-create hypershift-rg
```

### Region/Zone Issues
```
Zone "us-south-3" not available for PowerVS.

Available zones in us-south:
  ibmcloud pi service-list

Choose appropriate zone for your region.
```

## See Also

- [IBM Cloud PowerVS Documentation](https://cloud.ibm.com/docs/power-iaas)
- [HyperShift PowerVS Provider](https://hypershift.openshift.io/how-to/powervs/)