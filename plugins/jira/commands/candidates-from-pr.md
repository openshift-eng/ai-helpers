---
description: Given a GitHub PR, find candidate open Jira issues (matching component and target release) that the PR may fix
argument-hint: "<pr-url-or-number> [--repo <org/repo>] [--project <key>] [--target-release <version>] [--component <name>] [--limit <N>] [--min-score <0-100>] [--include-explicit] [--output text|json]"
---

## Name
jira:candidates-from-pr

## Synopsis
```
/jira:candidates-from-pr <pr-url-or-number> [options]
```

## Description

The `jira:candidates-from-pr` command takes a GitHub Pull Request and produces a ranked list of **open Jira issues that the PR may fix**, scoped by component and target release. It is intended for triage workflows where a PR was opened without an explicit Jira reference (or with an incomplete one) and a maintainer needs to decide which open bugs/stories the PR actually closes.

This is the inverse direction of `jira:extract-prs` (which goes Jira → PRs). Here the input is a PR and the output is a candidate set of Jiras with a confidence score and matched signals.

### What it does

1. **Fetches the PR** (title, body, labels, commits, file paths, and diff hunks).
2. **Extracts already-referenced Jira keys** from the PR title, body, commits, and branch name (e.g. `OCPBUGS-12345`, `SDN-1234`). These are validated and reported separately as "explicitly referenced" — by default they are **not** re-evaluated as candidates unless `--include-explicit` is passed.
3. **Derives triage signals** from the PR:
   - **Component(s)**: inferred from changed file paths and the repository (e.g. `openshift/ovn-kubernetes` → component `Networking / ovn-kubernetes`). The user can override with `--component`.
   - **Target release**: inferred from the PR's base branch (e.g. `release-4.18` → `4.18`, `main` → the current development version). The user can override with `--target-release`.
   - **Keywords/symbols**: function names, error strings, log messages, CLI flags, CRD/API field names touched by the diff.
4. **Queries open Jiras** via JQL, filtered by project, component, target release / fix version, and `statusCategory != Done`.
5. **Scores each candidate** by semantic match against the PR signals (symbol overlap, error-string match, keyword/title overlap, component agreement, recent activity). Each score includes a 1-2 sentence rationale and the matched signals.
6. **Outputs a ranked list** of candidates above `--min-score` (default `40`), capped at `--limit` (default `10`).

### What it does not do

- Does **not** modify any Jira issue, post comments, or link the PR. It is a read-only triage helper.
- Does **not** create new Jira issues. Use `/utils:process-renovate-pr` or `/jira:create` for creation.
- Does **not** replace human judgement. Confidence scores are advisory; a maintainer must confirm the link.

## Prerequisites

- `gh` CLI installed and authenticated with read access to the PR's repository.
- Jira MCP server configured (see `plugins/jira/README.md`).
- `jq` installed for JSON processing.

## Implementation

Load the skill file for detailed implementation guidance:

```text
plugins/jira/skills/candidates-from-pr/SKILL.md
```

### Process Flow

1. **Parse arguments**:
   - `$1` is required: a PR URL (`https://github.com/<org>/<repo>/pull/<n>`) or a PR number (in which case `--repo` must also be given).
   - Parse optional flags: `--repo`, `--project`, `--target-release`, `--component`, `--limit`, `--min-score`, `--include-explicit`, `--output`.
   - Defaults: `--limit 10`, `--min-score 40`, `--output text`.

2. **Fetch PR data**:
   ```bash
   gh pr view <number> --repo <org>/<repo> \
     --json number,url,title,body,headRefName,baseRefName,labels,author,commits,files
   gh pr diff <number> --repo <org>/<repo>
   ```

3. **Extract explicitly referenced Jira keys**:
   - Regex `\b[A-Z][A-Z0-9_]+-[0-9]+\b` against title, body, commit messages, and `headRefName`.
   - Validate each via `mcp__atlassian__jira_get_issue` (fields: `summary,status,issuetype,components,fixVersions,customfield_10855`).
   - Report these in a separate "Explicit references" block.

4. **Derive component**:
   - If `--component` provided, use it directly.
   - Otherwise, map repo + changed paths to component(s) using `plugins/teams/skills/list-components` or the `team_component_map.json` lookup. For OpenShift repos, default mappings include:
     - `openshift/ovn-kubernetes` → `Networking / ovn-kubernetes`
     - `openshift/cluster-network-operator` → `Networking / cluster-network-operator`
     - `openshift/origin` → component derived from changed test paths
   - If no mapping is confident, fall back to component-free search and warn the user.

5. **Derive target release**:
   - If `--target-release` provided, use it directly.
   - Otherwise, parse `baseRefName`:
     - `release-X.Y` → `X.Y`
     - `main` / `master` → the current development version (look up via `mcp__atlassian__jira_get_project_versions` and pick the latest unreleased version).
   - For OCPBUGS, target release is in `customfield_10855` (Target Version), not `fixVersions` (managed by release team — see `plugins/jira/reference/mcp-tools.md:295`). Query both for safety.

6. **Build JQL** and search for candidate Jiras:
   ```
   project = <KEY>
     AND statusCategory != Done
     AND component in (<COMPONENT(s)>)
     AND ("Target Version" = "<X.Y>" OR fixVersion = "<X.Y>")
   ORDER BY updated DESC
   ```
   Use `mcp__atlassian__jira_search` with `fields=summary,status,issuetype,components,fixVersions,customfield_10855,priority,description,updated,labels` and a generous limit (e.g. 50 — narrowed by JQL filters).

7. **Score candidates** (see SKILL for full rubric). Briefly:
   - **Symbol/identifier overlap** (function, struct, CRD field, error string): high weight.
   - **Keyword overlap** (PR title vs. Jira summary, error message in description): medium weight.
   - **Component agreement**: required for non-zero score unless component derivation was skipped.
   - **Recency**: small bonus for issues updated within the last 90 days.
   - **Penalties**: candidate is an Epic/Initiative (rarely "fixed by" a single PR) or has a different `Target Version`.

8. **Output**:
   - **Text** (default): a table with one row per candidate; columns: `#`, verdict, score, key, status, priority, **assignee** (required — show `unassigned` if null), summary, top matched signals, and Jira URL. End with the JQL used and a one-line verdict per candidate (`likely`, `possible`, `unlikely`).
   - **JSON** (`--output json`): structured payload with `pr`, `explicit_references`, `candidates[]`, and `metadata`. Each candidate object includes `assignee`.

9. **Always print the JQL used** so the user can iterate.

## Examples

1. **Basic usage with a PR URL**:
   ```
   /jira:candidates-from-pr https://github.com/openshift/ovn-kubernetes/pull/4567
   ```

2. **Override the target release** (e.g. when triaging a backport before the base branch is final):
   ```
   /jira:candidates-from-pr https://github.com/openshift/ovn-kubernetes/pull/4567 --target-release 4.18
   ```

3. **Restrict to a specific component**:
   ```
   /jira:candidates-from-pr 4567 --repo openshift/ovn-kubernetes \
     --component "Networking / ovn-kubernetes" --project OCPBUGS
   ```

4. **Tighter results, JSON output for downstream tooling**:
   ```
   /jira:candidates-from-pr https://github.com/openshift/ovn-kubernetes/pull/4567 \
     --limit 5 --min-score 60 --output json
   ```

5. **Re-score even keys already mentioned in the PR description**:
   ```
   /jira:candidates-from-pr https://github.com/openshift/ovn-kubernetes/pull/4567 --include-explicit
   ```

## Return Value

- **Claude agent text** (default): grouped report with two sections:
  1. **Explicit references** — Jira keys already mentioned in the PR, with status and target release.
  2. **Candidate matches** — ranked list of open Jiras the PR may fix, each with score, rationale, matched signals, and link.
- **JSON** (`--output json`): a structured object suitable for piping into other commands. Schema:
  ```json
  {
    "schema_version": "1.0",
    "metadata": { "generated_at": "...", "command": "candidates-from-pr" },
    "pr": { "url": "...", "number": 0, "title": "...", "base_ref": "...", "head_ref": "..." },
    "derived": { "components": ["..."], "target_release": "..." },
    "explicit_references": [ { "key": "...", "summary": "...", "status": "...", "target_release": "...", "assignee": "..." } ],
    "candidates": [
      {
        "key": "OCPBUGS-12345",
        "summary": "...",
        "url": "https://issues.redhat.com/browse/OCPBUGS-12345",
        "status": "New",
        "issuetype": "Bug",
        "priority": "Major",
        "assignee": "Jane Doe",
        "components": ["..."],
        "target_release": "4.18",
        "score": 78,
        "verdict": "likely",
        "rationale": "...",
        "matched_signals": ["error string 'failed to add subnet'", "function ensureSubnet", "title keyword 'subnet'"]
      }
    ]
  }
  ```

## Notes

- **Read-only**: the command never mutates Jira state.
- **Component mapping** is best-effort; pass `--component` for precision when the auto-derivation is wrong.
- **Target Version vs Fix Version**: for OCPBUGS the user-facing field is `Target Version` (`customfield_10855`); `fixVersions` is set by the release team. The query checks both, but the report displays `Target Version` when present.
- **Companion commands**:
  - `/jira:extract-prs` — opposite direction (Jira → PRs).
  - `/jira:reconcile-github` — state-mismatch reconciliation between linked GitHub issues and Jira.
  - `/utils:process-renovate-pr` — creates a *new* Jira from a Konflux/Renovate PR (does not match existing).

## Arguments

- `$1` (required): GitHub PR URL (`https://github.com/<org>/<repo>/pull/<n>`) or PR number.
- `--repo <org/repo>`: required if `$1` is just a number; ignored if a full URL is given.
- `--project <KEY>`: Jira project key to search (default: `OCPBUGS`).
- `--target-release <X.Y>`: override auto-detected target release (e.g. `4.18`).
- `--component <name>`: override auto-detected component. Repeatable.
- `--limit <N>`: maximum candidates to return (default: `10`).
- `--min-score <0-100>`: drop candidates scoring below this (default: `40`).
- `--include-explicit`: also score Jira keys already referenced in the PR (default: list them separately, do not re-score).
- `--output text|json`: output format (default: `text`).
