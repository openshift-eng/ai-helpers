---
name: HyperShift KubeVirt Provider
description: Use this skill when you need to deploy HyperShift clusters on existing Kubernetes clusters using KubeVirt virtualization
---

# HyperShift KubeVirt Provider

This skill provides implementation guidance for creating HyperShift clusters using the KubeVirt provider, which runs on existing Kubernetes clusters with special attention to network conflict prevention and virtual machine management.

## When to Use This Skill

This skill is automatically invoked by the `/hcp:generate kubevirt` command to guide the KubeVirt provider cluster creation process.

## Prerequisites

- Kubernetes cluster with KubeVirt installed and configured
- Sufficient compute resources on the host cluster
- Storage classes configured for VM disks
- HyperShift operator installed
- Pull secret for accessing OpenShift images

## KubeVirt Provider Overview

### KubeVirt Provider Peculiarities

- **Runs on existing Kubernetes cluster:** Host cluster provides compute resources
- **CRITICAL Network Isolation:** Management cluster network cannot conflict with HostedCluster network
- **Storage Requirements:** Requires storage classes for VM disks and persistent volumes
- **Virtual Machine Templates:** Uses VM-based nodes instead of bare metal
- **IPv6 Support:** Full IPv6 support available
- **Disconnected Capable:** Can run in airgapped environments
- **Resource Planning:** Requires sufficient compute resources on host cluster

### Network Conflict Prevention (CRITICAL)

The most important aspect of KubeVirt clusters is preventing network conflicts:

- **Service/Cluster/Machine CIDRs must not overlap with management cluster**
- **Default CIDRs are designed to avoid common management cluster ranges**
- **Always check management cluster CIDRs before setting HostedCluster CIDRs**

**Common management cluster ranges to avoid:**
- 10.128.0.0/14 (common OCP default)
- 10.0.0.0/16 (common private range)
- 192.168.0.0/16 (common private range)

## Implementation Steps

### Step 1: Analyze Cluster Description

Parse the natural language description for KubeVirt-specific requirements:

**Environment Type Detection:**
- **Development**: "dev", "development", "testing", "lab", "demo"
- **Production**: "prod", "production", "critical", "enterprise"
- **Disconnected**: "airgapped", "disconnected", "offline", "air-gapped"

**Resource Indicators:**
- **High Performance**: "performance", "fast", "high-compute", "intensive"
- **Standard**: Default moderate configuration
- **Minimal**: "small", "minimal", "basic", "edge"

**Network Requirements:**
- **IPv6**: "ipv6", "dual-stack", "ipv6-only"
- **Isolated**: "isolated", "private", "secure"

**Storage Requirements:**
- **Local Storage**: "local", "local storage", "hostpath"
- **Replicated**: "replicated", "distributed", "ceph", "longhorn"

### Step 2: Management Cluster Network Discovery

**CRITICAL FIRST STEP:** Always check management cluster networks to prevent conflicts.

**Prompt for management cluster information:**
```
🔹 **Management Cluster Networks**: To avoid conflicts, please run this command on your management cluster:

   `oc get network cluster -o yaml`

   From the output, what are the serviceNetwork and clusterNetwork CIDRs?
   - serviceNetwork CIDR: [e.g., 172.30.0.0/16]
   - clusterNetwork CIDR: [e.g., 10.128.0.0/14]
   - [Press Enter if you don't know - I'll use safe defaults]
```

**If user provides management cluster CIDRs:**
- Validate they don't overlap with our proposed defaults
- Adjust HostedCluster CIDRs if conflicts detected
- Document the conflict avoidance in the output

### Step 3: Apply KubeVirt Provider Defaults

**Required Parameters:**
- `--memory`: Memory allocation for VMs (default: 8Gi)
- `--cores`: CPU cores for VMs (default: 2)
- `--pull-secret`: Path to pull secret file
- `--release-image`: OpenShift release image

**IPv4 Non-Conflicting Defaults:**
- `--service-cidr`: 172.30.0.0/16 (avoids common 10.x ranges)
- `--cluster-cidr`: 10.132.0.0/14 (avoids common 10.128.x range)
- `--machine-cidr`: 192.168.126.0/24 (avoids common 192.168.1.x range)

**IPv6 Non-Conflicting Defaults:**
- `--service-cidr`: fd02::/112
- `--cluster-cidr`: fd01::/48
- `--machine-cidr`: fd03::/64

**Smart Defaults by Environment:**

**Development Environment:**
```bash
--memory 8Gi
--cores 2
--control-plane-availability-policy SingleReplica
--node-pool-replicas 2
```

**Production Environment:**
```bash
--memory 16Gi
--cores 4
--control-plane-availability-policy HighlyAvailable
--node-pool-replicas 3
--auto-repair true
```

**High-Performance Environment:**
```bash
--memory 32Gi
--cores 8
--control-plane-availability-policy HighlyAvailable
--node-pool-replicas 5
```

### Step 4: Interactive Parameter Collection

**Required Information Collection:**

1. **Cluster Name**
   ```
   🔹 **Cluster Name**: What would you like to name your cluster?
      - Must be DNS-compatible (lowercase, hyphens allowed)
      - Used for VM and resource naming
      - Example: dev-cluster, prod-app, test-env
   ```

2. **Management Cluster Network Check** (see Step 2)

3. **VM Resource Configuration**
   ```
   🔹 **VM Memory**: How much memory should each VM have?
      - Development: 8Gi (minimum recommended)
      - Production: 16Gi+ (better performance)
      - High-performance: 32Gi+ (intensive workloads)
      - [Press Enter for default based on environment]
   ```

   ```
   🔹 **VM CPU Cores**: How many CPU cores should each VM have?
      - Development: 2 cores (minimum recommended)
      - Production: 4+ cores (better performance)
      - High-performance: 8+ cores (intensive workloads)
      - [Press Enter for default based on environment]
   ```

4. **Pull Secret**
   ```
   🔹 **Pull Secret**: Path to your OpenShift pull secret file?
      - Required for accessing OpenShift container images
      - Download from: https://console.redhat.com/openshift/install/pull-secret
      - Example: /home/user/pull-secret.json
   ```

5. **OpenShift Version**
   ```
   🔹 **OpenShift Version**: Which OpenShift version do you want to use?

      📋 **Check supported versions**: https://amd64.ocp.releases.ci.openshift.org/

      - Enter release image URL: quay.io/openshift-release-dev/ocp-release:X.Y.Z-multi
      - [Press Enter for default: quay.io/openshift-release-dev/ocp-release:4.18.0-multi]
   ```

**Optional Configuration:**

6. **IPv6 Support** (if detected)
   ```
   🔹 **IPv6 Configuration**: Detected IPv6 requirement. Configure network stack:
      - ipv4: IPv4 only (default)
      - ipv6: IPv6 only
      - dual: Dual-stack (IPv4 + IPv6)
      - [Press Enter for default: ipv4]
   ```

7. **Storage Class**
   ```
   🔹 **Storage Class**: Which storage class should be used for VM disks?
      - List available storage classes on your cluster:
        kubectl get storageclass
      - [Press Enter to use cluster default]
   ```

8. **Node Count**
   ```
   🔹 **Node Pool Replicas**: How many worker nodes do you need?
      - Minimum: 2 (for basic redundancy)
      - Production recommended: 3+
      - [Press Enter for default based on environment type]
   ```

### Step 5: Network CIDR Validation

**If management cluster CIDRs provided, validate conflicts:**

```
## Network Conflict Check

Management cluster networks:
- Service Network: 172.30.0.0/16
- Cluster Network: 10.128.0.0/14

HostedCluster networks (checking for conflicts):
✅ Service CIDR: 172.30.0.0/16 (safe - different range)
❌ Cluster CIDR: 10.132.0.0/14 (CONFLICT with 10.128.0.0/14)
✅ Machine CIDR: 192.168.126.0/24 (safe)

Adjusting Cluster CIDR to avoid conflict:
New Cluster CIDR: 10.140.0.0/14
```

**If no management cluster info provided, use safe defaults:**
```
## Network Configuration (Safe Defaults)

Using safe default CIDRs that avoid common management cluster ranges:
- Service CIDR: 172.30.0.0/16 (avoids 10.x ranges)
- Cluster CIDR: 10.132.0.0/14 (avoids common 10.128.x)
- Machine CIDR: 192.168.126.0/24 (avoids common 192.168.1.x)
```

### Step 6: Generate Command

**Basic KubeVirt Cluster Command:**
```bash
hypershift create cluster kubevirt \
  --name <cluster-name> \
  --namespace <cluster-name>-ns \
  --memory <memory> \
  --cores <cores> \
  --pull-secret <pull-secret-path> \
  --release-image <release-image> \
  --service-cidr <service-cidr> \
  --cluster-cidr <cluster-cidr> \
  --machine-cidr <machine-cidr>
```

**Development Configuration Example:**
```bash
hypershift create cluster kubevirt \
  --name dev-cluster \
  --namespace dev-cluster-ns \
  --memory 8Gi \
  --cores 2 \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --service-cidr 172.30.0.0/16 \
  --cluster-cidr 10.132.0.0/14 \
  --machine-cidr 192.168.126.0/24 \
  --control-plane-availability-policy SingleReplica \
  --node-pool-replicas 2
```

**Production Configuration Example:**
```bash
hypershift create cluster kubevirt \
  --name production-cluster \
  --namespace production-cluster-ns \
  --memory 16Gi \
  --cores 4 \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --service-cidr 172.30.0.0/16 \
  --cluster-cidr 10.132.0.0/14 \
  --machine-cidr 192.168.126.0/24 \
  --control-plane-availability-policy HighlyAvailable \
  --node-pool-replicas 3 \
  --auto-repair
```

**IPv6 Configuration Example:**
```bash
hypershift create cluster kubevirt \
  --name ipv6-cluster \
  --namespace ipv6-cluster-ns \
  --memory 16Gi \
  --cores 4 \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --service-cidr fd02::/112 \
  --cluster-cidr fd01::/48 \
  --machine-cidr fd03::/64
```

**Disconnected Configuration Example:**
```bash
hypershift create cluster kubevirt \
  --name airgapped-cluster \
  --namespace airgapped-cluster-ns \
  --memory 16Gi \
  --cores 4 \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --service-cidr 172.30.0.0/16 \
  --cluster-cidr 10.132.0.0/14 \
  --machine-cidr 192.168.126.0/24 \
  --image-content-sources /path/to/image-content-sources.yaml \
  --additional-trust-bundle /path/to/ca-bundle.pem \
  --render
```

### Step 7: Pre-Flight Validation

**Provide validation commands:**
```
## Pre-Flight Checks

Before creating the cluster, verify your KubeVirt setup:

1. **KubeVirt Status:**
   kubectl get kubevirt -A

2. **Available Storage Classes:**
   kubectl get storageclass

3. **Node Resources:**
   kubectl top nodes

4. **Available Memory/CPU:**
   kubectl describe nodes | grep -E "(Allocatable|Allocated)"

5. **Network Configuration:**
   oc get network cluster -o yaml

6. **Required Compute Resources:**
   - Control Plane VMs: 3 x (<cores> cores, <memory> RAM)
   - Worker VMs: <replica-count> x (<cores> cores, <memory> RAM)
   - Total Required: <total-cores> cores, <total-memory> RAM
```

### Step 8: Post-Generation Instructions

**For Disconnected Environments:**
```
## Post-Creation Configuration (Disconnected)

After running the command above (with --render), you'll need to modify the generated manifests:

1. **Add ImageContentSources to HostedCluster:**
```yaml
spec:
  imageContentSources:
  - source: quay.io/openshift-release-dev/ocp-v4.0-art-dev
    mirrors:
    - registry.example.com:5000/openshift/release
  - source: quay.io/openshift-release-dev/ocp-release
    mirrors:
    - registry.example.com:5000/openshift/release-images
```

2. **Apply the manifests:**
```bash
kubectl apply -f <rendered-manifest-files>
```

**For All Environments:**
```
## Next Steps

1. **Monitor cluster creation:**
   kubectl get hostedcluster -n <cluster-namespace>
   kubectl get nodepool -n <cluster-namespace>

2. **Check VM creation:**
   kubectl get vmi -A

3. **Monitor VM startup:**
   kubectl get vmi -A -w

4. **Access cluster when ready:**
   hypershift create kubeconfig --name <cluster-name> --namespace <cluster-namespace>
   export KUBECONFIG=<cluster-name>-kubeconfig
   oc get nodes

5. **Verify network isolation:**
   oc get network cluster -o yaml  # Check HostedCluster networks
```

## Error Handling

### Network CIDR Conflicts

**Scenario:** HostedCluster CIDRs conflict with management cluster.

**Action:**
```
CIDR conflict detected:
- Management cluster: 10.128.0.0/14
- HostedCluster (proposed): 10.132.0.0/14
- Overlap detected!

Suggested alternative CIDRs:
- Service CIDR: 172.30.0.0/16 (safe)
- Cluster CIDR: 10.140.0.0/14 (avoids conflict)
- Machine CIDR: 192.168.126.0/24 (safe)

Update command with new CIDRs? [y/N]
```

### Insufficient Resources

**Scenario:** Host cluster lacks sufficient resources for VMs.

**Action:**
```
Insufficient resources on host cluster:

Required:
- CPU: 24 cores (3 control plane + 6 workers @ 4 cores each)
- Memory: 144Gi (3 control plane + 6 workers @ 16Gi each)

Available:
- CPU: 16 cores
- Memory: 96Gi

Suggestions:
1. Reduce VM resources (--memory 8Gi --cores 2)
2. Reduce worker count (--node-pool-replicas 2)
3. Use SingleReplica control plane
4. Add more nodes to host cluster
```

### Storage Class Issues

**Scenario:** No suitable storage class available.

**Action:**
```
No default storage class found. Available storage classes:

NAME                 PROVISIONER
local-path          rancher.io/local-path
ceph-rbd           kubernetes.io/rbd

Specify storage class in NodePool configuration:
  storageClassName: local-path

Or set a default storage class:
  kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### KubeVirt Not Ready

**Scenario:** KubeVirt is not properly installed or configured.

**Action:**
```
KubeVirt is not ready:

Check KubeVirt status:
  kubectl get kubevirt -A
  kubectl get pods -n kubevirt

Install KubeVirt if missing:
  kubectl apply -f https://github.com/kubevirt/kubevirt/releases/download/v1.0.0/kubevirt-operator.yaml
  kubectl apply -f https://github.com/kubevirt/kubevirt/releases/download/v1.0.0/kubevirt-cr.yaml

Verify installation:
  kubectl wait kv kubevirt --for condition=Available -n kubevirt --timeout=300s
```

## Best Practices

### Resource Planning

1. **Right-size VMs:** Don't over-provision for development environments
2. **Monitor resource usage:** Keep track of host cluster resource consumption
3. **Plan for growth:** Ensure host cluster can accommodate scaling
4. **Storage planning:** Use appropriate storage classes for performance needs

### Network Management

1. **Always check management cluster CIDRs:** Prevent network conflicts
2. **Document network design:** Keep records of CIDR allocations
3. **Plan for multiple clusters:** Reserve CIDR ranges for future clusters
4. **IPv6 considerations:** Plan dual-stack if needed

### Security

1. **Network isolation:** Ensure proper network segmentation
2. **Storage security:** Use encrypted storage where required
3. **Image security:** Use trusted image registries
4. **RBAC:** Implement proper role-based access control

### Performance

1. **VM sizing:** Balance resource allocation with performance needs
2. **Storage performance:** Use high-performance storage for production
3. **Network performance:** Consider SR-IOV for high-throughput workloads
4. **CPU pinning:** Consider CPU pinning for performance-critical workloads

## Anti-Patterns to Avoid

❌ **Ignoring network conflicts**
```
Using default CIDRs without checking management cluster
```
✅ Always check management cluster networks first

❌ **Under-provisioning VMs**
```
--memory 4Gi --cores 1  # Too small for OpenShift
```
✅ Use minimum 8Gi memory and 2 cores

❌ **Over-provisioning for development**
```
--memory 64Gi --cores 16 --node-pool-replicas 10  # Excessive for dev
```
✅ Use appropriate sizing for environment

❌ **Conflicting CIDR ranges**
```
Using 10.128.0.0/14 when management cluster uses 10.128.0.0/14
```
✅ Use non-overlapping CIDR ranges

## Example Workflows

### Development Lab
```
Input: "small kubevirt cluster for development testing"

Management cluster check:
- Service: 172.30.0.0/16
- Cluster: 10.128.0.0/14

Analysis:
- Environment: Development
- Scale: Small
- Network: Avoid 10.128.x range

Generated Command:
hypershift create cluster kubevirt \
  --name dev-lab \
  --namespace dev-lab-ns \
  --memory 8Gi \
  --cores 2 \
  --service-cidr 172.31.0.0/16 \
  --cluster-cidr 10.132.0.0/14 \
  --machine-cidr 192.168.126.0/24 \
  --control-plane-availability-policy SingleReplica \
  --node-pool-replicas 2
```

### Production Environment
```
Input: "high-performance kubevirt cluster for production workloads"

Analysis:
- Environment: Production
- Performance: High priority
- Availability: HA required

Generated Command:
hypershift create cluster kubevirt \
  --name prod-workloads \
  --namespace prod-workloads-ns \
  --memory 32Gi \
  --cores 8 \
  --service-cidr 172.30.0.0/16 \
  --cluster-cidr 10.132.0.0/14 \
  --machine-cidr 192.168.126.0/24 \
  --control-plane-availability-policy HighlyAvailable \
  --node-pool-replicas 5 \
  --auto-repair
```

## See Also

- [KubeVirt Documentation](https://kubevirt.io/user-guide/)
- [HyperShift KubeVirt Provider Guide](https://hypershift.openshift.io/how-to/kubevirt/)
- [OpenShift Virtualization](https://docs.openshift.com/container-platform/latest/virt/about-virt.html)
- [Network Configuration Best Practices](https://docs.openshift.com/container-platform/latest/networking/understanding-networking.html)