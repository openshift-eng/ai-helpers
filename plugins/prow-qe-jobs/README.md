# prow-qe-jobs Plugin

Plugin for listing and managing OpenShift QE Prow jobs, specifically focusing on upgrade-related test configurations.

## Commands

### `/prow-qe-jobs:list-qe-jobs`

Extracts and lists upgrade jobs from the openshift-tests-private CI operator configurations.

**Usage:**
```bash
# List all upgrade jobs
/prow-qe-jobs:list-qe-jobs

# Filter by platform
/prow-qe-jobs:list-qe-jobs gcp

# Filter by version
/prow-qe-jobs:list-qe-jobs 4.15

# Filter by upgrade type
/prow-qe-jobs:list-qe-jobs micro
```

**What it does:**
- Fetches CI configuration files from `https://github.com/openshift/release/tree/master/ci-operator/config/openshift/openshift-tests-private`
- Parses YAML files to identify upgrade-related jobs
- Displays job names with relevant metadata
- Supports optional filtering by pattern

## Installation

```bash
# Add the marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install prow-qe-jobs@ai-helpers
```

## Use Cases

- Quickly identify all QE upgrade jobs for a specific platform
- Find upgrade jobs for a particular OpenShift version
- Discover available upgrade test types (micro, minor, CI upgrades)
- Get an overview of the upgrade testing matrix

## Requirements

- Network access to fetch configurations from GitHub
- YAML parsing capabilities (handled automatically by Claude Code)

## Contributing

See [CLAUDE.md](../../CLAUDE.md) for contribution guidelines.
