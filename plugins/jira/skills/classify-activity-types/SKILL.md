---
name: classify-activity-types
description: Classify Jira issues into Red Hat Sankey Activity Type categories using MCP Jira tools. Supports single-issue and batch modes. Use when the user wants to classify or set activity types on Jira issues, or mentions activity types, work types, Sankey, or capacity allocation.
---

# Activity Type Classification

Classify Jira issues into Red Hat's Sankey capacity allocation categories and update them via MCP Jira tools. This skill supports two modes of operation:

- **Single-issue mode**: Classify one issue by key (invoked by `/jira:categorize-activity-type`)
- **Batch mode**: Classify all unclassified issues in a project (invoked by `/jira:batch-classify-activity-types`)

Both modes use identical classification logic, validation, and reporting.

## Valid Activity Types

These are the only valid values. Use the exact strings:

| Activity Type | Short Description |
|---|---|
| Associate Wellness & Development | Onboarding, training, AI learning, conferences, team health |
| Incidents & Support | Production incidents, customer escalations, on-call |
| Security & Compliance | CVEs, weaknesses, FedRAMP, compliance, security tooling |
| Quality / Stability / Reliability | Bugs, SLOs, chores, tech debt, toil reduction, PMR actions |
| Future Sustainability | Proactive architecture, productivity improvements, upstream, enablement |
| Product / Portfolio Work | New features, enhancements, strategic product/portfolio work |

For detailed definitions, subcategories, and edge cases, see [resources/activity-type-guidance.md](resources/activity-type-guidance.md).

## Activity Type Field

The Activity Type custom field ID is `customfield_10464`. This is the same across all projects on `redhat.atlassian.net`.

## Prerequisites Check

Before starting any work, verify MCP Jira tools are available:

1. Attempt to call `jira_search` with a simple query (e.g., `jql: "project = OCM" limit: 1`)
2. If the tool is not found or returns an MCP connection error, **stop immediately** and tell the user:
   - "The MCP Jira tools are not available. This workflow requires the mcp-atlassian MCP server to be configured with access to redhat.atlassian.net."
3. Do NOT proceed to any phase if this check fails

## Working Directory

Both modes write artifacts to `.work/activity-type-classifier/`. Create this directory before starting:

```bash
mkdir -p .work/activity-type-classifier
```

## Workflow

Copy this checklist and track progress:

```text
Classification Progress:
- [ ] Prerequisites: MCP Jira tools available
- [ ] Phase 1: Gather issues
- [ ] Phase 2: Classify each issue
- [ ] Phase 3: Validate & generate report
- [ ] Phase 4: Apply updates (with approval)
- [ ] Phase 5: Iterate (batch mode only)
```

### Phase 1: Gather Issues

#### Single-Issue Mode

Fetch the issue by key using `jira_get_issue`:
- Fields: `summary,description,issuetype,labels,parent,components,priority,customfield_10464`
- If the issue already has an Activity Type set (`customfield_10464` is not null), inform the user and stop

#### Batch Mode

Parse user input for:
- **Project key** (required) — e.g., OCM, ARO
- **Issue type** (optional, default: Epic)
- **Extra JQL filters** (optional) — e.g., `AND resolved >= "2025-01-01"`

**Always filter for issues without an Activity Type set.** The `"Activity Type" is EMPTY` condition is mandatory in every query — do not ask the user whether to include it.

Construct the JQL query using this template:

```sql
project = {PROJECT} AND issuetype = {TYPE} AND "Activity Type" is EMPTY
```

Common additions:
- Date filter: `AND resolved >= "2025-01-01"`
- Open issues only: `AND status != Closed`

Execute `jira_search` with `limit: 50`. If more results exist, make a second call with `start_at: 50` to get up to 100 total. Combine both result sets.

From each issue, extract: `key`, `summary`, `description` (truncate to 2000 chars), `labels`, `issuetype`, `status`, `priority`, `comment`, and `parent`. Save all extracted data to `.work/activity-type-classifier/issues.json`.

Report the count of issues found to the user before proceeding.

### Phase 2: Classify Issues

**Pre-check — Parent inheritance**: Before classifying each issue, check if it has a parent issue. If the parent has an Activity Type set (`customfield_10464`), inherit it directly — no further classification needed. Set confidence to "High" and reasoning to "Inherited from {PARENT_KEY}". To look up a parent's Activity Type, call `jira_get_issue` with the parent's key and check `customfield_10464`. Cache parent lookups to reduce API calls — multiple children may share the same parent.

For remaining issues (no parent or parent has no Activity Type), read summary, description, labels, comments, and status. Apply the classification rules below and the detailed guidance in [resources/activity-type-guidance.md](resources/activity-type-guidance.md).

Save classifications to `.work/activity-type-classifier/classifications.json` as a JSON array:

```json
[
  {
    "key": "OCM-12345",
    "summary": "Issue title",
    "activityType": "Product / Portfolio Work",
    "confidence": "High",
    "reasoning": "New customer-facing feature for cluster provisioning"
  }
]
```

In single-issue mode, this array contains exactly one entry. In batch mode, it contains all classified issues.

If total issues exceed 50 (batch mode), process in sub-batches of 20 to manage context.

### Phase 3: Validate and Report

Run the validation and report generation scripts. These are located in `scripts/` relative to this skill's directory.

1. Run the validation script:
   ```bash
   bash plugins/jira/skills/classify-activity-types/scripts/validate-classifications.sh .work/activity-type-classifier/classifications.json
   ```
2. Fix any validation errors before proceeding
3. Generate the report:
   ```bash
   python3 plugins/jira/skills/classify-activity-types/scripts/generate-report.py .work/activity-type-classifier/classifications.json .work/activity-type-classifier/report.md
   ```
4. Display the report summary to the user

### Phase 4: Apply Updates

#### Single-Issue Mode with `--auto-apply`

- If `--auto-apply` flag is present AND confidence is **High**: automatically update the Activity Type field without prompting
- Otherwise: present the classification and ask for confirmation before applying

#### Batch Mode

1. Ask the user for **explicit approval** before modifying any Jira issues
2. If `--dry-run` flag is present, skip this phase entirely
3. Max 2 concurrent MCP update calls to avoid rate limiting
5. Report progress every 10 issues
6. On error: log the failure, continue with remaining issues
7. After completion, summarize successes and failures

#### Update Format

```python
jira_update_issue(
    issue_key="OCM-12345",
    additional_fields={"customfield_10464": {"value": "Product / Portfolio Work"}}
)
```

#### Success Confirmation

```text
Updated OCM-12345: Activity Type set to "Product / Portfolio Work"
  View at: https://redhat.atlassian.net/browse/OCM-12345
```

### Phase 5: Iterate (Batch Mode Only)

After applying updates, offer to re-run the workflow:
- Classified issues will no longer match the JQL query (Activity Type is no longer empty)
- A new batch of unclassified issues can be gathered and processed
- Track cumulative stats across iterations

## Classification Rules

When classifying an issue:

1. **Read carefully** — consider summary, description, labels, comments, and linked issues
2. **Business intent over technical details** — a Kubernetes refactoring driven by product requirements is "Product / Portfolio Work", not "Future Sustainability"
3. **Security always wins** — if an issue involves CVEs, vulnerabilities, compliance, or security tooling, classify as "Security & Compliance" regardless of other aspects
4. **Primary purpose** — when an issue spans multiple categories, choose the one that best matches the primary motivation
5. **Confidence levels**:
   - **High** — clear match, unambiguous indicators
   - **Medium** — reasonable match but some ambiguity
   - **Low** — uncertain, multiple categories could apply
6. **Truncate descriptions** — use the first 2000 characters of the description for classification

For the complete category definitions with subcategories and examples, see [resources/activity-type-guidance.md](resources/activity-type-guidance.md).

## Error Handling

- **Issue not found**: Display error and suggest verifying issue key
- **Permission denied**: Inform user they lack update permissions
- **Invalid field value**: Verify Activity Type value matches allowed options
- **MCP connection error**: Suggest checking MCP server configuration
- **Parent fetch failure**: Continue without parent context, note in reasoning

## Reference Files

| File | Purpose | When to Read |
|---|---|---|
| [resources/activity-type-guidance.md](resources/activity-type-guidance.md) | Full Sankey category definitions and subcategories | Phase 2 (classifying) |
| [resources/report-template.md](resources/report-template.md) | Report format reference | Phase 3 (report generation) |
| [scripts/validate-classifications.sh](scripts/validate-classifications.sh) | Validate classifications JSON | Phase 3 (validation) |
| [scripts/generate-report.py](scripts/generate-report.py) | Generate markdown report from JSON | Phase 3 (report generation) |
| [scripts/cleanup.sh](scripts/cleanup.sh) | Remove data artifacts, preserve reports | Post-workflow cleanup |
