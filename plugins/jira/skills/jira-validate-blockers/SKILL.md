---
name: JIRA Release Blocker Validator
description: Detailed implementation guide for validating proposed release blockers
command: /jira:validate-blockers
---

# JIRA Release Blocker Validator - Implementation Guide

This skill provides detailed implementation guidance for the `/jira:validate-blockers` command, which helps release managers make data-driven blocker approval/rejection decisions.

## When to Use This Skill

This skill is invoked automatically when the `/jira:validate-blockers` command is executed. It provides step-by-step implementation details for:
- Querying JIRA for proposed release blockers (Release Blocker = Proposed)
- Scoring blockers against Red Hat OpenShift release blocker criteria
- Generating APPROVE/REJECT/DISCUSS recommendations

## Prerequisites

- Jira MCP server must be configured (see plugin README)
- MCP tools available: `mcp__atlassian__jira_*`
- Read-only access to JIRA APIs (no credentials required for public Red Hat JIRA issues)
- For single bug mode: bug must be accessible and exist

## Detailed Implementation Steps

### Phase 1: Parse Arguments

**Parse command-line arguments:**
- Extract target version from $1 (optional, format: X.Y like "4.21")
- Extract component filter from $2 (optional, supports comma-separated values)
- Extract `--bug` flag value (optional, for single bug validation mode)

**Project:**
- Hardcoded to "OCPBUGS" project

**Validate inputs:**
- If neither `--bug` nor `target-version` is provided, error out with message: "Error: Either target-version or --bug must be provided. Usage: /jira:validate-blockers [target-version] [component-filter] [--bug issue-key]"
- If target version provided, verify it matches pattern X.Y (e.g., "4.21", "4.22")
- If component filter provided without target version and without --bug, error out

### Phase 2: Build JQL Query for Proposed Blockers

**Determine query mode:**

1. **Single bug mode** (if `--bug` is provided):
   - Skip JQL query construction
   - Use `mcp__atlassian__jira_get_issue` to fetch the single bug
   - Target version and component filter are ignored in this mode
   - Proceed to analysis with single bug only

2. **Version + component mode** (if both target version and component are provided):
   - Build JQL query for proposed blockers matching target version and component filter
   - Continue with query construction below

3. **Version only mode** (if only target version provided):
   - Build JQL query for all proposed blockers for the target version
   - Continue with query construction below

**Base JQL for proposed blockers:**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed
```

**IMPORTANT**: Use `"Release Blocker" = Proposed` NOT `cf[12319743]`. The field ID `customfield_12319743` is the Release Blocker field, but in JQL use the field name.

**Version filter construction:**

When target version is provided (e.g., "4.21"), expand to search for both X.Y and X.Y.0:

```jql
AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0))
```

**Status exclusion filter:**

Always exclude already-fixed bugs:

```jql
AND status not in (Closed, "Release Pending", Verified, ON_QA)
```

**Component filter construction:**

**No component specified:**
- Query all components (no component filter in JQL)

**Single component:**
```jql
AND component = "{COMPONENT}"
```

**Multiple components (comma-separated):**
```jql
AND component IN ({COMPONENT_LIST})
```

**Final JQL examples:**

**Version only (4.21):**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0)) AND status not in (Closed, "Release Pending", Verified, ON_QA)
```

**Version + component (4.21, "Hypershift"):**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0)) AND status not in (Closed, "Release Pending", Verified, ON_QA) AND component = "Hypershift"
```

**Version + multiple components (4.21, "Hypershift,CVO"):**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0)) AND status not in (Closed, "Release Pending", Verified, ON_QA) AND component IN ("Hypershift", "Cluster Version Operator")
```

### Phase 3: Query Proposed Blockers

**Use MCP tools to fetch proposed blockers:**

For version/component mode, use `mcp__atlassian__jira_search`:
- **jql**: The constructed JQL query from Phase 2
- **fields**: "key,summary,priority,severity,status,assignee,created,updated,labels,components,description,reporter,customfield_12319743,customfield_12319940"
- **expand**: "renderedFields" (to get comments for workaround analysis)
- **limit**: 1000 (adjust based on expected results)

Parse the response to extract:
- Total count of proposed blockers
- List of bug objects with all required fields

Custom fields to include:
- `customfield_12319743` - Release Blocker status (should be "Proposed")
- `customfield_12319940` - Target Version

For single bug mode (`--bug` flag), use `mcp__atlassian__jira_get_issue`:
- **issue_key**: The bug key provided by user
- **fields**: Same fields as above plus custom fields
- **expand**: "renderedFields"
- **comment_limit**: 100 (need to check for workaround mentions)

**Handle query results:**
- If total is 0, display message: "✅ No proposed blockers found" with filter summary
- If total > 20, show progress indicator
- Cache all bug data for analysis (avoid re-querying)

### Phase 4: Analyze Each Proposed Blocker

Analyze each proposed blocker using Red Hat OpenShift release blocker criteria.

**Red Hat OpenShift Release Blocker Criteria:**

Based on the official OpenShift blocker definition, bugs should be approved as release blockers when they meet these criteria:

**Automatic/Strong Blockers (Recommend APPROVE):**
- **Component Readiness regressions** (label: ComponentReadinessRegression) - even tech-preview jobs, unless covered by approved exceptions
- **Service Delivery blockers** (label: ServiceDeliveryBlocker) - most bugs with this label are blockers
- **Data loss, service unavailability, or data corruption** - most bugs in this category are blockers
- **Install/upgrade failures** - may be blockers based on scope (all platforms vs specific form-factor)
- **Perception of failed upgrade** - bugs that appear as upgrade failures to users
- **Regressions from previous release** - most regressions are blockers (e.g., from Layered Product Testing)
- **Bugs severely impacting Service Delivery** - regressions/bugs in default ROSA/OSD/ARO fleet features without acceptable workaround

**Never Blockers (Recommend REJECT):**
- **Severity below Important** - no bugs with Low/Medium severity are blockers
- **New features without regressions** - most new feature bugs are NOT blockers unless they regress existing functionality
- **CI-only issues** - bugs that only affect CI infrastructure/jobs and don't impact product functionality are NOT release blockers
  - Look for labels: `ci-fail`, `ci-only`, `test-flake`
  - Check summary/description for keywords: "CI job", "test failure", "rehearsal", "periodic job", "e2e test"
  - Check comments for explicit statements like "Won't affect the product", "CI-only", "infrastructure issue"
  - Even if the bug describes install/upgrade failures, if it only manifests in CI environments, recommend REJECT

**Workaround Assessment (may affect recommendation):**

An acceptable workaround must meet ALL three criteria:
1. **Idempotent** - can be applied repeatedly without resulting change
2. **Safe at scale** - can be safely deployed to 1000's of clusters without material risk via automation
3. **Timely** - SD can implement before release is pushed to more Cincinnati channels (candidate, fast, stable)

If a workaround doesn't meet all three criteria, it's NOT an acceptable workaround.

**For each proposed blocker:**

1. **Fetch bug details** including summary, description, labels, priority, severity, comments
2. **Check for CI-only indicators** (REJECT criteria):
   - Check labels: `ci-fail`, `ci-only`, `test-flake`
   - Check summary/description for CI-specific keywords:
     - "CI job", "test failure", "rehearsal", "periodic job", "e2e test", "periodic-ci-"
   - Check comments for explicit CI-only statements:
     - "Won't affect the product"
     - "CI-only"
     - "infrastructure issue"
     - "only affects CI"
   - **If CI-only indicators found, recommend REJECT regardless of severity or failure type**
3. **Analyze blocker criteria** (if not CI-only):
   - Check labels: ComponentReadinessRegression, ServiceDeliveryBlocker, UpgradeBlocker
   - Check severity: Must be Important or higher (Critical/Urgent)
   - Analyze summary/description for keywords:
     - Data loss, corruption, service unavailable
     - Install failure, upgrade failure
     - Regression
   - Identify scope: All platforms vs specific form-factor/configuration
4. **Check for acceptable workarounds**:
   - Use `expand="renderedFields"` to get comment text
   - Search for keywords: "workaround", "work around", "alternative", "bypass"
   - Assess if workaround meets all 3 criteria (idempotent, safe at scale, timely)
5. **Generate recommendation**:
   - ✅ **APPROVE** - Meets automatic/strong blocker criteria, no acceptable workaround
   - ❌ **REJECT** - CI-only issue, OR severity below Important, OR new feature without regression, OR has acceptable workaround
   - ⚠️ **DISCUSS** - Edge cases requiring team discussion

**Use MCP tools:**
- `mcp__atlassian__jira_get_issue` with expand="renderedFields" to get comments
- Analyze comment text for workaround mentions

### Phase 5: Generate Validation Report

Create comprehensive Markdown report with all blocker validation results.

**Report Structure:**

```markdown
# 🚫 Release Blocker Validation Report
**Components**: {component list or "All"} | **Project**: OCPBUGS | **Proposed Blockers**: {count} | **Generated**: {timestamp}

## Summary
- ✅ **Recommend APPROVE**: X
- ❌ **Recommend REJECT**: Y
- ⚠️ **Needs DISCUSSION**: Z

---

## Blocker Analysis

### {BUG-KEY}: {Summary} {VERDICT}

**Recommendation**: {APPROVE/REJECT/DISCUSS} - {One-line justification}

**Criteria Matched**:
- {✅/❌} {Criterion name}
- {✅/❌} {Criterion name}
- ...

**Justification**:
{Detailed explanation of why this bug should or shouldn't be a blocker}

**Suggested Action**: {What to do next}

---

[Repeat for each proposed blocker]

---

## Next Steps
1. Review APPROVE recommendations - add to blocker list
2. Review REJECT recommendations - remove blocker status
3. Discuss unclear cases in triage meeting
```

**Special case for single bug mode:**

When `--bug` flag is used, adapt the report to focus on a single bug:
- Summary shows single bug details (key, summary, verdict)
- Analysis section shows detailed criteria analysis for this specific bug
- Next Steps adapted for single bug action

### Phase 6: Error Handling

**Invalid issue ID (single bug mode):**
- Display error: "Could not find issue {issue-id}"
- Verify issue ID is correct format
- Check user has access to the issue

**Invalid arguments:**
- Invalid component name: Warn but continue (JIRA will return no results)

**No proposed blockers found:**
- Display success message: "✅ No proposed blockers found"
- Show filter summary (components, project: OCPBUGS)
- Confirm no blocker decisions needed

**MCP tool errors:**
- If `mcp__atlassian__jira_search` fails, display JQL query and error message
- If `mcp__atlassian__jira_get_issue` fails:
  1. **Fallback to WebFetch**: Try fetching via `https://issues.redhat.com/browse/{issue-key}`
  2. **If WebFetch succeeds**: Parse the web page to extract bug details (summary, severity, description) and continue with validation
  3. **If WebFetch also fails**: Display clear error indicating bug doesn't exist or isn't accessible
- Provide troubleshooting guidance (check MCP server, verify credentials)

**Large result sets (>50 blockers):**
- Show progress indicators during analysis
- Consider warning user: "Found {count} proposed blockers. This may take a moment to analyze."

## Performance Considerations

- **Query optimization**: Only fetch proposed blockers (cf[12319940] = "Proposed")
- **Component scoping**: Use component filters to reduce result set size
- **Batch operations**: Use `mcp__atlassian__jira_search` with appropriate limits (avoid pagination when possible)
- **Caching**: Store bug data in memory during execution to avoid re-querying JIRA

## JQL Query Examples

**Version only (4.21):**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0)) AND status not in (Closed, "Release Pending", Verified, ON_QA)
```

**Version + single component (4.21, "Hypershift"):**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0)) AND status not in (Closed, "Release Pending", Verified, ON_QA) AND component = "Hypershift"
```

**Version + multiple components (4.21, multiple):**
```jql
project = OCPBUGS AND type = Bug AND "Release Blocker" = Proposed AND ("Target Version" in (4.21, 4.21.0) OR "Target Backport Versions" in (4.21, 4.21.0) OR affectedVersion in (4.21, 4.21.0)) AND status not in (Closed, "Release Pending", Verified, ON_QA) AND component IN ("Hypershift", "Cluster Version Operator")
```

**Field IDs Reference:**
- Release Blocker field: `customfield_12319743` (use `"Release Blocker"` in JQL)
- Target Version field: `customfield_12319940` (use `"Target Version"` in JQL)
