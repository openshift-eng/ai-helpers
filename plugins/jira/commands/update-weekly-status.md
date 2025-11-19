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
- Intelligent activity analysis (comments, child issues, linked PRs/MRs)
- Recent update warnings to prevent duplicate updates
- Batch processing with selective skip options
- Formatted status summaries with color-coded health indicators

[Extended thinking: This command streamlines weekly status update workflows by automating data gathering from Jira, GitHub, and GitLab, then intelligently drafting status summaries that encode team knowledge about how to analyze ticket activity. It ensures consistent formatting while allowing human oversight and refinement.]

## Implementation

The command executes the following workflow:

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
   - Extract project name for display purposes

### 2. Determine Target Component(s)

1. **If `--component` parameter is provided:**
   - Extract the component name from the parameter value
   - Use it directly in the JQL query

2. **If `--component` is NOT provided:**
   - Use `mcp__atlassian-mcp__jira_search_fields` with keyword "component" to find the component field ID
   - Use `mcp__atlassian-mcp__jira_search` with JQL: `project = "{project-key}" AND status != Closed` and `fields=components`
   - Extract all unique component names from the search results
   - Present components in a numbered list:
     ```text
     Available components for {project-key}:
     1. Component Name 1
     2. Component Name 2
     3. Component Name 3
     ...
     ```
   - Ask: "Please enter the number(s) of the component(s) you want to update (space-separated, e.g., '1 3 5'), or press Enter to skip component filtering:"
   - Parse the user's response and map the numbers back to component names
   - If user presses Enter without selection, skip component filtering
   - If multiple components are selected, process each component separately (run steps 3-6 for each component)

### 3. Resolve User Identifiers

For each user filter parameter provided:

1. **Check if it's an email** (contains `@`):
   - Use as-is for JQL query

2. **If it's a display name** (doesn't contain `@`):
   - Use `mcp__atlassian-mcp__jira_get_user_profile` with the name as the `user_identifier` parameter
   - The tool accepts display names, usernames, email addresses, or account IDs
   - When the user profile is returned, show:
     - Display name
     - Email address
     - Account ID
   - Ask for confirmation: "Found user: [Display Name] ([Email]). Is this correct?"
   - If confirmed, use the email address for the JQL query
   - If not confirmed or lookup fails, ask user to provide the email address directly

3. **Handle exclusion prefix** (exclamation mark):
   - Strip the exclamation mark prefix before doing the lookup
   - Remember to apply exclusion logic when building JQL

### 4. Find Status Summary Custom Field

1. **Auto-detect Status Summary field:**
   - Use `mcp__atlassian-mcp__jira_search_fields` with keyword "status summary"
   - Look for fields matching "Status Summary" (case-insensitive)
   - If multiple matches found, present options to user for selection
   - If no matches found, ask user to provide the custom field ID (e.g., `customfield_12320841`)
   - Store the field ID for use in step 6

2. **Validate field access:**
   - Fetch a sample issue with this field to verify it's accessible
   - Confirm the field accepts text input

### 5. Build JQL Query and Find Issues

Build a JQL query based on the determined parameters:

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
- If no user parameters provided: No assignee filter (process all issues)
- If specific users provided (no exclusion prefix): Add `AND assignee IN (email1, email2, ...)`
- If excluded users provided (with exclusion prefix): Add `AND assignee NOT IN (email1, email2, ...)`
- If mixed: Combine appropriately with `AND assignee IN (...) AND assignee NOT IN (...)`

**Final query:**
```jql
ORDER BY rank ASC
```

Use `mcp__atlassian-mcp__jira_search` with this JQL to find all matching issues.

### 6. Process Each Issue

For each issue found, execute the following steps:

#### a. Gather Information Efficiently

**IMPORTANT**: Only fetch the fields you need to save context and API calls:
- Use `fields=summary,status,assignee,issuelinks,comment,{status-summary-field-id}` when getting issue details
- Use `expand=changelog` to get field update history
- Set `comment_limit=20` to limit comment history to recent activity

For each issue:

1. **Check when Status Summary was last updated:**
   - Look in the changelog for the most recent update to the Status Summary field
   - Calculate hours since last update
   - If updated within last 24 hours, flag for warning

2. **Check recent non-automation comments** (last 7 days):
   - Fetch comments with `expand=renderedFields`
   - Filter comments to those created in the last 7 days
   - Exclude automated comments (bot accounts, system updates)
   - Extract key information and blockers from comments

3. **Check child issues updated in last 7 days:**
   - Use JQL: `parent = {ISSUE-KEY} AND updated >= -7d`
   - Fetch child issue summaries and status transitions
   - Note any completed, started, or blocked child issues

4. **Check linked GitHub PRs and GitLab MRs:**
   - First get all child issues: `parent = {ISSUE-KEY}`
   - For each child issue, check the `issuelinks` field for external links
   - Look for issue link types pointing to GitHub PRs or GitLab MRs
   - **For GitHub PRs found:**
     - Extract repo and PR number from URL
     - Use `gh pr view {PR-NUMBER} --repo {REPO} --json state,updatedAt,mergedAt,title` to check activity
     - Check if PRs were updated or merged in the last 7 days
     - Note PR state (open, merged, closed)
   - **For GitLab MRs found:**
     - Note MR URLs for manual checking (GitLab CLI integration is optional)
   - **If no child issues exist:**
     - Check the parent issue's `issuelinks` field directly for PR/MR references

5. **Check current status summary value:**
   - Fetch `fields={status-summary-field-id}` to get existing status text
   - Parse existing color status if present (Red/Yellow/Green)

#### b. Analyze and Draft Update

Based on the gathered information, draft a status update following this template:

```text
* Color Status: {Red, Yellow, Green}
 * Status summary:
     ** Thing 1 that happened since last week
     ** Thing 2 that happened since last week
     ** Thing N that happened since last week
 * Risks:
     ** Risk 1 that might affect delivery
     ** Risk 2 that might affect delivery
```

**Color Status Guidelines:**
- **Green**: On track, good progress, PRs merged or in review, no blockers
- **Yellow**: Minor concerns, some blockers but manageable, slow progress
- **Red**: Significant blockers, no progress, major risks, dependencies blocking work

**Status Summary Guidelines:**
- Be specific: Reference PR numbers, child issue keys, specific accomplishments
- Focus on changes since last week: New PRs, merged changes, completed tasks
- Include context: Why things are blocked, what dependencies are needed
- Avoid vague phrases: Use "PR #123 merged adding feature X" not "ongoing work"

**Risks Section Guidelines:**
- Only include if there are actual risks
- Be specific about what might go wrong
- Include dependencies, blockers, resource constraints
- If no risks, you can omit this section or use "** None at this time"

#### c. Present to User for Review

Before updating, check if the Status Summary was updated in the last 24 hours:

**If updated within last 24 hours:**
- Show a warning:
  ```text
  ⚠️  WARNING: This issue's Status Summary was last updated X hours ago (on YYYY-MM-DD at HH:MM).

  Current Status Summary:
  {current-status-text}
  ```
- Ask: "This issue was recently updated. Do you want to skip it? (yes/no/show-proposed)"
  - `yes` or `skip`: Move to next issue
  - `no` or `continue`: Proceed with showing proposed update
  - `show-proposed`: Show the proposed update and ask again

**For all issues (or if proceeding after warning):**

Show the user:
```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue: {ISSUE-KEY} - {Summary}
Assignee: {Assignee Name}
Current Status: {Current Issue Status}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recent Activity Analysis:
• Comments: {count} new comments in last 7 days
• Child Issues: {count} updated in last 7 days ({X} completed, {Y} in progress)
• GitHub PRs: {count} active ({X} merged, {Y} open)
• GitLab MRs: {count} active

Current Status Summary:
{existing-status-text-or-"None"}

Proposed Status Update:
{drafted-status-update}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Ask the user to choose:
- `approve` or `a`: Proceed with the proposed update
- `modify` or `m`: Modify the text (prompt for new text)
- `skip` or `s`: Skip this issue and move to next
- `quit` or `q`: Stop processing remaining issues

**If user chooses `modify`:**
- Show the proposed text in an editable format
- Ask: "Please provide your updated status text (maintain the bullet format):"
- Accept multi-line input
- Validate format (should start with `* Color Status:`)
- Show the modified version and ask for final confirmation

#### d. Update the Issue

Once approved, use `mcp__atlassian-mcp__jira_update_issue` with:
```json
{
  "issue_key": "{ISSUE-KEY}",
  "fields": {
    "{status-summary-field-id}": "{formatted-status-text}"
  }
}
```

**IMPORTANT**: The Status Summary field requires exact formatting with bullet points as shown in the template above.

After successful update:
- Display confirmation: `✓ Updated {ISSUE-KEY}`
- Continue to next issue

### 7. Summary Report

After processing all issues (or if user quits early), provide a summary:

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

**Example Output:**
```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue: OCPSTRAT-1234 - Implement API authentication
Assignee: Antoni Segura
Current Status: In Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recent Activity Analysis:
• Comments: 3 new comments in last 7 days
• Child Issues: 2 updated in last 7 days (1 completed, 1 in progress)
• GitHub PRs: 2 active (1 merged, 1 open)

Current Status Summary:
None

Proposed Status Update:
* Color Status: Green
 * Status summary:
     ** PR #456 merged adding OAuth2 token validation with comprehensive unit tests
     ** AUTH-102 completed: token refresh mechanism implemented
     ** AUTH-103 in progress: session handling refactor, draft PR submitted for review
 * Risks:
     ** None at this time

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Choose: [a]pprove, [m]odify, [s]kip, [q]uit: a

✓ Updated OCPSTRAT-1234

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Weekly Status Update Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project: OCPSTRAT
Component: Control Plane
Label Filter: strategic-work

Total Issues Found: 5
Issues Updated: 4
  • Green: 3
  • Yellow: 1
  • Red: 0
Issues Skipped: 1
  • Recently updated: 1
  • User skipped: 0

Updated Issues:
• OCPSTRAT-1234: https://issues.redhat.com/browse/OCPSTRAT-1234
• OCPSTRAT-1235: https://issues.redhat.com/browse/OCPSTRAT-1235
• OCPSTRAT-1236: https://issues.redhat.com/browse/OCPSTRAT-1236
• OCPSTRAT-1237: https://issues.redhat.com/browse/OCPSTRAT-1237

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

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
   - Look for PRs in child issues, not just parent issues

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
