# Report Writer Plugin

An intelligent agent plugin that generates comprehensive weekly team activity reports by systematically collecting and analyzing data from Atlassian Jira. This plugin automates the tedious process of gathering sprint data, tracking issue changes, and producing detailed activity summaries.

## Overview

The Report Writer agent follows a rigorous 5-step workflow to ensure complete data capture and accuracy:

1. **Parse Parameters** - Extract project, component, date range, and optional notes
2. **Discover Board** - Identify the correct Jira agile board for the project
3. **Find Sprint** - Locate the sprint that overlaps with the target reporting week
4. **Fetch Issue Keys** - Retrieve all issues in the sprint (with optional component filtering)
5. **Collect Complete Data** - Fetch full issue details including changelogs and comments

The agent generates structured reports that include:
- Sprint summary metrics
- Issues with activity during the reporting period
- Team member contributions
- PR activity and status transitions
- Custom notes and context

**Report Output**:
- **Key Highlights**: Displays a concise summary with metrics, top contributors, achievements, and concerns
- **Full Report**: Complete markdown report displayed in-line and saved to disk
- **Report File**: Saved as `/tmp/weekly-{timestamp}/weekly-report.md` for sharing and archival

## Features

- ✅ **Accurate Week Calculation** - Uses Monday-Sunday format with configurable week offsets
- ✅ **Activity Filtering** - Only includes issues with activity during the target week
- ✅ **Complete Data Collection** - Fetches full issue history including changelogs and comments
- ✅ **Component Filtering** - Generate reports for specific components within a project
- ✅ **Data Preservation** - Saves individual JSON files per issue for audit and analysis
- ✅ **Batch Processing** - Efficient parallel fetching with configurable batch size (1-10)
- ✅ **Verification Steps** - Validates data completeness before report generation
- ✅ **Dual Report Views** - Shows key highlights summary and full detailed report
- ✅ **Markdown Export** - Saves complete report as shareable markdown file

## Prerequisites

- Claude Code installed
- Jira MCP server configured and running

## Setup

### Option 1: Using npx (Recommended for Atlassian Cloud)

```bash
# Add the Atlassian MCP server
claude mcp add atlassian npx @modelcontextprotocol/server-atlassian
```

Configure your Jira credentials according to the [Atlassian MCP documentation](https://github.com/modelcontextprotocol/servers/tree/main/src/atlassian).

**Required tokens:**
- **JIRA API TOKEN**: Generate at https://id.atlassian.com/manage-profile/security/api-tokens

### Option 2: Using External Server (Recommended for Jira Data Center)

Connect Claude to an already running Jira MCP Server:

```bash
# Add the Atlassian MCP server via SSE transport
claude mcp add --transport sse atlassian http https://127.0.0.1:8080/sse
```

### Option 3: Running Jira MCP Server with Podman/Docker

Start the Atlassian MCP server in a container:

```bash
# Start the server with podman
podman run -i --rm -p 8080:8080 \
  -e "JIRA_URL=https://issues.redhat.com" \
  -e "JIRA_USERNAME=your-username" \
  -e "JIRA_API_TOKEN=your-api-token" \
  -e "JIRA_PERSONAL_TOKEN=your-personal-token" \
  -e "JIRA_SSL_VERIFY=true" \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport sse --port 8080 -vv

# Or with docker
docker run -i --rm -p 8080:8080 \
  -e "JIRA_URL=https://issues.redhat.com" \
  -e "JIRA_USERNAME=your-username" \
  -e "JIRA_API_TOKEN=your-api-token" \
  -e "JIRA_PERSONAL_TOKEN=your-personal-token" \
  -e "JIRA_SSL_VERIFY=true" \
  ghcr.io/sooperset/mcp-atlassian:latest \
  --transport sse --port 8080 -vv
```

**Required tokens:**
- **JIRA PERSONAL TOKEN**: Generate at https://issues.redhat.com/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens
- **JIRA API TOKEN**: For Atlassian Cloud compatibility

## Usage

### Basic Usage

Generate a report for the previous week (Monday-Sunday):

```
Can you generate a weekly report for the last week for the project CLID?
```

### With Component Filter

Generate a report for a specific component:

```
Can you generate a weekly report for the last week for the project CLID and component oc-mirror?
```

### Custom Week Offset

Generate a report for the current week:

```
Generate a weekly report for this week (week-offset 0) for project CLID
```

Generate a report for two weeks ago:

```
Generate a report for project CLID with week-offset -2
```

### With Custom Notes

Include additional context in the report:

```
Generate a sprint report for CLID Sprint 278 and include these notes:
- Major milestone: Feature X completed
- Blockers resolved: Infrastructure access granted
- Next sprint focus: Performance optimization
```

### With Custom Batch Size

Adjust the parallel fetch batch size for rate limiting or performance:

```
Generate a report for CLID last week with batch-size 2
```

For faster processing (if API allows):
```
Generate a report for CLID last week with batch-size 10
```

## Parameters

The agent supports the following parameters (specified in natural language):

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `--project` | Project key (REQUIRED) | None | `CLID` |
| `--component` | Component filter (optional) | None | `oc-mirror` |
| `--week-offset` | Weeks back from current week | `-1` | `0` (this week), `-1` (last week), `-2` (two weeks ago) |
| `--batch-size` | Number of issues to fetch in parallel | `5` | `1` (slow/rate limited), `10` (fast) |
| `--notes` | Manual notes to include | None | Custom text |
| `--slack-file` | Path to Slack standup file | None | `/path/to/standup.txt` |

## Output Format

### Report Presentation

The agent provides **two views** of the report:

#### 1. Key Highlights (Displayed First)
A concise executive summary shown immediately:
```
════════════════════════════════════════════════════════════
WEEKLY REPORT HIGHLIGHTS
════════════════════════════════════════════════════════════
Project: CLID
Sprint: Sprint 278
Period: 2025-10-20 - 2025-10-26

📊 METRICS
- Total Issues in Sprint: 15
- Issues with Activity: 8
- Issues Closed: 3
- Issues In Progress: 5

👥 TOP CONTRIBUTORS
- John Doe: 12 updates
- Jane Smith: 8 updates
- Bob Wilson: 5 updates

🎯 KEY ACHIEVEMENTS
- Feature X completed and merged
- Critical bug fix deployed to production

⚠️  BLOCKERS/CONCERNS
- Waiting on infrastructure team for access
- API rate limiting impacting development
════════════════════════════════════════════════════════════
```

#### 2. Full Report Structure

The complete markdown report includes:

1. **Header**
   - Project name and sprint name
   - Date range (Monday-Sunday format)
   - Component filter (if applied)

2. **Summary Metrics**
   - Total issues in sprint
   - Issues with activity during report week
   - Activity breakdown by type

3. **Issues with Activity** (grouped by activity type)
   - Issues closed during the week
   - Issues with status transitions
   - Issues with significant comments
   - Issues with PR activity
   - Issues added to or removed from sprint

4. **Team Member Contributions**
   - Activity summary per team member

5. **PR Activity**
   - PRs created, updated, or merged during the week

6. **Additional Notes**
   - Custom notes from `--notes` or `--slack-file`

The full report is:
- Displayed to you in the conversation
- Saved to `/tmp/weekly-{timestamp}/weekly-report.md` in markdown format

### Data Files

The agent creates a working directory at `/tmp/weekly-{timestamp}/` and saves individual JSON files for each issue:

- Each issue gets its own file named `{ISSUE_KEY}.json` (e.g., `CLID-460.json`)
- Complete issue data including changelogs and comment history
- All custom fields and metadata

These files can be used for:
- Audit trails
- Custom analysis
- Debugging report generation
- Historical reference
- Individual issue inspection

**Example final output:**
```
════════════════════════════════════════════════════════════
REPORT GENERATION COMPLETE
════════════════════════════════════════════════════════════
📁 Working Directory: /tmp/weekly-20251029-143022.323/

📊 Data Files:
   - Issue Files: 15/15 (one file per issue)
   - Total Size: 127 KB
   - Contains Changelogs: ✓ Yes
   - Contains Comments: ✓ Yes
   - Sample Files: CLID-460.json, CLID-461.json, CLID-462.json, ...

📄 Report File:
   - Location: /tmp/weekly-20251029-143022.323/weekly-report.md
   - Format: Markdown
   - Status: ✓ Saved successfully

✅ Report has been displayed above with key highlights and full details
════════════════════════════════════════════════════════════
```

## How It Works

### Week Calculation

The agent uses **Monday-Sunday** week format exclusively:

- **week-offset = -1** (default): Previous Monday-Sunday
- **week-offset = 0**: Current Monday-Sunday
- **week-offset = -2**: Two weeks ago Monday-Sunday

**Example:** If today is Thursday, Oct 30, 2025:
- Current week: Monday Oct 27 - Sunday Nov 2
- Last week (offset -1): Monday Oct 20 - Sunday Oct 26

### Activity Filtering

The report **only includes issues with activity during the target week**:

- Status transitions (using changelog timestamps)
- Field changes (assignee, priority, labels, etc.)
- Comments added
- PR activity
- Sprint assignments

Issues completed before the report week are fetched for context but excluded from the final report.

### Data Collection Process

1. **Issue Discovery**: Uses JQL to find all issues in the target sprint
2. **Batch Fetching**: Retrieves issues in parallel batches (default: 5, configurable with `--batch-size`)
3. **Complete Data**: Fetches all fields with `fields="*all"` and `expand="changelog"`
4. **Individual File Writing**: Each issue is immediately saved to its own `{ISSUE_KEY}.json` file
5. **Verification**: Validates all files exist and contain complete data before report generation
6. **Filtering**: Reads all issue files and analyzes changelogs to identify activity within the target week

**Performance tuning**: Adjust `--batch-size` between 1 (slowest, safest) and 10 (fastest, may hit rate limits) based on your Jira server's capacity and network conditions.

## Troubleshooting

### No boards found for project

**Problem:** The agent can't find an agile board for your project.

**Solution:** Verify that:
- Your project has an agile board configured in Jira
- You have permissions to access the board
- The project key is correct

### Sprint not found for date range

**Problem:** No sprint overlaps with the target week.

**Solution:**
- Check if your team uses sprints in Jira
- Verify the project follows an agile methodology
- Try a different week offset
- Confirm sprint dates in Jira

### Missing changelogs in data

**Problem:** The data file doesn't contain changelogs.

**Solution:** This indicates a bug in the agent. The agent should automatically retry with the correct parameters. If the issue persists, please report it.

### Empty report

**Problem:** Report shows no activity for the week.

**Solution:**
- Verify the week offset is correct
- Check if there was actual activity in Jira during that week
- Ensure component filter isn't too restrictive
- Review the data file to confirm issues were fetched

### API rate limiting

**Problem:** Jira MCP server returns rate limiting errors.

**Solution:**
- Use a smaller batch size: `--batch-size 1` or `--batch-size 2`
- The agent will implement exponential backoff between batches
- Example: `Generate a report for CLID last week with batch-size 1`
- Contact your Jira administrator if limits are too restrictive

## Examples

### Example 1: Basic Weekly Report

**Input:**
```
Generate a weekly report for last week for project CLID
```

**Output:**
- Key highlights summary displayed first
- Full markdown report displayed in conversation
- Report covering Monday-Sunday of previous week
- All issues with activity during that week
- Team contributions summary
- Individual data files at `/tmp/weekly-{timestamp}/{ISSUE_KEY}.json`
- Report file saved at `/tmp/weekly-{timestamp}/weekly-report.md`

### Example 2: Component-Filtered Report

**Input:**
```
Generate a report for the oc-mirror component from last week's sprint in CLID
```

**Output:**
- Report filtered to oc-mirror component only
- Activity for issues tagged with oc-mirror
- Component-specific metrics

### Example 3: Custom Week with Notes

**Input:**
```
Generate a sprint report for CLID for this week and include notes about the architecture review meeting
```

**Output:**
- Report for current week (Monday-Sunday)
- Includes custom notes section
- Full activity breakdown

## Best Practices

1. **Run reports consistently** - Generate reports on the same day each week (e.g., Monday mornings)
2. **Review data files** - Keep the JSON files for historical analysis
3. **Share the report file** - The markdown file at `/tmp/weekly-{timestamp}/weekly-report.md` can be:
   - Copied to shared drives or wikis
   - Attached to emails
   - Committed to documentation repositories
   - Imported into reporting tools
4. **Use component filters** - For large projects, generate component-specific reports
5. **Add context with notes** - Include standup notes or meeting highlights
6. **Verify date ranges** - Double-check the week offset produces the correct date range
7. **Archive reports** - Save both the markdown report and JSON data files for sprint retrospectives
