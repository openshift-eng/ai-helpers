---
name: External Links
description: GitHub PR and GitLab MR integration for status analysis
---

# External Links

This module extracts and analyzes GitHub Pull Requests and GitLab Merge Requests linked to Jira issues. It enriches the status analysis with code-level activity.

## Overview

External link analysis follows this flow:

```
1. Check prerequisites (gh/glab CLI)
         │
         ▼
2. Extract PR/MR URLs from issue data
         │
         ▼
3. Fetch PR/MR metadata via CLI
         │
         ▼
4. Filter to date range
         │
         ▼
5. Categorize by state
         │
         ▼
6. Build external_links result
```

## Prerequisites Check

Before processing, verify required tools are available:

```bash
# Check for GitHub CLI
if command -v gh &> /dev/null; then
    gh auth status 2>&1
    # If authenticated, gh_available = true
fi

# Check for GitLab CLI (optional)
if command -v glab &> /dev/null; then
    glab auth status 2>&1
    # If authenticated, glab_available = true
fi
```

**If gh is not available**:
- Log warning: "GitHub CLI (gh) not installed. PR metadata will be limited."
- Continue with URL extraction only (no state/merge info)
- Provide installation guidance in output

**If glab is not available**:
- Log info: "GitLab CLI (glab) not installed. MR URLs will be noted for manual checking."
- Continue with URL extraction only

## Step 1: Extract PR/MR URLs

### Source 1: Jira Remote Links (via changelog)

Remote links appear in changelog as `RemoteIssueLink` field changes:

```python
for issue in all_issues:
    for history in issue.changelog.histories:
        for item in history.items:
            if item.field == "RemoteIssueLink":
                url = extract_url(item.toString or item.to_string)
                if is_github_pr(url) or is_gitlab_mr(url):
                    add_to_links(url, source="remote_link", issue_key=issue.key)
```

**URL patterns**:
```regex
# GitHub PR
https?://github\.com/([^/]+)/([^/]+)/pull[s]?/(\d+)

# GitLab MR
https?://gitlab\.com/([^/]+)/([^/]+)/-/merge_requests/(\d+)
https?://([^/]+)/([^/]+)/([^/]+)/-/merge_requests/(\d+)  # Self-hosted GitLab
```

### Source 2: Issue Description

Parse the description field for PR/MR URLs:

```python
description = issue.fields.description or ""
github_prs = re.findall(r'https?://github\.com/[^/]+/[^/]+/pulls?/\d+', description)
gitlab_mrs = re.findall(r'https?://[^/]+/[^/]+/[^/]+/-/merge_requests/\d+', description)
```

### Source 3: Comments

Parse all comments for PR/MR URLs:

```python
for comment in issue.comments:
    body = comment.body or ""
    github_prs = re.findall(r'https?://github\.com/[^/]+/[^/]+/pulls?/\d+', body)
    gitlab_mrs = re.findall(r'https?://[^/]+/[^/]+/[^/]+/-/merge_requests/\d+', body)
    # Track which comment mentioned it for context
```

### Source 4: Issue Links Field

Check the `issuelinks` field for web links:

```python
for link in issue.issuelinks:
    if link.type == "Web Link" or hasattr(link, 'object'):
        url = link.object.url if hasattr(link, 'object') else link.url
        # Check if it matches PR/MR patterns
```

### Deduplication

Merge URLs found in multiple sources:

```json
{
  "url": "https://github.com/openshift/hypershift/pull/6444",
  "sources": ["remote_link", "comment", "description"],
  "found_in_issues": ["OCPSTRAT-1234", "OCPSTRAT-1235"]
}
```

Sort `sources` and `found_in_issues` alphabetically for consistency.

## Step 2: Fetch GitHub PR Metadata

For each unique GitHub PR URL:

```bash
gh pr view {PR-NUMBER} --repo {OWNER}/{REPO} --json state,title,isDraft,updatedAt,mergedAt,createdAt,url
```

**Parse the output**:

```json
{
  "url": "https://github.com/openshift/hypershift/pull/6444",
  "state": "MERGED",
  "title": "Add support for custom OVN subnets",
  "isDraft": false,
  "createdAt": "2025-01-05T10:00:00Z",
  "updatedAt": "2025-01-08T15:30:00Z",
  "mergedAt": "2025-01-08T15:30:00Z"
}
```

**State values**:
- `OPEN`: PR is open and awaiting review/merge
- `CLOSED`: PR was closed without merging
- `MERGED`: PR was merged

**Error handling**:
- If PR not found (deleted/private): Log warning, exclude from results
- If rate limited: Display error with reset time, pause and retry or skip
- If auth fails: Log warning, continue without metadata

## Step 3: Fetch GitLab MR Metadata (if glab available)

For each unique GitLab MR URL:

```bash
glab mr view {MR-NUMBER} --repo {PROJECT-PATH} --output json
```

**Parse the output**:

```json
{
  "url": "https://gitlab.com/org/project/-/merge_requests/123",
  "state": "merged",
  "title": "Implement feature Y",
  "draft": false,
  "created_at": "2025-01-05T10:00:00Z",
  "updated_at": "2025-01-08T15:30:00Z",
  "merged_at": "2025-01-08T15:30:00Z"
}
```

**If glab not available**:
- Keep URL in list with `state: "unknown"`
- Note in output: "MR status unknown - check manually"

## Step 4: Filter to Date Range

Filter PRs/MRs to those with activity in the analysis date range:

```python
def is_active_in_range(pr, start_date, end_date):
    # Check if any relevant date falls within range
    dates_to_check = [
        pr.get("createdAt"),
        pr.get("updatedAt"),
        pr.get("mergedAt")
    ]
    for date_str in dates_to_check:
        if date_str:
            date = parse_date(date_str)
            if start_date <= date <= end_date:
                return True
    return False

active_prs = [pr for pr in all_prs if is_active_in_range(pr, start_date, end_date)]
```

**Also track**:
- PRs merged within date range → achievements
- PRs updated within date range → in progress
- PRs created within date range → new work started

## Step 5: Categorize by State

Group PRs/MRs by their current state and recent activity:

```json
{
  "merged_in_range": [
    {
      "url": "https://github.com/org/repo/pull/456",
      "title": "Add OAuth2 token validation",
      "merged_at": "2025-01-08T15:30:00Z",
      "found_in_issues": ["OCPSTRAT-1235"]
    }
  ],
  "open_and_active": [
    {
      "url": "https://github.com/org/repo/pull/789",
      "title": "Session handling refactor",
      "state": "OPEN",
      "isDraft": true,
      "updated_at": "2025-01-10T10:00:00Z",
      "found_in_issues": ["OCPSTRAT-1237"]
    }
  ],
  "open_and_stale": [
    {
      "url": "https://github.com/org/repo/pull/123",
      "title": "Old feature",
      "state": "OPEN",
      "updated_at": "2024-12-01T10:00:00Z",
      "found_in_issues": ["OCPSTRAT-1238"]
    }
  ],
  "closed_without_merge": [
    {
      "url": "https://github.com/org/repo/pull/100",
      "title": "Abandoned approach",
      "state": "CLOSED",
      "found_in_issues": ["OCPSTRAT-1239"]
    }
  ]
}
```

**Categorization logic**:

| Category | Criteria |
|----------|----------|
| merged_in_range | state=MERGED AND mergedAt within date range |
| open_and_active | state=OPEN AND updatedAt within date range |
| open_and_stale | state=OPEN AND updatedAt before date range |
| closed_without_merge | state=CLOSED |

## Step 6: Build External Links Result

Produce the final structure for the `IssueActivityData`:

```json
{
  "external_links": {
    "github_prs": [
      {
        "url": "https://github.com/openshift/hypershift/pull/6444",
        "state": "MERGED",
        "title": "Add support for custom OVN subnets",
        "isDraft": false,
        "mergedAt": "2025-01-08T15:30:00Z",
        "sources": ["remote_link", "comment"],
        "found_in_issues": ["OCPSTRAT-1234", "OCPSTRAT-1235"],
        "activity_in_range": true
      }
    ],
    "gitlab_mrs": [
      {
        "url": "https://gitlab.com/org/project/-/merge_requests/123",
        "state": "unknown",
        "title": null,
        "sources": ["description"],
        "found_in_issues": ["OCPSTRAT-1236"],
        "note": "GitLab CLI not available - check manually"
      }
    ],
    "summary": {
      "total_prs": 5,
      "merged_in_range": 2,
      "open_and_active": 2,
      "open_and_stale": 1,
      "total_mrs": 1,
      "mr_status_unknown": 1
    }
  }
}
```

## Integration with Activity Analysis

The external links data feeds into the activity analysis:

### Achievements

PRs merged in date range become achievements:

```python
for pr in external_links.merged_in_range:
    achievements.append({
        "description": f"PR #{pr.number} merged: {pr.title}",
        "source": "github",
        "url": pr.url,
        "date": pr.mergedAt
    })
```

### In Progress

Open PRs with recent activity become in-progress items:

```python
for pr in external_links.open_and_active:
    status = "Draft PR" if pr.isDraft else "PR in review"
    in_progress.append({
        "description": f"{status}: {pr.title}",
        "source": "github",
        "url": pr.url
    })
```

### Risks

Stale open PRs may indicate risks:

```python
for pr in external_links.open_and_stale:
    days_stale = (today - pr.updated_at).days
    if days_stale > 14:
        risks.append({
            "description": f"Stale PR #{pr.number} ({days_stale} days without update)",
            "severity": "low",
            "url": pr.url
        })
```

## URL Parsing Utilities

### Extract Owner/Repo/Number from GitHub URL

```python
def parse_github_pr_url(url):
    # https://github.com/owner/repo/pull/123
    match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/pulls?/(\d+)', url)
    if match:
        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "number": int(match.group(3))
        }
    return None
```

### Extract Project/Number from GitLab URL

```python
def parse_gitlab_mr_url(url):
    # https://gitlab.com/org/project/-/merge_requests/123
    # https://gitlab.example.com/group/subgroup/project/-/merge_requests/123
    match = re.match(r'https?://([^/]+)/(.+)/-/merge_requests/(\d+)', url)
    if match:
        return {
            "host": match.group(1),
            "project": match.group(2),
            "number": int(match.group(3))
        }
    return None
```

## Error Handling

| Error | Handling |
|-------|----------|
| gh not installed | Log warning, continue with URL-only extraction |
| gh auth failed | Log warning with `gh auth login` guidance |
| PR not found (404) | Log warning, exclude from results |
| Rate limited (403) | Display reset time, pause or skip remaining PRs |
| Network timeout | Retry once, then log warning and continue |
| Invalid URL format | Log warning, skip URL |
| glab not installed | Log info, mark MRs as "check manually" |

## Performance Tips

1. **Batch PR fetches**: If multiple PRs from same repo, consider using GitHub GraphQL API
2. **Parallelize**: PR metadata fetches are independent, run concurrently
3. **Cache results**: Store PR metadata to avoid re-fetching during refinement
4. **Limit scope**: Only fetch metadata for PRs that might be in date range (check URL first if possible)
5. **Fail fast**: If gh auth fails, skip all PR fetches rather than failing each one

## Installation Guidance

If tools are missing, provide helpful installation instructions:

**GitHub CLI (gh)**:
```text
GitHub CLI not installed. To enable PR metadata:

macOS:    brew install gh
Linux:    See https://github.com/cli/cli/blob/trunk/docs/install_linux.md
Windows:  winget install --id GitHub.cli

Then authenticate: gh auth login
```

**GitLab CLI (glab)**:
```text
GitLab CLI not installed. MR URLs will be noted for manual checking.

To enable MR metadata:
macOS:    brew install glab
Linux:    See https://gitlab.com/gitlab-org/cli#installation

Then authenticate: glab auth login
```
