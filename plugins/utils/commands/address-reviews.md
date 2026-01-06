---
description: Fetch and address review comments from GitHub PRs or Gerrit changes
argument-hint: "<url-or-pr-number>"
---

## Name
utils:address-reviews

## Synopsis
```
/utils:address-reviews <url-or-pr-number>
```

## Description
This command automates the process of addressing code review comments from **GitHub pull requests** or **Gerrit changes**. It automatically detects the platform from the URL, fetches all comments, categorizes them by priority (blocking, change requests, questions, suggestions), and systematically addresses each one.

**Supported Platforms:**
- **GitHub**: Full URL, short format (`owner/repo#123`), or PR number
- **Gerrit**: Any Gerrit instance URL (OpenDev, Google, custom)

The command intelligently filters out outdated comments, bot-generated content, and handles platform-specific workflows (GitHub's force-push vs Gerrit's amend + `git review`).

## Implementation

### Step 0: Detect Platform and Parse Input

1. **Parse the input argument** (`$ARGUMENTS`):

   **Auto-detection rules:**
   ```
   Input contains "github.com"           → GitHub
   Input contains "/c/" or "/#/c/"       → Gerrit
   Input matches owner/repo#number       → GitHub (short format)
   Input is just a number                → GitHub (PR in current repo)
   Input contains "review." or "gerrit"  → Gerrit
   ```

2. **For GitHub:**
   - Extract owner, repo, PR number from URL
   - Or use current repo if just PR number provided

3. **For Gerrit:**
   - Extract base URL, project, change number, optional patchset
   - Supported formats:
     - `https://review.example.com/c/org/project/+/123456`
     - `https://review.example.com/c/org/project/+/123456/3`
     - `https://review.example.com/#/c/123456/`

4. **Display detected platform:**
   ```
   🔍 Detected platform: GitHub (github.com/example-org/example-repo)
   📋 PR #123: Example pull request title...
   ```
   or
   ```
   🔍 Detected platform: Gerrit (review.example.com)
   📋 Change 123456: Example change subject
   ```

---

## GitHub Workflow

### Step 1-GH: Checkout the PR Branch

1. **Determine PR number**: Use parsed URL or `gh pr list --head <current-branch>`
2. **Checkout**: Use `gh pr checkout <PR_NUMBER>` if not already on the branch, then `git pull`
3. **Verify clean working tree**: Run `git status`. If uncommitted changes exist, ask user how to proceed

### Step 2-GH: Fetch PR Comments

1. **Use the CLI tool for fetching**:
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     "https://github.com/{owner}/{repo}/pull/{pr_number}"
   ```

2. **Or fetch directly via gh CLI**:

   a. **First pass - Get metadata only** (IDs, authors, lengths, URLs):
   ```bash
   # Get issue comments (general PR comments)
   gh pr view <PR_NUMBER> --json comments --jq '.comments | map({
     id, author: .author.login, length: (.body | length), type: "issue_comment"
   })'

   # Get reviews
   gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/reviews --jq 'map({
     id, author: .user.login, length: (.body | length), state, type: "review"
   })'

   # Get review comments (inline)
   gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments --jq 'map({
     id, author: .user.login, length: (.body | length), path, line, type: "review_comment"
   })'
   ```

   b. **Apply filtering**:
   - Filter out: `line == null` (outdated)
   - Filter out: `length > 5000`
   - Filter out: CI bots (`openshift-ci-robot`, `metal3-io-bot`, etc.)

### Step 3-GH: Address Comments

For each comment (prioritized: BLOCKING → CHANGE_REQUEST → QUESTION → SUGGESTION):

**If code change needed:**
1. Make the change
2. Stage: `git add <file>`
3. Amend commit: `git commit --amend --no-edit`
4. Push: `git push --force-with-lease`
5. Post reply:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments/<comment_id>/replies \
     -f body="Done. [description]\n\n---\n*AI-assisted response via Claude Code*"
   ```

**If declining or clarifying:**
- Post reply with explanation using same API

---

## Gerrit Workflow

### Step 1-GR: Fetch Change and Checkout

1. **Check git-review installation**:
   ```bash
   which git-review
   ```
   If not installed, note that manual workflow will be needed.

2. **Checkout the change** (if using git-review):
   ```bash
   git review -d <change-number>
   ```
   Or manually checkout if not using git-review.

3. **Verify clean working tree**: `git status`

### Step 2-GR: Fetch Gerrit Comments

1. **Use the CLI tool for fetching**:
   ```bash
   python3 plugins/utils/skills/gerrit-review/fetch_gerrit_comments.py \
     --unresolved-only \
     "<gerrit_url>"
   ```

2. **Parse output** to extract:
   - Change metadata (number, project, branch, status)
   - Unresolved comments with author, file, line, message

3. **If no unresolved comments**: Exit with success message

### Step 3-GR: Address Comments

For each comment (prioritized: BLOCKING → CHANGE_REQUEST → QUESTION → SUGGESTION):

**If code change needed:**
1. Make the change
2. Stage: `git add <file>`
3. Continue to next comment (batch changes)

**After all changes:**
1. Amend the commit (Gerrit workflow):
   ```bash
   git commit --amend
   ```
   - Keep the Change-Id in commit message!

2. Push to Gerrit:
   ```bash
   git review
   ```
   Or without git-review:
   ```bash
   git push origin HEAD:refs/for/<branch>
   ```

### Step 4-GR: Generate Response Template

Since Gerrit API requires authentication for posting, generate a template:

```
Responses to post on Gerrit:

[file.py:45] - Addressed
Fixed the null check as suggested.

[file.py:89] - Clarification
This approach provides better performance. See docs/perf.md.

Please post these responses on: <gerrit_url>
```

---

## Common Steps (Both Platforms)

### Categorize and Prioritize Comments

1. **Filter out non-actionable**:
   - Pure acknowledgments ("LGTM", "Thanks!")
   - Bot-generated (CI results)
   - Already resolved

2. **Categorize**:
   - **BLOCKING**: Critical issues (security, bugs, breaking)
   - **CHANGE_REQUEST**: Code improvements, refactoring
   - **QUESTION**: Clarification requests
   - **SUGGESTION**: Optional improvements, nits

3. **Group by file**, then by proximity (within 10 lines)

4. **Prioritize**: BLOCKING → CHANGE_REQUEST → QUESTION → SUGGESTION

5. **Present summary and confirm** before proceeding

### Address Comments

**For code changes:**
- Validate the request makes sense
- Implement minimal, focused changes
- Amend relevant commits (keep history clean)

**For questions:**
- Provide clear, detailed answers (2-4 sentences)
- Include file:line references

**For declining:**
- Explain technical reasoning (3-5 sentences)
- Be respectful and professional

### Summary

Display final summary:
```
Review Feedback Addressed
=========================
Platform: GitHub / Gerrit
Reference: PR #123 / Change 123456

Comments processed: 8
  - Code changes made: 5
  - Questions answered: 2
  - Declined with explanation: 1

Changes pushed successfully.
```

## Guidelines

- **Be thorough but efficient**
- **Maintain professional tone** in all replies
- **Prioritize code quality** over quick fixes
- **Platform-specific workflows**: GitHub uses force-push, Gerrit uses amend + git review
- **When in doubt**, ask the user
- **Use TodoWrite** to track progress through multiple comments

## Arguments
- $1: URL or PR number (required)
  - GitHub: `https://github.com/owner/repo/pull/123`, `owner/repo#123`, or `123`
  - Gerrit: `https://review.opendev.org/c/project/+/123`

## Examples

1. **GitHub PR by URL**:
   ```
   /utils:address-reviews https://github.com/example-org/example-repo/pull/123
   ```

2. **GitHub PR by number** (in repo):
   ```
   /utils:address-reviews 123
   ```

3. **GitHub short format**:
   ```
   /utils:address-reviews example-org/example-repo#123
   ```

4. **Gerrit change**:
   ```
   /utils:address-reviews https://review.example.com/c/org/project/+/123456
   ```

5. **Gerrit with specific patchset**:
   ```
   /utils:address-reviews https://review.example.com/c/org/project/+/123456/3
   ```

## See Also

- `plugins/utils/skills/github-review/SKILL.md` - GitHub CLI tool documentation
- `plugins/utils/skills/gerrit-review/SKILL.md` - Gerrit CLI tool documentation
