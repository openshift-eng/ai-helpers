# bug-triage

AI-powered bug triage for OpenShift teams. Analyzes untriaged OCPBUGS issues and posts structured triage comments directly on each Jira issue before bug scrub meetings.

## Commands

| Command | Description |
|---------|-------------|
| `/bug-triage:scrub` | Analyze untriaged bugs for a team and post AI triage comments |

## How It Works

1. Looks up the team's components and repos from `team_component_map.json` (via the `teams` plugin)
2. Queries OCPBUGS for untriaged bugs under those components
3. Groups CVE trackers and ART Bot issues into clusters
4. Analyzes each bug: sub-area, routing, importance, bug vs RFE, duplicates, related context
5. Posts a structured triage comment on each issue with a confidence score
6. Adds an idempotency label to prevent double-commenting

## Quick Start

```bash
# Basic triage (any team)
/bug-triage:scrub --team "Network Ingress and DNS" --since last-week

# With team-specific docs for richer analysis
/bug-triage:scrub --team "Network Ingress and DNS" --team-docs ~/network-edge-tools/plugins/nid/team-docs

# Single issue (demo/testing)
/bug-triage:scrub --team "Core Networking" --issue OCPBUGS-83283 --dry-run
```

## Team Documentation

Teams can provide optional documentation files for richer triage analysis. See `reference/team-docs-spec.md` for the full specification.

```text
team-docs/
├── sub-areas.md        # Sub-area taxonomy (enables detailed classification)
├── routing-guide.md    # Misrouting detection keywords
└── context/            # FAQs, AGENTS.md copies, dev guides
```

## Prerequisites

- `jira` CLI ([ankitpokhrel/jira-cli](https://github.com/ankitpokhrel/jira-cli)) installed and authenticated
- `gh` CLI for GitHub PR discovery (optional but recommended)
- OCPBUGS project access (view, comment, edit labels)
