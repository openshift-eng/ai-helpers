# PR to OC Tests

Claude Code plugin that generates executable OpenShift `oc` test cases from GitHub Pull Requests.

## Overview

Automatically create comprehensive test cases from any GitHub PR. This plugin analyzes PR code changes—API types, CRDs, controllers—and generates ready-to-run `oc` commands for testing, including:

- Operator installation via OLM
- Environment setup
- Custom Resource creation
- Verification commands
- Cleanup procedures

## Features

### Skills

- **Test Case Generator** - Comprehensive analysis of PR code changes
  - Parses PR files to identify API types and CRDs
  - Generates OLM-based operator installation commands
  - Creates Custom Resource manifests based on PR changes
  - Produces verification and cleanup commands

### Commands

| Command | Description |
|---------|-------------|
| `/generate-from-pr <pr-url>` | Generate test cases with `oc` commands |
| `/generate-execution-steps <pr-url>` | Generate detailed execution steps |

## Installation

### Step 1: Create Claude commands directory

```bash
mkdir -p ~/.claude/commands
```

### Step 2: Link the command files

```bash
ln -s /path/to/pr-to-oc-tests/commands/generate-from-pr.md ~/.claude/commands/generate-from-pr.md
ln -s /path/to/pr-to-oc-tests/commands/generate-execution-steps.md ~/.claude/commands/generate-execution-steps.md
```

**Example** (adjust path to your location):
```bash
ln -s ~/ai-helpers/plugins/pr-to-oc-tests/commands/generate-from-pr.md ~/.claude/commands/generate-from-pr.md
ln -s ~/ai-helpers/plugins/pr-to-oc-tests/commands/generate-execution-steps.md ~/.claude/commands/generate-execution-steps.md
```

### Step 3: Verify installation

```bash
ls -la ~/.claude/commands/
# Should show:
# generate-from-pr.md -> /path/to/pr-to-oc-tests/commands/generate-from-pr.md
# generate-execution-steps.md -> /path/to/pr-to-oc-tests/commands/generate-execution-steps.md
```

## Usage

### Step 1: Start Claude Code CLI

```bash
claude
```

### Step 2: Run a command

**Generate test cases:**
```bash
/generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72
```

**Generate execution steps:**
```bash
/generate-execution-steps https://github.com/openshift/hypershift/pull/1234
```

### Non-Interactive Mode

Run directly from terminal without starting Claude:

```bash
claude --print "/generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72"
```

## Example Session

```
$ claude

╭─────────────────────────────────────────────────────────────╮
│ Claude Code                                                  │
╰─────────────────────────────────────────────────────────────╯

> /generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72

● Analyzing PR #72: "Add trustDomain field propagation"
● Reading PR description and files changed...
● Generating test cases...
● Output saved to: op_pr_add-trustdomain-field-propagation/test-cases.md
```

## Supported PR Types

| PR Type | What It Generates |
|---------|-------------------|
| API Changes | Field tests, validation tests |
| Controller Changes | Reconciliation tests, child resource verification |
| CRD Updates | Schema validation tests |
| Bug Fixes | Reproduction and verification tests |
| Config Changes | Propagation tests |

## Prerequisites

- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **oc CLI**: OpenShift CLI installed
- **Cluster Access**: Admin access to run generated commands

## Plugin Structure

```
pr-to-oc-tests/
├── .claude-plugin/
│   └── plugin.json           # Plugin metadata
├── commands/
│   ├── generate-from-pr.md   # Test case generation command
│   └── generate-execution-steps.md  # Execution steps command
├── skills/
│   └── test-case-generator/
│       └── SKILL.md          # Detailed templates and patterns
└── README.md
```

## Output Location

Generated files are saved to a directory named after the PR:
```
op_pr_<short-description>/
├── test-cases.md
└── execution-steps.md
```

**Examples**:
| PR Title | Output Directory |
|----------|------------------|
| "Add trustDomain field to SpireServer" | `op_pr_add-trustdomain-field-to-spireserver/` |
| "Fix must-gather scripts discovery" | `op_pr_fix-must-gather-scripts-discovery/` |
| "OCPBUGS-12345: Update reconcile logic" | `op_pr_update-reconcile-logic/` |

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

### GitHub CLI error

If you see `gh: command not found`, this is expected. The plugin uses browser tools to analyze PRs, not the GitHub CLI.
