# k8s-ocp-olm-expert Agent

An elite software engineering agent with deep, specialized expertise in Kubernetes (k8s), OpenShift (OCP), and Operator Lifecycle Manager (OLM) v0 and v1.

## Overview

This agent is automatically invoked when working with:
- Kubernetes resources (pods, deployments, services, etc.)
- OpenShift-specific features and configurations
- Operator development and troubleshooting
- OLM installations and upgrades
- Cluster debugging and must-gather analysis

## Prerequisites

Before using this agent, you need to configure it with paths to your local OLM development repositories.

### Option 1: Quick Setup (Recommended for New Team Members)

If you don't have the OLM repositories cloned yet:

```bash
/olm-team:dev-setup
```

This will:
1. Fork all OLM repositories to your GitHub account
2. Clone them to your local machine
3. Automatically configure the agent with the correct paths

### Option 2: Configure Existing Repositories

If you already have the repositories cloned:

```bash
/olm-team:configure-agent
```

This will guide you through creating the configuration file with paths to your existing repository checkouts.

## Configuration File

The agent expects a configuration file at: `~/.config/claude-code/olm-agent-config.json`

### Configuration Structure

```json
{
  "repositories": {
    "openshift_docs": "/path/to/openshift-docs",
    "olm_v0_upstream": {
      "operator_lifecycle_manager": "/path/to/operator-lifecycle-manager",
      "operator_registry": "/path/to/operator-registry",
      "api": "/path/to/api"
    },
    "olm_v0_downstream": {
      "operator_framework_olm": "/path/to/operator-framework-olm",
      "operator_marketplace": "/path/to/operator-marketplace"
    },
    "olm_v1_upstream": {
      "operator_controller": "/path/to/operator-controller"
    },
    "olm_v1_downstream": {
      "operator_framework_operator_controller": "/path/to/operator-framework-operator-controller",
      "cluster_olm_operator": "/path/to/cluster-olm-operator"
    }
  }
}
```

### Required Repositories

The agent requires access to these repositories:

**Documentation:**
- `openshift-docs` - OpenShift product documentation (*.adoc files)

**OLM v0 Upstream:**
- `operator-lifecycle-manager` - Core OLM v0 runtime
- `operator-registry` - Catalog and bundle management
- `api` - OLM API definitions and CRDs

**OLM v0 Downstream:**
- `operator-framework-olm` - OpenShift distribution of OLM v0
- `operator-marketplace` - OperatorHub integration

**OLM v1 Upstream:**
- `operator-controller` - Core OLM v1 runtime

**OLM v1 Downstream:**
- `operator-framework-operator-controller` - OpenShift distribution of OLM v1
- `cluster-olm-operator` - OLM cluster operator

## Features

### Proactive Engagement

The agent automatically activates when it detects:
- Kubernetes resource discussions
- OpenShift-specific terminology
- Operator or OLM-related topics
- YAML manifests with k8s/OCP API versions
- Cluster debugging scenarios

### Documentation Integration

The agent:
- Searches local OpenShift documentation (*.adoc files)
- Provides file paths and line numbers for relevant docs
- Identifies documentation gaps
- References source code when appropriate

### Code-Aware Responses

The agent references:
- Upstream and downstream OLM v0 code
- Upstream and downstream OLM v1 code
- OpenShift API definitions
- Production-tested best practices

### Structured Output

For documentation queries, the agent provides:
- **Documentation Found**: Files, line numbers, and quotes
- **Documentation Gaps**: Missing content and where it should be added
- **Context**: How the documentation relates to your question

## Usage Examples

### Debugging a Pod Failure

```
User: I'm seeing CrashLoopBackOff on my etcd pod in OpenShift
Agent: [Automatically engages k8s-ocp-olm-expert]
       Let me help you debug this pod failure...
```

### Creating an Operator Bundle

```
User: I need to create a new operator bundle for OLM v1
Agent: [Automatically engages k8s-ocp-olm-expert]
       I'll guide you through creating an OLM v1 operator bundle...
       [References: ${OLM_V1_UPSTREAM_CONTROLLER}/docs/...]
```

### Finding Documentation

```
User: Where is catalogd CA configuration documented?
Agent: ## Documentation Found
       [Structured response with file paths and line numbers]

       ## Documentation Gaps
       [Identifies missing documentation]
```

## Updating Configuration

To update your repository paths:

```bash
/olm-team:configure-agent
```

Or manually edit: `~/.config/claude-code/olm-agent-config.json`

## Troubleshooting

### Configuration Not Found

If you see:
```
⚠️  Agent configuration not found or invalid.
```

Run:
```bash
/olm-team:configure-agent
```

### Repository Paths Invalid

If paths don't exist, either:
1. Update paths in config file
2. Run `/olm-team:dev-setup` to clone missing repositories

### Repositories Out of Date

The agent uses your local checkouts. To get latest changes:

```bash
cd /path/to/repository
git fetch upstream
git merge upstream/HEAD  # Uses the default branch (main or master)
```

Or if you need to specify the branch explicitly:
```bash
git merge upstream/main   # For repos using main
git merge upstream/master # For repos using master
```

## Related Commands

- `/olm-team:dev-setup` - Clone and configure all OLM repositories
- `/olm-team:configure-agent` - Create/update agent configuration

## Support

For issues or questions:
- Repository: https://github.com/openshift-eng/ai-helpers
- Issues: https://github.com/openshift-eng/ai-helpers/issues
