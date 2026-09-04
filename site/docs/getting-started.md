# Getting Started

AI Helpers is a marketplace of plugins for OpenShift engineering workflows.
Add the marketplace once, then install only the plugins you need.

## Codex

Add the marketplace:

```text
codex plugin marketplace add openshift-eng/ai-helpers
```

Install the recommended starter plugins:

```text
codex plugin add openshift-developer@ai-helpers
codex plugin add jira@ai-helpers
codex plugin add code-review@ai-helpers
```

Install any other plugin from this site with the same pattern:

```text
codex plugin add <plugin-name>@ai-helpers
```

## Claude Code

### Add the marketplace

```text
/plugin marketplace add openshift-eng/ai-helpers
```

### Browse plugins

Open the plugin manager to browse the catalog:

```text
/plugin
```

### Install a plugin

```text
/plugin install <plugin-name>@ai-helpers
```

For example:

```text
/plugin install jira@ai-helpers
```

### Update installed plugins

Refresh the catalog, then reinstall a plugin to pick up its current version:

```text
/plugin marketplace update ai-helpers
/plugin install <plugin-name>@ai-helpers
```

### Preview a branch

Before a marketplace change merges, add a fork and branch directly:

```text
/plugin marketplace add https://github.com/<user>/ai-helpers.git#<branch>
```
