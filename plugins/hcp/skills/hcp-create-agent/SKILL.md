---
name: HyperShift Agent Provider
description: Use this skill when you need to deploy HyperShift clusters on bare metal, edge environments, or disconnected infrastructures using pre-provisioned agents
---

# HyperShift Agent Provider

This skill provides implementation guidance for creating HyperShift clusters using the Agent provider, which is designed for bare metal and edge deployments where pre-provisioned agents are available.

## When to Use This Skill

This skill is automatically invoked by the `/hcp:generate agent` command to guide the Agent provider cluster creation process.

## Prerequisites

- HyperShift operator installed and configured
- Pre-provisioned agents available in a Kubernetes namespace
- Pull secret for accessing OpenShift images
- Understanding of the target deployment environment

## Agent Provider Overview

### What is the Agent Provider?

The Agent provider:
- Designed for bare metal and edge deployments
- Requires pre-provisioned agents (nodes registered in advance)
- No cloud provider automation - manual network configuration required
- Suitable for disconnected/airgapped environments
- Direct control over hardware and network configuration

### Common Use Cases

- **Edge Computing**: Remote locations with limited connectivity
- **Bare Metal**: On-premises hardware without cloud automation
- **Disconnected Environments**: Airgapped environments with security requirements
- **Custom Hardware**: Specialized hardware configurations
- **Regulatory Compliance**: Environments requiring specific data locality

## Implementation Steps

### Step 1: Analyze Cluster Description

Parse the natural language description for Agent-specific requirements:

**Environment Type Detection:**
- **Edge**: "edge", "remote", "limited connectivity", "small footprint"
- **Bare Metal**: "bare metal", "on-premises", "physical hardware", "custom hardware"
- **Disconnected**: "airgapped", "disconnected", "offline", "secure environment"

**Resource Indicators:**
- **Minimal**: "small", "edge", "minimal resources", "single node"
- **Standard**: "production", "multi-node", "high availability"

**Special Requirements:**
- **FIPS**: "fips", "compliance", "security"
- **Custom Storage**: "local storage", "storage class", "persistent volumes"
- **Network Isolation**: "isolated", "private network", "custom networking"

### Step 2: Apply Agent Provider Defaults

**Required Parameters:**
- `--agent-namespace`: Namespace where agents are located
- `--pull-secret`: Path to pull secret file
- `--release-image`: OpenShift release image
- `--base-domain`: Base domain for the cluster (prompt user if not in description)

**Smart Defaults by Environment:**

**Edge Environment:**
```bash
--control-plane-availability-policy SingleReplica
--node-pool-replicas 1
--arch amd64  # or arm64 if specified
```

**Bare Metal Environment:**
```bash
--control-plane-availability-policy HighlyAvailable
--node-pool-replicas 3
--auto-repair true
```

**Disconnected Environment:**
```bash
--render  # Always render for review
--image-content-sources /path/to/image-content-sources.yaml
--additional-trust-bundle /path/to/ca-bundle.pem
```

### Step 3: Interactive Parameter Collection

**Required Information Collection:**

1. **Cluster Name**
   ```
   🔹 **Cluster Name**: What would you like to name your cluster?
      - Must be DNS-compatible (lowercase, hyphens allowed)
      - Will be used for resource naming
      - Example: edge-lab-01, production-cluster
   ```

2. **Agent Namespace**
   ```
   🔹 **Agent Namespace**: In which namespace are your agents located?
      - This should be the namespace where you registered your agents
      - Example: default, agent-system, cluster-agents
      - [Press Enter for default: default]
   ```

3. **Pull Secret**
   ```
   🔹 **Pull Secret**: Path to your OpenShift pull secret file?
      - Required for accessing OpenShift container images
      - Download from: https://console.redhat.com/openshift/install/pull-secret
      - Example: /home/user/pull-secret.json
   ```

4. **Base Domain** (if not specified in description)
   ```
   🔹 **Base Domain**: What base domain should be used for cluster DNS?
      - This will be used for cluster API and application routes
      - Example: example.com, lab.internal, edge.local
   ```

5. **OpenShift Version**
   ```
   🔹 **OpenShift Version**: Which OpenShift version do you want to use?

      📋 **Check supported versions**: https://amd64.ocp.releases.ci.openshift.org/

      - Enter release image URL: quay.io/openshift-release-dev/ocp-release:X.Y.Z-multi
      - [Press Enter for default: quay.io/openshift-release-dev/ocp-release:4.18.0-multi]
   ```

**Optional Configuration (based on description analysis):**

6. **Architecture** (if detected)
   ```
   🔹 **Architecture**: Detected ARM architecture mention. Confirm architecture:
      - amd64 (x86_64)
      - arm64 (aarch64)
      - [Press Enter for default: amd64]
   ```

7. **FIPS Mode** (if compliance mentioned)
   ```
   🔹 **FIPS Mode**: Enable FIPS mode for compliance?
      - Required for certain regulatory environments
      - May impact performance
      - [yes/no] [Press Enter for default: no]
   ```

### Step 4: Disconnected Environment Handling

If disconnected/airgapped environment is detected:

**Additional Required Information:**

1. **Mirror Registry**
   ```
   🔹 **Mirror Registry**: What is your mirror registry domain?
      - This registry should contain mirrored OpenShift images
      - Example: registry.example.com:5000
   ```

2. **Image Content Sources**
   ```
   🔹 **Image Content Sources**: Path to image content sources file?
      - Required for mapping official images to mirror registry
      - Example: /path/to/image-content-sources.yaml
   ```

3. **Additional Trust Bundle** (optional)
   ```
   🔹 **Additional Trust Bundle**: Path to custom CA bundle? (Optional)
      - Required if mirror registry uses custom certificates
      - Example: /path/to/ca-bundle.pem
      - [Press Enter to skip]
   ```

**Always Use --render for Disconnected:**
- Include `--render` flag to generate manifests for review
- Provide post-generation instructions for required manifest modifications

### Step 5: Agent Availability Validation

**Provide Agent Check Commands:**
```
Before creating the cluster, verify your agents are available:

Check agents in namespace:
  kubectl get agents -n <agent-namespace>

Verify agent status:
  kubectl describe agents -n <agent-namespace>

Ensure agents are:
  - In "Available" state
  - Not bound to other clusters
  - Meet minimum resource requirements
```

### Step 6: Generate Command

**Basic Agent Cluster Command:**
```bash
hypershift create cluster agent \
  --name <cluster-name> \
  --namespace <cluster-name>-ns \
  --agent-namespace <agent-namespace> \
  --pull-secret <pull-secret-path> \
  --release-image <release-image> \
  --base-domain <base-domain>
```

**With Environment-Specific Flags:**

**Edge/Minimal Configuration:**
```bash
hypershift create cluster agent \
  --name edge-cluster \
  --namespace edge-cluster-ns \
  --agent-namespace default \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --base-domain edge.local \
  --control-plane-availability-policy SingleReplica \
  --node-pool-replicas 1
```

**Production/HA Configuration:**
```bash
hypershift create cluster agent \
  --name production-cluster \
  --namespace production-cluster-ns \
  --agent-namespace agent-system \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --base-domain example.com \
  --control-plane-availability-policy HighlyAvailable \
  --node-pool-replicas 3 \
  --auto-repair
```

**Disconnected Configuration:**
```bash
hypershift create cluster agent \
  --name secure-cluster \
  --namespace secure-cluster-ns \
  --agent-namespace agent-system \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --base-domain internal.example.com \
  --image-content-sources /path/to/image-content-sources.yaml \
  --additional-trust-bundle /path/to/ca-bundle.pem \
  --render
```

**FIPS-Enabled Configuration:**
```bash
hypershift create cluster agent \
  --name compliance-cluster \
  --namespace compliance-cluster-ns \
  --agent-namespace agent-system \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --base-domain secure.example.com \
  --fips
```

### Step 7: Post-Generation Instructions

**For Disconnected Environments:**

Provide additional configuration needed after cluster creation:

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
  - source: registry.redhat.io/multicluster-engine
    mirrors:
    - registry.example.com:5000/openshift/multicluster-engine
```

2. **Disable Default OperatorHub Sources:**
```yaml
spec:
  configuration:
    operatorhub:
      disableAllDefaultSources: true
```

3. **Apply the manifests:**
```bash
kubectl apply -f <rendered-manifest-files>
```
```

**For All Environments:**

```
## Next Steps

1. **Verify agents are available:**
   kubectl get agents -n <agent-namespace>

2. **Monitor cluster creation:**
   kubectl get hostedcluster -n <cluster-namespace>
   kubectl get nodepool -n <cluster-namespace>

3. **Check agent assignment:**
   kubectl get agents -n <agent-namespace> -o wide

4. **Access cluster when ready:**
   hypershift create kubeconfig --name <cluster-name> --namespace <cluster-namespace>
```

## Error Handling

### No Agents Available

**Scenario:** No agents found in specified namespace.

**Action:**
```
No agents found in namespace "default".

Please ensure:
1. Agents are properly registered
2. Agents are in "Available" state
3. Correct namespace specified

Check agents:
  kubectl get agents -A

Register new agents using the agent-based installer or manual process.
```

### Insufficient Agents

**Scenario:** Not enough agents for requested replicas.

**Action:**
```
Only 2 agents available, but you requested 3 node replicas.

Options:
1. Reduce node-pool-replicas to 2
2. Register additional agents
3. Use SingleReplica control plane (reduces total requirement)

Would you like me to adjust the configuration?
```

### Agent Already Bound

**Scenario:** Agents are already assigned to another cluster.

**Action:**
```
Some agents are already bound to other clusters.

Available agents: 1
Bound agents: 2

Check agent status:
  kubectl describe agents -n <namespace>

Free up agents by deleting unused clusters or register new agents.
```

### Disconnected Image Access

**Scenario:** Can't access release images in disconnected environment.

**Action:**
```
Release image access failed. In disconnected environments:

1. Ensure mirror registry contains required images
2. Verify image-content-sources file mapping
3. Check custom CA bundle configuration
4. Validate network connectivity to mirror registry

Mirror required images using:
  oc adm release mirror --to <mirror-registry>
```

## Best Practices

### Agent Management

1. **Pre-provision agents:** Register agents before cluster creation
2. **Agent naming:** Use descriptive names for easier management
3. **Resource allocation:** Ensure agents meet minimum requirements
4. **Health monitoring:** Monitor agent status regularly

### Network Configuration

1. **DNS planning:** Ensure proper DNS resolution for base domain
2. **Load balancing:** Configure external load balancer for API access
3. **Ingress:** Plan for application ingress and routing
4. **Firewall:** Configure appropriate firewall rules

### Security

1. **Pull secret security:** Protect pull secret files
2. **FIPS compliance:** Enable FIPS for regulated environments
3. **Certificate management:** Plan for custom certificate authorities
4. **Network isolation:** Implement appropriate network segmentation

### Disconnected Deployments

1. **Mirror planning:** Pre-mirror all required images
2. **Catalog management:** Prepare custom operator catalogs
3. **Certificate management:** Plan for custom CA bundles
4. **Registry security:** Secure mirror registry access

## Anti-Patterns to Avoid

❌ **Assuming cloud automation**
```
"Create cluster with autoscaling"
```
✅ Agent provider requires manual agent provisioning

❌ **Insufficient agent planning**
```
Not checking agent availability before cluster creation
```
✅ Always verify sufficient agents are available

❌ **Ignoring disconnected requirements**
```
Using public image references in airgapped environment
```
✅ Properly configure image content sources and mirror registry

❌ **Inadequate resource planning**
```
Using minimal agents for production workloads
```
✅ Size agents appropriately for expected workloads

## Example Workflows

### Edge Deployment
```
Input: "small edge cluster for remote office monitoring"

Analysis:
- Environment: Edge
- Scale: Minimal
- Use case: Monitoring

Generated Command:
hypershift create cluster agent \
  --name edge-monitoring \
  --namespace edge-monitoring-ns \
  --agent-namespace default \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --base-domain edge.local \
  --control-plane-availability-policy SingleReplica \
  --node-pool-replicas 1
```

### Secure Data Center
```
Input: "airgapped production cluster for financial data processing"

Analysis:
- Environment: Disconnected/Secure
- Scale: Production
- Use case: Financial (compliance required)

Generated Command:
hypershift create cluster agent \
  --name financial-prod \
  --namespace financial-prod-ns \
  --agent-namespace secure-agents \
  --pull-secret /path/to/pull-secret.json \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi \
  --base-domain secure.financial.internal \
  --image-content-sources /path/to/image-content-sources.yaml \
  --additional-trust-bundle /path/to/ca-bundle.pem \
  --fips \
  --render
```

## See Also

- Agent-based OpenShift Installation Documentation
- HyperShift Agent Provider Documentation
- OpenShift Disconnected Installation Guide
- Agent-based Installer Documentation