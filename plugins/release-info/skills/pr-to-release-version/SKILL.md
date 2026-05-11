---
name: PR to Release Version
description: "Traces a GitHub PR to the first OCP z-stream release that shipped it. Auto-applies when asked which release contains a PR, when a PR or commit shipped, or to find a PR in a z-stream payload."
---

# PR to Release Version

Determines which OCP z-stream release first shipped a given GitHub PR. Works for PRs from any repo that ships a component in the OCP release payload.

## When to Use This Skill

This skill automatically applies when:
- Asked which OCP release contains a specific PR
- Asked when a PR or commit was shipped
- Tracing a bug fix to a z-stream release
- Checking if a PR landed in a specific OCP version

## How to Run

Run the script at `${CLAUDE_PLUGIN_ROOT}/skills/pr-to-release-version/pr-to-release-version.sh`:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/pr-to-release-version/pr-to-release-version.sh" <pr-url-or-number> <minor-version> [--repo <org/repo>]
```

### Examples

```bash
# Full PR URL (repo extracted automatically)
bash "${CLAUDE_PLUGIN_ROOT}/skills/pr-to-release-version/pr-to-release-version.sh" https://github.com/openshift/hypershift/pull/7685 4.21

# PR number with explicit repo
bash "${CLAUDE_PLUGIN_ROOT}/skills/pr-to-release-version/pr-to-release-version.sh" 7685 4.21 --repo openshift/hypershift

# Different repo
bash "${CLAUDE_PLUGIN_ROOT}/skills/pr-to-release-version/pr-to-release-version.sh" https://github.com/openshift/cluster-kube-apiserver-operator/pull/1893 4.17
```

### Input

- **PR**: A GitHub PR URL or number. If using a number, `--repo` is required.
- **Minor version**: The user must provide the target OCP minor version (e.g., `4.17`). If not provided, ask for it before running. A PR can ship in multiple streams via cherrypicks, so this cannot be inferred.

### Output

The script prints a structured result to stdout and progress to stderr:

```text
PR: #7685 (OCPBUGS-76447: Add UserAgent telemetry to CPO Azure SDK clients)
Merged: 2026-04-28 to release-4.21
Component: hypershift
First z-stream: 4.21.13
Payload commit: 6202ab927f91ca188e621b62c802d8f3e5de1c48
Verification: https://github.com/openshift/hypershift/compare/6202ab92...6202ab92
```

Report the result to the user. If the script exits with an error, report the error message.

### Prerequisites

The script requires `oc`, `gh` (authenticated), `jq`, and `curl`. It also needs a pull secret with access to `quay.io/openshift-release-dev`. The script auto-discovers pull secrets from: `$PULL_SECRET`, `~/pull-secret.txt`, `~/pull-secret.json`, `~/.docker/config.json`, `$XDG_RUNTIME_DIR/containers/auth.json`, `~/.config/containers/auth.json`.

### How It Works

1. Gets the PR merge commit via `gh pr view`
2. Maps the repo to an OCP payload component using `oc adm release info` image annotations
3. Binary searches across accepted z-streams (~6 iterations for ~60 releases) using `gh api compare` to find the first z-stream that includes the merge commit
