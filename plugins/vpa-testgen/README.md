# VPA Test Generator Plugin

Generate E2E tests for VPA (Vertical Pod Autoscaler) operator from descriptions or PRs.

## Overview

This plugin automates the creation of Ginkgo-based E2E tests by analyzing text descriptions, bug/feature scenarios, or GitHub PRs for the VPA operator.

## Commands

| Command | Description |
|---------|-------------|
| `/vpa-testgen:generate-vpa-tests` | Generate E2E tests for VPA operator |

## Quick Start

```bash
# Generate tests from text description
/vpa-testgen:generate-vpa-tests VPA should handle pods with no resource requests

# Generate tests for a bug
/vpa-testgen:generate-vpa-tests Bug: VPA updater crashes when deployment has 0 replicas

# Generate tests from GitHub PR
/vpa-testgen:generate-vpa-tests https://github.com/openshift/vertical-pod-autoscaler-operator/pull/123

# With custom output directory
/vpa-testgen:generate-vpa-tests "VPA memory scaling" --output-dir ./test/e2e/vpa
```

## Features

- **Flexible Input**: Accepts text descriptions, bug/feature scenarios, or GitHub PR URLs
- **PR Analysis**: Analyzes PR changes for implementation context
- **Ginkgo Patterns**: Generates tests following OpenShift E2E conventions
- **VPA-Specific**: Includes VPA component patterns (recommender, updater, admission controller)
- **Ready to Use**: Output is structured for immediate integration

## Output Structure

```
.work/vpa-testgen/{scenario-name}/
├── {scenario}_test.go      # Main test file
├── helpers.go              # Test helpers (if needed)
└── README.md               # Test documentation
```

## Input Types

| Type | Example |
|------|---------|
| **Text description** | `VPA should scale memory correctly` |
| **Bug scenario** | `Bug: VPA crashes with empty containerPolicies` |
| **Feature scenario** | `Feature: VPA supports CronJob workloads` |
| **GitHub PR URL** | `https://github.com/openshift/.../pull/123` |

## Requirements

- `gh` CLI - For PR analysis (optional but recommended)

## Related Plugins

- [`openshift:new-e2e-test`](../openshift/README.md) - General OpenShift E2E test creation
- [`jira:generate-test-plan`](../jira/README.md) - Manual test plan generation
