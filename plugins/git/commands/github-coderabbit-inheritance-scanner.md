---
description: Scan openshift org repos for .coderabbit.yaml/.coderabbit.yml files missing inheritance
argument-hint: "[--dry-run]"
---

## Name
git:github-coderabbit-inheritance-scanner

## Synopsis
```
/git:github-coderabbit-inheritance-scanner
/git:github-coderabbit-inheritance-scanner --dry-run
```

## Description
The `git:github-coderabbit-inheritance-scanner` command scans all repositories in the `openshift` GitHub organization that contain a `.coderabbit.yaml` or `.coderabbit.yml` file and verifies each one has `inheritance: true` set. This ensures repos with custom CodeRabbit configurations still inherit the org-wide review rules defined in [openshift/coderabbit](https://github.com/openshift/coderabbit).

The `openshift/coderabbit` repo itself is excluded from results since it is the source of the global rules.

After scanning, the command offers to open PRs on non-compliant repos to add `inheritance: true`. PRs are always opened from a personal fork to avoid needing direct push access to upstream repos.

## Arguments
- `--dry-run`: Perform all scanning and checks (including searching for existing PRs) but do not actually create forks, push branches, or open PRs. Displays exactly what would be done for each non-compliant repo.

## Implementation

### Prerequisites
- **GitHub CLI (`gh`)**: Must be installed and authenticated with access to the `openshift` org.
  ```bash
  gh auth status
  ```
  The token must have the `workflow` scope to sync forks that contain GitHub Actions workflow files. If missing, warn the user and skip those repos rather than failing.

### Steps

1. **Search for `.coderabbit.yaml` files across the openshift org** using the `git:github-coderabbit-inheritance-scanner-search` skill. Use GitHub code search via `gh api` to find repos efficiently.

2. **For each repo, fetch the raw file and check for `inheritance: true`**. Use the `git:github-coderabbit-inheritance-scanner-check` skill to classify each repo as compliant, non-compliant (missing key), non-compliant (explicitly false), or error.

3. **For each non-compliant repo, check for an existing open PR** whose title contains `"CodeRabbit inheritance"` (case-insensitive substring match, since teams sometimes modify the PR title to satisfy merge requirements). Use the `git:github-coderabbit-inheritance-scanner-existing-pr` skill. Record the PR URL and how long it has been open.

4. **Format and present the results** as a markdown report:

   ```
   ## CodeRabbit Inheritance Scanner Report

   ### Summary
   - Total repos with .coderabbit.yaml: <count>
   - Compliant (inheritance: true): <count>
   - Non-compliant: <count>
   - Existing fix PRs open: <count>

   ### Repos with `inheritance: false` (explicitly disabled)
   | Repository | File Link | Existing PR |
   |---|---|---|
   | openshift/<repo> | [.coderabbit.yaml](link) | [#123](link) (open 5 days) |

   ### Repos missing `inheritance` key
   | Repository | File Link | Existing PR |
   |---|---|---|
   | openshift/<repo> | [.coderabbit.yaml](link) | None |

   ### Compliant repos (inheritance: true)
   <collapsed list>

   ### Errors (could not fetch file)
   <list if any>
   ```

5. **Offer to open fix PRs** for non-compliant repos that do not already have an open PR. Present the list and ask for confirmation (unless `--dry-run`).
   - If `--dry-run`: Display what would be done for each repo (fork, sync, branch, commit, PR) and stop.
   - If not `--dry-run`: Ask the user "Open PRs for these N repos? (y/n)" and proceed only on confirmation.

6. **Open fix PRs** using the `git:github-coderabbit-inheritance-scanner-open-pr` skill for each repo that needs a PR. This skill handles forking, syncing, branching, committing, pushing, and creating the PR. Collect all created PR URLs.

7. **Present final results** with links to all created PRs.

## Skills Used

This command delegates to the following skills:

- `git:github-coderabbit-inheritance-scanner-search` - Search for repos with `.coderabbit.yaml` files
- `git:github-coderabbit-inheritance-scanner-check` - Check a repo's `.coderabbit.yaml` for `inheritance: true`
- `git:github-coderabbit-inheritance-scanner-existing-pr` - Search for an existing fix PR on a repo
- `git:github-coderabbit-inheritance-scanner-open-pr` - Fork, sync, and open a fix PR on a repo

## Examples

1. **Scan only (report + offer to fix)**:
   ```
   /git:github-coderabbit-inheritance-scanner
   ```

2. **Dry run (report + show what would be done, no PRs opened)**:
   ```
   /git:github-coderabbit-inheritance-scanner --dry-run
   ```

## Notes
- Uses GitHub code search API to efficiently find repos with `.coderabbit.yaml` files without iterating all ~800 repos.
- Searches for both `.coderabbit.yaml` and `.coderabbit.yml` extensions.
- The `openshift/coderabbit` repository is excluded since it defines the global rules.
- PRs are always opened from the authenticated user's fork, never by pushing directly to upstream repos.
- Before opening a PR, the fork's default branch is synced with upstream to ensure the PR is based on the latest code.
- If `gh repo sync` fails due to missing `workflow` scope, the repo is skipped with a warning.
- Private repos may be skipped depending on `gh` authentication scope; this is acceptable.
- GitHub code search API may have a short indexing delay, so very recently added files might not appear.
- Rate limiting pauses are included between API calls to avoid hitting GitHub rate limits.

## See Also
- Global CodeRabbit config: https://github.com/openshift/coderabbit
- Related Command: `ci:analyze-pr-reverts` - Analyzes PR reverts and recommends CodeRabbit rules
