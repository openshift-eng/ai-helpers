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
- **[team-info.md](skills/node/references/shared/team-info.md)**: mission, ceremonies, channels, key links, plugin routing

Other plugins (e.g. `node-cve`) reference these files instead of maintaining
their own copies. When component ownership or version mappings change, update
the shared files here.

## Commands

### `node-team:overview`

Shows team component ownership, repos, sub-teams, sprint info, and which specialized plugins handle which domain. Also syncs the team roster cache in `~/.node-assistant/`.

### `node-team:setup`

Clones a Node team repo and sets up a git worktree for development, optionally tied to a Jira ticket or PR.

### `node-team:preflight`

Tests all authentication tokens (GitHub, Jira) and CLI tools required by Node team workflows in a single pass. Run before `setup`, `node-cve:triage`, or `node-bug:triage` to catch expired or missing credentials early.

### `node-team:cleanup`

Purges cached artifacts produced by Node team plugins: triage reports, cloned repos, dist-git clones, Vagrant VMs, and roster cache. Onboarding progress and the node-cve posting audit log are kept unless confirmed separately.

## Skill

### `node`

Activates on any OpenShift node-layer task. Routes through reference documents that capture tribal knowledge and non-obvious nuances. Starts at [`skills/node/references/INDEX.md`](skills/node/references/INDEX.md):

- **Shared Data**: canonical component/version data for all Node plugins
- **Setup**: environment and access prerequisites
- **Development**: per-component dev notes for kubelet, MCO, CRI-O, crun/conmon, the Kueue operator, and git worktrees
- **Deployment**: deploying debug binaries to RHCOS nodes (cross-compile, SSH bastion, drop-in or bind-mount deploy, rollback)
- **Jira**: Red Hat Jira REST API reference (auth, endpoints, ADF, custom fields, JQL recipes, OCPNODE/OCPBUGS triage)
- **Red Hat Support**: KB articles and support cases
- **Platform Documentation**: version-aware Kubernetes and OpenShift docs lookup
- **Prometheus**: node-layer metrics queries

## Plugin Family

node-team is the umbrella plugin for the OpenShift Node team. Specialized
plugins depend on node-team's shared data and extend its capabilities:

| Plugin | Domain | Status |
|--------|--------|--------|
| `node-team` | Development, deployment, debugging (see [Commands](#commands)) | Active |
| [`node-cve`](../node-cve/) | CVE triage with reachability analysis | Active |
| [`node-bug`](../node-bug/) | General bug triage and assignment | Active |
| [`node-onboarding`](../node-onboarding/) | Team onboarding workflows | Active |
| [`node-rpm`](../node-rpm/) | RPM management (cri-tools pattern) | Active |

### Shared Data Contract

Satellite plugins reference shared data at `skills/node/references/shared/`.
Do not move or rename these files without updating all consumer plugins.

Relative links from a satellite plugin into this one only resolve in a repo
checkout. Installed plugins live in versioned cache directories, so consumers
locate the files in one of these ways:

- repo checkout: `plugins/node-team/skills/node/references/`
- installed: `"${CLAUDE_PLUGIN_ROOT}"/../../node-team/*/skills/node/references/`
  (from the satellite plugin's root)
- or by invoking the `node-team:node` skill and reading from its base directory

### Compliance

Compliance documentation for the Node team plugin family is at
[`docs/compliance/`](docs/compliance/). This covers the medium-risk AI agent
controls required by Red Hat's Enterprise AI Risk Management Standard.

## Configuration

| Variable | Purpose |
|----------|---------|
| `JIRA_API_TOKEN` | Jira API token. Falls back to the macOS Keychain item `JIRA_API_TOKEN` or Linux `secret-tool lookup service redhat key JIRA_API_TOKEN` |
| `JIRA_USER` | Jira account email. Falls back to `JIRA_EMAIL`, the Keychain item's account, then `git config user.email` |
| `JIRA_EMAIL` | Alternative name for `JIRA_USER` (used when `JIRA_USER` is unset) |
| `RH_API_OFFLINE_TOKEN` | Red Hat API offline token for KB and support case lookups (keychain or secret-tool, see [`support.md`](skills/node/references/support.md)) |
| `NODE_ASSISTANT_CONFIG_ISSUE` | Jira issue holding the roster attachments. Default `OCPNODE-4230` |

See [`jira.md`](skills/node/references/jira.md) for the authentication chain. Tokens are passed to curl on stdin, never on the command line.

Team rosters are maintained as `team-roster-*.json` attachments on the Jira config issue `OCPNODE-4230`. Override with the `NODE_ASSISTANT_CONFIG_ISSUE` environment variable. `/node-team:overview` syncs them to `~/.node-assistant/`; see the Team Roster section of [`jira.md`](skills/node/references/jira.md).
