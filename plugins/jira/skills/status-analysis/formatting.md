---
name: Formatting
description: Output templates for status summaries in different formats
---

# Formatting

This module defines output templates for status summaries. It transforms analyzed data into human-readable formats suitable for different output targets.

## Overview

Two output formats are supported:

| Format | Used By | Output Target | Syntax |
|--------|---------|---------------|--------|
| `markdown_comment` | `/jira:status-rollup` | Jira comment | Markdown |
| `ryg_field` | `/jira:update-weekly-status` | Status Summary field | Bullet-point template |

## Format: markdown_comment

Used by `/jira:status-rollup` to post a comprehensive status comment to a Jira issue. The comment is posted using `contentFormat: "markdown"` so Jira renders it correctly.

### Template

```markdown
## Status Rollup: {start-date} to {end-date}

**Overall Status:** {health-emoji} {health-statement}

### This Period

**Completed:**
{for each achievement}
  1. [{issue-key}]({issue-url}) - {achievement-description}
{end for}

**In Progress:**
{for each in-progress item}
  1. [{issue-key}]({issue-url}) - {progress-description}
{end for}

**Blocked:**
{for each blocker}
  1. [{issue-key}]({issue-url}) - {blocker-description}
{if blocker.quote}
> {blocker.quote}
{end if}
{end for}

### Next Steps

{for each planned item}
- {planned-item-description}
{end for}

### Risks

{if risks exist}
{for each risk}
- **{risk.severity}:** {risk.description}
{end for}
{else}
- None identified
{end if}

### Metrics

- **Total Issues:** {metrics.total_descendants}
- **Completed:** {metrics.completed} ({metrics.completion_percentage}%)
- **In Progress:** {metrics.in_progress}
- **Blocked:** {metrics.blocked}
- **Updated This Period:** {metrics.updated_in_range}

---

*Generated with [Claude Code](https://claude.com/claude-code) via `/jira:status-rollup {root-issue} --start-date {start-date} --end-date {end-date}`*
```

### Health Status Mapping

| Health | Label | Statement Examples |
|--------|-------|-------------------|
| Green | GREEN | "On track with good progress" |
| Yellow | YELLOW | "Minor concerns but progressing" |
| Red | RED | "Blocked and needs attention" |

**Note**: Use plain text labels (GREEN, YELLOW, RED) for health status. Markdown does not support Jira's icon macros.

### Example Output

```markdown
## Status Rollup: 2025-01-06 to 2025-01-13

**Overall Status:** GREEN Feature is on track. Core authentication work completed this week with 2 PRs merged. UI integration starting with design approved.

### This Period

**Completed:**
1. [AUTH-101](https://redhat.atlassian.net/browse/AUTH-101) - OAuth2 implementation (PR #456 merged, all review feedback addressed)
1. [AUTH-102](https://redhat.atlassian.net/browse/AUTH-102) - Token validation with comprehensive unit tests

**In Progress:**
1. [UI-201](https://redhat.atlassian.net/browse/UI-201) - Login UI components (design review completed, implementing responsive layout)
1. [AUTH-103](https://redhat.atlassian.net/browse/AUTH-103) - Session handling refactor (draft PR submitted)

**Blocked:**
1. [AUTH-104](https://redhat.atlassian.net/browse/AUTH-104) - Azure AD integration (waiting on subscription approval)
> Need Azure subscription approved before proceeding - submitted ticket #12345

### Next Steps

- Complete session handling refactor (AUTH-103) and submit for review
- Finish login UI responsive implementation (UI-201)
- Begin end-to-end testing (AUTH-107) once session handling is merged

### Risks

- **Medium:** API deprecation in upstream dependency may require refactor in Q2

### Metrics

- **Total Issues:** 15
- **Completed:** 8 (53%)
- **In Progress:** 4
- **Blocked:** 1
- **Updated This Period:** 6

---

*Generated with [Claude Code](https://claude.com/claude-code) via `/jira:status-rollup FEATURE-123 --start-date 2025-01-06 --end-date 2025-01-13`*
```

## Format: ryg_field

Used by `/jira:update-weekly-status` to update the Status Summary custom field.

### Template

```
* Color Status: {Red|Yellow|Green}
 * Status summary:
     ** {achievement-or-progress-1}
     ** {achievement-or-progress-2}
     ** {achievement-or-progress-N}
 * Risks:
     ** {risk-1-or-"None at this time"}
```

### Formatting Rules

1. **Exact spacing matters**: The field may have specific formatting requirements
   - Top-level bullet: `* ` (asterisk + space)
   - Second-level: ` * ` (space + asterisk + space)
   - Third-level: `     ** ` (5 spaces + double asterisk + space)

2. **Color Status line**: Always first, exactly one of Red/Yellow/Green

3. **Status summary section**:
   - Focus on concrete achievements and progress
   - Reference PR numbers, issue keys, specific accomplishments
   - Be specific: "PR #456 merged adding OAuth2" not "ongoing work"

4. **Risks section**:
   - Include if there are actual risks
   - Be specific about what might go wrong
   - Use "None at this time" if no risks identified

### Color Status Guidelines

| Color | When to Use | Indicators |
|-------|-------------|------------|
| **Green** | On track, good progress | PRs merged, tasks completed, no blockers |
| **Yellow** | Minor concerns | Slow progress, manageable blockers, waiting on dependencies |
| **Red** | Significant issues | No progress, major blockers, deadline at risk |

### Content Guidelines

**DO**:
- Reference specific PR numbers: "PR #456 merged"
- Reference child issue keys: "AUTH-101 completed"
- Mention specific accomplishments: "OAuth2 token validation implemented"
- Include timeline context: "Expected to complete by EOW"
- Quote specific blockers: "Waiting on Azure subscription (ticket #12345)"

**DON'T**:
- Use vague phrases: "ongoing work", "making progress", "continuing development"
- Omit specifics: "Fixed some bugs" → "Fixed 3 authentication edge cases in PR #789"
- Forget blockers: Always surface what's blocking progress
- Over-promise: Be realistic about risks and timelines

### Example Outputs

**Green Status**:
```
* Color Status: Green
 * Status summary:
     ** PR #456 merged adding OAuth2 token validation with comprehensive unit tests
     ** AUTH-102 completed: token refresh mechanism implemented and tested
     ** AUTH-103 in progress: session handling refactor, draft PR submitted for review
 * Risks:
     ** None at this time
```

**Yellow Status**:
```
* Color Status: Yellow
 * Status summary:
     ** UI-201 design review completed, implementation 60% complete
     ** AUTH-103 draft PR open but awaiting review capacity from team
     ** Made progress on auth integration but slower than planned
 * Risks:
     ** Review bandwidth may delay merge to next week
     ** Upstream API deprecation notice received - may need refactor
```

**Red Status**:
```
* Color Status: Red
 * Status summary:
     ** AUTH-104 blocked on Azure subscription approval for 2 weeks
     ** No PRs merged this period due to blocker
     ** Escalated to infrastructure team, awaiting response
 * Risks:
     ** Deadline at risk if subscription not approved by Friday
     ** May need to descope Azure AD integration from initial release
```

## Validation

Before outputting, validate the formatted text:

### ryg_field validation

- [ ] Starts with `* Color Status:` line
- [ ] Color is exactly one of: Red, Yellow, Green
- [ ] Status summary section present with at least one item
- [ ] Risks section present (even if "None at this time")
- [ ] Indentation matches expected format
- [ ] No empty bullet points
