---
name: CodeRabbit Rules from PR Reviews - Fetch Comments
description: Fetch and filter human review comments from recent merged PRs in a GitHub repository
---

# CodeRabbit Rules from PR Reviews - Fetch Comments

This skill runs a Python script that fetches human review comments from recent merged PRs in a given GitHub repository. It handles all GitHub API calls, bot filtering, noise removal, rate limiting, and pagination, returning clean JSON output for AI analysis.

## When to Use This Skill

Use this skill as Step 2-3 of the `/teams:coderabbit-rules-from-pr-reviews` command to collect review comments. The script replaces manual `gh api` calls with a single Python invocation.

## Prerequisites

1. **GitHub CLI (`gh`)**: Must be installed and authenticated.
2. **Python 3**: Python 3.6 or later.

## Script Location

```
plugins/teams/skills/coderabbit-rules-from-pr-reviews/fetch_pr_comments.py
```

## Usage

```bash
# Default: 30 most recent merged PRs
python3 plugins/teams/skills/coderabbit-rules-from-pr-reviews/fetch_pr_comments.py openshift/origin

# Custom count
python3 plugins/teams/skills/coderabbit-rules-from-pr-reviews/fetch_pr_comments.py openshift/origin --count 50

# Full URL
python3 plugins/teams/skills/coderabbit-rules-from-pr-reviews/fetch_pr_comments.py https://github.com/openshift/origin
```

## What the Script Does

1. **Parses the repo argument** — accepts `owner/repo` or full GitHub URL
2. **Fetches recent merged PRs** via `gh pr list`
3. **For each PR, fetches two types of comments**:
   - Inline code review comments (`/pulls/{number}/comments`)
   - General discussion comments (`/issues/{number}/comments`)
4. **Filters out noise**:
   - Bot accounts: logins ending in `[bot]` or matching known bots (`coderabbitai`, `openshift-ci`, `openshift-bot`, `openshift-merge-robot`, `codecov`, `dependabot`, `renovate`, `k8s-ci-robot`, etc.)
   - Prow commands: comments where every line starts with `/`
   - Approvals: `/lgtm`, `/approve`, `/hold`, etc.
   - Short comments: less than 20 characters
5. **Rate limiting**: 0.5s sleep between API calls, with retry logic for rate limit errors

## Output Format

JSON to stdout, progress to stderr:

```json
{
  "repo": "openshift/origin",
  "prs_analyzed": 30,
  "total_comments": 142,
  "unique_reviewers": 18,
  "reviewers": ["alice", "bob", "carol"],
  "prs": [
    {
      "number": 29500,
      "title": "Fix flaky test in e2e suite",
      "author": "dave",
      "url": "https://github.com/openshift/origin/pull/29500",
      "merged_at": "2026-03-25T14:30:00Z"
    }
  ],
  "comments": [
    {
      "pr": 29500,
      "user": "alice",
      "body": "This error should be wrapped with fmt.Errorf to preserve context",
      "path": "pkg/cmd/server/start.go",
      "type": "review",
      "pr_title": "Fix flaky test in e2e suite",
      "pr_author": "dave"
    },
    {
      "pr": 29500,
      "user": "bob",
      "body": "We should add a unit test for this edge case",
      "path": "",
      "type": "issue",
      "pr_title": "Fix flaky test in e2e suite",
      "pr_author": "dave"
    }
  ]
}
```

### Field Descriptions

- `repo`: The normalized `owner/repo` string
- `prs_analyzed`: Number of merged PRs fetched
- `total_comments`: Number of human review comments after filtering
- `unique_reviewers`: Count of distinct human reviewers
- `reviewers`: Sorted list of reviewer logins
- `prs[].number`: PR number
- `prs[].title`: PR title
- `prs[].author`: PR author login
- `prs[].url`: PR URL
- `prs[].merged_at`: Merge timestamp
- `comments[].pr`: PR number the comment belongs to
- `comments[].user`: Reviewer login
- `comments[].body`: Full comment text
- `comments[].path`: File path (for inline review comments; empty for discussion comments)
- `comments[].type`: `"review"` for inline code comments, `"issue"` for general discussion
- `comments[].pr_title`: Title of the PR
- `comments[].pr_author`: Author of the PR

## Notes

- Uses only Python standard library (no pip dependencies)
- Diagnostic/progress messages go to stderr, JSON data to stdout
- Handles GitHub API pagination for PRs with many comments
- Retries on rate limits with exponential backoff
- Analyzing 30 PRs typically takes 1-2 minutes (~60 API calls)
