---
name: create-pr
description: Create a pull request from the current branch for a Jira issue. Use when changes are committed and pushed and the user wants to open a PR linking back to a Jira issue.
---

## Name
openshift-developer:create-pr

## Synopsis
```text
/openshift-developer:create-pr <ISSUE_KEY> [--upstream <owner/repo>] [--head <fork-owner>:<branch>]
```

## Description
Creates a pull request from the current feature branch, linking it to a Jira issue. Reads the repo's PR template, inspects the commit log, and generates a well-structured PR title and body. Designed as the final step of the solve pipeline, after `/jira:solve`, `code-review:pre-commit-review` and `address-review-precommit`.

## Implementation

### Step 1: Gather context

1. Parse arguments:
   - `$1` — Jira issue key (required, e.g. `OCPBUGS-1234`)
   - `--upstream` — target repository (default: infer from `gh repo view --json nameWithOwner`)
   - `--head` — PR head ref in `fork-owner:branch` format (default: current branch)

2. Determine the current branch:
   ```bash
   BRANCH=$(git branch --show-current)
   ```

3. Discover remotes, then determine the base branch:
   ```bash
   REMOTE=$(git remote | head -1)
   BASE_BRANCH=$(git remote show "$REMOTE" | sed -n 's/.*HEAD branch: //p')
   ```
   Fall back to `main` if detection fails.

4. Read the commit history for the PR:
   ```bash
   git log "${BASE_BRANCH}..HEAD" --format="%h %s%n%n%b" --reverse
   ```

5. Read the PR template if it exists:
   ```bash
   cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null || true
   ```

### Step 2: Compose the PR

1. **Title**: Must start with `<ISSUE_KEY>: ` followed by a concise summary derived from the commits.

2. **Body**: Structure using the PR template if one exists. Include:
   - A description of the changes based on the commit log
   - A link to the Jira issue: `https://redhat.atlassian.net/browse/<ISSUE_KEY>`
   - The following footer at the very end:
     ```text
     Always review AI generated responses prior to use.
     Generated with [Claude Code](https://claude.com/claude-code) via openshift-developer plugin
     ```

### Step 3: Create the PR

Build and run the `gh pr create` command:

```bash
gh pr create \
  --repo <UPSTREAM> \
  --head <HEAD_REF> \
  --no-maintainer-edit \
  --title '<ISSUE_KEY>: <summary>' \
  --body '<body>'
```

- If `--upstream` was provided, use it as `--repo`.
- If `--head` was provided, use it directly.
- If neither was provided, omit `--repo` and `--head` (defaults to current repo context and current branch).

### Step 4: Report

Print the PR URL returned by `gh pr create`.

## Return Value
- **PR URL**: the URL of the newly created pull request

## Examples

1. **Create a PR for a Jira issue (simple)**:
   ```text
   /openshift-developer:create-pr CNTRLPLANE-1234
   ```

2. **Create a PR targeting a specific upstream from a fork**:
   ```text
   /openshift-developer:create-pr OCPBUGS-5678 --upstream openshift/hypershift --head hypershift-community:fix/OCPBUGS-5678
   ```

## Arguments
- `$1` — Jira issue key (required)
- `--upstream` — target repository in `owner/repo` format (optional)
- `--head` — PR head ref in `fork-owner:branch` format (optional)

## Guidelines

- Discover remotes first (e.g. `git remote` or `git branch -vv`) before selecting one
- Always include the Jira issue key prefix in the PR title
- Always include the AI-generated footer at the end of the PR body
- Use the repo's PR template when available
- Derive the PR description from the actual commit log, not from assumptions
