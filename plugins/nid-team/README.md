# NI&D Team Plugin

Development and workflow tools for the Network Ingress & DNS team.

## Prerequisites

- GitHub CLI (`gh`) authenticated with `read:project` and `project` scopes
- `acli` CLI for Jira access

## Installation

Add to your Claude Code settings:

```json
{
  "enabledPlugins": {
    "nid-team@ai-helpers": true
  }
}
```

## Commands

The plugin also exposes `sync-pr-dashboard`, `nudge-prs`, and `rebase-manager` as skills.
Select a workflow from the skill picker. The skills follow the same
command instructions and use the bundled scripts and shared team configuration.

### `/nid-team:sync-pr-dashboard`

Syncs the [NI&D PR Review](https://github.com/orgs/openshift/projects/28) GitHub Projects board. Populates PR Author, Area, and Author Type fields, syncs reviewer assignments to GitHub, adds shared repo and docs PRs, and uses AI to classify ambiguous areas.

Shared-repo discovery includes team authors, assignees, and actual reviewers.
GitHub review requests never qualify a PR for inclusion.
It tracks open PRs and merges from the last seven days so completed
reviews are accounted for between syncs. BGP Cloud Connector and its related
release CI changes use the **BGP** Area.

### `/nid-team:nudge-prs` (experimental)

Sends automated reminder comments on high-priority assigned PRs that have had no human activity for a configurable number of days. This command is experimental and may be removed in the future.

### `/nid-team:rebase-manager`

Plan and resume an upstream-to-downstream fork rebase, inspect carry decisions,
record validation at the candidate revision, and manage draft PR feedback.
Install the **openshift** plugin too: its shared `rebase` skill owns rebase
mechanics. The NI&D helper tracks local state and evidence; the agent performs
analysis, edits, and review.

A new bare invocation produces a plan. Explicit stages include `plan`, `apply`,
`validate`, `draft`, `review`, and `status`; reuse `--state-dir` to resume. State
stays outside the target checkout. A draft may obtain pending CI evidence, while
readiness requires current passing checks and resolved feedback. Humans retain
readiness and merge decisions. This workflow is manually invoked and does not
schedule runs or post replies without explicit authorization.

See the [manager skill](skills/rebase-manager/SKILL.md) and
[state helper workflow](rebase/WORKFLOW.md) for the artifact and recovery contracts.
