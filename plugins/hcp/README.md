# HCP Plugin

The HCP plugin generates intelligent `hypershift create cluster` commands from natural language descriptions across multiple cloud providers and platforms.

## Overview

This plugin translates natural language descriptions into precise, ready-to-execute `hypershift create cluster` commands, applying provider-specific best practices and handling complex parameter validation automatically. The plugin **generates commands for you to run** - it does not provision clusters directly.

## Commands

### `/hcp:generate`

Generate ready-to-execute hypershift cluster creation commands from natural language descriptions.

**Usage:**
```
/hcp:generate <provider> <cluster-description>
```

**Supported Providers:**
- `aws` - Amazon Web Services
- `azure` - Microsoft Azure (self-managed control plane)
- `kubevirt` - KubeVirt on existing Kubernetes clusters
- `openstack` - OpenStack clouds
- `powervs` - IBM Cloud PowerVS
- `agent` - Bare metal and edge deployments

**Examples:**
```bash
# AWS development cluster
/hcp:generate aws "development cluster for testing new features"

# High-availability KubeVirt cluster
/hcp:generate kubevirt "production cluster with high availability"

# Cost-optimized Azure cluster
/hcp:generate azure "small cluster for dev work, minimize costs"

# Disconnected bare metal cluster
/hcp:generate agent "airgapped cluster for secure environment"
```

## Key Features

- **Multi-Provider Support**: Works with AWS, Azure, KubeVirt, OpenStack, PowerVS, and Agent providers
- **Smart Analysis**: Extracts requirements from natural language descriptions
- **Interactive Prompts**: Guides users through provider-specific configurations
- **Best Practices**: Applies provider-specific defaults and optimizations
- **Security Validation**: Ensures safe parameter handling and credential management
- **Network Conflict Prevention**: Especially critical for KubeVirt deployments

## Provider-Specific Skills

The plugin uses specialized skills for each provider:

- **`hcp-create-aws`**: AWS-specific guidance including STS credentials, IAM roles, and VPC configuration
- **`hcp-create-azure`**: Azure identity configuration, resource groups, and region management
- **`hcp-create-kubevirt`**: Network conflict prevention, VM sizing, and storage class management
- **`hcp-create-openstack`**: OpenStack credentials, external networks, and flavor selection
- **`hcp-create-powervs`**: IBM Cloud integration, processor types, and resource group management
- **`hcp-create-agent`**: Bare metal deployment, agent management, and disconnected environments

## Installation

### From AI Helpers Marketplace

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the HCP plugin
/plugin install hcp@ai-helpers

# Use the command
/hcp:generate aws "development cluster for API testing"
```

### Manual Installation (Cursor)

```bash
# Clone the repository
mkdir -p ~/.cursor/commands
git clone git@github.com:openshift-eng/ai-helpers.git
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Common Use Cases

### Development Environments
- Quick cluster setup for testing
- Cost-optimized configurations
- Single replica control planes

### Production Deployments
- High-availability configurations
- Multi-zone deployments
- Auto-repair and monitoring enabled

### Edge Computing
- Minimal resource footprints
- Disconnected/airgapped environments
- Agent-based deployments

### Special Requirements
- FIPS compliance configurations
- IPv6 and dual-stack networking
- Custom storage and compute requirements

## Architecture

The plugin follows a modular architecture with:

1. **Main Command**: `/hcp:generate` acts as an orchestrator
2. **Provider Skills**: Specialized implementation guidance for each provider
3. **Interactive Workflows**: Guided parameter collection and validation
4. **Smart Defaults**: Environment-specific best practices

This design ensures:
- **Single Source of Truth**: Each provider's knowledge lives in one place
- **Extensibility**: Easy to add new providers or update existing ones
- **Maintainability**: Clear separation of concerns between providers

## Contributing

To add support for a new provider:

1. Create a new skill directory: `plugins/hcp/skills/hcp-create-<provider>/`
2. Implement the `SKILL.md` file following the established pattern
3. Update the main command to invoke the new skill
4. Test the implementation and add examples

See existing skills as reference implementations.

## Support

- **Issues**: [GitHub Issues](https://github.com/openshift-eng/ai-helpers/issues)
- **Documentation**: [HyperShift Documentation](https://hypershift.openshift.io/)
- **Skills**: View individual skill files in `plugins/hcp/skills/`

## License

This plugin is part of the AI Helpers project and follows the same licensing terms.