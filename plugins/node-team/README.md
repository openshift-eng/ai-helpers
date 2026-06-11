# Node Team Plugin

An OpenShift Node team assistant for development, deployment, debugging, and workflow tasks across the node layer — kubelet, MCO, CRI-O, crun, conmonrs, the Kueue operator, Jira, Red Hat KB/support cases, Prometheus, and platform docs.

This plugin is the team's umbrella: a hierarchical overview of how the Node team works, routing specialized work to dedicated plugins (e.g. CVE triage → [`node-cve`](../node-cve/)) rather than duplicating them. Over time it will absorb the team's onboarding docs, making it the starting point for understanding what the team does and which tool to use for what.

## Installation

```bash
/plugin install node-team@ai-helpers
```

## Skill

### `node`

A single skill that activates on any OpenShift node-layer task. It routes through a set of reference documents that capture tribal knowledge and non-obvious nuances rather than discoverable details (which Claude reads from source directly).

The skill starts at [`skills/node/references/INDEX.md`](skills/node/references/INDEX.md), which maps topics to the relevant reference:

- **Setup** — environment and access prerequisites (`SETUP.md`)
- **Development** — per-component dev notes for kubelet, MCO, CRI-O, crun/conmon, the Kueue operator, and git worktrees
- **Deployment** — deploying debug binaries to RHCOS nodes (cross-compile, SSH bastion, bind-mount deploy, rollback)
- **Jira** — Red Hat Jira REST API reference (auth, endpoints, ADF, custom fields, JQL recipes, OCPNODE/OCPBUGS triage)
- **Red Hat Support** — KB articles and support cases (`support.md`)
- **Platform Documentation** — version-aware Kubernetes and OpenShift docs lookup (`platform-docs.md`)
- **Prometheus** — node-layer metrics queries (`prometheus.md`)

## Configuration

Jira access uses a token from the `JIRA_API_TOKEN` environment variable or the macOS Keychain. See [`skills/node/references/jira.md`](skills/node/references/jira.md) for details.

Team rosters are maintained as `team-roster-*.json` attachments on the Jira config issue `OCPNODE-4230` (override with the `NODE_ASSISTANT_CONFIG_ISSUE` environment variable) and synced to `~/.node-assistant/`; see the Team Roster section of [`jira.md`](skills/node/references/jira.md).
