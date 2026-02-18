---
name: Revert PR
description: Git revert workflow and Revertomatic PR template for reverting merged PRs
---

# Revert PR

This skill provides the detailed git revert workflow and the exact PR body template used by [Revertomatic](https://github.com/stbenjam/revertomatic) for reverting merged pull requests that break CI or nightly payloads.

## When to Use This Skill

Use this skill when:

- A merged PR needs to be reverted to restore CI signal
- Following the [OpenShift quick-revert policy](https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert)
- You need the exact Revertomatic template format for the revert PR body
- You need to generate CI override commands for a revert PR

## Prerequisites

1. **GitHub CLI (`gh`)**: Installed and authenticated
   - Check: `gh auth status`

2. **Git**: Installed and configured
   - Check: `which git`

3. **Repository Access**: User must have push access to their fork of the target repository

## Implementation Steps

### Step 1: Extract PR Information

Use the `gh` CLI to fetch all necessary details about the PR being reverted:

```bash
# Fetch PR details as JSON
pr_data=$(gh pr view "$PR_URL" --json number,title,author,mergeCommit,baseRefName,state)

# Extract fields
pr_number=$(echo "$pr_data" | jq -r '.number')
pr_title=$(echo "$pr_data" | jq -r '.title')
pr_author=$(echo "$pr_data" | jq -r '.author.login')
merge_sha=$(echo "$pr_data" | jq -r '.mergeCommit.oid')
base_branch=$(echo "$pr_data" | jq -r '.baseRefName')
pr_state=$(echo "$pr_data" | jq -r '.state')
```

**Validation**:
- `pr_state` must be `MERGED`. If the PR is not merged, abort with an error.
- `merge_sha` must not be empty or null.

### Step 2: Identify the Upstream Repository

Parse the PR URL to determine owner and repository:

```bash
# From URL like https://github.com/openshift/kubernetes/pull/1703
# Extract: owner=openshift, repo=kubernetes
```

### Step 3: Ensure User Has a Fork

```bash
# Get authenticated user
gh_user=$(gh api user --jq '.login')

# Check if fork exists
if ! gh api "repos/$gh_user/$repo" &>/dev/null; then
    echo "Creating fork of $owner/$repo..."
    gh repo fork "$owner/$repo" --clone=false
    # Wait for fork to become available
    sleep 5
fi
```

### Step 4: Clone and Set Up Repository

If no local repository is available:

```bash
# Clone upstream (shallow for speed)
git clone -b "$base_branch" "https://github.com/$owner/$repo.git" /tmp/revert-workdir
cd /tmp/revert-workdir

# Add fork as remote
git remote add fork "git@github.com:$gh_user/$repo.git"
```

If using an existing local clone, ensure remotes are configured correctly:

```bash
# Verify upstream remote points to the correct repository
# Verify fork remote points to user's fork
git remote -v
```

### Step 5: Look Up JIRA Ticket for Context

When a JIRA ticket is provided, use the `fetch-jira-issue` skill to automatically gather context about what broke and which jobs need verification before unreverting.

```bash
# Path to the fetch-jira-issue script
jira_script="plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py"

# Fetch JIRA issue details
jira_data=$(python3 "$jira_script" "$JIRA" --format json 2>/dev/null)
```

**Extract context from the JIRA issue**:

From the JSON output, examine the `summary`, `comments`, and `linked_prs` fields to determine:

1. **What broke** (for the `{CONTEXT}` template variable):
   - Look at the issue summary and description for mentions of failing jobs, payloads, or test names
   - Check comments for links to failing Prow jobs, payload pages, or Sippy reports
   - Look for patterns like `e2e-aws`, `e2e-gcp`, `nightly`, `payload`, or release stream URLs

2. **Verification jobs** (for the unrevert instructions):
   - Identify which specific CI jobs are mentioned as broken in the ticket
   - These are the jobs the original author should run before re-landing their change
   - Common patterns: `e2e-aws`, `e2e-gcp`, `e2e-metal-ipi`, `e2e-ovn`, etc.

```bash
# Example: Extract context from JIRA data
jira_summary=$(echo "$jira_data" | jq -r '.summary')
jira_comments=$(echo "$jira_data" | jq -r '.comments[].body')

# Look for job names and payload URLs in the summary and comments
# to build the CONTEXT and VERIFICATION variables
```

**Fallback**: If the JIRA lookup fails (no token, network error, or insufficient detail in the ticket), ask the user interactively:
- "Why is this PR being reverted?"
- "What jobs should be run to verify a fix before unreverting?"

If the user also provided inline context as arguments, combine it with the JIRA-derived context.

### Step 6: Detect Commit Message Convention

Before creating the revert, check recent commits in the repository to determine if it uses a special commit/PR title prefix convention.

```bash
# Check the last 20 commit subjects on the base branch
git log "upstream/$base_branch" --oneline -20
```

**UPSTREAM carry convention**: Some repositories (notably `openshift/kubernetes` and other repos carrying upstream patches) use the prefix format `UPSTREAM: <tag>:` in commit messages. Common tags include `<carry>`, `<drop>`, and upstream cherry-pick numbers like `<12345>`.

**Detection logic**:
- If a significant number of recent commits use the `UPSTREAM: <tag>:` format, the revert must follow the same convention.
- The revert commit message and PR title should use:
  ```
  UPSTREAM: <carry>: Revert "ORIGINAL_TITLE" because REASON
  ```
  For example:
  ```
  UPSTREAM: <carry>: Revert "UPSTREAM: 12345: Fix kubelet crash" because it broke e2e-aws jobs
  ```
- If the repo does NOT use this convention, use the standard format described in Step 9.

Store the detected convention for use in Steps 7 and 9.

### Step 7: Create Revert Branch and Perform Revert

```bash
# Fetch latest from upstream
git fetch upstream

# Create revert branch from base branch
revert_branch="revert-${pr_number}-$(date +%s%3N)"
git checkout -b "$revert_branch" "upstream/$base_branch"

# Revert the merge commit (first parent = base branch)
git revert -m1 --no-edit "$merge_sha"
```

**Important**: The `-m1` flag tells git to revert relative to the first parent of the merge commit, which is the base branch. This effectively undoes the changes introduced by the PR.

#### Handling Merge Conflicts

If `git revert` fails with conflicts, determine the best strategy:

**Strategy A: Resolve simple/obvious conflicts**

Use this when conflicts are trivial and unambiguous:
- Generated files (go.sum, vendor directories, generated protobuf, etc.)
- One-line changes where the resolution is obvious
- Whitespace or formatting-only conflicts

To resolve:
1. Examine the conflicting files with `git diff` and `git status`
2. Resolve each conflict
3. Stage the resolved files with `git add`
4. Complete the revert with `git revert --continue`
5. **IMPORTANT**: Amend the revert commit message to note the conflict resolution:
   ```bash
   git commit --amend -m "$(git log -1 --format=%B)

   Note: Merge conflicts in {FILE_LIST} were resolved manually.
   Conflicts were trivial ({DESCRIPTION}, e.g. 'generated file regeneration', 'one-line context change')."
   ```

**Strategy B: Revert dependent commits**

Use this when conflicts are non-trivial, meaning later commits depend on the changes introduced by the PR being reverted:

1. Identify which subsequent commits conflict with the revert:
   ```bash
   # List commits after the merge commit on the base branch
   git log --oneline "$merge_sha"..upstream/"$base_branch"
   ```
2. Determine which of these commits touch the same files and depend on the reverted changes
3. Abort the current revert: `git revert --abort`
4. Revert in reverse chronological order — revert the dependent commits first, then the target commit:
   ```bash
   # Revert dependent commits first (newest to oldest)
   git revert --no-edit <dependent_sha_newest>
   git revert --no-edit <dependent_sha_next>
   # ... then revert the original target
   git revert -m1 --no-edit "$merge_sha"
   ```
5. **IMPORTANT**: Amend the final commit message (or use an interactive squash) to document what was reverted:
   ```
   Note: The following dependent commits were also reverted because
   they conflict with or depend on the original change:
   - <sha1> <title1>
   - <sha2> <title2>
   ```
6. Inform the user which additional commits were reverted and why, so the PR body can include this information

After conflict resolution (either strategy), push to the fork:

```bash
# Push to fork
git push fork "$revert_branch:$revert_branch"
```

### Step 8: Generate CI Override Commands

After the revert PR is created, determine which CI jobs need `/override` commands:

```bash
# Get the revert PR's head SHA
pr_sha=$(gh pr view "$revert_pr_url" --json headRefOid --jq '.headRefOid')

# List all status contexts
statuses=$(gh api "repos/$owner/$repo/statuses/$pr_sha" --jq '.[].context' | sort -u)
```

**Filter out unoverridable jobs** - these are fast-running quality gates that should always pass:

Jobs matching the following pattern should NOT be overridden:
```
.*(unit|lint|images|verify|tide|verify-deps|fmt|vendor|vet)$
```

Format remaining jobs as override commands:
```
/override ci/prow/e2e-aws
/override ci/prow/e2e-gcp-ovn
/override ci/prow/e2e-metal-ipi
...
```

### Step 9: Create the Revert PR with Revertomatic Template

**PR Title Format** depends on the commit convention detected in Step 5:

**Standard repositories**:
```
{JIRA}: Revert #{PR_NUMBER} "{ORIGINAL_TITLE}"
```
Example: `TRT-9999: Revert #1703 "Fix kubelet crash on restart"`

**UPSTREAM carry repositories** (e.g., openshift/kubernetes):
```
{JIRA}: UPSTREAM: <carry>: Revert "{ORIGINAL_TITLE}" because {REASON}
```
Example: `TRT-9999: UPSTREAM: <carry>: Revert "UPSTREAM: 12345: Fix kubelet crash" because it broke e2e-aws nightly jobs`

**PR Body - Revertomatic Template**:

This is the exact template format used by [Revertomatic](https://github.com/stbenjam/revertomatic). Use this format precisely:

```
Reverts #{ORIGINAL_PR_NUMBER} ; tracked by {JIRA_ISSUE}

Per [OpenShift policy](https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert), we are reverting this breaking change to get CI and/or nightly payloads flowing again.

{CONTEXT}

To unrevert this, revert this PR, and layer an additional separate commit on top that addresses the problem. Before merging the unrevert, please run these jobs on the PR and check the result of these jobs to confirm the fix has corrected the problem:

```
{OVERRIDE_COMMANDS}
```

CC: @{ORIGINAL_AUTHOR}
```

**Template Variables**:
- `{ORIGINAL_PR_NUMBER}`: The PR number being reverted (e.g., `1703`)
- `{JIRA_ISSUE}`: The JIRA ticket tracking the revert (e.g., `TRT-9999`)
- `{CONTEXT}`: Explanation of why the revert is needed, derived from the JIRA ticket (Step 5) or provided by the user (e.g., "This PR broke all e2e-aws jobs on the 4.18 nightly payload at https://amd64.ocp.releases.ci.openshift.org/...")
- `{OVERRIDE_COMMANDS}`: The list of `/override` commands for CI jobs that need to be bypassed
- `{ORIGINAL_AUTHOR}`: GitHub username of the original PR author

**Create the PR**:

```bash
gh pr create \
  --repo "$owner/$repo" \
  --base "$base_branch" \
  --head "$gh_user:$revert_branch" \
  --title "$jira: Revert #$pr_number \"$pr_title\"" \
  --body "$rendered_body"
```

### Step 10: Post Override Commands (Optional)

After the revert PR is created, the override commands can be posted as a comment on the PR to make it easy to copy-paste:

```bash
gh pr comment "$revert_pr_url" --body "/override ci/prow/e2e-aws
/override ci/prow/e2e-gcp
..."
```

**Note**: Override commands may need to be posted after CI jobs have started running and reported their status contexts. If no statuses are available yet, inform the user they can run `/ci:revert-pr` override commands later, or manually check the PR for required overrides.

## Error Handling

### PR Not Merged

```
Error: PR #1703 is in state OPEN, not MERGED.
Only merged PRs can be reverted with this command.
```

### Merge Commit Not Found

```
Error: Could not find merge commit SHA for PR #1703.
The PR may have been squash-merged or rebased.
```

For squash-merged PRs, the merge commit SHA is the squash commit itself. Use `gh pr view` to get the correct SHA.

### Revert Conflict

```
Error: git revert -m1 failed due to conflicts.
```

See Step 7 for the two conflict resolution strategies:
- **Strategy A**: Resolve simple/obvious conflicts directly (generated files, one-liners) and note this in the commit message
- **Strategy B**: If conflicts are non-trivial, revert the dependent commits as well and document them in the commit message and PR body

### Fork Creation Timeout

```
Warning: Fork not ready after creation. Waiting...
```

If the fork was just created, retry with exponential backoff (up to ~30 seconds).

### No Statuses Available

```
Note: No CI status contexts found on the revert PR yet.
Override commands will be available after CI jobs start running.
```

## Examples

### Example 1: Full Revert Workflow

```bash
# Input
PR_URL="https://github.com/openshift/kubernetes/pull/1703"
JIRA="TRT-9999"
CONTEXT="This PR broke all jobs on https://amd64.ocp.releases.ci.openshift.org/releasestream/4.15.0-0.nightly/release/4.15.0-0.nightly-2023-10-03-025546"
VERIFY="Run e2e-aws and e2e-gcp jobs"

# Result: Creates PR with title
# TRT-9999: Revert #1703 "UPSTREAM: 12345: Fix kubelet crash on restart"
```

### Example 2: Generated PR Body

```markdown
Reverts #1703 ; tracked by TRT-9999

Per [OpenShift policy](https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert), we are reverting this breaking change to get CI and/or nightly payloads flowing again.

This PR broke all jobs on https://amd64.ocp.releases.ci.openshift.org/releasestream/4.15.0-0.nightly/release/4.15.0-0.nightly-2023-10-03-025546

To unrevert this, revert this PR, and layer an additional separate commit on top that addresses the problem. Before merging the unrevert, please run these jobs on the PR and check the result of these jobs to confirm the fix has corrected the problem:

```
/override ci/prow/e2e-aws
/override ci/prow/e2e-gcp-ovn
/override ci/prow/e2e-metal-ipi
```

CC: @originalauthor
```

## Notes

- The Revertomatic template is important for consistency across OpenShift revert PRs
- The `git revert -m1` flag is critical: it specifies the first parent (base branch) as the mainline for the revert
- Branch naming uses `revert-{number}-{timestamp_millis}` to avoid collisions with existing branches
- The unrevert instructions in the template guide the original author on how to re-land their changes with a fix
- Override commands exclude fast-running quality gates (unit, lint, images, verify, tide, verify-deps, fmt, vendor, vet)

## See Also

- Related Command: `/ci:revert-pr` - The user-facing command that uses this skill (`plugins/ci/commands/revert-pr.md`)
- Related Skill: `fetch-jira-issue` - Fetches JIRA issue details for automatic context extraction (`plugins/ci/skills/fetch-jira-issue/SKILL.md`)
- Revertomatic: https://github.com/stbenjam/revertomatic
- OpenShift Quick Revert Policy: https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert
