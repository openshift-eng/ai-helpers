---
name: fetch-pr-comments
description: Fetch new review comments from a GitHub PR, filtered to trusted users (org members + allowed bots). Use when monitoring a PR for feedback, checking for new review comments, or building a review-response workflow.
---

# Fetch PR Comments

Fetch all comments from a GitHub pull request, filtered to trusted users only. Trusted users are GitHub org members and explicitly allowed bots. Untrusted comments are silently excluded.

This skill fetches from all three GitHub comment endpoints (inline review comments, review summaries, and PR conversation comments), providing a complete picture of PR feedback.

## When to Use This Skill

Use this skill when you need to:

- Check a PR for new review comments that need attention
- Monitor a PR for feedback during an agentic workflow
- Build a review-response loop that only processes trusted feedback
- Fetch all actionable PR comments in a single call

## Prerequisites

1. **`gh` CLI**: Authenticated with `gh auth login`
2. **Repository read access**: The token must have permission to read PR comments and check org membership

## Implementation

### Basic usage

```bash
result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/fetch-pr-comments/fetch_pr_comments.sh" \
  --repo owner/repo \
  --pr 123)
```

### With custom trusted bots and exclusions

```bash
result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/fetch-pr-comments/fetch_pr_comments.sh" \
  --repo owner/repo \
  --pr 123 \
  --trusted-bots "coderabbitai,dependabot" \
  --exclude-ids "12345,67890")
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--repo` | Yes | GitHub repository in `owner/repo` format |
| `--pr` | Yes | Pull request number |
| `--trusted-bots` | No | Comma-separated bot logins to trust (default: `coderabbitai`) |
| `--exclude-ids` | No | Comma-separated comment IDs to skip (already processed) |

### Output

JSON on stdout:

```json
{
  "inline_comments": [
    {"id": "123", "user": "reviewer", "path": "pkg/server.go", "body": "This needs a nil check"}
  ],
  "reviews": [
    {"id": "456", "user": "reviewer", "state": "CHANGES_REQUESTED", "body": "See inline comments"}
  ],
  "issue_comments": [
    {"id": "789", "user": "coderabbitai[bot]", "body": "Static analysis found..."}
  ],
  "all_ids": ["123", "456", "789"],
  "total": 3,
  "formatted": {
    "inline": "**reviewer** on `pkg/server.go`:\nThis needs a nil check\n---",
    "reviews": "**reviewer** (CHANGES_REQUESTED):\nSee inline comments\n---",
    "issue_comments": "**coderabbitai[bot]**:\nStatic analysis found...\n---"
  }
}
```

### Using in a polling loop

The `all_ids` and `--exclude-ids` fields enable stateful polling across iterations:

```bash
PROCESSED_IDS=""

while true; do
  sleep 300

  result=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/fetch-pr-comments/fetch_pr_comments.sh" \
    --repo owner/repo --pr 123 --exclude-ids "$PROCESSED_IDS")

  total=$(echo "$result" | jq -r '.total')
  if [[ "$total" -gt 0 ]]; then
    # Process comments...
    new_ids=$(echo "$result" | jq -r '.all_ids | join(",")')
    PROCESSED_IDS="${PROCESSED_IDS:+$PROCESSED_IDS,}$new_ids"
  fi
done
```

### Using formatted output for Claude prompts

The `formatted` fields provide ready-to-use text:

```bash
inline=$(echo "$result" | jq -r '.formatted.inline')
reviews=$(echo "$result" | jq -r '.formatted.reviews')
issue_comments=$(echo "$result" | jq -r '.formatted.issue_comments')
```

## How It Works

1. Fetches from three GitHub API endpoints:
   - `repos/{repo}/pulls/{pr}/comments` — inline code review comments
   - `repos/{repo}/pulls/{pr}/reviews` — review summaries (CHANGES_REQUESTED, etc.)
   - `repos/{repo}/issues/{pr}/comments` — PR conversation thread
2. Identifies all unique comment authors
3. Checks each author against the trusted bots list and org membership (`gh api orgs/{org}/members/{login}`)
4. Filters comments to trusted authors only
5. Excludes already-processed comment IDs
6. Filters out APPROVED and PENDING reviews (no actionable content)
7. Returns structured JSON with both raw data and pre-formatted text

## Trust Model

A user is trusted if they match ANY of:
- Their login matches a `--trusted-bots` entry (with or without `[bot]` suffix)
- They are a member of the repository's GitHub organization

All other commenters are silently excluded.

## See Also

- Related Skill: `check-pr-ci-status` — Check CI status and detect new failures
- Related Skill: `upload-screenshot` — Upload images to GitHub for PR comments
- Related Command: `/utils:address-reviews` — Full review-addressing workflow
