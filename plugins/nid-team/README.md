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

### `/nid-team:sync-pr-dashboard`

Syncs the [NI&D PR Review](https://github.com/orgs/openshift/projects/28) GitHub Projects board. Populates PR Author, Area, and Author Type fields, syncs reviewer assignments to GitHub, adds shared repo and docs PRs, and uses AI to classify ambiguous areas.

### `/nid-team:nudge-prs` (experimental)

Sends automated reminder comments on high-priority assigned PRs that have had no human activity for a configurable number of days. This command is experimental and may be removed in the future.

