# ARO HCP Jira Conventions

This file provides ARO HCP team-specific conventions for working with Jira issues in the ARO project.

## When to Use

This file is loaded automatically by `/jira:update-weekly-status` when:
- Project key is "ARO"
- Component is one of: `aro-hcp-qe`, `aro-hcp-clusters-service`, `aro-hcp-clusters-service-east`, `aro-hcp-clusters-service-west`

## Project Information

| Field | Value |
|-------|-------|
| **Project Key** | ARO |
| **Project Name** | Azure Red Hat OpenShift |
| **Managed by** | Senior Engineering Manager |
| **Teams** | CS West, CS East (separate engineering lead), QE |

## Components

| Component | Team | Description |
|-----------|------|-------------|
| `aro-hcp-qe` | QE | Test automation and quality coverage |
| `aro-hcp-clusters-service` | CS (shared) | Overall cluster service before east/west assignment |
| `aro-hcp-clusters-service-east` | CS East | Cluster service (east region) |
| `aro-hcp-clusters-service-west` | CS West | Cluster service (west region) |

## Weekly Status Updates (`/jira:update-weekly-status`)

### Issue Type Filter

When running `/jira:update-weekly-status` against the ARO project, **only process Features and Initiatives**. The Status Summary field (`customfield_10814`) is only available on these issue types in the ARO project — it cannot be set on Epics, Stories, Tasks, or Bugs.

### Milestone-Based Prioritization

Status updates are prioritized by milestone. Process issues in this order:

**Tier 1 — HPSTRAT-63 (MSFT Public Preview)**: ALL Features/Initiatives that are children of this milestone MUST have their Status Summary updated, regardless of whether they had activity this week. This is the current active milestone.

**Tier 2 — HPSTRAT-130 (General Availability)**: Features/Initiatives under this milestone get a status update only if they had activity this week. Update is optional for inactive items.

**Tier 3 — Everything else**: Features/Initiatives not under either milestone but with activity in the last 7 days should also be updated.

### Implementation: Gathering Issues by Milestone

To find issues by milestone, use `parent = HPSTRAT-63` and `parent = HPSTRAT-130` JQL queries. These milestones are parents of the Features/Initiatives.

**Step 1**: Fetch HPSTRAT-63 children (mandatory updates):
```jql
parent = HPSTRAT-63 AND project = ARO AND issuetype in (Feature, Initiative) AND status != Closed
```
With component filter, add: `AND component = "{component}"`

**Step 2**: Fetch HPSTRAT-130 children updated this week (optional updates):
```jql
parent = HPSTRAT-130 AND project = ARO AND issuetype in (Feature, Initiative) AND status != Closed AND updated >= -7d
```
With component filter, add: `AND component = "{component}"`

**Step 3**: Fetch remaining active items not under either milestone:
```jql
project = ARO AND issuetype in (Feature, Initiative) AND status != Closed AND updated >= -7d AND NOT parent = HPSTRAT-63 AND NOT parent = HPSTRAT-130
```
With component filter, add: `AND component = "{component}"`

**Presentation**: Group issues by tier in the processing workflow:
```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HPSTRAT-63 (Public Preview) — {N} Features/Initiatives [ALL require update]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {list issues}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HPSTRAT-130 (GA) — {N} with activity this week [update optional]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {list issues}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Other active — {N} with activity this week
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {list issues}
```

### Status Summary Format (ARO-specific)

The ARO project uses a **prepend** model for Status Summary — new updates are added at the top, preserving the history of previous updates. This differs from the default OCPSTRAT behavior which replaces the entire field. The field value and its history are ADF nodes, not plaintext or Markdown.

**Format for each update entry:**

```text
{YYYY-MM-DD}: Color Status: {Green|Yellow|Red}
- {Current state bullet 1 — what happened this week}
- {Current state bullet 2}
- Risks: {risk or "None at this time"}
```

This is the logical content shown in Jira. Write each entry as the following ADF nodes (shown for a Green update on 2026-06-05):

```json
[
  {
    "type": "paragraph",
    "content": [{"type": "text", "text": "2026-06-05: Color Status: Green"}]
  },
  {
    "type": "bulletList",
    "content": [
      {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "ARO-17759 closed; ARO-26913 is in review."}]}]},
      {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "72% complete (18/25 descendants closed)."}]}]},
      {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Risks: None at this time"}]}]}
    ]
  }
]
```

**Rules:**
1. **Prepend, don't replace**: Prepend the new entry nodes to the existing ADF document's `content` array. Keep all previous nodes intact; never stringify, render-and-reparse, or nest the existing `doc` inside a new one.
2. **Date stamp**: Each entry starts with the date in `YYYY-MM-DD` format.
3. **No duplication**: Only include what changed since the last update. If something was reported last week and hasn't changed, don't repeat it. Focus on: what's new, what moved, what's blocked.
4. **Concise**: 2-4 bullets per update. One sentence per bullet.

For an existing `issue.current_status_summary` ADF document, construct the value to write as follows:

```javascript
const existingNodes = issue.current_status_summary?.content ?? [];
const nextStatusSummary = {
  type: "doc",
  version: 1,
  content: [...newEntryNodes, ...existingNodes]
};
```

When no value exists, use `content: newEntryNodes`. `newEntryNodes` is the dated paragraph and bullet list shown above. This yields a newest-first multi-week history without losing prior entries.

### Updating the Status Summary Field

The Status Summary field (`customfield_10814`) is a rich text field that stores content as Atlassian Document Format (ADF). The `contentFormat: "markdown"` parameter does **not** auto-convert custom field values — it only applies to standard fields like `description`. Always construct ADF JSON directly and use `contentFormat: "adf"`.

When writing to `customfield_10814`:

1. Read the current raw ADF value first (from the pre-gathered JSON `issue.current_status_summary`)
2. Generate the new entry (date + color + bullets)
3. Prepend the new entry nodes to the existing document's `content` nodes
4. Construct the full ADF document and write via `editJiraIssue`

If the current value is null/empty, just write the new entry.

**MCP call:**
```javascript
editJiraIssue(
  cloudId: "redhat.atlassian.net",
  issueIdOrKey: "{ISSUE_KEY}",
  contentFormat: "adf",
  fields: {
    "customfield_10814": {
      "type": "doc",
      "version": 1,
      "content": [
        // ...newEntryNodes,
        // ...existingStatusSummary.content
      ]
    }
  }
)
```

See the [ADF template in formatting.md](../skills/status-analysis/formatting.md#adf-template-for-ryg_field) for the exact node structure.

**IMPORTANT**: If `editJiraIssue` fails with "Field cannot be set" error, the issue is not a Feature or Initiative. Skip it and log a warning — do not fall back to adding a comment.

## Jira Hierarchy (ARO Project)

```text
Initiative
  └── Feature          ← Status Summary lives here
        └── Epic
              └── Story / Task / Bug
                    └── Sub-task
```

- **Status Summary** is set on Features and Initiatives only
- **PRs/MRs** should be linked to Stories, Tasks, or Bugs (not Epics or above)
- Use `/jira:trace-work` to ensure PR→Jira linking at the correct level

## See Also

- `/jira:update-weekly-status` — Weekly status updates (applies ARO conventions automatically)
- `/jira:trace-work` — Trace PRs/MRs to Jira issues
- `/jira:grooming` — Backlog grooming with component filter
- `gcp-hcp` skill — Similar conventions for the GCP project
