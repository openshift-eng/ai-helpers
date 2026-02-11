---
description: Update weekly status summaries for Jira issues with component and user filtering
argument-hint: "[project-key] [--component name] [--label label-name] [user-filters...]"
---

## Name

jira:update-weekly-status

## Synopsis

```
/jira:update-weekly-status [project-key] [--component <component-name>] [--label <label-name>] [user-filters...]
```

## Description

The `jira:update-weekly-status` command automates the process of updating weekly status summaries for Jira issues in a specified project. It analyzes recent activity across tickets, GitHub PRs, and GitLab MRs to draft color-coded status updates (Red/Yellow/Green), then allows you to review and modify them before updating Jira.

This command is particularly useful for:

- Weekly status updates on strategic issues
- Team lead status reporting workflows
- Consistent formatting across status updates
- Reducing manual effort in gathering context from multiple sources

Key capabilities:

- **Efficient batch data gathering** using async Python script
- Interactive component selection from available project components
- User filtering by email or display name (with auto-resolution)
- Intelligent activity analysis using `childIssuesOf()` for full hierarchy traversal
- GitHub PR and GitLab MR integration via external links
- Recent update warnings to prevent duplicate updates
- Batch processing with selective skip options
- Formatted status summaries with color-coded health indicators (Red/Yellow/Green)

This command uses the **Status Analysis Engine** skill for core analysis logic. See `plugins/jira/skills/status-analysis/SKILL.md` for detailed implementation.

[Extended thinking: This command streamlines weekly status update workflows by first gathering all data efficiently using an async Python script, then processing each issue with focused LLM context. This two-phase approach minimizes API calls and ensures consistent, high-quality analysis.]

## Implementation

The command executes in two phases:

### Phase 1: Data Gathering

#### Step 1. Parse Arguments and Determine Target Project

1. **Parse command-line arguments:**
   - Extract project key from first positional argument (e.g., `OCPSTRAT`, `OCPBUGS`)
   - Parse optional `--component <component-name>` parameter
   - Parse optional `--label <label-name>` parameter
   - Parse user filter parameters (space-separated emails or names)
   - User filters support exclusion by prefixing with an exclamation mark (example: !<user@example.com>)

2. **If project key is NOT provided:**
   - Use `mcp__atlassian-mcp__jira_get_all_projects` to list all accessible projects
   - Present projects in a numbered list with keys and names
   - Ask: "Please enter the number of the project you want to update:"
   - Parse response and extract project key

3. **Validate project access:**
   - Use `mcp__atlassian-mcp__jira_search` with JQL: `project = "{project-key}" AND status != Closed`
   - Verify the project exists and is accessible

#### Step 2. Determine Target Component(s)

1. **If `--component` parameter is provided:**
   - Use the component name directly

2. **If `--component` is NOT provided:**
   - Use `mcp__atlassian-mcp__jira_search_fields` with keyword "component" to find the component field ID
   - Use `mcp__atlassian-mcp__jira_search` with JQL: `project = "{project-key}" AND status != Closed` and `fields=components`
   - Extract all unique component names from the search results
   - Present components in a numbered list
   - Ask: "Please enter the number(s) of the component(s) you want to update (space-separated), or press Enter to skip:"
   - If multiple components selected, process each separately

#### Step 3. Resolve User Identifiers

For each user filter parameter:

1. **Check if it's an email** (contains `@`): Use as-is for script parameter

2. **If it's a display name** (doesn't contain `@`):
   - Use `mcp__atlassian-mcp__jira_get_user_profile` with the name as the `user_identifier` parameter
   - Show found user details and ask for confirmation
   - If confirmed, use the email address; if not, ask for email directly

3. **Handle exclusion prefix** (exclamation mark):
   - Strip the prefix before lookup
   - Remember to use `--exclude-assignee` parameter for the script

#### Step 4. Run Data Gatherer Script

Execute the Python data gatherer with the resolved parameters:

```bash
python3 {plugins-dir}/jira/skills/status-analysis/scripts/gather_status_data.py \
  --project {PROJECT-KEY} \
  --component "{COMPONENT-NAME}" \
  --label "{LABEL-NAME}" \
  --assignee {email1} --assignee {email2} \
  --exclude-assignee {excluded-email} \
  --verbose
```

**Script location**: `plugins/jira/skills/status-analysis/scripts/gather_status_data.py`

**Script output**:

- Directory: `.work/weekly-status/{YYYY-MM-DD}/`
- `manifest.json`: Processing config and issue list
- `issues/{ISSUE-KEY}.json`: Per-issue data with descendants and PRs

**Wait for script completion** and verify output exists before proceeding.

#### Step 5. Verify Data Collection

Read the manifest file to confirm successful collection:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data Collection Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issues found: {count}
Descendants: {count}
PRs collected: {count}
Date range: {start} to {end}
Output: .work/weekly-status/{date}/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Phase 2: Issue Processing (Interactive)

Process each issue one at a time, loading fresh context for each.

#### Step 6. Load Required Skill

**This step is mandatory before processing any issues:**

```
Skill(jira:status-analysis)
```

This loads the Status Analysis Engine skill which provides:

- Activity analysis methodology
- R/Y/G status formatting rules
- Health status determination logic

#### Step 7. Process Each Issue

For each issue listed in the manifest:

##### a. Read Pre-Gathered Data

Read the issue's JSON file from `.work/weekly-status/{date}/issues/{ISSUE-KEY}.json`

The file contains:

```json
{
  "issue": {
    "key": "OCPSTRAT-1234",
    "summary": "...",
    "status": "In Progress",
    "assignee": {"email": "...", "name": "..."},
    "current_status_summary": "...",
    "last_status_summary_update": "..."
  },
  "descendants": {
    "total": 15,
    "by_status": {"Closed": 5, "In Progress": 8, "To Do": 2},
    "updated_in_range": [...],
    "completion_pct": 33.3
  },
  "changelog_in_range": [...],
  "comments_in_range": [...],
  "prs": [...]
}
```

##### b. Analyze Activity (using Status Analysis Engine)

Using the pre-gathered data, apply the activity analysis rules from `activity-analysis.md`:

1. **Identify key events** from changelog_in_range:
   - Status transitions
   - Assignee changes
   - Priority changes

2. **Analyze comments** (excluding bots with `is_bot: true`):
   - Look for blockers, risks, achievements
   - Note significant updates

3. **Analyze PR activity**:
   - PRs with `commits_in_range > 0` (active development)
   - PRs with `reviews_in_range > 0` (review activity)
   - Recently merged PRs (`state: MERGED`)
   - Draft PRs awaiting work

4. **Determine health status**:
   - **Green**: Good progress, PRs merged/in review, no blockers
   - **Yellow**: Minor concerns, slow progress, manageable blockers
   - **Red**: Significant blockers, no progress, major risks

##### c. Generate Status Update

Format using `ryg_field` template:

```
* Color Status: {Red, Yellow, Green}
 * Status summary:
     ** Thing 1 that happened since last week
     ** Thing 2 that happened since last week
 * Risks:
     ** Risk 1 (or "None at this time")
```

##### d. Present to User for Review

**If Status Summary was updated within last 24 hours:**

```text
⚠️  WARNING: This issue's Status Summary was last updated X hours ago (on YYYY-MM-DD at HH:MM).

Current Status Summary:
{current-status-text}
```

Ask: "This issue was recently updated. Do you want to skip it? (yes/no/show-proposed)"

**For all issues (or if proceeding after warning):**

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue: {ISSUE-KEY} - {Summary}
Assignee: {Assignee Name}
Current Status: {Current Issue Status}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recent Activity Analysis:
• Descendants: {total} total, {updated_in_range count} updated this week
• Completion: {completion_pct}% ({by_status breakdown})
• PRs: {count} ({merged} merged, {open} open, {draft} drafts)
• Commits in range: {total commits across PRs}
• Reviews in range: {total reviews across PRs}

Current Status Summary:
{existing-status-text-or-"None"}

Proposed Status Update:
{drafted-status-update}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Options:

- `approve` or `a`: Proceed with the proposed update
- `modify` or `m`: Modify the text (prompt for new text)
- `skip` or `s`: Skip this issue and move to next
- `quit` or `q`: Stop processing remaining issues

**If user chooses `modify`:**

- Show the proposed text in an editable format
- Ask: "Please provide your updated status text (maintain the bullet format):"
- Validate format (should start with `* Color Status:`)
- Show modified version and ask for final confirmation

##### e. Update the Issue

Use `mcp__atlassian-mcp__jira_update_issue`:

```json
{
  "issue_key": "{ISSUE-KEY}",
  "fields": {
    "customfield_12320841": "{formatted-status-text}"
  }
}
```

Display confirmation: `✓ Updated {ISSUE-KEY}`

#### Step 8. Summary Report

After processing all issues (or if user quits early):

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Weekly Status Update Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project: {PROJECT-KEY}
Component: {COMPONENT-NAME or "All components"}
Label Filter: {LABEL or "None"}
Date Range: {start} to {end}

Total Issues Found: {total}
Issues Updated: {updated-count}
  • Green: {green-count}
  • Yellow: {yellow-count}
  • Red: {red-count}
Issues Skipped: {skipped-count}
  • Recently updated: {recent-count}
  • User skipped: {user-skip-count}

Updated Issues:
{list-of-updated-issue-keys-with-links}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Data Gatherer Script

The Python script (`gather_status_data.py`) handles efficient batch data collection:

### Features

- **Async HTTP requests** using aiohttp for parallel fetching
- **Jira rate limiting**: 2 concurrent requests, 300ms delays
- **GitHub GraphQL batching**: Up to 30 PRs per request with retry logic
- **Date range filtering**: Only includes activity within the specified period

### Environment Variables

- `JIRA_TOKEN` or `JIRA_PERSONAL_TOKEN`: Jira API bearer token
- `GITHUB_TOKEN` or `gh auth token`: GitHub access token

### Output Structure

```
.work/weekly-status/{YYYY-MM-DD}/
├── manifest.json           # Config and issue list
└── issues/
    ├── OCPSTRAT-1234.json  # Per-issue data
    ├── OCPSTRAT-1235.json
    └── ...
```

### Per-Issue JSON Schema

```json
{
  "issue": {
    "key": "string",
    "summary": "string",
    "status": "string",
    "assignee": {"email": "string", "name": "string"},
    "current_status_summary": "string|null",
    "last_status_summary_update": "string|null"
  },
  "descendants": {
    "total": "number",
    "by_status": {"status_name": "count"},
    "updated_in_range": [
      {"key": "string", "summary": "string", "status": "string", "updated": "string"}
    ],
    "completion_pct": "number"
  },
  "changelog_in_range": [
    {"date": "string", "author": "string", "items": [...]}
  ],
  "comments_in_range": [
    {"author": "string", "date": "string", "body": "string", "is_bot": "boolean"}
  ],
  "prs": [
    {
      "url": "string",
      "number": "number",
      "title": "string",
      "state": "OPEN|CLOSED|MERGED",
      "is_draft": "boolean",
      "review_decision": "string|null",
      "dates": {"created_at": "string", "updated_at": "string", "merged_at": "string|null"},
      "files_changed": {"total": "number", "additions": "number", "deletions": "number"},
      "activity_summary": {
        "commits_in_range": "number",
        "reviews_in_range": "number",
        "review_comments_in_range": "number"
      }
    }
  ]
}
```

## Return Value

- **Updated Issues**: Jira issues with refreshed Status Summary fields
- **Summary Report**: Console output showing update statistics and issue links
- **User Interaction Log**: Clear feedback on each decision point

## Examples

1. **With project, component, and label (recommended)**:

   ```bash
   /jira:update-weekly-status OCPSTRAT --component "Hosted Control Planes" --label "control-plane-work"
   ```

   Output: Runs data gatherer, then processes each issue interactively

2. **Interactive mode (prompts for project and component)**:

   ```bash
   /jira:update-weekly-status
   ```

   Output: Prompts for project selection, then component selection

3. **Specify project, auto-select component**:

   ```bash
   /jira:update-weekly-status OCPSTRAT
   ```

   Output: Prompts for component selection from OCPSTRAT components

4. **With label filter**:

   ```bash
   /jira:update-weekly-status OCPSTRAT --label strategic-work
   ```

   Output: Prompts for component, filters issues with "strategic-work" label

5. **With specific users (by email)**:

   ```bash
   /jira:update-weekly-status OCPBUGS antoni@redhat.com jdoe@redhat.com
   ```

   Output: Only processes issues assigned to Antoni or Jane

6. **With excluded users (by email)**:

   ```bash
   /jira:update-weekly-status OCPSTRAT !manager@redhat.com
   ```

   Output: Processes all issues except those assigned to <manager@redhat.com>

7. **With usernames (requires confirmation)**:

   ```bash
   /jira:update-weekly-status OCPSTRAT "Antoni Segura" "Jane Doe"
   ```

   Output: Looks up users by name, asks for confirmation, then processes their issues

8. **Full example with all options**:

   ```bash
   /jira:update-weekly-status OCPSTRAT --component "Control Plane" --label strategic-work antoni@redhat.com !dave@redhat.com
   ```

   Output: Processes OCPSTRAT issues in "Control Plane" component with "strategic-work" label, assigned to Antoni, excluding Dave

## Arguments

- `project-key` (optional): The Jira project key (e.g., `OCPSTRAT`, `OCPBUGS`). If not provided, prompts for selection
- `--component <name>` (optional): Filter by specific component name. If not provided, prompts for selection
- `--label <label-name>` (optional): Filter by specific label (e.g., `control-plane-work`, `strategic-work`)
- `user-filters` (optional): Space-separated list of user emails or display names
  - Prefix with exclamation mark to exclude specific users (example: !<manager@redhat.com>)
  - Display names without @ symbol will trigger user lookup with confirmation

## Notes

### Important Implementation Details

1. **Two-Phase Execution**:
   - Phase 1 (Data Gathering): Python script collects all data efficiently in parallel
   - Phase 2 (Processing): LLM analyzes each issue with clean context

2. **Efficiency**:
   - Batch data gathering minimizes API calls
   - Pre-filtered data (date range) reduces context size
   - Each issue processed with fresh context for better analysis

3. **User Experience**:
   - Always warn about recently updated issues (last 24 hours)
   - Recommend skipping recently updated issues
   - Allow user to modify status text
   - Provide clear progress indicators for batch processing
   - Show issue links in final summary for easy navigation

4. **Error Handling**:
   - Invalid project key: Display error with available projects
   - Invalid component: Display available components
   - User lookup fails: Ask for email directly
   - Script execution failure: Display error and suggest checking environment variables
   - API errors during update: Display error and continue with next issue

5. **Format Validation**:
   - Validate Status Summary text format before updating
   - Ensure bullet point structure is maintained
   - Check for Color Status line (Red/Yellow/Green)
   - Warn if format doesn't match expected template

### Prerequisites

- **Python 3.8+** with `aiohttp` package installed
- **Jira MCP server** configured and accessible
- **Environment variables**:
  - `JIRA_TOKEN` or `JIRA_PERSONAL_TOKEN`: Jira API bearer token
  - `GITHUB_TOKEN` or authenticated `gh` CLI

Check for required tools:

```bash
# Check Python and aiohttp
python3 -c "import aiohttp; print('aiohttp OK')"

# Check if the Jira token is defined
test -n "$JIRA_TOKEN"

# Check GitHub token (via gh CLI)
gh auth token &> /dev/null
```

Install aiohttp if needed:

```bash
pip install aiohttp
```

### Customization for Different Teams

Teams can customize this command by:

1. Creating project-specific skills with default label filters
2. Defining team-specific Status Summary field mappings (modify `--status-field` parameter)
3. Customizing color status thresholds based on team velocity
4. Adding team-specific keywords for risk/blocker detection

See the Jira plugin's skills directory for examples of project-specific customizations.

## Related

- **Shared skill**: `plugins/jira/skills/status-analysis/SKILL.md`
- **Data gatherer script**: `plugins/jira/skills/status-analysis/scripts/gather_status_data.py`
- **Single-issue rollup**: `/jira:status-rollup` - Generate comprehensive status comment for one issue
