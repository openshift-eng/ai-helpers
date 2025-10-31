---
name: Weekly Report Generation
description: Generate comprehensive weekly team activity reports from Jira with complete issue data, changelogs, and activity filtering
---

# Weekly Report Generation

This skill generates detailed weekly team activity reports by systematically collecting Jira data, filtering by activity within a specific reporting window, and producing structured markdown reports.

## When to Use This Skill

Use this skill when implementing the `/report-writer:weekly` command. The skill provides step-by-step guidance for:
- Discovering Jira boards and sprints for a project
- Fetching complete issue data with changelogs via MCP tools and saving to individual files
- Filtering issues by activity within the report week
- Generating comprehensive team activity reports

## Prerequisites

1. **Jira MCP Server**
   - Must be configured and running
   - See plugin README for setup instructions
   - Required MCP tools (use EXACTLY these):
     - `mcp__atlassian__jira_get_agile_boards` - for finding boards
     - `mcp__atlassian__jira_get_sprints_from_board` - for finding sprints
     - `mcp__atlassian__jira_get_board_issues` - for getting issue keys (NOT `jira_get_sprint_issues`)
     - `mcp__atlassian__jira_get_issue` - for fetching complete issue data

2. **jq** (for verification)
   - Check: `which jq`
   - Used for verifying JSON file structure
   - Install if needed: `sudo dnf install jq` or `brew install jq`

## Input Parameters

Parse these parameters from the user's command:

- `--project`: Jira project key (e.g., "CLID") - **REQUIRED**
- `--component`: Component filter (e.g., "oc-mirror") - optional
- `--week-offset`: Weeks back from current (default: -1)
  - `-1`: Last week (previous Monday-Sunday)
  - `0`: Current week (this Monday-Sunday)
  - `-2`: Two weeks ago
- `--batch-size`: Issues per parallel batch (default: 5, range: 1-10)
- `--slack-file`: Path to Slack standup file - optional
- `--notes`: Additional notes text - optional

**Validation**:
- If no `--project` specified, ask user to provide it
- Default `--week-offset` to -1 if not specified
- Default `--batch-size` to 5 if not specified
- Validate batch-size is between 1-10

## Implementation Steps

### Step 1: Discover Board ID

**Objective**: Find the Jira board ID for the specified project.

**Action**:
```bash
Call: mcp__atlassian__jira_get_agile_boards(project_key="{PROJECT}")
```

**Process**:
1. Call the MCP tool with project key from parameters
2. If multiple boards returned, select one with `"type": "scrum"`
3. If only one board returned, use that board
4. Extract and store `board_id` and `board_name`

**Example response**:
```json
[{"id": 18785, "name": "CLID Board", "type": "scrum"}]
```

**Error handling**: If no boards found, inform user that project may not have an agile board configured.

### Step 2: Calculate Target Week and Find Sprint

**Objective**: Identify the sprint that overlaps with the reporting week.

**Week Calculation Rules**:
- Weeks ALWAYS run Monday-Sunday (Mon-Sun format)
- Calculate based on `week-offset` parameter:
  - `week-offset = -1`: Previous Monday-Sunday
  - `week-offset = 0`: Current Monday-Sunday
  - `week-offset = -2`: Two weeks ago Monday-Sunday

**Example**: If today is Thursday Oct 30, 2025:
- Current week: Monday Oct 27 - Sunday Nov 2
- Last week (offset -1): Monday Oct 20 - Sunday Oct 26

**Action**:
```
Call: mcp__atlassian__jira_get_sprints_from_board(board_id={BOARD_ID})
```

**Process**:
1. Calculate target Monday-Sunday date range based on week-offset
2. Call MCP tool to get ALL sprints (active, closed, future)
3. For each sprint, check if sprint dates overlap with target week
4. Select sprint with most overlap
5. Extract and store `sprint_id` and `sprint_name`

**Validation**: Only one sprint should overlap with the date range.

### Step 3: Get Sprint Issue Keys

**Objective**: Retrieve all issue keys from the identified sprint.

**CRITICAL**: Use `mcp__atlassian__jira_get_board_issues` (NOT `jira_get_sprint_issues`) to avoid large response errors. Only request the "key" field.

**Action**:
```
Call: mcp__atlassian__jira_get_board_issues(
    board_id={BOARD_ID},
    jql="Sprint = {SPRINT_ID}",
    fields="key",
    limit=50
)
```

**With component filter**:
```
Call: mcp__atlassian__jira_get_board_issues(
    board_id={BOARD_ID},
    jql="Sprint = {SPRINT_ID} AND component = '{COMPONENT}'",
    fields="key",
    limit=50
)
```

**Process**:
1. Build JQL query with sprint ID
2. Add component filter to JQL if `--component` was specified
3. Request only "key" field for efficiency
4. Extract array of issue keys (e.g., `["CLID-460", "CLID-461", "CLID-462"]`)

**Error handling**: If no issues found, verify sprint ID and inform user.

### Step 4: Fetch Complete Issue Data and Save Individual Files

**Objective**: Fetch complete issue data with changelogs via MCP tools and save each issue as an individual JSON file.

#### Step 4a: Create Working Directory

**Action**:
```bash
mkdir -p "/tmp/weekly-$(date +'%Y%m%d-%H%M%S')"
```

**Store the directory path** in a variable for later use. Inform user:
```
Creating working directory: /tmp/weekly-{timestamp}/
```

#### Step 4b: Fetch Issues via MCP Tools and Save Individual Files

**Objective**: Fetch all issues with complete data using MCP tools in batches, saving each to its own JSON file.

**Process**:
1. Split issue keys into batches (default batch size: 5)
2. For each batch, call `mcp__atlassian__jira_get_issue` in parallel with:
   - `issue_key="{ISSUE_KEY}"`
   - `fields="*all"`
   - `expand="changelog"`
   - `comment_limit=100`
3. Immediately save each fetched issue to its own JSON file: `/tmp/weekly-{timestamp}/{ISSUE_KEY}.json`

**Example**: For 19 issues with batch size 5:
```
Batch 1: Fetch and save CLID-281, CLID-476, CLID-420, CLID-198, CLID-442
Batch 2: Fetch and save CLID-437, CLID-434, CLID-465, CLID-471, CLID-472
...
```

**Progress tracking**: Inform user about progress:
```
Fetching issues: batch 1/4 (5 issues)
✓ Saved CLID-281.json
✓ Saved CLID-476.json
✓ Saved CLID-420.json
✓ Saved CLID-198.json
✓ Saved CLID-442.json

Fetching issues: batch 2/4 (5 issues)
...
```

**IMPORTANT**: Use the Write tool to save each issue immediately after fetching to avoid holding large amounts of data in context.

#### Step 4c: Verify Data Completeness

After all batches complete, verify data completeness:

1. **Count JSON files**:
   ```bash
   ls /tmp/weekly-{timestamp}/*.json | wc -l
   ```
   Should match the number of issue keys from Step 3.

2. **Verify file structure** (check a sample file):
   ```bash
   # Check that key field exists
   jq -e '.key' /tmp/weekly-{timestamp}/{SAMPLE_ISSUE_KEY}.json

   # Check that changelogs field exists
   jq -e 'has("changelog")' /tmp/weekly-{timestamp}/{SAMPLE_ISSUE_KEY}.json

   # Check that summary exists
   jq -e '.fields.summary' /tmp/weekly-{timestamp}/{SAMPLE_ISSUE_KEY}.json
   ```
   All should succeed (exit code 0).

3. **Check directory size**:
   ```bash
   du -sh /tmp/weekly-{timestamp}/
   ```
   Should be reasonable (typically 5-10 KB per issue).

4. **List saved files** (for user visibility):
   ```bash
   ls -lh /tmp/weekly-{timestamp}/*.json | head -5
   ```

**Inform user**:
```
✓ Data collection complete
  Directory: /tmp/weekly-{timestamp}/
  Issue Files: 29/29
  Total Size: 245 KB
  Sample Verification:
    - Key field: ✓ Present
    - Changelogs: ✓ Present
    - Summary: ✓ Present
  Ready for report generation
```

**If verification fails**:
- Check which issues are missing files
- Re-fetch any failed issues individually
- Report detailed error about what went wrong (missing field, file not created, etc.)

### Step 5: Generate Report

**Objective**: Analyze issue data and create comprehensive markdown report.

#### Step 5a: Load and Filter Issues

**Action**: Read all JSON files from working directory and filter by activity.

**CRITICAL FILTERING RULE**: Only include issues with activity during the report week.

**Activity types to check** (within report week date range):
- Status transitions (from changelogs)
- Field changes (assignee, priority, labels, etc.)
- Comments added
- Sprint assignments/removals
- PR activity

**Process**:
1. Read each JSON file from `/tmp/weekly-{timestamp}/`
2. Parse changelogs and comments
3. Check timestamps against report week date range
4. Mark issues with activity in report week
5. Exclude issues with no activity in report week from report

#### Step 5b: Calculate Metrics

Analyze filtered issues to calculate:

**Summary Metrics**:
- Total issues in sprint (all fetched issues)
- Issues with activity during report week (filtered count)
- Issues closed during week
- Issues with status changes
- Issues with comments
- Issues with PR activity

**Team Contributions**:
- Activity count per team member (from changelogs/comments)
- Issues assigned per person
- Comments authored per person

**PR Activity**:
- PRs created during week
- PRs merged during week
- PRs updated during week

#### Step 5c: Build Report Structure

Create markdown report with these sections:

```markdown
# Weekly Team Activity Report

**Project**: {PROJECT}
**Sprint**: {SPRINT_NAME}
**Period**: {START_DATE} - {END_DATE}
{Component filter if applicable}

## Summary Metrics

- Total Issues in Sprint: {total}
- Issues with Activity: {active}
- Issues Closed: {closed}
- Issues In Progress: {in_progress}
- New Comments: {comment_count}

## Issues with Activity

### Closed This Week
- [CLID-460](link) - Issue title
  - Closed by: User Name
  - Date: YYYY-MM-DD
  - Summary: Brief description

### Status Changes
- [CLID-461](link) - Issue title
  - Changed from: In Progress → Code Review
  - Date: YYYY-MM-DD

### Active Discussions
- [CLID-462](link) - Issue title
  - Comments: 3 new comments
  - Contributors: User1, User2

## Team Contributions

- **User Name 1**: 8 updates (3 issues closed, 5 comments)
- **User Name 2**: 5 updates (2 status changes, 3 comments)

## Pull Request Activity

- **Merged**: 3 PRs
- **Created**: 5 PRs
- **Updated**: 8 PRs

## Additional Notes

{Content from --notes or --slack-file if provided}

---
Generated: {timestamp}
```

#### Step 5d: Save Report

**Action**: Save complete report to file and display to user.

1. **Save to file**:
   ```
   Write to: /tmp/weekly-{timestamp}/weekly-report.md
   ```

2. **Display highlights**:
   Show concise summary with key metrics, top contributors, and achievements.

3. **Display full report**:
   Show complete markdown report to user.

4. **Inform user of file location**:
   ```
   📄 Full report saved to: /tmp/weekly-{timestamp}/weekly-report.md
   ```

## Output Format

The skill produces:

1. **Working Directory**: `/tmp/weekly-{timestamp}/`
   - Contains individual issue JSON files
   - Contains final markdown report

2. **Issue Data Files**: `{ISSUE_KEY}.json`
   - One file per issue
   - Complete data with changelogs

3. **Report File**: `weekly-report.md`
   - Comprehensive markdown report
   - Filtered to report week activity

4. **Console Output**:
   - Progress updates during execution
   - Verification statistics
   - Report highlights
   - Full report text

## Error Handling

**Common issues**:

- **No boards found**: Project may not have agile board configured
- **No sprint overlaps**: Check week calculation or use custom date range
- **API rate limiting**: Reduce `--batch-size` to 1-2
- **Missing changelogs**: Verify using `expand="changelog"` parameter in MCP calls
- **Empty sprints**: Confirm with user and generate report noting no activity
- **File write failures**: Check `/tmp` directory permissions and available disk space
- **Verification failures**: Re-fetch failed issues individually and verify MCP response is complete

## Quality Checklist

Before completing, verify:
- [ ] All parameters were correctly parsed
- [ ] Board and sprint were successfully identified
- [ ] Target week calculated correctly (Monday-Sunday)
- [ ] Working directory created
- [ ] All issues fetched via MCP tools in batches
- [ ] Each issue saved to individual JSON file immediately after fetching
- [ ] File count matches expected number of issues
- [ ] Sample file verified to have required fields (key, summary, changelog)
- [ ] Directory size is reasonable (5-10 KB per issue)
- [ ] User informed of directory and file count with verification status
- [ ] Issues filtered to report week activity only
- [ ] Report saved to markdown file
- [ ] Highlights displayed to user
- [ ] Full report displayed to user
- [ ] File paths communicated to user

## Final Output

Always provide this summary to the user:

```
════════════════════════════════════════════════════════════
REPORT GENERATION COMPLETE
════════════════════════════════════════════════════════════
📁 Working Directory: /tmp/weekly-{timestamp}/

📊 Data Files:
   - Issue Files: {count}/{total}
   - Total Size: {size}
   - Sample Files: CLID-460.json, CLID-461.json, ...

📄 Report File:
   - Location: /tmp/weekly-{timestamp}/weekly-report.md
   - Format: Markdown
   - Status: ✓ Saved successfully

✅ Report has been displayed above with highlights and full details
════════════════════════════════════════════════════════════
```

This summary is mandatory and ensures the user knows exactly where to find all generated artifacts.
