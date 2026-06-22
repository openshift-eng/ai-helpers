# openshift-developer

Executable workflows for OpenShift development.

These workflows are meant to be a common engine for different consumption models: 

- Developer's laptop
- Shared infrastructure like Prow for the OCPBUG autofix platform
- Slack chai-bot

 Each skill and command is a self-contained unit of work that any of these environments can invoke identically.

## Common workflows

### Pre-PR (author loop)

1. `/jira:solve` — Pick up a Jira issue, analyze it, implement the fix.
2. `/code-review:pre-commit-review` — Run a code review on the local changes before pushing.
3. `/openshift-developer:address-review-precommit` — Apply the review findings, run verification, commit, and push.

### Post-PR (review loop)

1. `/code-review:pr` — Review an open PR for correctness and improvements.
2. `/openshift-developer:address-review-pr` — Fetch reviewer comments, categorize by priority, make code changes, post replies, and push.

Repeat steps 4-5 until the PR is approved.

## What's included

### Plugins

- `jira` — Jira automation
- `ci` — OpenShift CI / Prow job analysis
- `golang` — Go development tools
- `prodsec-skills` — Product security skills
- `git` — Git workflow automation and utilities

### Skills

- **jira:solve** — Pick up a Jira issue, analyze it, implement the fix, and open a PR. (via `jira` plugin)
- **git:git-commit-format** — Conventional commit formatting rules: types, scopes, required footers (Signed-off-by, Commit-Message-Assisted-by), and gitlint validation. (via `git` plugin)
- **code-review:pre-commit-review** — Run a code review on local changes before pushing. (via `code-review` plugin)
- **address-review-precommit** — Fix code review findings in the current branch before committing: applies fixes, runs verification, and pushes.
- **code-review:pr** — Review an open PR for correctness and improvements. (via `code-review` plugin)
- **address-review-pr** — Fetch and address all PR review comments: categorizes by priority, makes code changes, posts replies, and pushes.

### Hooks

- **ensure-precommit** — On `SessionStart`, installs pre-commit and pre-push hooks via `pre-commit` if the repo has a `.pre-commit-config.yaml`. Fails if `pre-commit` is not installed. Every commit and push is then gated by the repo's hooks at zero ongoing token cost.

### MCP Servers

- **atlassian** — Atlassian MCP server (`https://mcp.atlassian.com/v1/mcp`)

## Prerequisites

- `pre-commit` — hook manager (`pip install pre-commit` or `brew install pre-commit`)
- `gitlint` — commit message linter (`pip install gitlint`)
- `gopls` — Go language server (`go install golang.org/x/tools/gopls@latest`)
- `gh` — GitHub CLI, authenticated (`brew install gh`)

## Installation

Add the marketplaces (one-time):

```sh
claude plugin marketplace add openshift-eng/ai-helpers
claude plugin marketplace add RedHatProductSecurity/prodsec-skills
```

Install the bundle:

```sh
claude plugin install openshift-developer@ai-helpers
```

## Note for non-Claude Code editors

This bundle can also be installed via APM with `--target`:

```sh
apm install openshift-eng/ai-helpers/plugins/openshift-developer --global --target cursor
```

