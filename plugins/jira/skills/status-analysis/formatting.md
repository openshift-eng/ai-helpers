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
| `wiki_comment` | `/jira:status-rollup` | Jira comment | Jira wiki markup |
| `ryg_field` | `/jira:update-weekly-status` | Status Summary field | Bullet-point template |

## Format: wiki_comment

Used by `/jira:status-rollup` to post a comprehensive status comment to a Jira issue.

### Template

```
h2. Status Rollup: {start-date} to {end-date}

*Overall Status:* {health-emoji} {health-statement}

h3. This Period

*Completed:*
{for each achievement}
*# [{issue-key}|{issue-url}] - {achievement-description}
{end for}

*In Progress:*
{for each in-progress item}
*# [{issue-key}|{issue-url}] - {progress-description}
{end for}

*Blocked:*
{for each blocker}
*# [{issue-key}|{issue-url}] - {blocker-description}
{if blocker.quote}
{quote}{blocker.quote}{quote}
{end if}
{end for}

h3. Next Steps

{for each planned item}
* {planned-item-description}
{end for}

h3. Risks

{if risks exist}
{for each risk}
* *{risk.severity}:* {risk.description}
{end for}
{else}
* None identified
{end if}

h3. Metrics

* *Total Issues:* {metrics.total_descendants}
* *Completed:* {metrics.completed} ({metrics.completion_percentage}%)
* *In Progress:* {metrics.in_progress}
* *Blocked:* {metrics.blocked}
* *Updated This Period:* {metrics.updated_in_range}

----

_Generated with [Claude Code|https://claude.com/claude-code] via {{/jira:status-rollup {root-issue} --start-date {start-date} --end-date {end-date}}}_
```

### Jira Wiki Markup Reference

| Element | Syntax | Example |
|---------|--------|---------|
| Heading 2 | `h2. Text` | `h2. Status Rollup` |
| Heading 3 | `h3. Text` | `h3. This Period` |
| Bold | `*text*` | `*Completed:*` |
| Link | `[text\|url]` | `[OCPSTRAT-123\|https://issues.redhat.com/browse/OCPSTRAT-123]` |
| Bullet list | `* item` | `* First item` |
| Nested bullet | `*# item` | `*# Nested item` |
| Quote block | `{quote}text{quote}` | `{quote}User said this{quote}` |
| Monospace | `{{text}}` | `{{/jira:status-rollup}}` |
| Horizontal rule | `----` | `----` |
| Italic | `_text_` | `_Generated with..._ ` |

### Health Emoji Mapping

| Health | Emoji | Statement Examples |
|--------|-------|-------------------|
| Green | (/) | "On track with good progress" |
| Yellow | (!) | "Minor concerns but progressing" |
| Red | (x) | "Blocked and needs attention" |

**Note**: Jira uses `(/)`, `(!)`, `(x)` for checkmark, warning, and X icons respectively.

### Example Output

```
h2. Status Rollup: 2025-01-06 to 2025-01-13

*Overall Status:* (/) Feature is on track. Core authentication work completed this week with 2 PRs merged. UI integration starting with design approved.

h3. This Period

*Completed:*
*# [AUTH-101|https://issues.redhat.com/browse/AUTH-101] - OAuth2 implementation (PR #456 merged, all review feedback addressed)
*# [AUTH-102|https://issues.redhat.com/browse/AUTH-102] - Token validation with comprehensive unit tests

*In Progress:*
*# [UI-201|https://issues.redhat.com/browse/UI-201] - Login UI components (design review completed, implementing responsive layout)
*# [AUTH-103|https://issues.redhat.com/browse/AUTH-103] - Session handling refactor (draft PR submitted)

*Blocked:*
*# [AUTH-104|https://issues.redhat.com/browse/AUTH-104] - Azure AD integration (waiting on subscription approval)
{quote}Need Azure subscription approved before proceeding - submitted ticket #12345{quote}

h3. Next Steps

* Complete session handling refactor (AUTH-103) and submit for review
* Finish login UI responsive implementation (UI-201)
* Begin end-to-end testing (AUTH-107) once session handling is merged

h3. Risks

* *Medium:* API deprecation in upstream dependency may require refactor in Q2

h3. Metrics

* *Total Issues:* 15
* *Completed:* 8 (53%)
* *In Progress:* 4
* *Blocked:* 1
* *Updated This Period:* 6

----

_Generated with [Claude Code|https://claude.com/claude-code] via {{/jira:status-rollup FEATURE-123 --start-date 2025-01-06 --end-date 2025-01-13}}_
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

## Building Output from Analysis Data

### For wiki_comment format

```python
def format_wiki_comment(issue_data, config):
    output = []

    # Header
    output.append(f"h2. Status Rollup: {config.date_range.start} to {config.date_range.end}")
    output.append("")

    # Overall status
    health = issue_data.analysis.health
    emoji = {"green": "(/)", "yellow": "(!)", "red": "(x)"}[health]
    output.append(f"*Overall Status:* {emoji} {issue_data.analysis.health_reason}")
    output.append("")

    # Completed section
    output.append("h3. This Period")
    output.append("")
    output.append("*Completed:*")
    for achievement in issue_data.analysis.achievements:
        issue_url = f"https://issues.redhat.com/browse/{achievement.issue_key}"
        output.append(f"*# [{achievement.issue_key}|{issue_url}] - {achievement.description}")

    # In Progress section
    output.append("")
    output.append("*In Progress:*")
    for item in issue_data.analysis.in_progress:
        issue_url = f"https://issues.redhat.com/browse/{item.issue_key}"
        output.append(f"*# [{item.issue_key}|{issue_url}] - {item.description}")

    # Blocked section
    output.append("")
    output.append("*Blocked:*")
    for blocker in issue_data.analysis.blockers:
        issue_url = f"https://issues.redhat.com/browse/{blocker.issue_key}"
        output.append(f"*# [{blocker.issue_key}|{issue_url}] - {blocker.description}")
        if blocker.quote:
            output.append(f"{{quote}}{blocker.quote}{{quote}}")

    # ... continue with Next Steps, Risks, Metrics, Footer

    return "\n".join(output)
```

### For ryg_field format

```python
def format_ryg_field(issue_data, config):
    output = []
    health = issue_data.analysis.health.capitalize()  # Green, Yellow, Red

    output.append(f"* Color Status: {health}")
    output.append(" * Status summary:")

    # Combine achievements and in-progress items
    items = []
    for achievement in issue_data.analysis.achievements[:3]:  # Limit to top 3
        items.append(achievement.description)
    for progress in issue_data.analysis.in_progress[:2]:  # Add up to 2 in-progress
        items.append(progress.description)

    for item in items:
        output.append(f"     ** {item}")

    # Risks section
    output.append(" * Risks:")
    if issue_data.analysis.risks:
        for risk in issue_data.analysis.risks[:2]:  # Limit to top 2
            output.append(f"     ** {risk.description}")
    else:
        output.append("     ** None at this time")

    return "\n".join(output)
```

## Validation

Before outputting, validate the formatted text:

### wiki_comment validation

- [ ] Heading syntax correct (`h2.`, `h3.`)
- [ ] Links properly formatted (`[text|url]`)
- [ ] Nested bullets use correct syntax (`*#`)
- [ ] No unescaped special characters that break wiki markup
- [ ] Footer includes command attribution

### ryg_field validation

- [ ] Starts with `* Color Status:` line
- [ ] Color is exactly one of: Red, Yellow, Green
- [ ] Status summary section present with at least one item
- [ ] Risks section present (even if "None at this time")
- [ ] Indentation matches expected format
- [ ] No empty bullet points

## Escaping Special Characters

### Jira Wiki Markup

Characters that need escaping:

| Character | Escape As | Context |
|-----------|-----------|---------|
| `{` | `\{` | Avoid triggering macros |
| `}` | `\}` | Avoid triggering macros |
| `[` | `\[` | Avoid creating links |
| `]` | `\]` | Avoid creating links |
| `*` | `\*` | When not intended as bold |
| `_` | `\_` | When not intended as italic |
| `|` | `\|` | Inside table cells or links |

### Status Summary Field

The Status Summary field may have less strict parsing, but still:
- Avoid HTML tags
- Escape any markup that might be interpreted
- Keep text plain and readable
