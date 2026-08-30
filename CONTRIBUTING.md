# Contributing to ai-helpers

Thank you for your interest in contributing to the ai-helpers plugin marketplace for Claude Code.

## Adding a New Plugin

1. Create your plugin under `plugins/<plugin-name>/`
2. Add a `.claude-plugin/plugin.json` with name, version, description, and author
3. Add at least one command in `commands/`
4. Add an `OWNERS` file listing approvers and reviewers for your plugin
5. Register your plugin in `.claude-plugin/marketplace.json`
6. Run `make lint` to validate, then `make update` to regenerate site content

### OWNERS File

Every plugin must have an `OWNERS` file at its root. This controls who can approve PRs that touch the plugin. Example:

```yaml
approvers:
- ai-helpers-admins
- your-github-username
reviewers:
- ai-helpers-admins
- your-github-username
```

The `ai-helpers-admins` group should always be included. Add yourself and any co-maintainers.

### Approval Process

This repo uses Prow's `auto_approve_unowned_subfolders` — any collaborator can approve PRs for plugin directories. Protected directories (`.github`, `scripts`, `evals`, `images`, `tests`) require admin approval.

Run `make list-unprotected` to see which directories are open for contributions.

## Plugin Versioning Policy

All plugins use [semantic versioning](https://semver.org/):

- **PATCH** (0.0.x): Bug fixes, typo corrections, minor improvements
- **MINOR** (0.x.0): New commands, skills, hooks, or features
- **MAJOR** (x.0.0): Breaking changes to existing commands

If your PR modifies plugin code (commands, skills, hooks, or plugin.json), you **must** bump the version in that plugin's `plugins/<name>/.claude-plugin/plugin.json`. CI will fail if you forget. README.md and OWNERS changes do not require version bumps.

Bump **once per affected plugin per pull request**. Compare each modified plugin's `plugin.json` to the version on the pull request's **base branch tip** (not the merge-base). If this PR already bumped that plugin relative to the base tip, do not bump it again.

CI finds changed plugins from the merge-base among commands, skills, hooks, and plugin.json (files that only changed on the base branch do not count), then requires each of those versions to be higher than the base branch tip.

## Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. For each plugin whose commands, skills, hooks, or plugin.json you changed, bump its version once if it is not already higher than the base branch (skip if this PR already bumped it)
5. Run `make lint` to validate plugin structure
6. Run `make update` to regenerate site content
7. Submit a PR

### Testing locally

You can test plugins locally before submitting:

```
/plugin marketplace add <your-fork-url>
/plugin install <plugin>@<your-marketplace-name>
```

## Documentation Site

The marketplace website uses MkDocs Material and is published to GitHub Pages
from `.github/workflows/site.yml`. The plugin and category pages are generated
from `.claude-plugin/marketplace.json` and the plugin source trees.

Do not edit generated files under `site/docs/plugins/`,
`site/docs/categories/`, `site/docs/index.md`, or `site/mkdocs.yml`. Run
`make update` to regenerate them, `make site-build` for the same strict build
used in CI, or `make site-serve` to preview the site at
`http://127.0.0.1:8000/ai-helpers/`.

## Command Frontmatter

Each command `.md` file must start with YAML frontmatter between `---` markers:

```yaml
---
description: "Brief description of what the command does"
argument-hint: "<required-arg> [optional-arg] [--flag <value>]"
example: "/plugin:command arg1 arg2 --flag value"
---
```

| Field | Required | Description |
|-------|----------|-------------|
| `description` | Yes | Brief description of the command |
| `argument-hint` | Yes | Shows expected arguments |
| `example` | No | A real-world invocation example |

## Code Review

All PRs require review before merging. Reviewers will check:
- Plugin structure follows conventions (use `make lint`)
- Version is bumped appropriately for code changes
- OWNERS file is present with appropriate approvers
- Commands have proper frontmatter
- No sensitive information is included

## Getting Help

If you have questions:
- Check existing plugins for examples
- Review the [Claude Code plugin documentation](https://docs.anthropic.com/en/docs/claude-code/plugins)
- Open an issue for discussion
