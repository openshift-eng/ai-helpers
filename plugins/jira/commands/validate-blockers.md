---
description: Validate proposed release blockers using Red Hat OpenShift release blocker criteria
argument-hint: "[target-version] [component-filter] [--bug issue-key]"
---

## Name
jira:validate-blockers

## Synopsis
```
/jira:validate-blockers [target-version] [component-filter] [--bug issue-key]
```

**Note**: `target-version` is required unless `--bug` is provided.

## Description
The `jira:validate-blockers` command helps release managers make data-driven decisions on proposed release blockers. It analyzes bugs with "Release Blocker = Proposed" status using Red Hat OpenShift release blocker criteria and provides clear APPROVE/REJECT/DISCUSS recommendations with detailed justification.

This command is essential for:
- Validating proposed release blockers
- Making blocker approval/rejection decisions
- Understanding why a bug should or shouldn't block a release
- Reviewing blocker criteria compliance

## Key Features

- **Proposed Blocker Focus** – Automatically filters for bugs with Release Blocker = Proposed
- **Red Hat OpenShift Release Blocker Criteria** – Analyzes against documented blocker criteria
- **Clear Recommendations** – Provides APPROVE, REJECT, or DISCUSS recommendations
- **Detailed Justification** – Shows which criteria matched and analysis rationale
- **Component Filtering** – Scope validation to specific components

## Implementation

For detailed implementation guidance including JQL queries, scoring algorithms, and decision logic, see the [jira-validate-blockers skill](../skills/jira-validate-blockers/SKILL.md).

### High-Level Workflow

1. **Parse Arguments and Build Filters** – Extract arguments (target version, component filter, bug ID). Build JQL query for:
   - **Single bug mode** (if --bug provided): Query specific bug by issue key (version not required)
   - **Component + version mode** (if both provided): Query proposed blockers matching target version and component, excluding already-fixed bugs (status not in Closed, Release Pending, Verified, ON_QA)
   - **Version only mode** (if version provided): Query all proposed blockers for target version, excluding already-fixed bugs
   - **Error**: If neither --bug nor version provided, show error message

2. **Query Proposed Blockers** – Use MCP tools to fetch bugs based on mode:
   - Single bug: Fetch one specific bug with all fields
   - Component + version: Fetch proposed blockers matching version and component filter, excluding already-fixed statuses
   - Version only: Fetch all proposed blockers for target version, excluding already-fixed statuses

3. **Analyze Each Blocker** – Apply Red Hat OpenShift release blocker criteria:
   - Strong blockers: Component Readiness regression, Service Delivery blocker, data loss, install/upgrade failures, service unavailability, regressions
   - Never blockers: Severity below Important, new features without regression
   - Workaround assessment: Check if acceptable workaround exists (idempotent, safe at scale, timely)

4. **Generate Recommendations** – Create report with APPROVE/REJECT/DISCUSS verdicts and justifications.

### Technical Details

The skill file provides complete details on:
- JQL query construction for proposed blockers
- Blocker scoring criteria and point values
- Workaround assessment logic
- Decision thresholds

## Usage Examples

### Version-Based Validation

1. **Validate all proposed blockers for a target version**:
   ```
   /jira:validate-blockers 4.21
   ```

### Component-Based Validation

2. **Validate blockers for a specific component and version**:
   ```
   /jira:validate-blockers 4.21 "Hypershift"
   ```

### Single Bug Validation

3. **Validate a specific proposed blocker (version not required)**:
   ```
   /jira:validate-blockers --bug OCPBUGS-36846
   ```

## Output Format

The command outputs a blocker validation report:

```markdown
# 🚫 Release Blocker Validation Report
**Components**: All | **Project**: OCPBUGS | **Proposed Blockers**: 5 | **Generated**: 2025-11-23

## Summary
- ✅ **Recommend APPROVE**: 2
- ❌ **Recommend REJECT**: 1
- ⚠️ **Needs DISCUSSION**: 2

---

## Blocker Analysis

### OCPBUGS-12345: Cluster install fails on AWS ✅ APPROVE

**Recommendation**: APPROVE - This bug meets blocker criteria

**Criteria Matched**:
- ✅ Install/upgrade failure
- ✅ Affects all users
- ✅ No acceptable workaround

**Justification**:
Install failures are strong blockers. This bug prevents cluster installation on AWS, affecting all users attempting AWS deployments. No workaround exists.

**Suggested Action**: Approve as release blocker

---

### OCPBUGS-12346: UI button misaligned ❌ REJECT

**Recommendation**: REJECT - This bug does not meet blocker criteria

**Criteria Matched**:
- ❌ Cosmetic/UI-only issue (not data loss/corruption/unavailability)
- ❌ Severity: Low (must be Important or higher)

**Justification**:
Bugs with severity below Important are never blockers. This is a cosmetic issue with no functional impact.

**Suggested Action**: Reject as release blocker, triage to appropriate sprint

---

## Next Steps
1. Review APPROVE recommendations - add to blocker list
2. Review REJECT recommendations - remove blocker status
3. Discuss unclear cases in triage meeting
```

## Arguments

**IMPORTANT**: Either `target-version` OR `--bug` must be provided. If neither is provided, the command will error out.

### Core Arguments

- **$1 – target-version** *(required unless --bug is provided)*
  Target release version to validate blockers for. Format: `X.Y` (e.g., `4.21`, `4.22`)

  The implementation automatically:
  - Expands version to search for both `X.Y` and `X.Y.0` in Target Version, Target Backport Versions, and Affected Version fields
  - Excludes already-fixed bugs with status: Closed, Release Pending, Verified, ON_QA

  Examples:
  - `4.21` - Validates active proposed blockers for 4.21
  - `4.22` - Validates active proposed blockers for 4.22

  **Note**: Not required when `--bug` is provided.

- **$2 – component-filter** *(optional)*
  Component name(s) to filter proposed blockers. Supports single or multiple (comma-separated) components.

  Examples:
  - `"Hypershift"` - Single component
  - `"Hypershift,Cluster Version Operator"` - Multiple components

  **Note**: Ignored if `--bug` is provided. Requires `target-version` to be specified.

  Default: All components for the target version

- **--bug** *(optional)*
  Validate a single specific bug by its JIRA issue key.

  When provided, analyzes only this bug and ignores both target-version and component-filter.

  Examples:
  - `--bug OCPBUGS-36846`

  **Note**: When `--bug` is provided, target-version and component-filter are ignored.

  Default: Not specified

## Return Value

- **Markdown Report**: Blocker validation report with recommendations
- **Exit Code**:
  - `0` - Success
  - `1` - Error querying JIRA or analyzing bugs

## Prerequisites

- Jira MCP server must be configured (see [plugin README](../README.md))
- MCP tools provide read-only access to JIRA APIs
- No JIRA credentials required for read operations (public Red Hat JIRA issues)
- Access to JIRA projects (OCPBUGS)
- Permission to search and view issues in target projects
