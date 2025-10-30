---
description: Generate ready-to-execute hypershift cluster creation commands from natural language descriptions
argument-hint: <provider> <cluster-description>
---

## Name
hcp:generate

## Synopsis
```
/hcp:generate <provider> <cluster-description>
```

## Description
The `hcp:generate` command translates natural language descriptions into precise, ready-to-execute `hypershift create cluster` commands. It supports multiple cloud providers and platforms, each with their specific requirements and best practices.

**Important**: This command **generates commands for you to run** - it does not provision clusters directly.

This command is particularly useful for:
- Generating complete, copy-paste-ready hypershift commands with proper parameters
- Applying provider-specific best practices and configurations automatically
- Handling complex parameter validation and smart defaults
- Providing interactive prompts for missing critical information
- Learning proper hypershift command syntax and options

## Key Features

- **Multi-Provider Support** - AWS, Azure, KubeVirt, OpenStack, PowerVS, and Agent providers
- **Smart Analysis** - Extracts platform, configuration, and requirements from natural language
- **Interactive Prompts** - Asks for missing critical information with helpful guidance
- **Provider Expertise** - Applies platform-specific best practices and configurations
- **Security Validation** - Ensures safe parameter handling and credential management
- **Namespace Management** - Implements best practices for cluster isolation

## Implementation

The `hcp:generate` command runs in multiple phases:

### 🎯 Phase 1: Load Provider-Specific Implementation Guidance

Invoke the appropriate skill based on provider using the Skill tool:

- **Provider: `aws`** → Invoke `hcp-create-aws` skill
  - Loads AWS-specific requirements and configurations
  - Provides STS credentials handling
  - Offers region and availability zone guidance
  - Handles IAM roles and VPC configuration

- **Provider: `azure`** → Invoke `hcp-create-azure` skill
  - Loads Azure-specific requirements (self-managed control plane only)
  - Provides resource group and location guidance
  - Handles identity configuration options
  - Manages virtual network integration

- **Provider: `kubevirt`** → Invoke `hcp-create-kubevirt` skill
  - Loads KubeVirt-specific network conflict prevention
  - Provides virtual machine configuration guidance
  - Handles storage class requirements
  - Manages IPv4/IPv6 CIDR validation

- **Provider: `openstack`** → Invoke `hcp-create-openstack` skill
  - Loads OpenStack-specific requirements
  - Provides floating IP network guidance
  - Handles flavor selection and custom images
  - Manages network topology configuration

- **Provider: `powervs`** → Invoke `hcp-create-powervs` skill
  - Loads PowerVS/IBM Cloud specific requirements
  - Provides region and zone guidance
  - Handles IBM Cloud API key configuration
  - Manages processor and memory specifications

- **Provider: `agent`** → Invoke `hcp-create-agent` skill
  - Loads bare metal and edge deployment guidance
  - Provides pre-provisioned agent requirements
  - Handles manual network configuration
  - Manages disconnected environment setup

### 📝 Phase 2: Parse Arguments & Detect Context

Parse command arguments:
- **Required:** `provider`, `cluster-description`
- Parse natural language description for:
  - Environment type (development, production, disconnected)
  - Special requirements (FIPS, architecture, storage)
  - Resource constraints (cost-optimization, performance)
  - Network requirements

### ⚙️ Phase 3: Apply Provider-Specific Defaults and Validation

**Universal requirements (applied to ALL clusters):**
- **Namespace strategy:** Generate unique namespace based on cluster name (`{cluster-name}-ns`)
- **Security validation:** Scan for credentials or sensitive data
- **Release image:** Always include `--release-image` with proper version

**Provider-specific validation:**
- Network conflict prevention (especially KubeVirt)
- Credential requirements validation
- Region/zone availability checks
- Resource limit validation

### 💬 Phase 4: Interactive Prompts (Provider-Guided)

Each provider skill guides the collection of missing information:

**Common prompts for all providers:**
- Cluster name (if not specified)
- Pull secret path
- OpenShift version/release image
- Base domain (where applicable)

**Provider-specific prompts:**
- AWS: STS credentials, IAM role ARN, region selection
- Azure: Identity configuration method, resource group name
- KubeVirt: Management cluster network CIDRs, storage classes
- OpenStack: External network UUID, flavor selection
- PowerVS: IBM Cloud resource group, processor specifications
- Agent: Agent namespace, pre-provisioned agent details

### 🔒 Phase 5: Security and Configuration Validation

**Security checks:**
- Scan all inputs for credentials, API keys, or secrets
- Validate that sensitive information uses placeholder values
- Ensure proper credential file references

**Configuration validation:**
- Verify required parameters are present
- Validate parameter combinations and dependencies
- Check for common misconfigurations

### ✅ Phase 6: Generate Command

Based on provider skill guidance:
- Construct complete `hypershift create cluster` command
- Apply smart defaults for optional parameters
- Include all required provider-specific flags
- Format command for copy-paste execution

### 📤 Phase 7: Return Result

Display to user:
- **Summary:** Brief description of what will be created
- **Generated Command:** Complete, executable command
- **Key Decisions:** Explanation of important choices made
- **Next Steps:** What to do after running the command
- **Provider-specific notes:** Any special considerations

## Usage Examples

1. **Create AWS development cluster**:
   ```
   /hcp:generate aws "development cluster for testing new features"
   ```
   → Invokes `hcp-create-aws` skill, prompts for AWS-specific details

2. **Create production KubeVirt cluster**:
   ```
   /hcp:generate kubevirt "production cluster with high availability"
   ```
   → Invokes `hcp-create-kubevirt` skill, handles network conflict prevention

3. **Create cost-optimized Azure cluster**:
   ```
   /hcp:generate azure "small cluster for dev work, minimize costs"
   ```
   → Invokes `hcp-create-azure` skill, applies cost optimization

4. **Create disconnected agent cluster**:
   ```
   /hcp:generate agent "airgapped cluster for secure environment"
   ```
   → Invokes `hcp-create-agent` skill, handles disconnected requirements

5. **Create FIPS-enabled OpenStack cluster**:
   ```
   /hcp:generate openstack "production cluster with FIPS compliance"
   ```
   → Invokes `hcp-create-openstack` skill, applies FIPS configuration

6. **Create ARM-based PowerVS cluster**:
   ```
   /hcp:generate powervs "arm64 cluster for multi-arch testing"
   ```
   → Invokes `hcp-create-powervs` skill, handles ARM architecture

## Arguments

- **$1 – provider** *(required)*
  Cloud provider or platform to use.
  **Options:** `aws` | `azure` | `kubevirt` | `openstack` | `powervs` | `agent`

- **$2 – cluster-description** *(required)*
  Natural language description of the desired cluster.
  Use quotes for multi-word descriptions: `"production cluster with HA"`

  **Description should include:**
  - Environment type (development, production, testing)
  - Special requirements (FIPS, architecture, storage)
  - Resource preferences (cost-optimized, high-performance)
  - Network requirements (disconnected, private)

## Return Value

- **Summary**: Brief description of the cluster that will be created
- **Generated Command**: Complete `hypershift create cluster` command
- **Key Decisions**: Explanation of choices made during generation
- **Next Steps**: Instructions for executing the command and post-creation tasks

**Example output:**
```
## Summary
Creating a development AWS hosted cluster with basic configuration.

## Generated Command
```bash
hypershift create cluster aws \
  --name dev-cluster \
  --namespace dev-cluster-ns \
  --region us-east-1 \
  --instance-type m5.large \
  --pull-secret /path/to/pull-secret.json \
  --node-pool-replicas 2 \
  --zones us-east-1a,us-east-1b \
  --control-plane-availability-policy SingleReplica \
  --sts-creds /path/to/sts-creds.json \
  --role-arn arn:aws:iam::123456789:role/hypershift-role \
  --base-domain example.com \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi
```

## Key Decisions
- Used SingleReplica for development (cost-effective)
- Selected 2 zones for basic redundancy
- m5.large instances balance cost and performance for dev workloads
- **Unique namespace**: `dev-cluster-ns` for better isolation and disaster recovery

## Next Steps
1. Ensure your pull secret file exists at the specified path
2. Verify AWS credentials are configured
3. Confirm STS credentials file is accessible
4. Run the command above to create your cluster
```

## Error Handling

### Invalid Provider

**Scenario:** User specifies unsupported provider.

**Action:**
```
Invalid provider "gcp". Supported providers: aws, azure, kubevirt, openstack, powervs, agent

Did you mean "aws"?
```

### Missing Description

**Scenario:** User doesn't provide cluster description.

**Action:**
```
Cluster description is required. Please describe what kind of cluster you want.

Examples:
- "development cluster for testing"
- "production cluster with high availability"
- "cost-optimized cluster for demos"

Usage: /hcp:generate aws "development cluster for testing"
```

### Ambiguous Requirements

**Scenario:** Description is too vague or contradictory.

**Action:**
```
The description "fast and cheap cluster" has conflicting requirements.

Let me help clarify:
1. Performance-optimized (higher costs, better resources)
2. Cost-optimized (lower costs, minimal resources)
3. Balanced (moderate costs and performance)

Which approach do you prefer?
```

### Provider-Specific Errors

**Scenario:** Provider-specific validation fails.

**Action:**
- Forward to appropriate skill for specialized error handling
- Provide provider-specific guidance and solutions
- Offer alternative configurations when possible

## Best Practices

1. **Be descriptive:** Include environment type, requirements, and constraints
2. **Specify architecture:** Mention if you need ARM64 or specific architectures
3. **Include network needs:** Specify if disconnected or special networking required
4. **Mention compliance:** Include FIPS, security, or regulatory requirements
5. **Consider costs:** Specify if cost optimization is important
6. **Plan for growth:** Mention if cluster needs to scale or handle specific workloads

## Anti-Patterns to Avoid

❌ **Vague descriptions**
```
/hcp:generate aws "cluster"
```
✅ Be specific: "development cluster for API testing with minimal resources"

❌ **Conflicting requirements**
```
/hcp:generate aws "high-performance cluster but very cheap"
```
✅ Be realistic: "balanced cluster optimizing for cost while maintaining decent performance"

❌ **Provider mismatches**
```
/hcp:generate azure "cluster for my on-premises lab"
```
✅ Use appropriate provider: "kubevirt cluster for my on-premises lab"

## See Also

- `hypershift create cluster --help` - Official hypershift CLI documentation
- Provider-specific skills:
  - `hcp-create-aws` - AWS-specific guidance
  - `hcp-create-azure` - Azure-specific guidance
  - `hcp-create-kubevirt` - KubeVirt-specific guidance
  - `hcp-create-openstack` - OpenStack-specific guidance
  - `hcp-create-powervs` - PowerVS-specific guidance
  - `hcp-create-agent` - Agent provider guidance

## Skills Reference

The following skills are automatically invoked by this command based on provider:

**Provider-specific skills:**
- **hcp-create-aws** - AWS provider implementation details
- **hcp-create-azure** - Azure provider implementation details
- **hcp-create-kubevirt** - KubeVirt provider implementation details
- **hcp-create-openstack** - OpenStack provider implementation details
- **hcp-create-powervs** - PowerVS provider implementation details
- **hcp-create-agent** - Agent provider implementation details

To view skill details:
```bash
ls plugins/hypershift/skills/
cat plugins/hypershift/skills/hcp-create-aws/SKILL.md
cat plugins/hypershift/skills/hcp-create-kubevirt/SKILL.md
# ... etc for other providers
```