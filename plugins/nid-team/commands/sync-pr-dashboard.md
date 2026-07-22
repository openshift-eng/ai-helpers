---
description: Sync the NI&D GitHub Project board — populate PR authors, sync reviewers to assignees, add shared repo PRs, classify areas
argument-hint: ""
---

## Name

nid-team:sync-pr-dashboard

## Synopsis

```bash
/nid-team:sync-pr-dashboard
```

## Description

Syncs the NI&D PR Review GitHub Project board (https://github.com/orgs/openshift/projects/28). Runs a script for deterministic operations, then uses AI to classify ambiguous PR areas.

## Prerequisites

- GitHub CLI (`gh`) authenticated with `read:project` and `project` scopes
- Access to the openshift org

## Implementation

### Step 1: Run the sync script

Run `~/.claude/commands/sync-pr-dashboard.sh` (or `plugins/nid-team/scripts/pr-dashboard/sync-dashboard.sh`).

This handles:
- **PR Author** — Populates blank "PR Author" fields with display names
- **Reviewer Sync** — When Primary or Secondary Reviewer is set, comments `/assign @user` on the PR if not already assigned
- **Shared Repo PRs** — Adds team-authored PRs from shared repos (defined in `config.sh`)
- **Area (deterministic)** — Sets Area for repos with obvious mappings (defined in `REPO_TO_AREA` in `config.sh`)

### Step 2: Classify ambiguous PR areas with AI

After the script completes, run the helper script to get structured data on unclassified items:

```bash
~/.claude/commands/list-unclassified-areas.sh
```

This outputs each unclassified item with its item ID, repo, PR number, title, URL, and changed files.

For each item in the output, classify into one of these areas based on the title and changed files:

| Area | Option ID | Signals |
|---|---|---|
| **GWAPI** | `196a759b` | Files in `pkg/operator/controller/gateway*`, `pkg/operator/controller/gatewayclass*`, title mentions gateway/istio/sail/GWAPI/noOLM, api changes to gateway fields |
| **Router** | `667048b1` | Files in `pkg/operator/controller/ingress*`, router template changes, HAProxy config, route-controller-manager, IngressController API changes |
| **DNS** | `c2935ddd` | DNS-related api changes, coredns plugins |
| **ExDNS** | `b02c7810` | External DNS related changes |
| **ALBO** | `a6184328` | ALB related changes |
| **Misc** | `1ec39a5b` | OWNERS file updates, CI/Prow config, AGENTS.md, coderabbit config, repo meta, go bumps that span areas, docs that don't fit another area |
| **AI** | `9f9c29ab` | ai-helpers plugin PRs, MCP server tooling, Claude Code skills and agents |

4. Set the Area field:
```bash
gh project item-edit --project-id PVT_kwDOAAwXEc4BbxeH --id {item_id} --field-id PVTSSF_lADOAAwXEc4BbxeHzhW9Lxw --single-select-option-id {area_option_id}
```

5. Print what was classified: `SET AREA: repo#number → Area (reason)`

If the PR is clearly meta/repo-maintenance (OWNERS, CI config, go bumps spanning areas), use **Misc**. For feature/bug PRs that are ambiguous, default to **Router**.

### Step 3: Report summary

After the script and AI classification complete, output a summary table of all changes made during this sync. Use clickable markdown links for each PR. Group by operation type:

**Example output format:**

### Sync Summary

| Operation | PR | Detail |
|---|---|---|
| PR Author | [CIO#1503](https://github.com/openshift/cluster-ingress-operator/pull/1503) | → Ishmam A. |
| Shared PR Added | [release#81764](https://github.com/openshift/release/pull/81764) | by rhamini3 |
| Reviewer Assigned | [images#242](https://github.com/openshift/images/pull/242) | → @candita |
| Area (script) | [CDO#482](https://github.com/openshift/cluster-dns-operator/pull/482) | → DNS |
| Area (AI) | [CIO#1503](https://github.com/openshift/cluster-ingress-operator/pull/1503) | → GWAPI |
| Author Type | [CIO#1503](https://github.com/openshift/cluster-ingress-operator/pull/1503) | → Team |
| Jira Priority | [CDO#482](https://github.com/openshift/cluster-dns-operator/pull/482) | → High |

If nothing changed for an operation, omit it from the table.

If there were any reviewer assignments (including "Other") during this sync, also output a **PR Scrub Assignments** section in markdown bullet list format with clickable links and PR titles. Use this format:

**PR Scrub Assignments**

- [CIO#1456 — OCPBUGS-98310: Bump sail-operator install library to OSSM 3.4.0](https://github.com/openshift/cluster-ingress-operator/pull/1456) → @rikatz, @rhamini3
- [CIO#1469 — OCPBUGS-88353: Ensure canary cert matches the default ingress controller's cert](https://github.com/openshift/cluster-ingress-operator/pull/1469) → @bentito

Get the full PR title from the script output or via `gh pr view`. For "Other" assignments, show "→ Other" instead of a username.

End with instructions: "Use `/copy` to copy the assignments above and paste into the PR Scrub doc."

End with:

Dashboard: https://github.com/orgs/openshift/projects/28

## Examples

```bash
/nid-team:sync-pr-dashboard
```

## Notes

- The script and AI classification are both idempotent
- Only sets fields that are currently blank; does not overwrite existing values
- Reviewer sync uses Prow `/assign` comments (not GitHub API) due to org permissions
- AI classification only runs on PRs from ambiguous repos that don't have Area set
