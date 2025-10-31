# Report Writer Plugin

Generate comprehensive weekly team activity reports from Jira data with automated sprint discovery, issue tracking, and activity analysis.

## Overview

The Report Writer plugin provides the `/report-writer:weekly` command that systematically collects and analyzes Jira data to produce detailed team activity reports. It automatically discovers sprints, fetches complete issue data with changelogs, filters by activity within the reporting window, and generates structured markdown reports.

## Features

- ✅ **Accurate Week Calculation** - Uses Monday-Sunday format with configurable week offsets
- ✅ **Activity Filtering** - Only includes issues with activity during the target week
- ✅ **Complete Data Collection** - Fetches full issue history including changelogs and comments
- ✅ **Component Filtering** - Generate reports for specific components within a project
- ✅ **Reliable Data Processing** - Direct file saving with built-in verification
- ✅ **Batch Processing** - Efficient parallel fetching with configurable batch size (1-10)
- ✅ **Verification Steps** - Validates data completeness before report generation
- ✅ **Markdown Export** - Saves complete report as shareable markdown file

## Prerequisites

- Claude Code installed
- Jira MCP server configured and running
- jq (for JSON verification)

## Setup

### Option 1: Using npx (Recommended for Atlassian Cloud)

```bash
# Add the Atlassian MCP server
claude mcp add atlassian npx @modelcontextprotocol/server-atlassian
```

Configure your Jira credentials according to the [Atlassian MCP documentation](https://github.com/modelcontextprotocol/servers/tree/main/src/atlassian).

**Required tokens:**
- **JIRA API TOKEN**: Generate at [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

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
```

**Required tokens:**
- **JIRA PERSONAL TOKEN**: Generate at your Jira profile settings

## Usage

```
/report-writer:weekly --project <PROJECT> [OPTIONS]
```

**Required**: `--project` - Jira project key (e.g., CLID)

**Optional parameters**: See Parameters section below for full list.

For detailed examples, see the [Examples](#examples) section.

## Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `--project` | Project key (REQUIRED) | None | `CLID` |
| `--component` | Component filter (optional) | None | `oc-mirror` |
| `--week-offset` | Weeks back from current week | `-1` | `0` (this week), `-1` (last week), `-2` (two weeks ago) |
| `--batch-size` | Issues to fetch in parallel | `5` | `1` (slow/rate limited), `10` (fast) |
| `--notes` | Manual notes to include | None | Custom text |
| `--slack-file` | Path to Slack standup file | None | `/path/to/standup.txt` |

## Output Format

### Working Directory

All generated files are saved to `/tmp/weekly-{timestamp}/`:

- **Issue data files**: `{ISSUE_KEY}.json` - One file per issue with complete data
- **Report file**: `weekly-report.md` - Final markdown report

### Report Structure

The generated report includes:

1. **Header** - Project, sprint, date range, component filter (if applicable)
2. **Summary Metrics** - Total issues, issues with activity, breakdown by type
3. **Issues with Activity** - Grouped by activity type (closed, status changed, commented, etc.)
4. **Team Contributions** - Activity summary per team member
5. **PR Activity** - PRs created, updated, or merged during the week
6. **Additional Notes** - Content from `--notes` or `--slack-file`

### Example Output

```
════════════════════════════════════════════════════════════
REPORT GENERATION COMPLETE
════════════════════════════════════════════════════════════
📁 Working Directory: /tmp/weekly-20251029-143022/

📊 Data Files:
   - Issue Files: 15/15
   - Total Size: 127 KB

📄 Report File:
   - Location: /tmp/weekly-20251029-143022/weekly-report.md
   - Format: Markdown
   - Status: ✓ Saved successfully
════════════════════════════════════════════════════════════
```

## How It Works

### Week Calculation

Reports use **Monday-Sunday** week format:

- **week-offset = -1** (default): Previous Monday-Sunday
- **week-offset = 0**: Current Monday-Sunday
- **week-offset = -2**: Two weeks ago

**Example:** If today is Thursday, Oct 30, 2025:
- Current week: Monday Oct 27 - Sunday Nov 2
- Last week (offset -1): Monday Oct 20 - Sunday Oct 26

### Activity Filtering

Reports **only include issues with activity during the target week**:

- Status transitions (from changelog timestamps)
- Field changes (assignee, priority, labels, etc.)
- Comments added
- PR activity
- Sprint assignments

### Data Collection Process

1. **Discover Board & Sprint** - Find the appropriate Jira board and sprint
2. **Get Issue Keys** - Retrieve all issues in the sprint (with optional component filter)
3. **Fetch Complete Data** - Fetch issue data via MCP tools and save to individual JSON files
4. **Verify Data** - Validate all files exist and contain complete data (using jq)
5. **Generate Report** - Analyze activity and create markdown report

## Troubleshooting

### No boards found for project

**Solution:** Verify that:
- Your project has an agile board configured in Jira
- You have permissions to access the board
- The project key is correct

### Sprint not found for date range

**Solution:**
- Check if your team uses sprints in Jira
- Try a different week offset
- Confirm sprint dates in Jira

### API rate limiting

**Solution:**
- Use a smaller batch size: `--batch-size 1` or `--batch-size 2`
- Contact your Jira administrator if limits are too restrictive

### Empty report

**Solution:**
- Verify the week offset is correct
- Check if there was actual activity in Jira during that week
- Ensure component filter isn't too restrictive

## Advanced Usage

### Implementation Details

For detailed implementation steps, see [skills/weekly-report/SKILL.md](skills/weekly-report/SKILL.md).

The command fetches issue data via the Jira MCP server, saves individual JSON files for each issue, and verifies data completeness before generating the report.

## Examples

### Example 1: Basic Weekly Report

```
/report-writer:weekly --project CLID
```

Generates last week's report (previous Monday-Sunday) for all CLID issues.

### Example 2: Component-Filtered Report

```
/report-writer:weekly --project CLID --component oc-mirror
```

Generates last week's report filtered to the oc-mirror component only.

### Example 3: Current Week Report

```
/report-writer:weekly --project CLID --week-offset 0
```

Generates report for the current week (this Monday-Sunday).

### Example 4: Two Weeks Ago

```
/report-writer:weekly --project CLID --week-offset -2
```

Generates report from two weeks ago.

### Example 5: Custom Batch Size for Fast Networks

```
/report-writer:weekly --project CLID --batch-size 10
```

Fetches 10 issues in parallel for faster execution on good network connections.

### Example 6: Rate-Limited Environment

```
/report-writer:weekly --project CLID --batch-size 2
```

Reduces parallel fetching to avoid hitting API rate limits.

## Best Practices

1. **Run reports consistently** - Generate reports on the same day each week
2. **Archive reports** - Save the markdown file and JSON data for retrospectives
3. **Use component filters** - For large projects, generate component-specific reports
4. **Adjust batch size** - Balance performance with API rate limits
5. **Verify date ranges** - Double-check the week offset produces the correct range

## License

See repository LICENSE file.
