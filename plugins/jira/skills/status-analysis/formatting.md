---
name: Formatting
description: Output templates for status summaries in different formats
---

# Formatting

This module defines output templates for status summaries. It transforms analyzed data into human-readable formats suitable for different output targets.

## Overview

Four output formats are supported:

| Format | Used By | Output Target | Syntax |
|--------|---------|---------------|--------|
| `markdown_comment` | `/jira:status-rollup` | Jira comment | Markdown (via `contentFormat: "markdown"`) |
| `ryg_field` | `/jira:update-weekly-status` (default) | Status Summary field | Native ADF JSON |
| `ryg_field_markdown` | Explicitly opted-in consumers with a verified converter | Draft only; convert to ADF before writing | Standard Markdown bullets |
| `feature_markdown` | `/jira:generate-feature-updates` | stdout / localhost HTTP server | Markdown nested lists |

**Important**: When posting comments via `addCommentToJiraIssue` or updating descriptions via `editJiraIssue`, always include `contentFormat: "markdown"`.

For Markdown output formats, render PR references as `[owner/repo#number](PR_URL)` using the repository and URL present in the evidence. Do not emit bare `#number` or shorthand `repo#number` references, or print a raw PR URL in parentheses; the URL belongs in the Markdown link target. Do not invent a repository or URL when the evidence lacks one. These rules apply to Markdown output only; native `ryg_field` ADF logical-content examples remain unchanged, and this does not add a new ADF link-mark requirement.

## Format: markdown_comment

Used by `/jira:status-rollup` to post a comprehensive status comment to a Jira issue.

### Template

```markdown
## Status Rollup: {start-date} to {end-date}

**Overall Status:** {health-indicator} {health-statement}

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

### Health Indicator Mapping

| Health | Indicator | Statement Examples |
|--------|-----------|-------------------|
| Green | **[GREEN]** | "On track with good progress" |
| Yellow | **[YELLOW]** | "Minor concerns but progressing" |
| Red | **[RED]** | "Blocked and needs attention" |

### Example Output

```markdown
## Status Rollup: 2025-01-06 to 2025-01-13

**Overall Status:** **[GREEN]** Feature is on track. Core authentication work completed this week with 2 PRs merged. UI integration starting with design approved.

### This Period

**Completed:**
1. [AUTH-101](https://redhat.atlassian.net/browse/AUTH-101) - OAuth2 implementation ([openshift/hypershift#456](https://github.com/openshift/hypershift/pull/456) merged, all review feedback addressed)
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

This field requires ADF (Atlassian Document Format) JSON. The logical structure is a three-item bullet list:

- Color Status: {Red|Yellow|Green}
  - Status summary:
    - {achievement-or-progress-1}
    - {achievement-or-progress-2}
    - {achievement-or-progress-N}
  - Risks:
    - {risk-1-or-"None at this time"}

**ADF representation:** A `bulletList` with three `listItem` nodes. The "Status summary" and "Risks" items each contain a nested `bulletList` for their sub-items. See the [ADF template](#adf-template-for-ryg_field) below for the exact JSON structure.

### Formatting Rules

1. **Always construct ADF JSON directly**: The `customfield_10814` field requires an ADF document. Passing a plain string (even with `contentFormat: "markdown"`) will fail with `"Operation value must be an Atlassian Document"`.
   - Use `contentFormat: "adf"` on the `editJiraIssue` call
   - Pass the field value as a JSON object with `type: "doc"`, `version: 1`, and nested `bulletList`/`listItem`/`paragraph` nodes
   - **Do NOT** pass plain text strings, markdown, or Jira wiki syntax — the API rejects all non-ADF values

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

The examples below show the **logical content** (what the user sees in Jira). The actual value passed to `editJiraIssue` must be the ADF JSON equivalent — see the [ADF template](#adf-template-for-ryg_field).

**Green Status** (content):
- Color Status: Green
  - Status summary:
    - PR #456 merged adding OAuth2 token validation with comprehensive unit tests
    - AUTH-102 completed: token refresh mechanism implemented and tested
    - AUTH-103 in progress: session handling refactor, draft PR submitted for review
  - Risks:
    - None at this time

**Yellow Status** (content):
- Color Status: Yellow
  - Status summary:
    - UI-201 design review completed, implementation 60% complete
    - AUTH-103 draft PR open but awaiting review capacity from team
    - Made progress on auth integration but slower than planned
  - Risks:
    - Review bandwidth may delay merge to next week
    - Upstream API deprecation notice received - may need refactor

**Red Status** (content):
- Color Status: Red
  - Status summary:
    - AUTH-104 blocked on Azure subscription approval for 2 weeks
    - No PRs merged this period due to blocker
    - Escalated to infrastructure team, awaiting response
  - Risks:
    - Deadline at risk if subscription not approved by Friday
    - May need to descope Azure AD integration from initial release


## Format: ryg_field_markdown

This is a **draft-only** format for consumers that explicitly select
`ryg_field_markdown` and supply a verified Markdown-to-ADF converter before REST
API v3 writes. It is not a valid direct value for `customfield_10814`.
`contentFormat: "markdown"` does not convert custom field values. Keep `ryg_field`
as the default native ADF JSON format; it is not legacy Jira wiki text.

### External consumer and conversion boundary

This ai-helpers plugin **does not bundle or perform Markdown-to-ADF conversion**.
Only external clients with a verified conversion path may opt in; never improvise
conversion or send the draft string directly as a custom field value.

A public reference is [Herald at `54b490c`](https://github.com/celebdor/herald/tree/54b490c):
[`src/herald/jira.py::_text_to_adf`](https://github.com/celebdor/herald/blob/54b490c/src/herald/jira.py)
calls `pyadf.Document.from_markdown(text).to_adf()`, with
[`pyadf==0.5.2` pinned in `pyproject.toml`](https://github.com/celebdor/herald/blob/54b490c/pyproject.toml).
Its writer sends an ADF object in `customfield_10814` and verifies the PUT with a
GET and normalized-ADF comparison. These are source-verified reference behaviors,
not a claim that this plugin ran pyadf or provides that writer. Readback equality
does not establish structural compliance with the status-entry contract below.

Herald's [draft validator](https://github.com/celebdor/herald/blob/54b490c/src/herald/validation.py)
accepts case differences and leading whitespace; it is more permissive than this
canonical draft grammar, which remains unchanged. Its
[gatherer](https://github.com/celebdor/herald/blob/54b490c/src/herald/gather.py)
renders existing ADF to Markdown and its writer replaces the whole field. It is
an OCPSTRAT-style replacement reference, **not** an ARO raw-history-prepend
guarantee. An ARO-capable external writer must separately retain original raw
ADF nodes and prepend the validated new entry as project guidance requires;
never reconstruct historical ADF from rendered Markdown.

Before a REST API v3 PUT, the external client must convert the draft and validate
the **new status-entry document** using all [native `ryg_field` checks](#ryg_field-validation):

- A JSON object with `type: "doc"`, `version: 1`, and one top-level `bulletList`.
- Exactly three `listItem` nodes in that list, in order.
- First item: `Color Status:` followed by exactly one of `Red`, `Yellow`, `Green`.
- Second item: `Status summary:` with a nested `bulletList` containing at least one item.
- Third item: `Risks:` with a nested `bulletList` containing at least one item
  (use `None at this time` when there are no risks); no empty text nodes.

Then apply required raw-ADF history preservation and write an ADF object, not the
draft. Stop if conversion, structural validation or required history support is
unavailable. See selected-format handling in [SKILL.md](SKILL.md#step-5-format-output)
and the weekly command; the default native ADF construction and history path
are unchanged.

### Template

```markdown
* Color Status: {Red|Yellow|Green}
* Status summary:
  * {achievement-or-progress-1}
  * {achievement-or-progress-2}
* Risks:
  * {risk-1-or-"None at this time"}
```

### Formatting Rules

- Use standard Markdown unordered-list markers: `* ` for top-level items and
  `  * ` for items nested under a section.
- Do not use Jira wiki-style `**` markers or indentation-only pseudo-lists.
- Keep `Color Status`, `Status summary`, and `Risks` as top-level bullets.
- Put each achievement, progress item, and risk under its corresponding section.
- Include exactly one Color Status line, first, as `* Color Status: Red`,
  `* Color Status: Yellow`, or `* Color Status: Green`.
- Include at least one status summary item and a Risks section; use
  `  * None at this time` when there are no risks.
- Render each unambiguously confirmed PR reference as a Markdown link labeled `owner/repo#number`,
  using the repository and URL in the evidence (for example,
  `[openshift/hypershift#456](https://github.com/openshift/hypershift/pull/456)`).
- For confirmed PR references, use qualified labels rather than bare `#number`
  or shorthand `repo#number`; the evidence URL is the authority for identity.
- For confirmed PRs, do not print a raw PR URL in parentheses, such as `Enhancement PR (https://...)`;
  put the URL only in the Markdown link target.
- Do not infer or fabricate a repository or URL. If a reference cannot be tied
  unambiguously to a confirmed PR URL, retain its original text **exactly verbatim**,
  add no repository or link, and do not guess or request human input.
- Qualify only references unambiguously identified as PRs by their evidence. Do
  not transform arbitrary `#N` text, issues, language names or headings. Preserve
  unknown references and unrelated links exactly verbatim; never attach a separate
  PR URL to unrelated prose. For multiple references, qualify only those confirmed
  by evidence and leave the others verbatim. If a written repository conflicts
  with the evidence URL, keep that reference exactly as written and unlinked.
- Preserve supplied PR destinations, including query strings, fragments and
  subpages. A confirmed `/pull/3/files` reference belongs in a Markdown link
  target; do not fabricate a replacement URL by stripping the subpath.
- Output only the draft text, with no code fence, preamble, or explanation.

### Example

```markdown
* Color Status: Green
* Status summary:
  * [openshift/hypershift#456](https://github.com/openshift/hypershift/pull/456) merged adding OAuth2 token validation with comprehensive unit tests
  * [openshift/enhancements#1945](https://github.com/openshift/enhancements/pull/1945) (EtcdBackup CRD for OADP integration) remains open
* Risks:
  * Review bandwidth may delay the follow-up merge
```

## Format: feature_markdown

Used by `/jira:generate-feature-updates` to produce concise executive-level feature summaries for weekly status documents (e.g., "Key Strategic Feature Updates" section).

### Template

```
- 🟢 [{ISSUE-KEY}](https://issues.redhat.com/browse/{ISSUE-KEY}): {issue summary}
    - {1-3 sentence prose summary of significant activity}
- 🔴 [{ISSUE-KEY-2}](https://issues.redhat.com/browse/{ISSUE-KEY-2}): {issue summary}
    - {1-3 sentence prose summary of significant activity}
```

Color circle mapping (from the `color` field in Status Summary):
- `Green` → 🟢
- `Yellow` → 🟡
- `Red` → 🔴
- No color / unknown → omit circle

### Formatting Rules

1. **Nested unordered list**: Top-level bullet is the feature link + summary, nested bullet is the update prose
2. **Markdown links**: Use `[KEY](url)` syntax (standard Markdown, not Jira wiki)
3. **Prose in nested bullet**: Each entry's update is 1-3 flowing sentences in a single nested list item
4. **Color circle prefix**: Each top-level bullet starts with a unicode circle (🟢🟡🔴) matching the Color Status from the Status Summary field. Omit the circle if no color is set.
5. **No metrics**: No completion percentages, issue counts, or tables
6. **Cross-references as markdown links**: Reference related issues, PRs, and people inline
7. **Continuous list**: All entries in one unordered list, no blank lines between items
8. **PR references**: Use `[owner/repo#N](url)` format when referencing specific PRs
9. **First names for attribution**: Use `author_name` fields (not `author` logins) when attributing contributions. Always use first names, never GitHub handles.

### Content Guidelines

**Focus on what matters to executives:**

- Features that made **significant progress** (PRs merged, milestones hit)
- Features that were **delivered or completed**
- Features whose **status color changed** this week (e.g., Green→Yellow, Yellow→Red) — a status change is always news
- Features that are **blocked or at risk** with new activity or updates this week
- **Scope changes** or strategic pivots

**R/Y/G status as prioritization, not inclusion:** Use the team's self-reported color status to order and prioritize the output (Red/Yellow before Green), but do not include a feature solely because it has been Red/Yellow — it must also have a status change or other significant activity this week.

**Attribution for recognition:**

- Name team members who drove key accomplishments
- Example: "Thanks to Contributor A's work on [openshift/hypershift#456](https://github.com/openshift/hypershift/pull/456), the migration path is now fully tested"

**Tone:**

- Executive-level: concise, direct, outcome-oriented
- Focus on "so what" rather than "what happened"
- Highlight customer or business impact where relevant

**DO**:
- Reference specific PRs, people, and customers
- Explain scope changes and their rationale
- Call out blockers with clear ownership
- Attribute contributions so team members get recognition
- Use first names for attribution (e.g., "Contributor B's PR #7746" not "contributor-b's PR #7746")

**DON'T**:
- List every sub-task or minor change
- Use vague language ("making progress", "ongoing work")
- Include metrics or completion percentages
- Use bullet points (prose only)
- Use GitHub handles (e.g., `contributor-b`, `contributor-c`). Always use first names from `author_name` fields instead.

### Example Outputs

```markdown
- 🟢 [OCPSTRAT-2426](https://issues.redhat.com/browse/OCPSTRAT-2426): Customer global pull secret in HCP for ROSA
    - Scope reduced to Managed OpenShift and platforms using node replacement strategy. E2E tests are already passing.
- 🟡 [OCPSTRAT-1409](https://issues.redhat.com/browse/OCPSTRAT-1409): Auto backup/restore for Hosted Clusters
    - A bug found in the implementation has highlighted a permission gap that we are going to cover with better UX.
- 🟢 [OCPSTRAT-1558](https://issues.redhat.com/browse/OCPSTRAT-1558): Shared ingress for HCP
    - Contributor C's [openshift/hypershift#7143](https://github.com/openshift/hypershift/pull/7143) landed this week, completing the core shared ingress controller. Integration tests are passing on AWS.
- 🔴 [OCPSTRAT-2100](https://issues.redhat.com/browse/OCPSTRAT-2100): IPv6 support for Hosted Control Planes
    - Blocked on upstream Kubernetes networking changes expected in 1.32. Contributor D has prepared the downstream patches and they are ready to go once the dependency lands.
```

### Significant Activity Filter

Skip issues with no noteworthy activity. An issue has significant activity if any of:

- **Status color changed** this week (e.g., Green→Yellow, Yellow→Red) — detected via changelog or by comparing `last_status_summary_update` with date range
- Status transitions (started, completed, blocked, reopened)
- PRs merged or new PRs opened
- Scope changes or priority changes
- Blocker identified or resolved
- Substantive comments from team members (not bot updates)

Issues with only minor updates (bot comments, trivial field changes) should be omitted. A feature that has been Red/Yellow for weeks with no new activity is not news — only include it if the color changed or there is a meaningful update this week.

### Pseudocode

```python
COLOR_CIRCLES = {"Green": "🟢", "Yellow": "🟡", "Red": "🔴"}

def format_feature_markdown(issue_data, config):
    output = []

    issue_url = f"https://issues.redhat.com/browse/{issue_data.issue_key}"
    circle = COLOR_CIRCLES.get(issue_data.color, "")
    prefix = f"{circle} " if circle else ""
    output.append(f"- {prefix}[{issue_data.issue_key}]({issue_url}): {issue_data.summary}")

    # Build prose from analysis
    sentences = []

    # Achievements / deliveries
    for achievement in issue_data.analysis.achievements:
        sentences.append(achievement.description)

    # Blockers / risks
    for blocker in issue_data.analysis.blockers:
        sentences.append(blocker.description)

    for risk in issue_data.analysis.risks:
        sentences.append(risk.description)

    # Combine into 1-3 sentences of flowing prose as a nested bullet
    # Use author_name (first names), never GitHub logins
    prose = synthesize_prose(sentences, max_sentences=3)
    output.append(f"    - {prose}")

    return "\n".join(output)
```

### feature_markdown validation

- [ ] Each entry is a top-level list item: `- 🟢 [ISSUE-KEY](url): summary`
- [ ] Color circle (🟢🟡🔴) matches the Color Status from the Status Summary field
- [ ] Update prose is a nested list item: `    - 1-3 sentences`
- [ ] No metrics or percentages
- [ ] All entries form one continuous unordered list
- [ ] Cross-references use markdown link syntax
- [ ] Issues with no significant activity are omitted
- [ ] No GitHub handles — only first names from `author_name` fields

## Building Output from Analysis Data

### For markdown_comment format

```python
def format_markdown_comment(issue_data, config):
    output = []

    # Header
    output.append(f"## Status Rollup: {config.date_range.start} to {config.date_range.end}")
    output.append("")

    # Overall status
    health = issue_data.analysis.health
    indicator = {"green": "**[GREEN]**", "yellow": "**[YELLOW]**", "red": "**[RED]**"}[health]
    output.append(f"**Overall Status:** {indicator} {issue_data.analysis.health_reason}")
    output.append("")

    # Completed section
    output.append("### This Period")
    output.append("")
    output.append("**Completed:**")
    for achievement in issue_data.analysis.achievements:
        issue_url = f"https://redhat.atlassian.net/browse/{achievement.issue_key}"
        output.append(f"1. [{achievement.issue_key}]({issue_url}) - {achievement.description}")

    # In Progress section
    output.append("")
    output.append("**In Progress:**")
    for item in issue_data.analysis.in_progress:
        issue_url = f"https://redhat.atlassian.net/browse/{item.issue_key}"
        output.append(f"1. [{item.issue_key}]({issue_url}) - {item.description}")

    # Blocked section
    output.append("")
    output.append("**Blocked:**")
    for blocker in issue_data.analysis.blockers:
        issue_url = f"https://redhat.atlassian.net/browse/{blocker.issue_key}"
        output.append(f"1. [{blocker.issue_key}]({issue_url}) - {blocker.description}")
        if blocker.quote:
            output.append(f"> {blocker.quote}")

    # ... continue with Next Steps, Risks, Metrics, Footer

    return "\n".join(output)
```

### For ryg_field format

Build the ADF JSON document directly. Each text item becomes a `listItem` containing a `paragraph` with a `text` node.

```python
def format_ryg_field(issue_data, config):
    health = issue_data.analysis.health.capitalize()  # Green, Yellow, Red

    # Combine achievements and in-progress items (limit to top 3+2)
    summary_texts = []
    for achievement in issue_data.analysis.achievements[:3]:
        summary_texts.append(achievement.description)
    for progress in issue_data.analysis.in_progress[:2]:
        summary_texts.append(progress.description)
    if not summary_texts:
        summary_texts.append("No status updates this period")

    # Risk texts
    risk_texts = []
    if issue_data.analysis.risks:
        for risk in issue_data.analysis.risks[:2]:
            risk_texts.append(risk.description)
    else:
        risk_texts.append("None at this time")

    # Helper: create a listItem with a single text paragraph
    def text_item(text):
        return {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ]}

    # Helper: create a listItem with a label paragraph + nested bullet list
    def section_item(label, child_texts):
        return {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": label}]},
            {"type": "bulletList", "content": [text_item(t) for t in child_texts]}
        ]}

    return {
        "type": "doc",
        "version": 1,
        "content": [{
            "type": "bulletList",
            "content": [
                text_item(f"Color Status: {health}"),
                section_item("Status summary:", summary_texts),
                section_item("Risks:", risk_texts),
            ]
        }]
    }
```

### For ryg_field_markdown format

Produce a draft using the [template and rules](#format-ryg_field_markdown), not a
regex transformation of activity descriptions. Draft formatting does not perform
final conversion; the [external client owns it](#external-consumer-and-conversion-boundary).
Use the same selection caps as native `ryg_field`: at most 3 achievements,
2 in-progress items and 2 risks. If no summary items are selected, emit
`  * No status updates this period` under `* Status summary:`. If no risks are
selected, emit `  * None at this time` under `* Risks:`.

These hypothetical fixtures constrain drafting, not executable rewrite behavior
or claims about the contents of actual PRs:

| Evidence and input | Required treatment |
|---|---|
| `fixes #12`, no PR evidence | Preserve the unknown reference; do not replace it with "pull request". |
| `closed #99`, evidence points to `/issues/99` | Preserve the issue reference; it is not a PR. |
| `ported C#12 code` or `fixed heading #1 in docs` | Preserve language text and heading numbers verbatim. |
| `#456 and #457 merged`, confirmed evidence `https://github.com/openshift/hypershift/pull/456` | Output `[openshift/hypershift#456](https://github.com/openshift/hypershift/pull/456) and #457 merged`. Qualify only 456; keep 457 verbatim. |
| `openshift/other#456`, evidence `https://github.com/openshift/hypershift/pull/456` | Output `openshift/other#456` exactly as written and unlinked; do not attach mismatched evidence or change the repository. |
| `https://github.com/o/r/pull/3/files`, confirmed PR evidence | Render `[o/r#3](https://github.com/o/r/pull/3/files)` without changing the destination. |
| `docs at https://example.com/x`, unrelated PR URL present separately | Preserve the documentation link; do not append or associate the unrelated PR. |
| A link on an unrecognized host with no verified PR identity | Preserve it as an unrelated/unknown link, not an inferred GitHub PR. |

As a reference implementation of the treatments above, the helper below qualifies
references from each activity record's evidence URL, not an assumed repository. It
accepts the dictionaries produced by `external-links.md` as well as attribute-style
records. Only a single unambiguous reference may inherit the record's URL;
unsupported references are generalized. Inline PR link labels are qualified from
their verified targets without changing the URL; other links, code, images, and
reference definitions are preserved. URLs cannot be rewritten as bare references.
Draft formatting still does not perform final Markdown-to-ADF conversion; the
[external client owns it](#external-consumer-and-conversion-boundary).

```python
import re


def markdown_activity_item(item):
    def field(name):
        if isinstance(item, dict):
            return item.get(name, "")
        return getattr(item, name, "")

    def pr_identity(url):
        match = re.fullmatch(
            r"https?://github\.com/([A-Za-z0-9_-]+/[A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?(?:[?#][^\s<>\[\]()]*)?",
            url if isinstance(url, str) else "",
        )
        return (match[1], match[2]) if match else None

    def pr_link(url, identity):
        repository, number = identity
        return f"[{repository}#{number}]({url})"

    def prose_url(url):
        target = url or ""
        if not pr_identity(target) and "?" not in target and "#" not in target:
            target = target.rstrip(".,;:!)")
        return target, (url or "")[len(target):], pr_identity(target)

    description = item if isinstance(item, str) else field("description")
    evidence_url = field("url")
    evidence = pr_identity(evidence_url)
    tokens = re.compile(
        r"(?P<definition>^[ ]{0,3}\[[^\]\n]+\]:[^\n]*)"
        r"|(?P<protected>(?P<ticks>`+)[^\n]*?(?P=ticks)|<https?://[^<>\n]*>|\[[^\]\n]*\]\[[^\]\n]*\])"
        r"|(?P<link>!?\[[^\]\n]*\]\((?:[^()\n]|\([^()\n]*\))*\))"
        r"|(?P<bracket>\[[^\]\n]*\])"
        r"|(?P<url>https?://[^\s<>\[\]]+)"
        r"|(?P<reference>(?<![\w/])(?:PR\s+)?(?P<repository>[\w.-]+(?:/[\w.-]+)?)?#(?P<number>[0-9]+)\b)",
        re.MULTILINE,
    )
    matches = list(tokens.finditer(description))
    references = [match for match in matches if match.group("reference")]
    links = [match for match in matches
             if match.group("link") or match.group("protected") or match.group("definition") or match.group("bracket")]
    linked_prs = [match for match in matches if prose_url(match.group("url"))[2]]

    def replace(match):
        if match.group("link"):
            inline = re.fullmatch(
                r"\[[^\]\n]*\]\([ \t]*(?:<(?P<angle>[^<>\s]+)>|(?P<plain>[^\s<>]+?))"
                r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*\)",
                match[0],
            )
            identity = pr_identity(inline.group("angle") or inline.group("plain")) if inline else None
            if identity:
                repository, number = identity
                return f"[{repository}#{number}" + match[0][match[0].index("]("):]
            return match[0]
        if match.group("protected") or match.group("definition") or match.group("bracket"):
            return match[0]
        target = match.group("url")
        if target:
            target, punctuation, identity = prose_url(target)
            return pr_link(target, identity) + punctuation if identity else match[0]
        if (evidence and len(references) == 1 and not links and not linked_prs
                and match.group("number") == evidence[1]
                and match.group("repository") in (None, evidence[0])):
            return pr_link(evidence_url, evidence)
        return "pull request"

    rendered = tokens.sub(replace, description)
    if evidence and not references and not links and not linked_prs:
        rendered += f" ({pr_link(evidence_url, evidence)})"
    return rendered


def format_ryg_field_markdown(issue_data, config):
    output = []
    health = issue_data.analysis.health.capitalize()  # Green, Yellow, Red
    output.append(f"* Color Status: {health}")
    output.append("* Status summary:")

    items = [markdown_activity_item(item) for item in issue_data.analysis.achievements[:3]]
    items.extend(markdown_activity_item(item) for item in issue_data.analysis.in_progress[:2])
    if not items:
        items = ["No status updates this period"]
    output.extend(f"  * {item}" for item in items)

    output.append("* Risks:")
    risks = issue_data.analysis.risks[:2]
    output.extend(f"  * {markdown_activity_item(risk)}" for risk in risks)
    if not risks:
        output.append("  * None at this time")

    return "\n".join(output)
```

### For feature_markdown format

```python
COLOR_CIRCLES = {"Green": "🟢", "Yellow": "🟡", "Red": "🔴"}

def format_feature_markdown(issue_data, config):
    # Skip issues with no significant activity
    if not has_significant_activity(issue_data):
        return None

    output = []
    issue_url = f"https://issues.redhat.com/browse/{issue_data.issue_key}"
    circle = COLOR_CIRCLES.get(issue_data.color, "")
    prefix = f"{circle} " if circle else ""
    output.append(f"- {prefix}[{issue_data.issue_key}]({issue_url}): {issue_data.summary}")

    # Synthesize 1-3 sentences of executive prose from:
    # - achievements (PRs merged, milestones, deliveries)
    # - blockers and risks (with ownership)
    # - scope changes or strategic pivots
    # - attribution (use first names from author_name, never GitHub logins)
    prose = synthesize_executive_prose(issue_data.analysis)
    output.append(f"    - {prose}")

    return "\n".join(output)


def has_significant_activity(issue_data):
    """Return True if issue has noteworthy activity worth reporting."""
    # Check if the status color changed this week
    if status_color_changed_in_range(issue_data):
        return True

    return (
        len(issue_data.analysis.achievements) > 0
        or len(issue_data.analysis.blockers) > 0
        or len(issue_data.analysis.risks) > 0
        or any(t.to in ("Closed", "Done", "Blocked") for t in issue_data.changelog.status_transitions)
        or any(pr.state == "MERGED" for pr in issue_data.external_links.github_prs)
    )


def status_color_changed_in_range(issue_data):
    """Check if the R/Y/G status color changed during the date range."""
    # Look for Status Summary field changes in changelog_in_range
    for entry in issue_data.changelog_in_range:
        for item in entry.get("items", []):
            if item.get("field") == "Status Summary":
                old_value = item.get("from", "")
                new_value = item.get("to", "")
                old_color = parse_color_status(old_value if isinstance(old_value, str) else "")
                new_color = parse_color_status(new_value if isinstance(new_value, str) else "")
                if old_color != new_color:
                    return True
    return False


def parse_color_status(status_summary):
    """Extract Red/Yellow/Green from status summary text."""
    if not status_summary:
        return None
    # Handle both "* Color Status: Green" and "{color:#d04437}Red{color}" formats
    for color in ("Red", "Yellow", "Green"):
        if color in status_summary:
            return color
    return None
```

## Validation

Before outputting, validate the formatted text:

### markdown_comment validation

- [ ] Heading syntax correct (`##`, `###`)
- [ ] Links properly formatted (`[text](url)`)
- [ ] Numbered lists use `1.` prefix
- [ ] Blockquotes use `>` prefix
- [ ] Footer includes command attribution

### ryg_field validation

- [ ] Value is a valid ADF JSON document with `type: "doc"` and `version: 1`
- [ ] Top-level content is a single `bulletList` with exactly 3 `listItem` nodes
- [ ] First item text starts with `Color Status:` followed by exactly one of: Red, Yellow, Green
- [ ] Second item has text `Status summary:` with a nested `bulletList` containing at least one item
- [ ] Third item has text `Risks:` with a nested `bulletList` (at least "None at this time")
- [ ] No empty text nodes

### ryg_field_markdown validation

- [ ] Exactly one Color Status line, first: `* Color Status: Red`, `* Color Status: Yellow`, or `* Color Status: Green`
- [ ] `Status summary` and `Risks` are top-level `* ` bullets
- [ ] Summary items and risks use two-space nested `  * ` bullets
- [ ] Contains no Jira wiki-style `**` sub-bullets
- [ ] No empty bullet points
- [ ] Confirmed qualified PR links agree with their evidence URLs; unknown/issue references and unrelated text remain exactly verbatim, without guesses or requests for input

## Escaping Special Characters

### Markdown in Jira Comments

Backslash escaping (`\*`, `\[`, etc.) is unreliable in Jira Cloud's markdown rendering and may be stripped or mis-rendered. When literal special characters are needed, wrap them in inline code backticks instead.

### Status Summary Field

The Status Summary field (`customfield_10814`) is a rich text field that stores content as Atlassian Document Format (ADF). The `contentFormat: "markdown"` parameter on `editJiraIssue` does **not** auto-convert custom field values — it only applies to standard fields like `description`. Passing a plain string for this field will fail with `"Operation value must be an Atlassian Document"`.

**Always construct ADF JSON directly** and use `contentFormat: "adf"`.

#### ADF template for ryg_field

```json
{
  "type": "doc",
  "version": 1,
  "content": [{
    "type": "bulletList",
    "content": [
      {
        "type": "listItem",
        "content": [{"type": "paragraph", "content": [
          {"type": "text", "text": "Color Status: Green"}
        ]}]
      },
      {
        "type": "listItem",
        "content": [
          {"type": "paragraph", "content": [
            {"type": "text", "text": "Status summary:"}
          ]},
          {"type": "bulletList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [
              {"type": "text", "text": "Item 1 text here"}
            ]}]},
            {"type": "listItem", "content": [{"type": "paragraph", "content": [
              {"type": "text", "text": "Item 2 text here"}
            ]}]}
          ]}
        ]
      },
      {
        "type": "listItem",
        "content": [
          {"type": "paragraph", "content": [
            {"type": "text", "text": "Risks:"}
          ]},
          {"type": "bulletList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [
              {"type": "text", "text": "None at this time"}
            ]}]}
          ]}
        ]
      }
    ]
  }]
}
```

Each status summary bullet and each risk bullet is a `listItem` containing a `paragraph` with a `text` node. Add or remove `listItem` entries in the nested `bulletList` arrays as needed.

**Do NOT** pass plain strings, markdown, Jira wiki syntax (`*`, `**`, `h2.`, etc.), or raw HTML as the field value.
