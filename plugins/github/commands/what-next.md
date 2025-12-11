---
description: Identify what to focus on next based on PRs, issues, and milestones
argument-hint: [--contributing path]
---

## Name
github:what-next

## Synopsis
```
/github:what-next [--contributing path]
```

## Description
The `github:what-next` command helps developers identify what to focus on next by analyzing open PRs, assigned work, and milestone issues. It presents a prioritized list of actionable items based on common open-source contribution workflows.

This command is particularly useful for:
- Starting your work day with a clear focus
- Identifying PRs that need your review
- Tracking the status of your own PRs
- Finding priority issues to work on next
- Understanding your current workload at a glance

The command automatically:
- Identifies PRs where your review is needed
- Shows your open PRs and their review status
- Finds priority issues from the next milestone
- Respects contribution guidelines if present

## Prerequisites

1. **GitHub CLI (`gh`)** must be installed and authenticated
   - Check: `gh auth status`
   - Install: https://cli.github.com/

2. **Repository context**: Must be run from within a Git repository that has a GitHub remote

## Implementation

Execute the following steps to gather information and present suggestions:

### Step 1: Get GitHub Username
```bash
gh api user --jq '.login'
```
Store this as `GITHUB_USER` for filtering throughout.

### Step 2: Read Contribution Guidelines (Optional)
If `--contributing` path is provided, or if `CONTRIBUTING.md` exists in the repository root:
- Read the file to understand project-specific review and priority conventions
- Look for guidance on:
  - Required number of reviewers
  - Priority label conventions
  - Milestone-based workflows
  - Any special review request processes

If no contributing file is found, use sensible defaults.

### Step 3: Fetch Open PRs
```bash
gh pr list --state open --json number,title,author,isDraft,reviewRequests,reviews,assignees,updatedAt,url
```

Process the PR data into categories:

**A. PRs Needing Your Review** (highest priority):
- Exclude drafts (unless you're an assignee with recent comments)
- Exclude PRs authored by you
- Exclude PRs that are "sufficiently reviewed" (see heuristics below)
- Prioritize PRs where you are explicitly in `reviewRequests`

**B. Your Assigned PRs with Activity**:
- PRs where you are an assignee (including drafts)
- Check for recent comments that may need response:
  ```bash
  gh pr view <number> --json comments --jq '.comments[-1]'
  ```

**C. Your Open PRs (non-draft)**:
- PRs authored by you that are not drafts
- Categorize by review status:
  - Has APPROVED and no CHANGES_REQUESTED = ready to merge
  - Has CHANGES_REQUESTED = needs your attention
  - No reviews yet = waiting for review

**D. Your Drafts**:
- Draft PRs authored by you
- Note how recently they were updated

### Step 4: Find Milestone Issues
Get the next milestone with a due date:
```bash
gh api repos/:owner/:repo/milestones --jq '[.[] | select(.state == "open") | select(.due_on)] | sort_by(.due_on) | .[0] | {number, title, due_on}'
```

If a milestone exists, fetch its issues:
```bash
gh issue list --milestone "<milestone_title>" --state open --json number,title,labels,assignees,url
```

Sort issues by priority labels (common conventions):
1. `priority/critical` or `critical` - highest
2. `priority/high` or `high-priority`
3. `priority/normal` or no priority label
4. `priority/low` or `low-priority`

Also recognize:
- `good first issue` - suitable for newcomers
- `help wanted` - explicitly seeking contributors

Select up to 3 issues, preferring:
1. Unassigned issues
2. Issues assigned to the current user
3. Issues with `help wanted` label

### Step 5: Format Output

Present findings as a prioritized action list:

```markdown
## What to Focus on Next

### PRs Needing Your Review
1. [PR #123](url) - "Title" by @author
   - You were requested as reviewer
   - Updated 2 hours ago

### Your Assigned PRs with Activity
1. [PR #456](url) - "Title" (draft)
   - @someone commented 3 hours ago - may need response

### Your Open PRs
1. [PR #789](url) - "Title"
   - Status: Approved, ready to merge
2. [PR #790](url) - "Title"
   - Status: Changes requested by @reviewer

### Your Drafts
1. [PR #791](url) - "Title"
   - Last updated 3 days ago

### Priority Issues for [Milestone Name] (due YYYY-MM-DD)
1. [#100](url) - "Issue title" `priority/high`
   - Unassigned
2. [#101](url) - "Another issue" `help wanted`
   - Assigned to you
3. [#102](url) - "Third issue"
   - Unassigned

---
*PRs take precedence over new work. Review others' PRs first, then address feedback on yours, then pick up new issues.*
```

If any section is empty, note it (e.g., "No PRs currently need your review").

### Sufficient Review Heuristics

A PR is considered "sufficiently reviewed" (exclude from review list) if:
- Has 1+ APPROVED review AND no CHANGES_REQUESTED
- Has CHANGES_REQUESTED (needs author attention, not more reviews)
- Has 2+ reviews submitted in the last 24 hours (active discussion)
- All explicitly requested reviewers have submitted reviews

### Error Handling

- **Not in a git repo**: Display error and suggest running from a repository
- **gh not authenticated**: Display error with `gh auth login` instructions
- **No GitHub remote**: Display error explaining GitHub remote is required
- **No milestones**: Skip the milestone section, note "No open milestones with due dates"
- **API rate limits**: Display warning and suggest waiting

## Return Value

- **Console Output**: Formatted markdown summary of prioritized work items
- **Sections included**:
  - PRs needing review (from others)
  - Your assigned PRs with activity
  - Your open PRs with status
  - Your draft PRs
  - Priority issues from next milestone

## Examples

1. **Basic usage**:
   ```
   /github:what-next
   ```
   Output: Prioritized list of PRs and issues based on default heuristics

2. **With custom contributing file**:
   ```
   /github:what-next --contributing docs/CONTRIBUTING.md
   ```
   Output: Same as above, but uses project-specific conventions from the specified file

3. **In a repo with no open PRs or milestones**:
   ```
   /github:what-next
   ```
   Output:
   ```markdown
   ## What to Focus on Next

   ### PRs Needing Your Review
   No PRs currently need your review.

   ### Your Open PRs
   You have no open PRs.

   ### Priority Issues
   No open milestones with due dates found.

   ---
   *Consider checking the issue tracker for unassigned issues or starting new work.*
   ```

## Arguments

- `--contributing` (optional): Path to a contributing guidelines file
  - Default: Looks for `CONTRIBUTING.md` in repository root
  - If provided, reads project-specific conventions for review requirements and priority labels
  - Example: `--contributing docs/CONTRIBUTING.md`

## See Also
- `git:summary` - Quick overview of repository state
- `git:suggest-reviewers` - Find appropriate reviewers for your PR
