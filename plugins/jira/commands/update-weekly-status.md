---
description: Update weekly status summaries for Jira issues with component and user filtering
argument-hint: [project-key] [--component name] [--label label-name] [user-filters...]
---

## Name
jira:update-weekly-status

## Synopsis
```bash
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
- Interactive component selection from available project components
- User filtering by email or display name (with auto-resolution)
- Intelligent activity analysis using `childIssuesOf()` for full hierarchy traversal
- GitHub PR and GitLab MR integration via external links
- Recent update warnings to prevent duplicate updates
- Batch processing with selective skip options
- Formatted status summaries with color-coded health indicators (Red/Yellow/Green)

This command uses the **Status Analysis Engine** skill for core analysis logic. See `plugins/jira/skills/status-analysis/SKILL.md` for detailed implementation.

**IMPORTANT - Skill Loading Requirement:**
Before processing any issues, you MUST invoke `Skill(jira:status-analysis)` to load the Status Analysis Engine skill. This ensures proper use of `childIssuesOf()` for hierarchy traversal and consistent analysis methodology. Do NOT rely on conversation summaries or memory - always load the skill explicitly at the start of execution.

[Extended thinking: This command streamlines weekly status update workflows by automating data gathering from Jira, GitHub, and GitLab, then intelligently drafting status summaries that encode team knowledge about how to analyze ticket activity. It ensures consistent formatting while allowing human oversight and refinement.]

## Implementation

The command executes the following workflow:

### 0. Load Required Skills (MANDATORY)

**This step is non-negotiable and must be performed first:**

```
Skill(jira:status-analysis)
```

This loads the Status Analysis Engine skill which provides:
- Proper `childIssuesOf()` usage for hierarchy traversal
- Activity analysis methodology
- External links processing (GitHub PRs, GitLab MRs)
- R/Y/G status formatting rules

**Do NOT skip this step even in continued sessions.** Session summaries do not preserve skill context.

### 1. Parse Arguments and Determine Target Project

1. **Parse command-line arguments:**
   - Extract project key from first positional argument (e.g., `OCPSTRAT`, `OCPBUGS`)
   - Parse optional `--component <component-name>` parameter
   - Parse optional `--label <label-name>` parameter
   - Parse user filter parameters (space-separated emails or names)
   - User filters support exclusion by prefixing with an exclamation mark (example: !user@example.com)

2. **If project key is NOT provided:**
   - Use `mcp__atlassian-mcp__jira_get_all_projects` to list all accessible projects
   - Present projects in a numbered list with keys and names
   - Ask: "Please enter the number of the project you want to update:"
   - Parse response and extract project key

3. **Validate project access:**
   - Use `mcp__atlassian-mcp__jira_search` with JQL: `project = "{project-key}" AND status != Closed`
   - Verify the project exists and is accessible

### 2. Determine Target Component(s)

1. **If `--component` parameter is provided:**
   - Use the component name directly in the JQL query

2. **If `--component` is NOT provided:**
   - Use `mcp__atlassian-mcp__jira_search_fields` with keyword "component" to find the component field ID
   - Use `mcp__atlassian-mcp__jira_search` with JQL: `project = "{project-key}" AND status != Closed` and `fields=components`
   - Extract all unique component names from the search results
   - Present components in a numbered list
   - Ask: "Please enter the number(s) of the component(s) you want to update (space-separated), or press Enter to skip:"
   - If multiple components selected, process each separately

### 3. Resolve User Identifiers

For each user filter parameter:

1. **Check if it's an email** (contains `@`): Use as-is for JQL query

2. **If it's a display name** (doesn't contain `@`):
   - Use `mcp__atlassian-mcp__jira_get_user_profile` with the name as the `user_identifier` parameter
   - Show found user details and ask for confirmation
   - If confirmed, use the email address for JQL; if not, ask for email directly

3. **Handle exclusion prefix** (exclamation mark):
   - Strip the prefix before lookup
   - Remember to apply exclusion logic when building JQL

### 4. Find Status Summary Custom Field

1. **Auto-detect Status Summary field:**
   - Use `mcp__atlassian-mcp__jira_search_fields` with keyword "status summary"
   - Look for fields matching "Status Summary" (case-insensitive)
   - If multiple matches, present options for selection
   - If no matches, ask user to provide the custom field ID (e.g., `customfield_12320841`)

2. **Validate field access:**
   - Fetch a sample issue with this field to verify it's accessible

### 5. Build JQL Query and Find Issues

**Base query:**
```jql
project = "{PROJECT-KEY}" AND
status != Closed AND
status != "Release Pending"
```

**Add optional filters:**
- If `--component` provided or selected: Add `AND component = "<COMPONENT-NAME>"`
- If `--label` provided: Add `AND labels = "<LABEL-NAME>"`

**Add user filters:**
- If specific users provided (no exclusion prefix): Add `AND assignee IN (email1, email2, ...)`
- If excluded users provided (with exclusion prefix): Add `AND assignee NOT IN (email1, email2, ...)`

**Final query:** `ORDER BY rank ASC`

Use `mcp__atlassian-mcp__jira_search` to find all matching issues.

### 6. Process Each Issue

For each root issue found, execute the Status Analysis Engine:

#### a. Initialize Analysis Configuration

```json
{
  "root_issues": ["{issue-key}"],
  "date_range": {
    "start": "{today - 7 days}",
    "end": "{today}"
  },
  "output_format": "ryg_field",
  "output_target": "field",
  "external_links_enabled": true,
  "cache_to_file": false
}
```

#### b. Execute Status Analysis Engine

Follow the skill documentation in `plugins/jira/skills/status-analysis/`:

1. **Data Collection** (`data-collection.md`):
   - Fetch root issue with `fields=summary,status,assignee,issuelinks,comment,{status-summary-field-id}`
   - Use `expand=changelog` to get field update history
   - Set `comment_limit=20` to limit comment history
   - Discover descendants via JQL: `issue in childIssuesOf({issue-key})`
   - Check when Status Summary was last updated (for recent update warning)

2. **Activity Analysis** (`activity-analysis.md`):
   - Filter changelog and comments to last 7 days
   - Exclude automated comments (bot accounts, system updates)
   - Identify status transitions, blockers, risks, achievements
   - Determine health status (Green/Yellow/Red)

3. **External Links** (`external-links.md`):
   - Extract GitHub PRs from root and descendant issue links
   - Use `gh pr view {PR-NUMBER} --repo {REPO} --json state,updatedAt,mergedAt,title`
   - Track PRs merged/updated in last 7 days
   - Note GitLab MR URLs for manual checking

4. **Formatting** (`formatting.md`):
   - Generate R/Y/G template using `ryg_field` format:
     ```
     * Color Status: {Red, Yellow, Green}
      * Status summary:
          ** Thing 1 that happened since last week
          ** Thing 2 that happened since last week
      * Risks:
          ** Risk 1 (or "None at this time")
     ```

#### c. Present to User for Review

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
• Comments: {count} new comments in last 7 days
• Descendants: {count} updated in last 7 days ({X} completed, {Y} in progress)
• GitHub PRs: {count} active ({X} merged, {Y} open)
• GitLab MRs: {count} active

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

#### d. Update the Issue

Use `mcp__atlassian-mcp__jira_update_issue`:
```json
{
  "issue_key": "{ISSUE-KEY}",
  "fields": {
    "{status-summary-field-id}": "{formatted-status-text}"
  }
}
```

Display confirmation: `✓ Updated {ISSUE-KEY}`

### 7. Summary Report

After processing all issues (or if user quits early):

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Weekly Status Update Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project: {PROJECT-KEY}
Component: {COMPONENT-NAME or "All components"}
Label Filter: {LABEL or "None"}

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

## Return Value
- **Updated Issues**: Jira issues with refreshed Status Summary fields
- **Summary Report**: Console output showing update statistics and issue links
- **User Interaction Log**: Clear feedback on each decision point

## Examples

1. **Interactive mode (prompts for project and component)**:
   ```bash
   /jira:update-weekly-status
   ```
   Output: Prompts for project selection, then component selection, processes all matching issues

2. **Specify project, auto-select component**:
   ```bash
   /jira:update-weekly-status OCPSTRAT
   ```
   Output: Prompts for component selection from OCPSTRAT components

3. **Specify project and component**:
   ```bash
   /jira:update-weekly-status OCPSTRAT --component "Control Plane"
   ```
   Output: Processes all OCPSTRAT issues in "Control Plane" component

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
   Output: Processes all issues except those assigned to manager@redhat.com

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

9. **Multiple components**:
   ```bash
   /jira:update-weekly-status OCPBUGS
   ```
   Then select: `1 3 5` when prompted for components
   Output: Processes each selected component separately

## Arguments
- `project-key` (optional): The Jira project key (e.g., `OCPSTRAT`, `OCPBUGS`). If not provided, prompts for selection
- `--component <name>` (optional): Filter by specific component name. If not provided, prompts for selection
- `--label <label-name>` (optional): Filter by specific label (e.g., `strategic-work`, `technical-debt`)
- `user-filters` (optional): Space-separated list of user emails or display names
  - Prefix with exclamation mark to exclude specific users (example: !manager@redhat.com)
  - Can mix inclusion and exclusion (example: user1@redhat.com !user2@redhat.com)
  - Display names without @ symbol will trigger user lookup with confirmation

## Notes

### Important Implementation Details

1. **Efficiency**:
   - Don't fetch all fields (`*all`) - only get what you need
   - Always use `expand=changelog` to get update history
   - Use `comment_limit=20` to limit API response size
   - Batch API calls where possible

2. **User Experience**:
   - Always warn about recently updated issues (last 24 hours)
   - Recommend skipping recently updated issues
   - Allow user to modify status text
   - Provide clear progress indicators for batch processing
   - Show issue links in final summary for easy navigation

3. **GitHub Integration**:
   - Detect GitHub repo from issue links (don't hardcode)
   - Use `gh` CLI for PR information (check if installed first)
   - Handle cases where `gh` is not available gracefully
   - Look for PRs in descendant issues, not just root issues

4. **GitLab Integration**:
   - GitLab CLI (`glab`) integration is optional
   - If not available, note GitLab MR URLs for manual checking
   - Future enhancement: add `glab` support similar to `gh`

5. **Error Handling**:
   - Invalid project key: Display error with available projects
   - Invalid component: Display available components
   - User lookup fails: Ask for email directly
   - No Status Summary field: Ask user to provide custom field ID
   - API errors: Display clear error messages and continue with next issue

6. **Format Validation**:
   - Validate Status Summary text format before updating
   - Ensure bullet point structure is maintained
   - Check for Color Status line (Red/Yellow/Green)
   - Warn if format doesn't match expected template

### Prerequisites

- **Jira MCP server** configured and accessible
- **GitHub CLI** (`gh`) installed and authenticated (optional but recommended)
- **GitLab CLI** (`glab`) installed and authenticated (optional)
- **Jira permissions** to update Status Summary field

Check for required tools:
```bash
# Check for gh CLI
which gh && gh auth status

# Check for glab CLI (optional)
which glab && glab auth status
```

If `gh` is not installed:
- macOS: `brew install gh`
- Linux: See <https://github.com/cli/cli/blob/trunk/docs/install_linux.md>
- Authenticate: `gh auth login`

### Customization for Different Teams

Teams can customize this command by:
1. Creating project-specific skills with default label filters
2. Defining team-specific Status Summary field mappings
3. Customizing color status thresholds based on team velocity
4. Adding team-specific keywords for risk/blocker detection

See the Jira plugin's skills directory for examples of project-specific customizations.

## Related

- **Shared skill**: `plugins/jira/skills/status-analysis/SKILL.md`
- **Single-issue rollup**: `/jira:status-rollup` - Generate comprehensive status comment for one issue
