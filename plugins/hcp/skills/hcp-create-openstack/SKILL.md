---
name: HyperShift OpenStack Provider
description: Use this skill when you need to deploy HyperShift clusters on OpenStack infrastructure with proper flavor selection and network configuration
---

# HyperShift OpenStack Provider

This skill provides implementation guidance for creating HyperShift clusters on OpenStack, handling OpenStack-specific requirements including credentials, networking, and flavor selection.

## When to Use This Skill

This skill is automatically invoked by the `/hcp:generate openstack` command to guide the OpenStack provider cluster creation process.

## Prerequisites

- OpenStack CLI configured with appropriate credentials
- OpenStack project with sufficient quotas
- External network configured for floating IPs
- HyperShift operator installed and configured

## OpenStack Provider Overview

### OpenStack Provider Peculiarities

- **Requires OpenStack credentials:** Must have valid clouds.yaml or environment variables
- **Floating IP networks needed:** External network access for cluster API
- **Flavor selection critical:** Instance flavors affect performance and cost
- **Custom images may be required:** RHCOS images for worker nodes
- **Network topology affects routing:** Proper network configuration essential

## Implementation Steps

### Step 1: Interactive Parameter Collection

**Required Parameters:**

1. **OpenStack Credentials**
   ```
   🔹 **OpenStack Credentials**: Path to OpenStack credentials file?
      - Usually clouds.yaml format
      - Example: /home/user/.config/openstack/clouds.yaml
   ```

2. **External Network**
   ```
   🔹 **External Network ID**: OpenStack external network UUID?
      - Required for floating IP allocation
      - Find with: openstack network list --external
   ```

3. **Flavor Selection**
   ```
   🔹 **Node Flavor**: Choose instance flavor:
      - m1.large (4 vCPU, 8GB RAM) - Standard workloads
      - m1.xlarge (8 vCPU, 16GB RAM) - Performance workloads
      - [default: m1.large]
   ```

### Step 2: Generate Command

**Standard Configuration:**
```bash
hypershift create cluster openstack \
  --name openstack-cluster \
  --namespace openstack-cluster-ns \
  --openstack-credentials-file /path/to/clouds.yaml \
  --openstack-external-network-id <external-network-uuid> \
  --openstack-node-flavor m1.large \
  --base-domain example.com \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi
```

## Error Handling

### External Network Not Found
```
External network with ID "<uuid>" not found.

List available external networks:
  openstack network list --external

Ensure network has proper routing configuration.
```

### Flavor Not Available
```
Flavor "m1.large" not available in this OpenStack deployment.

List available flavors:
  openstack flavor list

Choose appropriate flavor for your workload requirements.
```

## See Also

- [OpenStack Documentation](https://docs.openstack.org/)
- [HyperShift OpenStack Provider](https://hypershift.openshift.io/how-to/openstack/)