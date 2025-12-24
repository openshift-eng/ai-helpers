# ZTWIM Test Generator

Claude Code plugin that generates executable OpenShift `oc` test cases for **Zero Trust Workload Identity Manager (ZTWIM)** operator PRs.

## Overview

Automatically create comprehensive test cases from ZTWIM GitHub PRs. This plugin analyzes PR code changes—API types, CRDs, controllers—and generates ready-to-run `oc` commands for testing the ZTWIM operator, including:

- Operator installation via OLM
- Environment setup (trustDomain, clusterName, jwtIssuer)
- All ZTWIM Custom Resources (ZeroTrustWorkloadIdentityManager, SpireServer, SpireAgent, SpiffeCSIDriver, SpireOIDCDiscoveryProvider)
- Verification commands
- Cleanup procedures

## ZTWIM Operator

The [Zero Trust Workload Identity Manager](https://github.com/openshift/zero-trust-workload-identity-manager) operator provides SPIFFE/SPIRE-based workload identity for OpenShift clusters.

### Custom Resources

| CR | Description |
|----|-------------|
| `ZeroTrustWorkloadIdentityManager` | Main operator CR, manages all components |
| `SpireServer` | SPIRE server configuration |
| `SpireAgent` | SPIRE agent daemonset configuration |
| `SpiffeCSIDriver` | CSI driver for SVID injection |
| `SpireOIDCDiscoveryProvider` | OIDC discovery endpoint |

## Features

### Skills

- **ZTWIM Test Case Generator** - Comprehensive analysis of ZTWIM PR code changes
  - Parses PR files to identify API types and CRDs
  - Generates OLM-based operator installation commands
  - Creates all ZTWIM CR manifests
  - Produces verification and cleanup commands

### Commands

| Command | Description |
|---------|-------------|
| `/ztwim:generate-from-pr <pr-url>` | Generate test cases with `oc` commands |
| `/ztwim:generate-execution-steps <pr-url>` | Generate detailed execution steps |

## Installation

### Step 1: Create Claude commands directory

```bash
mkdir -p ~/.claude/commands
```

### Step 2: Link the command files

```bash
ln -s ~/ai-helpers/plugins/ztwim/commands/generate-from-pr.md ~/.claude/commands/ztwim-generate-from-pr.md
ln -s ~/ai-helpers/plugins/ztwim/commands/generate-execution-steps.md ~/.claude/commands/ztwim-generate-execution-steps.md
```

### Step 3: Verify installation

```bash
ls -la ~/.claude/commands/
# Should show:
# ztwim-generate-from-pr.md -> ~/ai-helpers/plugins/ztwim/commands/generate-from-pr.md
# ztwim-generate-execution-steps.md -> ~/ai-helpers/plugins/ztwim/commands/generate-execution-steps.md
```

## Usage

### Step 1: Start Claude Code CLI

```bash
claude
```

### Step 2: Run a command

**Generate test cases:**
```bash
/ztwim:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72
```

**Generate execution steps:**
```bash
/ztwim:generate-execution-steps https://github.com/openshift/zero-trust-workload-identity-manager/pull/72
```

### Non-Interactive Mode

Run directly from terminal without starting Claude:

```bash
claude --print "/ztwim:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72"
```

## Example Session

```
$ claude

╭─────────────────────────────────────────────────────────────╮
│ Claude Code                                                  │
╰─────────────────────────────────────────────────────────────╯

> /ztwim:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72

● Analyzing PR #72: "Add trustDomain field propagation"
● Reading PR description and files changed...
● Generating ZTWIM test cases...
● Output saved to: ztwim_pr_72_add-trustdomain-field-propagation/test-cases.md
```

## Supported PR Types

| PR Type | What It Generates |
|---------|-------------------|
| API Changes | Field tests for SpireServer, SpireAgent, etc. |
| Controller Changes | Reconciliation tests, operand verification |
| Config Propagation | Tests for config flow from main CR to operands |
| CRD Updates | Schema validation tests |
| Bug Fixes | Reproduction and verification tests |

## Prerequisites

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **oc CLI**: OpenShift CLI installed
- **Cluster Access**: Admin access to OpenShift cluster
- **OLM**: Operator Lifecycle Manager available (standard on OpenShift)

## Plugin Structure

```
ztwim/
├── .claude-plugin/
│   └── plugin.json           # Plugin metadata
├── commands/
│   ├── generate-from-pr.md   # Test case generation command
│   └── generate-execution-steps.md  # Execution steps command
├── skills/
│   └── test-case-generator/
│       └── SKILL.md          # ZTWIM templates and patterns
└── README.md
```

## Output Location

Generated files are saved to a directory named after the PR:
```
ztwim_pr_<number>_<short-description>/
├── test-cases.md
└── execution-steps.md
```

**Examples**:
| PR Title | Output Directory |
|----------|------------------|
| "Add trustDomain field to SpireServer" | `ztwim_pr_72_add-trustdomain-field-to-spireserver/` |
| "Fix must-gather scripts discovery" | `ztwim_pr_85_fix-must-gather-scripts-discovery/` |

## ZTWIM Test Setup Reference

Quick reference for setting up ZTWIM testing:

```bash
# 1. Install operator
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: zero-trust-workload-identity-manager
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: zero-trust-workload-identity-manager-og
  namespace: zero-trust-workload-identity-manager
spec:
  upgradeStrategy: Default
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-zero-trust-workload-identity-manager
  namespace: zero-trust-workload-identity-manager
spec:
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  name: openshift-zero-trust-workload-identity-manager
  channel: tech-preview-v0.2
EOF

# 2. Wait for operator
oc wait --for=condition=Available deployment -l app=zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s

# 3. Set environment
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}

# 4. Create all CRs
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: test01
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: cluster
spec:
  caSubject:
    commonName: $APP_DOMAIN
    country: "US"
    organization: "RH"
  jwtIssuer: https://$JWT_ISSUER_ENDPOINT
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireAgent
metadata:
  name: cluster
spec:
  nodeAttestor:
    k8sPSATEnabled: "true"
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpiffeCSIDriver
metadata:
  name: cluster
spec: {}
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireOIDCDiscoveryProvider
metadata:
  name: cluster
spec:
  jwtIssuer: https://$JWT_ISSUER_ENDPOINT
EOF
```

## Troubleshooting

### Command not found

If you see `Unknown slash command`, verify the symlinks are correct:
```bash
ls -la ~/.claude/commands/
```

Then restart Claude CLI:
```bash
# Exit current session (Ctrl+C or type 'exit')
claude
```

### ZTWIM Operator Not Available

Check if the operator is in the marketplace:
```bash
oc get packagemanifests -n openshift-marketplace | grep zero-trust
```

If not available, you may need to use a different catalog source or build from source.

## Related Links

- [ZTWIM Operator Repository](https://github.com/openshift/zero-trust-workload-identity-manager)
- [SPIFFE/SPIRE Documentation](https://spiffe.io/docs/)
- [OpenShift OLM Documentation](https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html)
