---
description: List PRs and issues requiring your attention
argument-hint: "[--repo <org/repo>]"
---

## Name
utils:gh-attention

## Synopsis
```
/utils:gh-attention [--repo <org/repo>]
```

## Description
The `utils:gh-attention` command identifies pull requests and issues that are waiting for your action. It scans for specific states where you are the blocker: unresolved review comments on your PRs, unanswered PR conversation comments, change requests you haven't addressed, merge conflicts, and unanswered questions on assigned issues.

This command helps cut through notification noise by focusing only on actionable items where others are waiting for your input.

## Implementation

### Step 0: Prerequisites and Setup

1. **Check `gh` CLI installation and authentication**:
   ```bash
   gh version || echo "gh CLI not installed. Install from https://cli.github.com/"
   gh auth status || gh auth login
   ```

2. **Parse arguments**:
   - Check for `--repo <org/repo>` flag
   - Extract repository if provided

3. **Get current username**:
   ```bash
   CURRENT_USER=$(gh api user -q .login)
   ```

### Step 1: Repository Discovery

**If `--repo` is provided**:
- Use the specified repository
- Skip discovery phase

**If no `--repo` argument**:

1. **Find all open PRs authored by current user**:
   ```bash
   gh search prs --author=@me --state=open --json number,repository,title,url,isDraft --limit 100
   ```

2. **Find all open issues assigned to current user**:
   ```bash
   gh search issues --assignee=@me --state=open --json number,repository,title,url --limit 100
   ```

3. **Filter out draft PRs immediately** to reduce API calls

4. **Extract unique repositories** from the results

### Step 2: Data Collection

**Use GraphQL for efficient data fetching:** GraphQL allows us to fetch all needed data in a single query and provides direct access to the `isResolved` field on review threads.

For each PR (non-draft only):

1. **Fetch all PR data using GraphQL**:

   Split the repository owner and name from `<REPO>` (format: `owner/name`).

   ```bash
   gh api graphql -f query='
   query($owner: String!, $name: String!, $number: Int!) {
     repository(owner: $owner, name: $name) {
       pullRequest(number: $number) {
         number
         title
         url
         createdAt
         mergeable
         reviewThreads(first: 100) {
           nodes {
             isResolved
             isOutdated
             comments(first: 20) {
               nodes {
                 author { login }
                 body
                 createdAt
                 path
                 line
               }
             }
           }
         }
         reviews(first: 50) {
           nodes {
             author { login }
             state
             submittedAt
             body
           }
         }
         comments(first: 100) {
           nodes {
             author { login }
             body
             createdAt
           }
         }
         commits(last: 50) {
           nodes {
             commit {
               committedDate
             }
           }
         }
       }
     }
   }' -f owner='<OWNER>' -f name='<NAME>' -F number=<PR_NUMBER>
   ```

2. **Parse the GraphQL response** to extract:
   - PR metadata (number, title, url, mergeable)
   - Review threads with resolution status
   - Reviews with state and timestamp
   - PR comments (general conversation comments)
   - Commit timestamps

For each issue:

1. **Fetch issue data using GraphQL**:

   ```bash
   gh api graphql -f query='
   query($owner: String!, $name: String!, $number: Int!) {
     repository(owner: $owner, name: $name) {
       issue(number: $number) {
         number
         title
         url
         body
         comments(first: 100) {
           nodes {
             author { login }
             body
             createdAt
           }
         }
       }
     }
   }' -f owner='<OWNER>' -f name='<NAME>' -F number=<ISSUE_NUMBER>
   ```

2. **Parse the GraphQL response** to extract issue details and comments

### Step 3: Analysis and Detection

#### A. Detect Merge Conflicts (CRITICAL Priority)

For each PR:
- Check `mergeable` field from Step 2.1
- If `mergeable == "CONFLICTING"`, flag as CRITICAL
- Record: `Merge conflict needs resolution`

#### B. Detect Review Feedback (HIGH Priority)

For each PR (from GraphQL data), check for any pending review feedback:

1. **Check for unresolved review threads**:
   - Filter review threads where:
     - `isResolved == false` (direct from GraphQL)
     - `isOutdated == false` (ignore outdated code comments)
     - First comment author is not a bot (`dependabot`, `renovate`, `openshift-ci-robot`, `openshift-ci`)
   - For each unresolved thread:
     - Get the last comment in the thread
     - If `last_comment.author.login == CURRENT_USER`, skip (you already responded)
     - Otherwise, record: `path:line - @author commented (X days ago)` with snippet (first 80 chars)

2. **Check for unaddressed change request reviews**:
   - Filter reviews where `state == "CHANGES_REQUESTED"`
   - For each change request:
     - Compare review `submittedAt` with commit dates (`commits.nodes[].commit.committedDate`)
     - If NO commits after the review, record: `@reviewer requested changes (X days ago)`
     - If multiple from same reviewer, use most recent

3. **Check for unanswered PR comments** (general conversation comments):
   - Get PR comments from GraphQL response
   - Find your last comment timestamp in the PR conversation
   - For comments after your last comment where:
     - `author.login != CURRENT_USER`
     - Author is not a bot (exclude `dependabot`, `renovate`, `openshift-ci-robot`, `openshift-ci`)
     - `body` contains `@{CURRENT_USER}` OR `body` contains `?`
   - Record: `@author commented in PR conversation (X days ago)` with snippet (first 80 chars)

4. **Combine and flag as HIGH priority** if any of: unresolved threads, unaddressed change requests, or unanswered PR comments exist

#### C. Detect Unanswered Issue Questions (LOW Priority)

For each assigned issue (from GraphQL data):

1. **Find your last comment timestamp**:
   - Scan comments from GraphQL response
   - Find most recent comment where `author.login == CURRENT_USER`

2. **Check for questions after your last comment**:
   - Look for comments where:
     - `createdAt > your_last_comment_timestamp`
     - `body` contains `@{CURRENT_USER}` OR `body` contains `?`
     - `author.login != CURRENT_USER`
     - Author is not a bot (exclude `dependabot`, `renovate`, `openshift-ci-robot`, `openshift-ci`)

3. **Also check the issue body** for unanswered questions if you haven't commented yet

4. **For each unanswered question**:
   - Flag as LOW priority
   - Record: `@author asked a question (X days ago)`
   - Use comment's `createdAt` to calculate waiting time

### Step 4: Calculate Waiting Time

For each detected item:
- Calculate days/hours since the triggering event (review submitted, comment posted, conflict detected)
- Format as human-readable: `3 days ago`, `5 hours ago`, `just now`

### Step 5: Sort and Prioritize

1. **Primary sort**: By priority level
   - CRITICAL (merge conflicts)
   - HIGH (review feedback - change requests, unresolved threads, and unanswered PR comments)
   - LOW (issue questions)

2. **Secondary sort**: By waiting time (oldest first within each priority)

### Step 6: Generate Output

**Header**:
```
Found X items requiring attention across Y repositories
```

**For each item, display**:
```
[PRIORITY_LEVEL] Repository: org/repo
  PR #123: Title of the pull request
  URL: https://github.com/org/repo/pull/123
  Reason: [specific reason - e.g., "2 unresolved comment threads"]
  Waiting: X days since last comment

  Details:
  • path/to/file.go:45 - @reviewer asked about error handling (2 days ago)
    "Should we add retry logic here?"
  • path/to/other.go:120 - @reviewer requested refactoring (3 days ago)
    "Consider extracting this into a helper function"
```

**Footer summary**:
```
Summary:
  1 PR with merge conflicts
  3 PRs with review feedback
  1 issue with unanswered questions
```

**If no items found**:
```
✓ No items requiring attention! All caught up.
```

### Step 7: Error Handling

**No repositories found**:
```
No open PRs or assigned issues found.
```

**API rate limit hit**:
```
⚠️  GitHub API rate limit reached after checking X items.
Try using --repo <org/repo> to narrow the scope.
Rate limit resets at: [timestamp from gh api rate_limit]
```

**Authentication failure**:
```
❌ GitHub CLI not authenticated.
Run: gh auth login
```

**Repository access denied**:
```
⚠️  Unable to access repository <org/repo> (private or insufficient permissions)
Skipping...
```

## Return Value

The command outputs a prioritized list of actionable items with:
- **Priority level**: CRITICAL, HIGH, or LOW
- **Repository and PR/issue number**: For navigation
- **URL**: Direct link to the item
- **Reason**: Why it requires attention
- **Waiting time**: How long since the triggering event
- **Details**: Specific comments, reviewers, or questions with context
- **Summary**: Count of items by category

Exit codes:
- `0`: Success (items found or no items found)
- `1`: Error (authentication failure, gh CLI not found)

## Examples

### Example 1: Check all repositories

```
/utils:gh-attention
```

Output:
```
Found 3 items requiring attention across 2 repositories

[HIGH] Repository: openshift/console
  PR #5678: Add dark mode toggle
  URL: https://github.com/openshift/console/pull/5678
  Reason: 2 unresolved review threads
  Waiting: 3 days since last comment

  Details:
  • src/components/Header.tsx:120 - @designer commented (3 days ago)
    "Can we use the theme constant instead of hardcoding?"
  • src/styles/theme.css:15 - @reviewer commented (2 days ago)
    "Should this support high contrast mode?"

[HIGH] Repository: openshift/origin
  PR #1234: Fix authentication timeout bug
  URL: https://github.com/openshift/origin/pull/1234
  Reason: 1 change request, 1 unresolved thread
  Waiting: 2 days since review

  Details:
  • @reviewer-name requested changes (2 days ago)
    "Please add unit tests for the timeout logic"
  • pkg/auth/handler.go:45 - @reviewer commented (1 day ago)
    "Should we log this error before returning?"

[LOW] Repository: openshift/enhancements
  Issue #234: Enhancement proposal for new API
  URL: https://github.com/openshift/enhancements/issues/234
  Reason: Unanswered question
  Waiting: 4 days since question

  Details:
  • @team-member asked a question (4 days ago)
    "@you What's the timeline for implementing this?"

Summary:
  2 PRs with review feedback
  1 issue with unanswered questions
```

### Example 2: Check specific repository

```
/utils:gh-attention --repo openshift/origin
```

Output:
```
Found 1 item requiring attention in openshift/origin

[HIGH] Repository: openshift/origin
  PR #1234: Fix authentication timeout bug
  URL: https://github.com/openshift/origin/pull/1234
  Reason: Change request not addressed
  Waiting: 2 days since review

  Details:
  • @reviewer-name requested changes (2 days ago)
    "Please add unit tests for the timeout logic"

Summary:
  1 PR with unaddressed change requests
```

### Example 3: No items requiring attention

```
/utils:gh-attention
```

Output:
```
✓ No items requiring attention! All caught up.
```

## Arguments:
- `--repo <org/repo>`: (Optional) Limit check to a specific repository. If omitted, checks all repositories with your open PRs or assigned issues.