---
description: Find Feature, Epic, and Story issues without QA assignments for a specific OpenShift version
argument-hint: --feature-label <label> [--feature-label <label2>] --target-version <version> [--epic-project <project>]
---

## Name
jira:query-qa-assignment

## Synopsis
```
/jira:query-qa-assignment --feature-label <label> [--feature-label <label2>] --target-version <version> [--epic-project <project>]
```

## Description
The `jira:query-qa-assignment` command finds Feature, Epic, and Story issues that are missing QA assignments for a specific OpenShift version. It helps identify gaps in QA coverage by checking:

1. **Features** filtered by label(s) and target version that lack a QA Contact
2. **Epics** for the target version and project(s) that lack a QA Contact
3. **QE Stories** (pre-merge testing, e2e testing automation, CI implementation) that lack an Assignee

This command is particularly useful for:
- Release planning and QA resource allocation
- Identifying QA coverage gaps before a release
- Sprint planning and grooming sessions
- Ensuring all Features, Epics, and Stories have proper QA assignments
- Tracking QA coverage metrics across the release

## Key Features

- **Multi-label Support** - Filter Features by one or more labels (e.g., CORS, SPLAT)
- **Version-Specific** - Target specific OpenShift versions (e.g., openshift-4.21)
- **Project Filtering** - Optionally filter Epics by project (e.g., CORS, SPLAT)
- **Hierarchical Analysis** - Checks Features → Epics → Stories in hierarchy
- **QE Story Detection** - Automatically identifies QE-related stories by prefix

## Implementation

The `jira:query-qa-assignment` command runs in several phases:

### 🔍 Phase 1: Parse and Validate Arguments

Parse command-line arguments:

**Arguments:**
- `--feature-label <label>` - Label to filter Features (can be specified multiple times)
  - Required: At least one feature label must be provided
  - Examples: `--feature-label CORS`, `--feature-label CORS --feature-label SPLAT`
- `--target-version <version>` - Target version to filter (required)
  - Format: `openshift-X.Y` or `X.Y`
  - Examples: `--target-version openshift-4.21`, `--target-version 4.21`
- `--epic-project <project>` - Project key(s) to filter Epics (optional, can be specified multiple times)
  - Examples: `--epic-project CORS`, `--epic-project CORS --epic-project SPLAT`

**Validation:**
```bash
# Example parsing
FEATURE_LABELS=()
TARGET_VERSION=""
EPIC_PROJECTS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --feature-label)
      FEATURE_LABELS+=("$2")
      shift 2
      ;;
    --target-version)
      TARGET_VERSION="$2"
      shift 2
      ;;
    --epic-project)
      EPIC_PROJECTS+=("$2")
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate required arguments
if [ ${#FEATURE_LABELS[@]} -eq 0 ]; then
  echo "Error: At least one --feature-label is required"
  exit 1
fi

if [ -z "$TARGET_VERSION" ]; then
  echo "Error: --target-version is required"
  exit 1
fi
```

**Error Handling:**
- Missing `--feature-label`: Display error and usage instructions
- Missing `--target-version`: Display error and usage instructions
- Invalid argument format: Show error with valid format examples

### 🛠️ Phase 2: Query Jira for Features

Find all Features matching the specified labels and target version:

**Method 1: Try jira CLI first (preferred)**
- Check if jira CLI is installed: `which jira`
- Build JQL query for Features:
  ```jql
  project = OCPSTRAT
  AND type = Feature
  AND (labels = "CORS" OR labels = "SPLAT")
  AND "Target Version" ~ "openshift-4.21"
  ```
- Execute query using jira CLI:
  ```bash
  jira issue list --jql "project = OCPSTRAT AND type = Feature AND (labels = \"CORS\" OR labels = \"SPLAT\") AND \"Target Version\" ~ \"openshift-4.21\"" --plain
  ```
- Parse output to extract Feature keys

**Method 2: Fall back to MCP Jira tools if CLI not available**
- Use MCP tool `mcp__atlassian__jira_search_issues`
- Build JQL query with same logic as CLI method
- Extract Feature keys from results

**Extract for each Feature:**
- Feature key (e.g., `OCPSTRAT-12345`)
- Feature summary
- Labels
- Target version

**Check QA Contact Field for each Feature:**
- Query the "QA Contact" custom field using `--raw` flag
- **IMPORTANT**: Same as Epics, the jira CLI does NOT display QA Contact field by default
- Red Hat Jira QA Contact field ID: `customfield_12315948` (same as Epics)
- Extract QA Contact:
  ```bash
  jira issue view FEATURE-KEY --raw | jq -r '.fields.customfield_12315948.displayName // "None"'
  ```
- Consider Feature as **missing QA** if:
  - QA Contact field is empty/null
  - QA Contact returns "None"

### 🔗 Phase 3: Find Epics for Target Version

Query Epics directly by project and target version (Feature-Epic parent-child relationships are not reliably queryable):

**Query Epics:**
1. **Build JQL query for Epics**:
   - Query by project(s) and target version
   - Example JQL:
     ```jql
     project = CORS AND type = Epic AND "Target Version" ~ "openshift-4.21"
     ```
   - If `--epic-project` specified, use only those projects
   - If `--epic-project` not specified, derive project from feature labels or query all

2. **Execute Epic query using jira CLI**:
   ```bash
   jira issue list --jql "project = CORS AND type = Epic AND \"Target Version\" ~ \"openshift-4.21\"" --plain --columns KEY,SUMMARY,STATUS
   ```

3. **Check QA Contact Field for each Epic**:
   - Query the "QA Contact" custom field using `--raw` flag
   - **IMPORTANT**: The jira CLI `issue list` and `issue view` commands do NOT display the QA Contact field by default
   - Must use jira CLI `--raw` flag to access QA Contact
   - Red Hat Jira QA Contact field ID: `customfield_12315948` (type: user picker)
   - Extract QA Contact:
     ```bash
     jira issue view EPIC-KEY --raw | jq -r '.fields.customfield_12315948.displayName // "None"'
     ```
   - Consider Epic as **missing QA** if:
     - QA Contact field is empty/null
     - QA Contact returns "None"

**Extract for each Epic:**
- Epic key (e.g., `CORS-1234`)
- Epic summary
- Epic status
- QA Contact value (or "None")
- Target version

### 📋 Phase 4: Find QE Stories from Epics

Find all QE-related Stories that link to the Epics found in Phase 3:

**Query QE Stories using Epic Link:**
1. **Build JQL query for Stories**:
   - Query Stories where "Epic Link" points to any of the found Epics
   - Filter by summary patterns for QE stories
   - Epic Link field ID: `customfield_12311140`
   - Example JQL:
     ```jql
     project = CORS
     AND "Epic Link" in (EPIC-1, EPIC-2, ...)
     AND (summary ~ "pre-merge testing" OR summary ~ "e2e testing" OR summary ~ "CI implementation")
     ```

2. **Execute Story query**:
   ```bash
   jira issue list --jql 'project = CORS AND "Epic Link" in (CORS-4267,CORS-4212,...) AND (summary ~ "pre-merge testing" OR summary ~ "e2e testing" OR summary ~ "CI implementation")' --csv --columns KEY,SUMMARY,ASSIGNEE,STATUS
   ```
   - Use `--csv` format for reliable parsing (handles multi-line summaries and special characters)
   - Use CSV format instead of plain text to avoid column alignment issues

3. **Filter by QE Story types**:
   - Stories with summary starting with:
     - "pre-merge testing"
     - "e2e testing automation"
     - "CI implementation"
     - "post-merge testing" (less common)

4. **Check Assignee field**:
   - Parse CSV output to check if Assignee column is empty
   - Consider Story as **missing Assignee** if:
     - Assignee field is empty/null
     - Assignee field contains "Unassigned"

**Extract for each QE Story:**
- Story key (e.g., `CORS-5678`)
- Story summary
- Assignee value (or "Unassigned")
- Parent Epic key (from Epic Link field)
- Story status
- Story type (pre-merge, e2e, CI, post-merge)

### 📊 Phase 5: Aggregate and Format Results

Organize findings into structured report:

**Report Structure:**

```markdown
# QA Assignment Report

**Generated**: {current-date}
**Query Parameters**:
- Labels: {label1, label2, ...}
- Target Version: {version}
- Projects: {project1, project2, ...} (or "All")

---

## Summary

**Features Found**: {count}
**Features Missing QA Contact**: {count}
**Epics Analyzed**: {count}
**Epics Missing QA Contact**: {count}
**QE Stories Found**: {count}
**QE Stories Missing Assignee**: {count}

---

## 📦 Features Analyzed

{For each Feature:}
### {FEATURE-KEY} - {Feature Summary}
- **Labels**: {labels}
- **Target Version**: {version}
- **QA Contact**: {name or ❌ None}

---

## ⚠️ Features Missing QA Contact

{If no Features missing QA Contact:}
✅ All Features have QA Contact assigned!

{Otherwise, for each Feature missing QA Contact:}
### {FEATURE-KEY} - {Feature Summary}
- **Project**: OCPSTRAT
- **Labels**: {labels}
- **QA Contact**: ❌ None
- **Target Version**: {version}
- **Link**: {feature-url}

---

## ⚠️ Epics Missing QA Contact

{If no Epics missing QA Contact:}
✅ All Epics have QA Contact assigned!

{Otherwise, for each Epic missing QA Contact:}
### {EPIC-KEY} - {Epic Summary}
- **Parent Feature**: {FEATURE-KEY}
- **Project**: {project}
- **QA Contact**: ❌ None
- **Status**: {status}
- **Link**: {epic-url}

---

## ⚠️ QE Stories Missing Assignee

{If no Stories missing Assignee:}
✅ All QE Stories have Assignee!

{Otherwise, for each Story missing Assignee:}
### {STORY-KEY} - {Story Summary}
- **Parent Epic**: {EPIC-KEY}
- **Parent Feature**: {FEATURE-KEY}
- **Assignee**: ❌ Unassigned
- **Status**: {status}
- **Story Type**: {pre-merge testing | e2e testing automation | CI implementation}
- **Link**: {story-url}

---

## 📊 Detailed Statistics

**Features Summary:**
- **Total Features**: {count}
- **Features with QA Contact**: {count} ({percentage}%)
- **Features missing QA Contact**: {count} ({percentage}%)

**Epics Summary:**
- **Total Epics**: {count}
- **Epics with QA Contact**: {count} ({percentage}%)
- **Epics missing QA Contact**: {count} ({percentage}%)

**By Project:**
{For each project:}
- **{PROJECT}**: {epic-count} Epics, {missing-qa-count} missing QA Contact

**QE Stories Summary:**
- **Total QE Stories**: {count}
- **Assigned**: {count} ({percentage}%)
- **Unassigned**: {count} ({percentage}%)

**By Story Type:**
- **Pre-merge Testing**: {count} stories, {missing-count} unassigned
- **E2E Testing Automation**: {count} stories, {missing-count} unassigned
- **CI Implementation**: {count} stories, {missing-count} unassigned

**QA Contacts Distribution:**
{For each QA contact:}
- **{Name}**: {feature-count} Features, {epic-count} Epics, {story-count} Stories

---

🤖 Generated with [Claude Code](https://claude.com/claude-code) via `/jira:query-qa-assignment`
```

### 💾 Phase 6: Save and Display

**Save to file:**
- Filename: `qa-assignment-{version}-{timestamp}.md`
- Location: `.work/qa-reports/` directory
- Example: `.work/qa-reports/qa-assignment-4.21-2025-10-31.md`

**Display to user:**
1. Show summary statistics
2. Highlight critical gaps (Epics/Stories without QA)
3. Provide file path for detailed report
4. Suggest next actions

**Example Console Output:**
```
QA Assignment Analysis Complete
================================

Query: Labels=[CORS, SPLAT], Version=openshift-4.21, Projects=[CORS, SPLAT]

Results:
  ✓ 15 Features analyzed
  ⚠️ 2 Features missing QA Contact
  ✓ 20 Epics analyzed
  ⚠️ 8 Epics missing QA Contact
  ✓ 45 QE Stories found
  ⚠️ 12 QE Stories missing Assignee

Coverage:
  Features: 87% have QA Contact
  Epics: 60% have QA Contact
  Stories: 73% have Assignee

Breakdown:
  Features without QA Contact:
    - OCPSTRAT-1234
    - OCPSTRAT-5678

  Epics without QA Contact:
    - CORS: 5 epics
    - SPLAT: 3 epics

  Stories without Assignee:
    - Pre-merge testing: 4 stories
    - E2E testing automation: 6 stories
    - CI implementation: 2 stories

Detailed report saved to:
  .work/qa-reports/qa-assignment-4.21-2025-10-31.md

Next Steps:
  1. Review Features and assign QA contacts
  2. Review Epics and assign QA contacts
  3. Assign QE stories to team members
  4. Re-run analysis to verify all assignments
```

## Usage Examples

1. **Single feature label with target version**:
   ```
   /jira:query-qa-assignment --feature-label CORS --target-version openshift-4.21
   ```

2. **Multiple feature labels with target version**:
   ```
   /jira:query-qa-assignment --feature-label CORS --feature-label SPLAT --target-version 4.21
   ```

3. **With epic project filter**:
   ```
   /jira:query-qa-assignment --feature-label CORS --target-version 4.21 --epic-project CORS --epic-project SPLAT
   ```

4. **Multiple feature labels and epic projects**:
   ```
   /jira:query-qa-assignment --feature-label CORS --feature-label NetworkEdge --target-version openshift-4.22 --epic-project CORS --epic-project SPLAT --epic-project OCPCLOUD
   ```

## Arguments

- **--feature-label <label>** – Label to filter Features *(required, repeatable)*
  - Can be specified multiple times for OR logic
  - Examples: `CORS`, `SPLAT`, `NetworkEdge`

- **--target-version <version>** – Target version *(required)*
  - Format: `openshift-X.Y` or `X.Y`
  - Examples: `openshift-4.21`, `4.21`, `4.22`

- **--epic-project <project>** – Project key to filter Epics *(optional, repeatable)*
  - Can be specified multiple times
  - Examples: `CORS`, `SPLAT`, `OCPCLOUD`
  - If omitted, all projects are included

## Return Value

- **Markdown Report**: Detailed report saved to `.work/qa-reports/qa-assignment-{version}-{timestamp}.md`
- **Summary Statistics**: Console output with counts and breakdown
- **Issue Lists**:
  - Features missing QA Contact
  - Epics missing QA Contact
  - QE Stories missing Assignee
- **Coverage Metrics**: Percentage of Features, Epics, and Stories with proper assignments

## Prerequisites

**Option 1: jira CLI (Preferred)**
- Install jira CLI: https://github.com/ankitpokhrel/jira-cli
- Configure authentication:
  ```bash
  jira init
  ```
- Verify installation:
  ```bash
  jira --version
  ```

**Option 2: MCP Jira Server (Fallback)**
- Claude Code with Atlassian MCP server configured
- See plugins documentation for MCP setup instructions

**Note**: The command will automatically try jira CLI first, then fall back to MCP if CLI is not available.

## Error Handling

### Missing Required Arguments

**Scenario**: User doesn't provide required `--feature-label` or `--target-version`.

**Action**:
```
Error: Missing required arguments

Usage: /jira:query-qa-assignment --feature-label <label> [--feature-label <label2>] --target-version <version> [--epic-project <project>]

Required:
  --feature-label <label>     Label to filter Features (can be specified multiple times)
  --target-version <version>  Target version (e.g., openshift-4.21)

Optional:
  --epic-project <project>    Project key to filter Epics (can be specified multiple times)

Examples:
  /jira:query-qa-assignment --feature-label CORS --target-version 4.21
  /jira:query-qa-assignment --feature-label CORS --feature-label SPLAT --target-version openshift-4.21 --epic-project CORS
```

### No Features Found

**Scenario**: Query returns no Features matching criteria.

**Action**:
```
No Features Found
=================

Query: Labels=[CORS, SPLAT], Version=openshift-4.21

No Features found matching the specified criteria.

Possible reasons:
  1. No Features have all specified labels
  2. Version not set or incorrect format
  3. Features exist but are in different projects

Suggestions:
  - Verify labels are correct
  - Check version format (should be "openshift-4.21" or "4.21")
  - Try querying Jira directly to verify Features exist
```

### No jira CLI and No MCP Available

**Scenario**: Neither jira CLI nor MCP tools are available.

**Action**:
```
Error: Cannot query Jira - no query method available

Please install one of the following:

1. jira CLI (recommended):
   Installation: https://github.com/ankitpokhrel/jira-cli
   Setup: jira init

2. Atlassian MCP Server:
   Setup instructions in plugins documentation

After installation, retry the command.
```

### Feature Has No Epics

**Scenario**: Feature found but has no child Epics.

**Action**:
- Note in report under Features section:
  ```
  ### OCPCLOUD-12345 - Feature Summary
  - **Labels**: CORS, SPLAT
  - **Target Version**: openshift-4.21
  - **Child Epics**: 0 (⚠️ No Epics found)
  ```
- Include in summary statistics

### Epic Has No Stories

**Scenario**: Epic found but has no child Stories.

**Action**:
- Include Epic in "Missing QA Contact" section if applicable
- Note in detailed Epic section:
  ```
  ### CORS-1234 - Epic Summary
  - **Parent Feature**: OCPCLOUD-12345
  - **QA Contact**: ❌ None
  - **Child Stories**: 0 (⚠️ No Stories found)
  ```

### Access Denied / Permission Issues

**Scenario**: User lacks permissions to view certain issues.

**Action**:
```
Warning: Access Denied for Some Issues
=======================================

The following issues could not be accessed:
  - CORS-1234 (Access denied)
  - SPLAT-5678 (Access denied)

Results may be incomplete.

Please ensure you have permissions to view issues in:
  - CORS project
  - SPLAT project
  - OCPCLOUD project

Contact your Jira administrator if you need access.
```

## Best Practices

1. **Regular Monitoring**: Run this command periodically during release planning
2. **Early Detection**: Run early in the release cycle to identify gaps
3. **Multiple Labels**: Use multiple labels to cover all relevant features
4. **Project Filtering**: Use project filter to focus on specific teams
5. **Follow-Up**: After assigning QA/Assignees, re-run to verify

## JQL Queries Used

The command builds and executes these JQL queries:

**1. Find Features:**
```jql
project = OCPSTRAT
AND type = Feature
AND labels = "CORS"
AND "Target Version" ~ "openshift-4.21"
```
For multiple labels, use OR:
```jql
project = OCPSTRAT
AND type = Feature
AND (labels = "CORS" OR labels = "SPLAT")
AND "Target Version" ~ "openshift-4.21"
```

**2. Find Epics by Project and Version:**
```jql
project = CORS
AND type = Epic
AND "Target Version" ~ "openshift-4.21"
```
For multiple projects:
```jql
project in (CORS, SPLAT)
AND type = Epic
AND "Target Version" ~ "openshift-4.21"
```

**3. Find QE Stories from Epics:**
```jql
project = CORS
AND "Epic Link" in (EPIC-1, EPIC-2, ...)
AND (
  summary ~ "pre-merge testing"
  OR summary ~ "e2e testing"
  OR summary ~ "CI implementation"
)
```

**Note**: Feature-Epic parent-child relationships are not reliably queryable via JQL, so we query Epics directly by project and version instead.

## Field Mappings

Different Jira instances may use different field names:

**QA Contact Field:**
- `customfield_12315948` (Red Hat Jira)
- `QA Contact`
- `QA Assignee`

**Target Version Field:**
- `Target Version`
- `Fix Version/s`
- `customfield_12319940` (common custom field)

**Epic Link Field:**
- `Epic Link`
- `Parent`
- `customfield_12311140` (common custom field)

The command will attempt to detect and use the correct field names.

## See Also

- `jira:grooming` - Generate grooming meeting agendas
- `jira:status-rollup` - Generate status rollups for Jira issues
- `jira:generate-test-plan` - Generate test plans for Jira issues

## Configuration

### jira CLI Configuration

If using jira CLI, configure your `.jira.yml`:

```yaml
server: https://issues.redhat.com
installation: cloud
```

### Custom Field IDs

If field detection fails, you can manually specify custom field IDs in the command implementation:

```bash
# Custom field IDs for Red Hat Jira
QA_CONTACT_FIELD="customfield_12315948"
TARGET_VERSION_FIELD="customfield_12319940"
EPIC_LINK_FIELD="customfield_12311140"
```
