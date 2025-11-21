---
description: Track and monitor your open Pull Requests across GitHub repositories
argument-hint: [--all | --current]
---

## Name
git:track-prs

## Synopsis
```
/git:track-prs              # All repos, all open PRs (including drafts)
/git:track-prs --current    # Current repo only
```

## Description
Monitor all open Pull Requests you've authored across GitHub repositories with a status dashboard showing review, CI, and activity status.

Shows all open PRs (including drafts) with status indicators to help identify which need attention.

**Modes** (mutually exclusive):
- **`--current`** – Only PRs in current repository (supports detailed status)
- **`--all`** – PRs across all repositories (default)

**Use cases:**
- Monitor PR review and CI status
- Identify PRs needing attention (failing CI, requested changes)
- Track workload across multiple projects
- Find stale PRs requiring follow-up

## Implementation

1. **Parse arguments** and determine scope (`--current` vs `--all`)

2. **Fetch PR data** using GitHub CLI:
   ```bash
   # Current repo (supports detailed status)
   gh pr list --author @me --state open \
     --json number,title,url,isDraft,reviewDecision,statusCheckRollup,updatedAt

   # All repos (limited fields available)
   gh search prs --author @me --state open \
     --json repository,number,title,url,isDraft,updatedAt,commentsCount --limit 100
   ```

   **Note**: `--all` mode has fewer status details due to GitHub API limitations.

3. **Categorize PRs** by status:

   **For `--current` mode** (full status available):
   - 🔴 Needs Action (changes requested, CI failed)
   - ⏳ Waiting for Review
   - ✅ Approved & Ready
   - 📝 Draft (marked with [DRAFT])
   - ⚠️ Stale (7+ days no update)

   **For `--all` mode** (limited status):
   - 📝 Draft (marked with [DRAFT])
   - 💬 Active (has recent comments)
   - ⚠️ Stale (7+ days no update)
   - Others (sorted by update time)

4. **Display dashboard** with grouped PRs and action items

## Return Value

Dashboard output showing:

```text
📊 PR Dashboard (12 open across 5 repos)

🔴 Needs Your Action (3)
  #12345 openshift/origin – Fix auth timeout
    Changes Requested | CI Failed | Updated 2h ago
    → https://github.com/openshift/origin/pull/12345

⏳ Waiting for Review (5)
  #56789 kubernetes/kubernetes – Add quota validation
    Review Required | CI Passing | Updated 1d ago
    → https://github.com/kubernetes/kubernetes/pull/56789

📝 Draft / WIP (2)
  #11111 openshift/api – Experiment with new API [DRAFT]
    Updated 3d ago
    → https://github.com/openshift/api/pull/11111

✅ Approved & Ready (2)
  ...

Priority Actions:
  1. Fix failing CI in openshift/origin #12345
  2. Address review comments in openshift/installer #45678
  3. Follow up on stale PR (14 days): openshift/cluster-api #78901
```

## Examples

```bash
# Track all open PRs across repos (includes drafts)
/git:track-prs

# Current repository only
/git:track-prs --current
```

## Arguments

- **`--all`** (optional): Track PRs across all repositories (default)
- **`--current`** (optional): Track PRs only in current repository

**Note**: `--all` and `--current` are mutually exclusive. If both are provided, `--current` takes precedence. Both modes show all open PRs including drafts.

## Prerequisites

**GitHub CLI (`gh`)** required:
```bash
which gh || echo "Install from https://cli.github.com/"
gh auth status || gh auth login
```
