# Node Team Plugin

An OpenShift Node team assistant for development, deployment, debugging, and workflow tasks across the node layer: kubelet, MCO, CRI-O, crun, conmonrs, the Kueue operator, Jira, Red Hat KB/support cases, Prometheus, and platform docs.

This plugin is the team's umbrella: it owns canonical shared data (component lists, repo mappings, version tables) and routes specialized work to dedicated plugins rather than duplicating them. Specialized plugins like [`node-cve`](../node-cve/) reference the shared data here instead of maintaining parallel copies.

## Installation

```bash
/plugin install node-team@ai-helpers
```

## Shared Data

The `skills/node/references/shared/` directory contains canonical data used by
all Node team plugins:

- **[components.md](skills/node/references/shared/components.md)**: full component list, downstream fork mappings, branch patterns, pscomponent labels, sub-teams
- **[version-map.md](skills/node/references/shared/version-map.md)**: OCP-to-K8s/CRI-O version formula, branch naming conventions

Other plugins (e.g. `node-cve`) reference these files instead of maintaining
their own copies. When component ownership or version mappings change, update
the shared files here.

## Commands

### `node-team:overview`

Shows team component ownership, repos, sub-teams, sprint info, and which specialized plugins handle which domain.

### `node-team:setup`

Clones a Node team repo and sets up a git worktree for development, optionally tied to a Jira ticket or PR.

### `node-team:preflight`

Tests all authentication tokens (GitHub, Jira) and CLI tools required by Node team workflows in a single pass. Run before `setup` or `node-cve:triage` to catch expired or missing credentials early.

## Skill

### `node`

Activates on any OpenShift node-layer task. Routes through reference documents that capture tribal knowledge and non-obvious nuances. Starts at [`skills/node/references/INDEX.md`](skills/node/references/INDEX.md):

- **Shared Data**: canonical component/version data for all Node plugins
- **Setup**: environment and access prerequisites
- **Development**: per-component dev notes for kubelet, MCO, CRI-O, crun/conmon, the Kueue operator, and git worktrees
- **Deployment**: deploying debug binaries to RHCOS nodes (cross-compile, SSH bastion, bind-mount deploy, rollback)
- **Jira**: Red Hat Jira REST API reference (auth, endpoints, ADF, custom fields, JQL recipes, OCPNODE/OCPBUGS triage)
- **Red Hat Support**: KB articles and support cases
- **Platform Documentation**: version-aware Kubernetes and OpenShift docs lookup
- **Prometheus**: node-layer metrics queries

## Plugin Routing

| Domain | Plugin | Command |
|--------|--------|---------|
| CVE triage | `node-cve` | `/node-cve:triage` |
| General development | `node-team` | `node-team:node` skill |
| Team overview | `node-team` | `/node-team:overview` |
| Repo setup | `node-team` | `/node-team:setup` |
| Auth verification | `node-team` | `/node-team:preflight` |

## Configuration

Jira access uses a token from `JIRA_API_TOKEN` or the macOS Keychain. See [`jira.md`](skills/node/references/jira.md) for details.

Team rosters are maintained as `team-roster-*.json` attachments on the Jira config issue `OCPNODE-4230`. Override with the `NODE_ASSISTANT_CONFIG_ISSUE` environment variable. Synced to `~/.node-assistant/`; see the Team Roster section of [`jira.md`](skills/node/references/jira.md).
