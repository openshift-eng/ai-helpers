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

The plugin also exposes `sync-pr-dashboard` and `nudge-prs` as Codex skills.
Select either workflow from Codex's skill picker. The skills follow the same
command instructions and use the bundled scripts and shared team configuration.

### `/nid-team:sync-pr-dashboard`

Syncs the [NI&D PR Review](https://github.com/orgs/openshift/projects/28) GitHub Projects board. Populates PR Author, Area, and Author Type fields, syncs reviewer assignments to GitHub, adds shared repo and docs PRs, and uses AI to classify ambiguous areas.

Shared-repo discovery includes team authors, assignees, reviewers, and requested
reviewers. It tracks open PRs and merges from the last seven days so completed
reviews are accounted for between syncs. BGP Cloud Connector and its related
release CI changes use the **BGP** Area.
Shared-repo candidates also need component or linked team-issue evidence;
unrelated review requests stay off the board, and uncertain matches are
reported for AI review.

### `/nid-team:nudge-prs` (experimental)

Sends automated reminder comments on high-priority assigned PRs that have had no human activity for a configurable number of days. This command is experimental and may be removed in the future.

