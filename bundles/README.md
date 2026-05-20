# Bundles

Bundles are curated sets of APM packages for common workflows. Each bundle is a
subdirectory with an `apm.yml` that lists dependencies — install one bundle and
get everything you need for that workflow.

## Available Bundles

| Bundle | Description |
|--------|-------------|
| [openshift-developer](openshift-developer/) | Skills and tools for any OpenShift engineer |

## Prerequisites

Some plugins in these bundles depend on plugins from the
`anthropics/claude-plugins-official` marketplace. Register it before
installing:

```sh
apm marketplace add anthropics/claude-plugins-official
```

## Usage

### Global install (recommended for personal dev environments)

Create `~/.apm/apm.yml` if it doesn't exist, then add the bundle as a
dependency:

```yaml
# ~/.apm/apm.yml
name: my-global-config
version: 1.0.0

dependencies:
  apm:
    - openshift-eng/ai-helpers/bundles/openshift-developer
```

Then install globally:

```sh
apm install --global
```

This installs all the skills, plugins, and MCP servers from the bundle into your
user-level configuration, available in every project.

### Project-scoped install

Add the bundle to your project's `apm.yml`:

```yaml
# apm.yml
name: my-project
version: 1.0.0

dependencies:
  apm:
    - openshift-eng/ai-helpers/bundles/openshift-developer
```

Then:

```sh
apm install
```

## Creating a new bundle

1. Create a subdirectory under `bundles/` with your bundle name
2. Add an `apm.yml` with `name`, `version`, `description`, and `dependencies`
3. Reference packages from this repo using virtual paths
   (e.g., `openshift-eng/ai-helpers/plugins/jira`) or any other APM package

Example:

```yaml
name: my-bundle
version: 1.0.0
description: A curated set of tools for my workflow.

dependencies:
  apm:
    - openshift-eng/ai-helpers/plugins/jira
    - openshift-eng/ai-helpers/plugins/ci
  mcp:
    - name: some-mcp-server
      transport: stdio
```
