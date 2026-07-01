---
name: rebase-library-go
description: Automatically rebase library-go dependencies in OpenShift operator repositories, update go mod/vendor, and create PRs
tools: [Bash, Read, Write, Edit]
---

# Rebase library-go Dependencies

This skill automates the process of updating library-go dependencies across OpenShift operator repositories.

## Target Repositories

- `openshift/cluster-authentication-operator`
- `openshift/cluster-kube-apiserver-operator`
- `openshift/cluster-openshift-apiserver-operator`

## Prerequisites

Before running this skill, verify:

1. **GitHub CLI (`gh`) is authenticated**: Run `gh auth status` to verify
2. **Git is configured**: Check `git config user.name` and `git config user.email`
3. **Go toolchain is available**: Verify `go version` works
4. **Forks exist**: The workflow requires pushing to personal forks, not upstream repositories directly

If any prerequisite fails, inform the user and stop.

## Workflow

**Setup (run once before processing repositories):**

1. **Get library-go latest commit SHA**:
   ```bash
   gh api repos/openshift/library-go/branches/master --jq '.commit.sha'
   ```
   Note: library-go uses `master` as default branch, not `main`

2. **Get current date** for branch naming:
   ```bash
   date +%Y-%m-%d
   ```

**For each target repository:**

1. **Check for existing PRs**
   - List open PRs with title matching "NO-JIRA: Automatic agentic rebase":
     ```bash
     gh pr list --repo openshift/{repo-name} --author @me --state open --search "NO-JIRA: Automatic agentic rebase" --json number,title,headRefName,body
     ```
   - If an existing PR is found:
     - Extract the library-go commit SHA from the PR body (look for `library-go commit:` line)
     - Compare with the current library-go master SHA:
       - **If SHAs match**: Skip this repository (PR is already up to date)
       - **If SHAs differ**: Close the old PR and continue with new PR creation:
         ```bash
         gh pr close {pr-number} --repo openshift/{repo-name} --comment "Closing in favor of newer library-go update (SHA: {new-short-sha})"
         ```
   - If no existing PR found: Continue with normal workflow

2. **Clone or update repository**
   - Use absolute path: `/home/user/git/ai-helpers/.work/rebase-library-go/{repo-name}/`
   - Clone with: `gh repo clone openshift/{repo-name}`
   - If already cloned, discover remote and pull latest:
     ```bash
     UPSTREAM=$(git remote -v | grep 'openshift/{repo-name}' | grep fetch | awk '{print $1}' | head -1)
     git fetch $UPSTREAM && git checkout master && git pull $UPSTREAM master
     ```

2. **Ensure fork exists**
   - Check/create fork: `gh repo fork openshift/{repo-name} --clone=false`
   - Fork may already exist (not an error)

3. **Create feature branch**
   - Branch name format: `agentic-rebase-library-go-{YYYY-MM-DD}`
   - Always create fresh branch from master: `git checkout -b agentic-rebase-library-go-{date}`

4. **Update library-go dependency**
   - Update go.mod to use latest master commit SHA:
     ```bash
     go get github.com/openshift/library-go@{full-sha}
     ```
   - Run `go mod tidy` (completes silently when successful)
   - Run `go mod vendor` (completes silently when successful)

5. **Verify changes**
   - Check changes with: `git diff --stat`
   - Expected files: `go.mod`, `go.sum`, vendor files
   - Typical change count: 5-10 files, 9-10 insertions/deletions

6. **Commit changes**
   - Create commit message in temp file:
     ```bash
     cat > /tmp/commit-msg.txt << 'EOF'
     NO-JIRA: Automatic agentic rebase: Update library-go to {short-sha}
     
     This is an automated dependency update created by Claude Code.
     Updates library-go to the latest master branch commit.
     
     library-go commit: {full-sha}
     Generated: {YYYY-MM-DD}
     EOF
     ```
   - Commit: `git add go.mod go.sum vendor/ && git commit -F /tmp/commit-msg.txt`

7. **Run verification and tests**
   - Run `make verify` to check code format and linting
   - Run `make test` to execute unit tests
   - **If either command fails**:
     - Read the error output carefully
     - Fix the issues (e.g., formatting errors, test failures)
     - Stage and commit the fixes:
       ```bash
       git add .
       git commit --amend --no-edit
       ```
   - Only proceed to push if both `make verify` and `make test` pass successfully

8. **Push to fork and create PR**
   - **IMPORTANT**: Before pushing, ask the user for explicit permission:
     - Use AskUserQuestion to confirm: "Ready to push branch `agentic-rebase-library-go-{date}` to your fork and create PR in openshift/{repo-name}?"
     - Only proceed with push/PR creation if user approves
   - Discover fork remote name (don't assume "fork"):
     ```bash
     FORK_REMOTE=$(git remote -v | grep '{username}/{repo-name}' | grep fetch | awk '{print $1}' | head -1)
     ```
   - If fork remote doesn't exist, add it (use SSH URL for authentication):
     ```bash
     if [ -z "$FORK_REMOTE" ]; then
       git remote add fork git@github.com:{username}/{repo-name}.git
       FORK_REMOTE="fork"
     fi
     ```
   - Push to fork: `git push $FORK_REMOTE agentic-rebase-library-go-{date}`
   - Create PR from fork to upstream:
     ```bash
     gh pr create \
       --repo openshift/{repo-name} \
       --head {username}:agentic-rebase-library-go-{date} \
       --title "NO-JIRA: Automatic agentic rebase: Update library-go to {short-sha}" \
       --body-file /tmp/pr-body.md
     ```
   - Do NOT use `--label` flags (labels may not exist in upstream repos)

8. **Create PR body template** (reuse for all repos):
   ```bash
   cat > /tmp/pr-body.md << 'EOF'
   ## Summary
   
   Automated dependency update for `github.com/openshift/library-go`.
   
   ## Details
   
   - **library-go commit**: [`{short-sha}`](https://github.com/openshift/library-go/commit/{full-sha})
   - **Update date**: {YYYY-MM-DD}
   - **Generated by**: Claude Code agentic workflow
   
   ## Changes
   
   - Updated `go.mod` and `go.sum`
   - Refreshed vendor directory
   
   ## Testing
   
   - [ ] CI tests pass
   - [ ] Manual verification recommended
   
   ---
   
   🤖 This PR was created automatically by an AI agent using Claude Code.
   EOF
   ```

9. **Report results**
   - PR URL
   - Diff summary (files changed, insertions, deletions)
   - Any warnings or errors

## Error Handling

- **Clone failures**: Report network/permission issues
- **go mod failures**: Report Go version or module resolution errors
- **No changes detected**: Skip PR creation, report that library-go is already up to date
- **Push failures (permission denied)**: Ensure fork exists and fork remote uses SSH URL format
- **PR creation failures**: Check authentication and fork setup
- **Label errors**: Ignore label failures (labels may not exist in upstream repos)
- **make verify failures**: Fix formatting/linting issues and amend commit before pushing
- **make test failures**: Investigate test failures, fix issues, and amend commit before pushing
- **Existing PR with same SHA**: Skip repository and report that PR is already up to date
- **Existing PR with different SHA**: Close old PR with explanatory comment, then create new PR

## Safety Considerations

- Always use absolute paths: `/home/user/git/ai-helpers/.work/rebase-library-go/`
- The `.work/` directory is gitignored
- Never force-push or modify existing PRs
- Always push to personal fork, never directly to upstream
- If conflicts occur during rebase, report and skip that repository
- Temporary files (`/tmp/commit-msg.txt`, `/tmp/pr-body.md`) are reusable across all repos

## Batch Execution

Process all three repositories sequentially (not in parallel) to:
- Provide clear progress updates
- Avoid rate limiting issues
- Allow early termination if systematic issues are detected

After all repositories are processed, provide a summary table:

```
| Repository                              | Status    | PR URL                          |
|-----------------------------------------|-----------|---------------------------------|
| cluster-authentication-operator         | Success   | https://github.com/...          |
| cluster-kube-apiserver-operator         | Success   | https://github.com/...          |
| cluster-openshift-apiserver-operator    | No change | (already up to date)            |
```

## Example Commands

**Get latest library-go commit SHA** (note: uses branches API, not commits):
```bash
gh api repos/openshift/library-go/branches/master --jq '.commit.sha'
# Returns: 19be6ed11363fd46f2a75dd94441a3a474504195
```

**Complete workflow for one repository**:
```bash
# Setup
REPO="cluster-authentication-operator"
SHA="19be6ed11363fd46f2a75dd94441a3a474504195"
SHORT_SHA="19be6ed"
DATE="2026-06-02"
BRANCH="agentic-rebase-library-go-${DATE}"

# Clone and setup
cd /home/user/git/ai-helpers/.work/rebase-library-go
gh repo clone openshift/${REPO}
cd ${REPO}

# Ensure fork exists
gh repo fork openshift/${REPO} --clone=false

# Create branch and update
git checkout -b ${BRANCH}
go get github.com/openshift/library-go@${SHA}
go mod tidy
go mod vendor

# Verify and commit
git diff --stat
git add go.mod go.sum vendor/
git commit -F /tmp/commit-msg.txt

# Run verification and tests
make verify
make test
# If either fails, fix issues and amend commit: git add . && git commit --amend --no-edit

# Push to fork (after getting user permission via AskUserQuestion)
FORK_REMOTE=$(git remote -v | grep "USERNAME/${REPO}" | grep fetch | awk '{print $1}' | head -1)
if [ -z "$FORK_REMOTE" ]; then
  git remote add fork git@github.com:USERNAME/${REPO}.git
  FORK_REMOTE="fork"
fi
git push $FORK_REMOTE ${BRANCH}

# Create PR (no labels)
gh pr create \
  --repo openshift/${REPO} \
  --head USERNAME:${BRANCH} \
  --title "NO-JIRA: Automatic agentic rebase: Update library-go to ${SHORT_SHA}" \
  --body-file /tmp/pr-body.md
```

## Notes

- **library-go uses `master` branch**, not `main`
- The skill uses the current date for branch naming and commit messages
- The skill respects existing PRs and won't create duplicates
- Vendor updates may be large (library-go has many dependencies)
- All three repos typically have the same change pattern (5 files, 9-10 lines)
- Use SSH URLs (`git@github.com:`) for fork remotes to ensure authentication works
- Ignore bash `_encode`/`_decode` errors in output (harmless shell snapshot artifacts)
