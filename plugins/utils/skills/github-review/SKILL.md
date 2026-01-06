---
name: GitHub Review
description: Fetch and analyze review comments from GitHub pull requests to help address code review feedback systematically
---

# GitHub Review

This skill enables AI agents to fetch, parse, and understand review comments from GitHub pull requests. It provides structured comment data that can be used to address reviewer feedback systematically, filtering out noise from bots and outdated comments.

## When to Use This Skill

Use this skill when the user wants to:
- Fetch review comments from a GitHub pull request
- Understand what feedback reviewers have left on a PR
- Address inline code comments systematically
- Get a summary of all comments on a pull request
- Filter out bot comments and outdated review comments

## Prerequisites

Before starting, verify these prerequisites:

1. **GitHub CLI (gh) Installation**
   - Check if installed: `which gh`
   - Installation: https://cli.github.com/
   - Required version: 2.0+

2. **GitHub CLI Authentication**
   - Check auth status: `gh auth status`
   - If not authenticated: `gh auth login`
   - Required for accessing private repositories

3. **Python 3 Installation**
   - Check if installed: `which python3`
   - Python 3.9+ recommended for type hint support

4. **Skill Script Location**
   - Script path: `plugins/utils/skills/github-review/fetch_github_comments.py`
   - Ensure the script is executable or run with `python3`

## Input Format

The user will provide one of the following:

1. **Full GitHub PR URL**:
   - `https://github.com/example-org/example-repo/pull/123`
   - `github.com/example-org/example-repo/pull/123`

2. **Short format**:
   - `example-org/example-repo#123`

3. **PR number only** (when in a git repository):
   - `12345` (with optional `--repo owner/repo`)

## Implementation Steps

### Step 1: Validate Prerequisites

1. **Check gh CLI**:
   ```bash
   which gh
   gh auth status
   ```

2. **If not authenticated**, instruct user:
   ```bash
   gh auth login
   ```

### Step 2: Fetch Comments

1. **Basic usage** (from PR URL):
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     "https://github.com/example-org/example-repo/pull/123"
   ```

2. **From PR number** (in a git repo):
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     12345
   ```

3. **With explicit repository**:
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     123 --repo example-org/example-repo
   ```

4. **Include bot comments** (filtered by default):
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     --include-bots \
     "https://github.com/example-org/example-repo/pull/123"
   ```

5. **Include outdated comments** (filtered by default):
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     --include-outdated \
     "https://github.com/example-org/example-repo/pull/123"
   ```

6. **Get raw JSON output** (for programmatic use):
   ```bash
   python3 plugins/utils/skills/github-review/fetch_github_comments.py \
     --json \
     "https://github.com/example-org/example-repo/pull/123"
   ```

### Step 3: Parse Output

The script outputs a structured text format:

```
======================================================================
GITHUB PULL REQUEST: #12345
Title: Fix authentication bug in OAuth handler
State: open
Author: johndoe
Branch: fix-oauth-bug → main
URL: https://github.com/example-org/example-repo/pull/123
======================================================================

Total comments: 8 (of 15 raw)
  - Filtered bot comments: 5
  - Filtered outdated comments: 2

  - PR conversation comments: 2
  - Review submissions: 3
  - Inline code comments: 3

======================================================================
COMMENTS
======================================================================

### PR-LEVEL COMMENTS ###

---
Author: reviewer1
Location: [Review - CHANGES_REQUESTED]
Time: 2025-01-05T10:30:00Z

Please address the security concern in the token validation.

### FILE: pkg/auth/oauth.go ###

---
Author: reviewer1
Location: [pkg/auth/oauth.go:45]
Time: 2025-01-05T10:32:00Z

This token validation is missing expiry check.

---
Author: reviewer2
Location: [pkg/auth/oauth.go:67]
Time: 2025-01-05T11:15:00Z

Consider using constant time comparison for token matching.

======================================================================
ACTION ITEMS
======================================================================

3 inline comment(s) on current code require attention.
Review each comment above and address the feedback.
```

### Step 4: Understand Comment Types

The script fetches three types of comments:

1. **Issue Comments** (PR Conversation)
   - General comments on the PR
   - Not tied to specific code lines
   - Location: `[PR Comment]`

2. **Reviews**
   - Review submissions (Approve, Request Changes, Comment)
   - May include summary body text
   - Location: `[Review - STATE]`

3. **Review Comments** (Inline)
   - Comments on specific lines of code
   - Include file path and line number
   - Location: `[file/path.go:123]`
   - May be marked `(OUTDATED)` if code has changed

### Step 5: Filtering Logic

By default, the script filters:

1. **Bot Comments**: Comments from known CI/automation bots
   - `openshift-ci-robot`, `openshift-ci`, `openshift-bot`
   - `github-actions[bot]`, `dependabot[bot]`, `renovate[bot]`
   - `codecov[bot]`, `sonarcloud[bot]`
   - Any author ending with `[bot]`

2. **Outdated Comments**: Inline comments where the code has changed
   - Identified by `line: null` with `original_line` present
   - These comments are no longer visible in the current diff

Use `--include-bots` and `--include-outdated` flags to include these.

## Output Format

### Text Output (default)

The default text output is optimized for AI consumption:
- Clear headers and separators
- Comment metadata (author, location, timestamp)
- Organized by file for inline comments
- Summary of action items at the end
- Filtering statistics to show what was excluded

### JSON Output (--json flag)

```json
{
  "pr": {
    "number": 12345,
    "title": "Fix authentication bug",
    "state": "open",
    "user": "johndoe",
    "head": "fix-oauth-bug",
    "base": "main",
    "html_url": "https://github.com/example-org/example-repo/pull/123"
  },
  "issue_comments": [
    {
      "id": 123456,
      "author": "reviewer1",
      "body": "Great work overall!",
      "created_at": "2025-01-05T10:00:00Z",
      "url": "https://github.com/...",
      "type": "issue_comment"
    }
  ],
  "reviews": [
    {
      "id": 789012,
      "author": "reviewer1",
      "body": "Please address security concern",
      "state": "CHANGES_REQUESTED",
      "submitted_at": "2025-01-05T10:30:00Z",
      "type": "review"
    }
  ],
  "review_comments": [
    {
      "id": 345678,
      "author": "reviewer1",
      "body": "Missing expiry check",
      "path": "pkg/auth/oauth.go",
      "line": 45,
      "diff_hunk": "@@ -40,10 +40,15 @@...",
      "type": "review_comment"
    }
  ]
}
```

## Error Handling

Handle these error scenarios gracefully:

1. **gh CLI not found**
   - Error: "'gh' CLI not found. Install from https://cli.github.com/"
   - Provide installation instructions

2. **Not authenticated**
   - Error: "Not logged into any GitHub hosts"
   - Instruct: `gh auth login`

3. **Invalid PR reference**
   - Error: "Could not parse GitHub PR URL: {url}"
   - Provide examples of valid formats

4. **PR not found (404)**
   - Error: "Failed to fetch PR details"
   - Verify PR number and repository access

5. **No repository context**
   - Error: "Could not determine repository. Use --repo or provide full URL."
   - User needs to specify `--repo owner/repo`

6. **Rate limiting**
   - gh CLI handles rate limiting automatically
   - May see delays on large PRs

## Known Bots (Filtered by Default)

| Bot | Purpose |
|-----|---------|
| openshift-ci-robot | OpenShift CI automation |
| openshift-ci | OpenShift CI status |
| openshift-bot | OpenShift automation |
| github-actions[bot] | GitHub Actions |
| dependabot[bot] | Dependency updates |
| renovate[bot] | Dependency updates |
| codecov[bot] | Code coverage reports |
| sonarcloud[bot] | Code quality analysis |

## Examples

### Example 1: Fetch comments from a PR URL

```bash
python3 plugins/utils/skills/github-review/fetch_github_comments.py \
  "https://github.com/example-org/example-repo/pull/123"
```

### Example 2: Fetch from PR number in current repo

```bash
cd ~/repos/origin
python3 ~/ai-helpers/plugins/utils/skills/github-review/fetch_github_comments.py 12345
```

### Example 3: Include all comments (no filtering)

```bash
python3 plugins/utils/skills/github-review/fetch_github_comments.py \
  --include-bots --include-outdated \
  "https://github.com/example-org/example-repo/pull/123"
```

### Example 4: Get JSON for scripting

```bash
python3 plugins/utils/skills/github-review/fetch_github_comments.py \
  --json \
  "https://github.com/example-org/example-repo/pull/123" \
  | jq '.review_comments | length'
```

### Example 5: Short format

```bash
python3 plugins/utils/skills/github-review/fetch_github_comments.py \
  "example-org/example-repo#123"
```

## Tips

- **Default filtering**: Bots and outdated comments are filtered by default to reduce noise
- **Use JSON for automation**: The `--json` flag provides structured data for scripting
- **Large PRs**: The script uses pagination, so it handles PRs with many comments
- **Private repos**: Ensure `gh auth status` shows access to the repository
- **Rate limits**: GitHub API has rate limits; gh CLI handles this automatically

## Integration with address-reviews Command

This skill powers the `/utils:address-reviews` slash command when a GitHub URL is detected:

1. The command auto-detects GitHub from the URL pattern
2. Can use this script to fetch comments (or use `gh` CLI directly)
3. Parses and categorizes the output
4. Systematically addresses each comment
5. Posts replies using `gh api`

The unified `/utils:address-reviews` command supports both GitHub and Gerrit, auto-detecting the platform from the URL.

See the `address-reviews.md` command for the full implementation.

## Comparison with Gerrit Skill

| Feature | GitHub | Gerrit |
|---------|--------|--------|
| CLI Tool | `fetch_github_comments.py` | `fetch_gerrit_comments.py` |
| Authentication | gh CLI (`gh auth login`) | None (public) / HTTP auth |
| Comment Types | Issue, Review, Review Comment | Patchset-level, Inline |
| Outdated Detection | `line == null` | N/A (Gerrit tracks by patchset) |
| Bot Filtering | Built-in | Manual |
| Posting Replies | Via gh API | Requires auth |

## Limitations

1. **Authentication required**: Must be logged in via `gh auth login`
2. **Rate limiting**: GitHub API has rate limits (5000 req/hour authenticated)
3. **No thread reconstruction**: Shows flat list, doesn't show reply chains
4. **No suggested changes**: Doesn't parse GitHub's "suggestion" format specially

## Future Enhancements

- Parse GitHub's suggested changes format
- Reconstruct comment reply threads
- Add resolution status detection (GitHub doesn't have native resolution)
- Support for GitHub Enterprise Server URLs
- Batch comment posting for efficiency

