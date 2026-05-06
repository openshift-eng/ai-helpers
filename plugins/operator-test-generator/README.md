# Operator Test Generator

Claude Code plugin that generates executable OpenShift `oc` test cases for **any operator PR** based on context.

## Audience

Operator developers and QE who need **executable `oc` test cases** for OpenShift operator PRs. This plugin is **operator- and OLM-specific**: it extracts CSV/CRD/samples from the repo and produces ready-to-run install → create CRs → verify → cleanup workflows. For generic test plans or non-operator PR testing guides, see `utils:generate-test-plan` or other testing-related plugins (e.g. a general "testing" plugin may serve a broader audience; this one targets operator PR test generation only).

## Overview

Automatically create comprehensive test cases from any OpenShift operator GitHub PR. This plugin **dynamically analyzes** the PR and repository to extract:

- Operator name, namespace, and installation details
- OLM package name, channel, and catalog source
- Custom Resource Definitions (CRDs) and their schemas
- Required permissions and RBAC
- Example CR manifests from samples

Then generates ready-to-run `oc` commands for testing.

## Features

- **Context-Aware**: Extracts operator details from repository files (CSV, CRDs, samples)
- **Any Operator**: Works with any OpenShift/Kubernetes operator
- **OLM Installation**: Generates Subscription, OperatorGroup, and namespace setup
- **Multi-CRD Support**: Handles operators with multiple Custom Resources
- **PR-Specific Tests**: Creates test cases based on what the PR changes
- **Complete Workflow**: Prerequisites → Install → Create CRs → Verify → Cleanup

## Commands

| Command | Description |
|---------|-------------|
| `/operator-test-generator:generate-from-pr <pr-url>` | Generate test cases with `oc` commands |
| `/operator-test-generator:generate-execution-steps <pr-url>` | Generate step-by-step execution procedure |

## Installation

### Step 1: Create Claude commands directory

```bash
mkdir -p ~/.claude/commands
```

### Step 2: Link the command files

```bash
ln -s ~/ai-helpers/plugins/operator-test-generator/commands/generate-from-pr.md \
  ~/.claude/commands/operator-test-generate-from-pr.md

ln -s ~/ai-helpers/plugins/operator-test-generator/commands/generate-execution-steps.md \
  ~/.claude/commands/operator-test-generate-execution-steps.md
```

### Step 3: Verify installation

```bash
ls -la ~/.claude/commands/
```

## Usage

### Basic Usage

```bash
# Start Claude Code CLI
claude

# Generate tests for any operator PR
/operator-test-generator:generate-from-pr https://github.com/<org>/<operator-repo>/pull/<number>
```

### Examples

```bash
# ZTWIM Operator
/operator-test-generator:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72

# LVMS Operator
/operator-test-generator:generate-from-pr https://github.com/openshift/lvm-operator/pull/500

# Cluster API Provider AWS
/operator-test-generator:generate-from-pr https://github.com/openshift/cluster-api-provider-aws/pull/1234

# Node Tuning Operator
/operator-test-generator:generate-from-pr https://github.com/openshift/cluster-node-tuning-operator/pull/800

# HyperShift
/operator-test-generator:generate-from-pr https://github.com/openshift/hypershift/pull/2000

# Any other operator
/operator-test-generator:generate-from-pr https://github.com/openshift/<operator>/pull/<number>
```

### Non-Interactive Mode

```bash
claude --print "/operator-test-generator:generate-from-pr https://github.com/openshift/lvm-operator/pull/500"
```

## How It Works

### 1. Context Extraction

The plugin navigates to the repository and extracts operator details from:

| File | Information |
|------|-------------|
| `config/manifests/bases/*.clusterserviceversion.yaml` | Package name, channel, install modes |
| `config/crd/bases/*.yaml` | CRD names, API groups, schemas |
| `config/manager/manager.yaml` | Namespace, deployment name |
| `config/samples/*.yaml` | Example CR manifests |
| `api/**/*_types.go` | Go types, field definitions |

### 2. Dynamic Generation

Based on extracted context, generates:

- **OLM Installation**: Namespace, OperatorGroup, Subscription
- **CR Creation**: For each CRD, using samples or schema defaults
- **PR-Specific Tests**: Based on changed files
- **Verification**: Status checks, log inspection
- **Cleanup**: In correct dependency order

### 3. Adaptation

The plugin adapts to different operator patterns:

| Pattern | Handling |
|---------|----------|
| Single CRD | Simple CR creation and test |
| Multiple CRDs | Ordered creation based on dependencies |
| OLM install | Generates Subscription-based install |
| Direct deploy | Generates kubectl apply commands |
| Namespaced | Includes namespace in commands |
| Cluster-scoped | Omits namespace |

## Supported Operators

Works with any operator that follows standard patterns:

- ✅ Operator SDK-based operators
- ✅ Kubebuilder-based operators  
- ✅ OLM-installable operators
- ✅ Direct deployment operators
- ✅ Single-CRD operators
- ✅ Multi-CRD operators

### Tested With

| Operator | Repository |
|----------|------------|
| ZTWIM | openshift/zero-trust-workload-identity-manager |
| LVMS | openshift/lvm-operator |
| Node Tuning | openshift/cluster-node-tuning-operator |
| CAPA | openshift/cluster-api-provider-aws |
| HyperShift | openshift/hypershift |
| etcd | openshift/cluster-etcd-operator |

## Output Format

```markdown
# Test Cases for <Operator> PR #<number>: <title>

## Operator Info
- Name: <operator-name>
- Namespace: <namespace>
- Package: <package-name>
- Channel: <channel>
- CRDs: <list>

## Prerequisites
<cluster access checks>

## 1. Install Operator
<OLM or direct installation commands>

## 2. Create Custom Resources
<CR creation for each CRD>

## 3. Test PR Changes
<PR-specific test cases>

## 4. Verification
<status checks, logs>

## 5. Cleanup
<cleanup in correct order>
```

## Output Location

Generated files are saved to:

```text
op_<operator>_pr_<number>_<description>/
├── test-cases.md
└── execution-steps.md
```

## Prerequisites

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **oc CLI**: OpenShift CLI installed
- **Cluster Access**: Admin access to OpenShift cluster
- **OLM**: Operator Lifecycle Manager (standard on OpenShift)

## Plugin Structure

```text
operator-test-generator/
├── .claude-plugin/
│   └── plugin.json           # Plugin metadata
├── commands/
│   ├── generate-from-pr.md   # Test case generation command
│   └── generate-execution-steps.md  # Execution steps command
├── skills/
│   └── test-case-generator/
│       └── SKILL.md          # Templates and patterns
└── README.md
```

## How Context Detection Works

```text
PR URL
  │
  ├─► Repository name ──► Operator name hint
  │
  ├─► config/manifests/bases/*.csv.yaml
  │     ├─► metadata.name ──► Package name
  │     ├─► spec.installModes ──► Namespace scope
  │     └─► spec.customresourcedefinitions ──► CRD list
  │
  ├─► config/crd/bases/*.yaml
  │     ├─► spec.group ──► API group
  │     ├─► spec.names.kind ──► Kind
  │     └─► spec.versions[].schema ──► Field definitions
  │
  ├─► config/samples/*.yaml
  │     └─► Example CR manifests ──► Default values
  │
  └─► PR files changed
        └─► What to specifically test
```

## Troubleshooting

### Command not found

```bash
# Check symlinks
ls -la ~/.claude/commands/

# Restart Claude
claude
```

### Operator not in marketplace

```bash
# Check available packages
oc get packagemanifests -n openshift-marketplace | grep <keyword>

# May need to add custom catalog source
```

### Context extraction issues

The plugin uses browser tools to read repository files. If extraction fails:
- Ensure PR URL is valid
- Check if repository is public
- Verify files exist at expected paths

## Contributing

To add support for new operator patterns:

1. Add detection logic in `commands/generate-from-pr.md`
2. Add templates in `skills/test-case-generator/SKILL.md`
3. Test with example PRs

## Related

- [ai-helpers](https://github.com/openshift-eng/ai-helpers) - Main repository
- [Operator SDK](https://sdk.operatorframework.io/) - Operator development
- [OLM](https://olm.operatorframework.io/) - Operator Lifecycle Manager
