---
description: Categorize JIRA tickets into activity types using AI
argument-hint: <issue-key> [--auto-apply]
---

## Name
jira:categorize-activity-type

## Synopsis
```
/jira:categorize-activity-type <issue-key> [--auto-apply]
```

## Description

Analyzes JIRA tickets and assigns appropriate Activity Type categories based on ticket content, issue type, labels, and parent Epic context. Uses AI-powered categorization with confidence scoring to ensure accurate assignments.

The command supports six activity type categories:
1. **Associate Wellness & Development** - Professional growth, training, learning, team building
2. **Incidents & Support** - Production incidents, customer support, troubleshooting, emergency fixes
3. **Security & Compliance** - Security vulnerabilities, compliance requirements, security patches, audits
4. **Quality / Stability / Reliability** - Bug fixes, test improvements, reliability enhancements, technical debt
5. **Future Sustainability** - Infrastructure improvements, developer experience, automation, tooling
6. **Product / Portfolio Work** - Feature development, product enhancements, new capabilities

## Implementation

### Phase 1: Fetch Ticket Data

Use MCP to fetch only the fields needed for categorization:

```python
issue_data = mcp__atlassian__jira_get_issue(
    issue_key="${1}",
    fields="summary,description,issuetype,labels,parent,components,priority,customfield_12320040"
)
```

Extract relevant fields:
- `summary` - Ticket title
- `description` - Detailed ticket description
- `issuetype.name` - Issue Type (Bug, Story, Task, Vulnerability, etc.)
- `labels` - Ticket labels
- `parent.key` - Parent Epic/Story key (if available)
- `components` - Component assignments
- `priority` - Priority level
- `customfield_12320040` - Current Activity Type value (if set)

### Phase 2: Invoke Categorization Skill

Delegate categorization analysis to the `categorize-activity-type` skill which implements:

1. **Issue Type Heuristics** - Apply default mappings:
   - Vulnerability/Weakness → Security & Compliance
   - Bug (security-related) → Security & Compliance
   - Bug (standard) → Quality / Stability / Reliability
   - Story (product) → Product / Portfolio Work
   - Task → Analyze parent context or keywords

2. **Keyword Scanning** - Search for indicator words:
   - Incidents: "incident", "outage", "customer issue", "emergency", "hotfix"
   - Security: "CVE", "vulnerability", "security patch", "compliance", "audit"
   - Quality: "bug", "flaky test", "memory leak", "crash", "error handling"
   - Sustainability: "refactor", "technical debt", "developer experience", "CI/CD", "automation"
   - Product: "feature", "enhancement", "capability", "user story", "requirement"
   - Wellness: "training", "learning", "conference", "onboarding", "mentoring"

3. **Parent Context Inheritance** - When ticket is child of Epic:
   - Fetch parent Epic details
   - Check parent's Activity Type (if set)
   - Inherit category with adjusted confidence

4. **Ambiguity Resolution** - Apply priority rules:
   - Security-related always takes precedence
   - Explicit keywords override issue type heuristics
   - Parent inheritance used when keywords unclear
   - Low confidence reported when evidence conflicts

See [skills/categorize-activity-type/SKILL.md](../skills/categorize-activity-type/SKILL.md) for detailed categorization methodology.

### Phase 3: Present Results

Display categorization analysis to user:

```
Activity Type: Quality / Stability / Reliability
Confidence: High

Reasoning: This is a Bug issue type focused on fixing a memory leak in the scanner
component. Memory leaks directly impact system stability and reliability. The description
mentions "intermittent crashes" and "resource exhaustion," which are classic reliability
concerns. No security implications mentioned, and this is a proactive fix rather than a
customer-facing incident.

Key Evidence:
- Issue Type: Bug
- Summary contains: "Fix memory leak"
- Description mentions: "crashes", "resource exhaustion", "intermittent failures"
- No security keywords present
- No parent Epic context available
```

### Phase 4: Apply Update (Conditional)

**Auto-apply logic:**

- If `--auto-apply` flag present AND confidence is **High**:
  - Automatically update Activity Type field
  - Display confirmation to user

- Otherwise (no flag OR confidence is Medium/Low):
  - Present suggestion to user
  - Ask for confirmation before applying
  - If user confirms, proceed with update
  - If user declines, exit without changes

**Update using MCP:**

```python
mcp__atlassian__jira_update_issue(
    issue_key="${1}",
    fields={
        "customfield_12320040": {  # Activity Type field
            "value": "<SELECTED_ACTIVITY_TYPE>"
        }
    }
)
```

**Success confirmation:**

```
✓ Updated ROX-12345: Activity Type set to "Quality / Stability / Reliability"
  View at: https://issues.redhat.com/browse/ROX-12345
```

### Phase 5: Error Handling

**Handle common errors:**

- **Issue not found**: Display error and suggest verifying issue key
- **Permission denied**: Inform user they lack update permissions
- **Invalid field value**: Verify Activity Type value matches allowed options
- **MCP connection error**: Suggest checking MCP server configuration

## Arguments

- **$1 - issue-key** (required)
  - JIRA issue key to categorize
  - Format: PROJECT-NUMBER (e.g., ROX-12345, OCPBUGS-67890)
  - Must be a valid, accessible JIRA issue

- **--auto-apply** (optional)
  - Automatically apply Activity Type when confidence is High
  - Without this flag, always prompts user for confirmation
  - Only applies for High confidence categorizations
  - Medium/Low confidence always requires manual confirmation

## Return Value

**Format:** Human-readable categorization analysis with optional JIRA update

**Components:**
1. **Selected Activity Type** - One of the six categories
2. **Confidence Level** - High, Medium, or Low
3. **Reasoning** - 2-3 sentences explaining the categorization with specific evidence
4. **Key Evidence** - Bullet points of relevant data from the ticket
5. **Update Confirmation** - Success message if Activity Type was applied

**Exit codes:**
- `0` - Success (with or without update)
- `1` - Error (invalid issue key, permission denied, MCP error, etc.)

## Examples

1. **Basic categorization (manual confirmation):**
   ```
   /jira:categorize-activity-type ROX-12345
   ```

   Result: Displays categorization analysis, prompts user to confirm before updating

2. **Auto-apply for high confidence:**
   ```
   /jira:categorize-activity-type ROX-12345 --auto-apply
   ```

   Result: If confidence is High, automatically updates Activity Type without prompting

3. **Process security vulnerability:**
   ```
   /jira:categorize-activity-type ROX-28072 --auto-apply
   ```

   Expected: Issue Type = Vulnerability → "Security & Compliance" (High confidence, auto-applied)

4. **Process bug with unclear context:**
   ```
   /jira:categorize-activity-type OCPBUGS-45678
   ```

   Expected: Analyzes keywords and parent Epic, may show Medium confidence, asks for confirmation

## See Also

- `jira:grooming` - Backlog grooming with activity type analysis
- `jira:create` - Create issues with pre-assigned activity types
- `jira:validate-blockers` - Validate release blockers with scoring

## Notes

- **Activity Type field ID**: `customfield_12320040` - **This is specific to Red Hat JIRA instances**. Other JIRA instances will have different custom field IDs for Activity Type. To find your instance's field ID:
  1. Use MCP to fetch any issue: `mcp__atlassian__jira_get_issue(issue_key="YOUR-ISSUE-KEY")`
  2. Search the response for "Activity Type" or your custom field name
  3. Note the field ID (e.g., `customfield_12345`) associated with that field
  4. Update the command implementation and skill to use your field ID instead of `customfield_12320040`
- **Requires MCP**: Jira MCP server must be configured (see [plugin README](../README.md))
- **Read and write permissions**: User must have permission to view and edit the specified JIRA issue
- **AI-powered**: Categorization uses LLM reasoning, not simple rule matching
- **Confidence scoring**: High confidence triggers auto-apply (with flag), Medium/Low always prompts
