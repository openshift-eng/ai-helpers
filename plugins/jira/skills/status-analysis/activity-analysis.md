---
name: Activity Analysis
description: Detecting blockers, progress, risks, and completion from Jira issue data
---

# Activity Analysis

This module analyzes the collected issue data to identify blockers, progress, risks, and achievements. It produces the `analysis` section of each `IssueActivityData` structure.

## Overview

Activity analysis follows this flow:

```
1. Filter data to date range
         │
         ▼
2. Analyze changelog for key events
         │
         ▼
3. Analyze comments for context
         │
         ▼
4. Aggregate descendant status
         │
         ▼
5. Determine overall health
         │
         ▼
6. Build analysis result
```

## Step 1: Filter Data to Date Range

Apply the configured date range to all data:

**Changelog filtering**:
```python
# Pseudocode
for entry in changelog.histories:
    entry_date = parse_date(entry.created)
    if start_date <= entry_date <= end_date:
        include entry in filtered_changelog
```

**Comment filtering**:
```python
for comment in comments:
    comment_date = parse_date(comment.created)
    if start_date <= comment_date <= end_date:
        include comment in filtered_comments
```

**Descendant filtering**:
```python
for descendant in descendants:
    descendant_date = parse_date(descendant.updated)
    descendant.updated_in_range = (start_date <= descendant_date <= end_date)
```

## Step 2: Analyze Changelog for Key Events

Parse the filtered changelog to identify significant events:

### Status Transitions

Extract all status changes:

```json
{
  "status_transitions": [
    {
      "from": "To Do",
      "to": "In Progress",
      "date": "2025-01-07T09:00:00Z",
      "author": "jdoe@example.com",
      "issue_key": "OCPSTRAT-1235"
    }
  ]
}
```

**Categorize transitions**:

| Category | Transitions | Meaning |
|----------|-------------|---------|
| Started | To Do → In Progress, Backlog → In Progress | Work began |
| Completed | In Progress → Done, In Progress → Closed, In Review → Done | Work finished |
| Blocked | Any → Blocked, Any status with "blocked" | Work stopped |
| Reopened | Done → In Progress, Closed → Reopened | Issue came back |
| Review | In Progress → In Review, In Progress → Code Review | Awaiting review |

### Assignee Changes

Track who is working on what:

```json
{
  "assignee_changes": [
    {
      "from": "user1@example.com",
      "to": "user2@example.com",
      "date": "2025-01-08T10:00:00Z",
      "issue_key": "OCPSTRAT-1235"
    }
  ]
}
```

### Priority/Severity Changes

Note escalations or de-escalations:

```json
{
  "priority_changes": [
    {
      "from": "Medium",
      "to": "High",
      "date": "2025-01-09T11:00:00Z",
      "issue_key": "OCPSTRAT-1235"
    }
  ]
}
```

## Step 3: Analyze Comments for Context

Scan comment text for keywords and patterns that indicate status:

### Blocker Detection

**Keywords** (case-insensitive):
- "blocked", "blocking", "blocker"
- "waiting on", "waiting for", "depends on"
- "stuck", "stalled", "halted"
- "dependency", "dependent on"
- "can't proceed", "cannot proceed"
- "need", "require" (when followed by external resource)

**Pattern matching**:
```regex
blocked\s+(by|on|waiting)\s+(.+)
waiting\s+(on|for)\s+(.+)
depends?\s+on\s+(.+)
need[s]?\s+(access|approval|input|response)\s+(from|to)\s+(.+)
```

**Extract blocker details**:
```json
{
  "blockers": [
    {
      "issue_key": "OCPSTRAT-1235",
      "description": "Waiting on infrastructure team for Azure subscription",
      "source": "comment",
      "date": "2025-01-08T14:00:00Z",
      "author": "jdoe@example.com",
      "quote": "Need Azure subscription approved before proceeding - submitted ticket #12345"
    }
  ]
}
```

### Risk Detection

**Keywords** (case-insensitive):
- "risk", "risky", "at risk"
- "concern", "concerned", "concerning"
- "problem", "problematic"
- "issue" (when describing a problem, not Jira issue)
- "delay", "delayed", "slipping"
- "might not", "may not", "won't make"
- "deadline", "timeline" (in negative context)

**Pattern matching**:
```regex
(at\s+)?risk\s+(of|that)\s+(.+)
concern(ed)?\s+(about|that|with)\s+(.+)
might\s+not\s+(make|meet|finish|complete)\s+(.+)
delay(ed)?\s+(by|due to|because)\s+(.+)
```

**Extract risk details**:
```json
{
  "risks": [
    {
      "issue_key": "OCPSTRAT-1234",
      "description": "May slip deadline due to API changes in upstream",
      "source": "comment",
      "date": "2025-01-10T09:00:00Z",
      "author": "jsmith@example.com",
      "severity": "medium"
    }
  ]
}
```

### Completion/Achievement Detection

**Keywords** (case-insensitive):
- "completed", "complete", "done", "finished"
- "merged", "landed", "shipped"
- "delivered", "released", "deployed"
- "resolved", "fixed", "closed"
- "PR merged", "MR merged"

**Pattern matching**:
```regex
(PR|MR|pull request|merge request)\s*#?\d+\s+(merged|landed)
completed\s+(.+)
finished\s+(.+)
shipped\s+(.+)
```

**Extract achievement details**:
```json
{
  "achievements": [
    {
      "issue_key": "OCPSTRAT-1236",
      "description": "PR #456 merged adding OAuth2 token validation",
      "source": "comment",
      "date": "2025-01-09T16:00:00Z"
    }
  ]
}
```

### Progress Detection

**Keywords** (case-insensitive):
- "started", "starting", "began", "beginning"
- "working on", "implementing", "developing"
- "in progress", "underway", "ongoing"
- "reviewing", "in review", "under review"
- "testing", "in testing"
- "draft PR", "WIP"

**Extract progress details**:
```json
{
  "in_progress": [
    {
      "issue_key": "OCPSTRAT-1237",
      "description": "Session handling refactor, draft PR submitted",
      "source": "comment",
      "date": "2025-01-10T10:00:00Z"
    }
  ]
}
```

### Help Needed Detection

**Keywords**:
- "need help", "need assistance"
- "looking for", "seeking"
- "anyone know", "does anyone"
- "stuck on", "struggling with"

## Step 4: Aggregate Descendant Status

Calculate metrics across all descendants:

```json
{
  "metrics": {
    "total_descendants": 15,
    "by_status": {
      "Done": 8,
      "In Progress": 4,
      "To Do": 2,
      "Blocked": 1
    },
    "completed": 8,
    "in_progress": 4,
    "not_started": 2,
    "blocked": 1,
    "completion_percentage": 53,
    "updated_in_range": 6
  }
}
```

**Status categorization**:

| Category | Statuses |
|----------|----------|
| Completed | Done, Closed, Resolved, Release Pending, Verified, ON_QA |
| In Progress | In Progress, In Review, Code Review, Testing, In Development |
| Not Started | To Do, Backlog, Open, New |
| Blocked | Blocked, On Hold, Waiting |

**Completion percentage**:
```
completion_percentage = (completed / total_descendants) * 100
```

## Step 5: Determine Overall Health

Based on collected signals, determine the health status:

### Health: Green

**Indicators** (any of):
- Completion percentage increased since last period
- PRs merged or in active review
- Status transitions show forward progress
- No blockers identified
- No high-severity risks

**Thresholds**:
- Completion percentage > 50% OR increased by > 10%
- At least 1 achievement in date range
- Zero blockers
- Zero high-severity risks

### Health: Yellow

**Indicators** (any of):
- Slow progress (few status changes)
- Minor blockers that are being addressed
- Risks identified but manageable
- Some items stalled but majority progressing
- Waiting on external dependencies with clear timeline

**Thresholds**:
- Completion percentage between 25-50%
- 1-2 blockers with known resolution path
- Medium-severity risks only
- At least some activity in date range

### Health: Red

**Indicators** (any of):
- Significant blockers with no resolution path
- No progress in date range
- Multiple high-severity risks
- Critical dependencies unmet
- Deadline at risk

**Thresholds**:
- Completion percentage < 25% with no recent progress
- 3+ blockers OR any blocker without resolution
- High-severity risks
- No achievements in date range AND no active work

### Health Decision Logic

```python
def determine_health(analysis):
    # Red conditions (any triggers red)
    if analysis.blockers and any(b.unresolved for b in analysis.blockers):
        return "red"
    if len(analysis.blockers) >= 3:
        return "red"
    if any(r.severity == "high" for r in analysis.risks):
        return "red"
    if not analysis.achievements and not analysis.in_progress:
        return "red"

    # Green conditions (all must be true)
    if (analysis.achievements
        and not analysis.blockers
        and not any(r.severity in ["high", "medium"] for r in analysis.risks)):
        return "green"

    # Default to yellow
    return "yellow"
```

## Step 6: Build Analysis Result

Combine all analysis into the final structure:

```json
{
  "analysis": {
    "health": "green",
    "health_reason": "Good progress with 2 PRs merged and no blockers",
    "blockers": [],
    "risks": [
      {
        "issue_key": "OCPSTRAT-1234",
        "description": "API deprecation in upstream may require refactor",
        "severity": "low"
      }
    ],
    "achievements": [
      "PR #456 merged adding OAuth2 token validation (OCPSTRAT-1235)",
      "AUTH-101 completed: token refresh mechanism (OCPSTRAT-1236)"
    ],
    "in_progress": [
      "Session handling refactor, draft PR in review (OCPSTRAT-1237)"
    ],
    "metrics": {
      "total_descendants": 15,
      "completed": 8,
      "in_progress": 4,
      "not_started": 2,
      "blocked": 1,
      "completion_percentage": 53,
      "updated_in_range": 6
    },
    "notable_transitions": [
      "OCPSTRAT-1235: To Do → Done",
      "OCPSTRAT-1236: In Progress → Done"
    ],
    "key_comments": [
      {
        "issue_key": "OCPSTRAT-1234",
        "author": "jdoe@example.com",
        "date": "2025-01-09",
        "quote": "PR #456 merged with all review feedback addressed"
      }
    ]
  }
}
```

## Cross-Referencing

Enhance analysis by cross-referencing data:

### Comment ↔ Status Transition

When a comment mentions completion AND a status transition to Done exists within 24 hours:
- Link them together for richer context
- Use comment text to describe the achievement

### Blocker ↔ Descendant

When a blocker is mentioned AND a descendant is in Blocked status:
- Link them together
- Use descendant's status for validation

### PR Mention ↔ External Links

When a comment mentions "PR #123" AND external-links module finds that PR:
- Link them together
- Use PR metadata (merged date, state) to validate comment claims

## Priority Scoring

Score items by importance for summary generation:

| Factor | Points |
|--------|--------|
| Blocker mentioned | +10 |
| Risk mentioned | +7 |
| Completion mentioned | +5 |
| Status transition | +3 |
| PR/MR reference | +4 |
| Recent (last 2 days) | +2 |
| From assignee | +2 |
| Contains quote-worthy text | +3 |

Higher-scored items appear first in summaries.

## Bot Comment Detection

Filter out automated comments that don't provide human insight:

**Known bot patterns**:
- Author display name contains: "Automation", "Bot", "GitHub Actions", "Jenkins"
- Author email domain: `noreply@`, `automation@`
- Comment body patterns:
  - Starts with "Build triggered"
  - Contains "automatically generated"
  - Contains "This is an automated message"
  - Jira workflow transitions ("Status changed by workflow")

**Keep these "bot" comments** (they have useful info):
- GitHub/GitLab integration comments with PR links
- CI status updates with test results
