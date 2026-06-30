# Node Onboarding Plugin

Interactive onboarding for new OpenShift Node team members. Replaces the
manual Google Doc walkthrough with a guided checklist that validates access,
tracks progress, and provides step-by-step instructions.

Part of the [node-team plugin family](../node-team/).

## Installation

```bash
/plugin install node-onboarding@ai-helpers
```

Requires `node-team` (installed automatically as a dependency).

## Commands

### `node-onboarding:checklist`

Interactive onboarding workflow that guides through access setup, tool
installation, and environment configuration. Supports dev and QE tracks.

```bash
# Start onboarding (dev track, default)
/node-onboarding:checklist

# QE-specific onboarding
/node-onboarding:checklist --track qe

# Resume from where you left off
/node-onboarding:checklist --resume

# Run automated checks only (no prompts)
/node-onboarding:checklist --check-only
```

#### What it covers

- Prerequisites (VPN, Jira, ServiceNow)
- Access and permissions (LDAP groups, Google Groups, Slack, calendars)
- GCP access (openshift-gce-devel)
- IDE license (GoLand)
- GitHub setup (openshift org membership)
- Jira Dashboard access
- Development environment (Go, kubectl, oc, repo cloning)
- Cluster creation (ClusterBot, AWS, GCP)
- Customer support readiness (SupportShell, yank, omc)
- QE-specific setup (when `--track qe`)

#### Progress tracking

Progress is saved to `~/.node-assistant/onboarding-progress.json`. Use
`--resume` to pick up where you left off. Delete the progress file to
start fresh.

### `node-onboarding:resources`

Prints categorized bookmarks for day-to-day Node team work: Jira boards,
Slack channels, documentation, upstream meetings, and support portals.

```bash
/node-onboarding:resources
```

## Prerequisites

- GitHub CLI (`gh`) for automated access checks
- Optional: `JIRA_API_TOKEN` for Jira validation checks
