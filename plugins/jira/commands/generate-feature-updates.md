---
description: Generate strategic feature updates for weekly status documents
argument-hint: "[project-key] [--component name] [--label label-name] [user-filters...]"
---

## Name

jira:generate-feature-updates

## Synopsis

```
/jira:generate-feature-updates [project-key] [--component <component-name>] [--label <label-name>] [user-filters...]
```

## Description

The `jira:generate-feature-updates` command generates concise executive-level feature summaries for weekly status documents. It analyzes recent activity across Jira issues and their descendants to produce prose-style updates suitable for the "Key Strategic Feature Updates" section of weekly reports.

This command is particularly useful for:

- Weekly executive status documents
- Strategic feature progress summaries
- Stakeholder communication on feature delivery
- Identifying blocked or at-risk features

Key capabilities:

- **Efficient batch data gathering** using async Python script
- Interactive component selection from available project components
- User filtering by email or display name (with auto-resolution)
- Intelligent activity analysis using `childIssuesOf()` for full hierarchy traversal
- GitHub PR and GitLab MR integration via external links
- Automatic filtering: skips issues with no significant activity
- Batch processing with full-section review
- Nested list output: feature link as top-level bullet, update prose as nested bullet

This command uses the **Status Analysis Engine** skill for core analysis logic. See `plugins/jira/skills/status-analysis/SKILL.md` for detailed implementation.

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
   - Ask: "Please enter the number of the project you want to generate updates for:"
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
   - Ask: "Please enter the number(s) of the component(s) you want to generate updates for (space-separated), or press Enter to skip:"
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

### Phase 2: Processing (Batch)

#### Step 6. Load Required Skill

**This step is mandatory before processing any issues:**

```
Skill(jira:status-analysis)
```

This loads the Status Analysis Engine skill which provides:

- Activity analysis methodology
- Feature markdown formatting rules
- Health status determination logic

#### Step 7. Process ALL Issues (Batch)

Unlike `update-weekly-status` which processes issues one at a time interactively, this command processes all issues in batch and presents a complete section for review.

For each issue listed in the manifest:

##### a. Triage and Summarize Issues

Run the summarize script in batch mode with `--only-significant` to triage and summarize all issues in a single call. If a `--label` filter was used for data gathering, pass it here too to separate issues that don't carry the label:

```bash
python3 {plugins-dir}/jira/skills/status-analysis/scripts/summarize_issue.py \
  .work/weekly-status/{date}/issues/ --only-significant --label {label-name}
```

This combines triage and summarization: it filters to issues with significant activity (PRs merged, status changes, color changes, human comments, descendant updates) and outputs a structured summary for each. PR author names are included in the output (from `commits_in_range` and `reviews_in_range` data) — use these first names for attribution, never GitHub handles.

**Label filtering**: When `--label` is provided, any issues missing that label are listed separately under a `MISSING LABEL` header. Present this list to the user and ask whether to include each one. These are typically descendant features that appeared in the hierarchy but aren't directly tracked under the label.

**IMPORTANT — parallelization**: The batch summarize output can be large. If the output exceeds comfortable context size, split processing across parallel Bash calls or sub-agents. For example, process Yellow/Red issues in one call and Green issues in another. Never loop through issues sequentially with individual script calls.

##### c. Analyze Activity (using Status Analysis Engine)

Using the pre-gathered data, apply the activity analysis rules from `activity-analysis.md`:

1. **Read the existing Status Summary field** (`current_status_summary` in JSON):
   - Parse the R/Y/G color status (Red, Yellow, Green) — this is the team's own self-assessment
   - Check `last_status_summary_update` — if the status was updated within the date range, the team actively reported this week
   - Check `changelog_in_range` for changes to the Status Summary field — a color change (e.g., Green→Yellow, Yellow→Red) is always significant
   - Use the R/Y/G status to **prioritize and order** the output (Red/Yellow features appear before Green), but do not include a feature *solely* because it is Red/Yellow — there must also be a status change or other activity this week

2. **Identify key events** from changelog_in_range:
   - Status transitions
   - Assignee changes
   - Priority/scope changes
   - Status Summary field changes (color transitions)

3. **Analyze comments** (excluding bots with `is_bot: true`):
   - Look for blockers, risks, achievements
   - Note significant updates

4. **Analyze PR activity**:
   - PRs with `commits_in_range > 0` (active development)
   - PRs with `reviews_in_range > 0` (review activity)
   - Recently merged PRs (`state: MERGED`)
   - Draft PRs awaiting work
   - Use `author_name` fields (not `author` logins) when attributing contributions. Always use first names, never GitHub handles.

5. **Determine if significant**: Skip issues with no noteworthy activity (only bot comments, trivial field changes, no PRs merged or opened). A color change in the Status Summary field (e.g., Green→Red) counts as significant activity and should always be included.

##### d. Generate feature_markdown Entry

Before generating entries, check for significant issues that have no Color Status in their Status Summary field. If any are found, list them and ask the user:

```text
The following features have significant activity but no R/Y/G color status set:
  1. ISSUE-KEY: Issue summary
  2. ISSUE-KEY: Issue summary

What color circle should each use? Enter colors (e.g. "1:green 2:yellow"), "all:green" to set all, or "skip" to omit circles:
```

Then, for each issue with significant activity, format as a nested unordered list item with a color circle prefix (🟢🟡🔴) matching the Color Status from the Status Summary field or the user's override (`Green` → 🟢, `Yellow` → 🟡, `Red` → 🔴, no color → omit circle):

```markdown
- 🟢 [ISSUE-KEY](https://issues.redhat.com/browse/ISSUE-KEY): Issue summary
    - 1-3 sentences of executive prose focusing on significant progress, deliveries, blockers, or risks. Attribute contributions to team members by first name (from `author_name` fields, never GitHub logins). Reference PRs and related issues as markdown links.
```

**Content priorities** (in order):
1. Features delivered or completing
2. Features whose status changed to Red or Yellow this week
3. Features with Red/Yellow status and new activity this week
4. Features with significant progress (PRs merged, scope changes)

**Skip** issues where nothing noteworthy happened in the date range.

##### e. Assemble Full Section

Combine all entries into a single unordered list, ordered by significance:

1. Completed/delivered features first
2. Features whose status changed to Red or Yellow this week
3. Red/Yellow features with new activity
4. Features with notable progress

All entries form one continuous markdown unordered list (no blank lines between items).

#### Step 8. Present for Review

Display the complete assembled section:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Key Strategic Feature Updates
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issues analyzed: {total}
Features with significant activity: {included}
Features skipped (no activity): {skipped}
Date range: {start} to {end}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{assembled feature updates section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Before presenting, run the validation script to check for GitHub handle usage:

```bash
python3 {plugins-dir}/jira/skills/status-analysis/scripts/validate_feature_updates.py \
  --markdown /tmp/feature-updates.md \
  --data-dir .work/weekly-status/{date}/issues/
```

If violations are found, fix them (replace handles with first names from `author_name` fields) before presenting to the user.

Options:

- `approve` or `a`: Accept and output
- `modify` or `m`: Modify the section (rewrite entries, skip/reorder features)
- `regenerate` or `r`: Regenerate from cached data with different focus
- `quit` or `q`: Abort

**If user chooses `modify`:**

- Ask what changes they want (rewrite specific entries, remove entries, reorder, change tone)
- Apply changes and present again

#### Step 9. Output Delivery

Default: print the final markdown to stdout.

**Optional output mode** (parsed from original arguments):

- `--serve`: Convert markdown to HTML and serve on localhost for easy copy/paste into Google Docs

##### HTML conversion and serving (`--serve`)

1. Write the final markdown to `/tmp/feature-updates.md`

2. Run the validation script to ensure no GitHub handles remain:

```bash
python3 {plugins-dir}/jira/skills/status-analysis/scripts/validate_feature_updates.py \
  --markdown /tmp/feature-updates.md \
  --data-dir .work/weekly-status/{date}/issues/
```

If violations are found, fix them before converting to HTML.

3. Convert to styled HTML using the Python `markdown` library:

```python
import markdown

with open("/tmp/feature-updates.md") as f:
    html = markdown.markdown(f.read())

with open("/tmp/feature-updates.html", "w", encoding="utf-8") as f:
    f.write("""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; line-height: 1.6; font-size: 11pt; }
a { color: #1a73e8; text-decoration: none; }
a:hover { text-decoration: underline; }
ul { margin-bottom: 0.5em; }
li { margin-bottom: 0.3em; }
</style></head><body>
""")
    f.write(html)
    f.write("</body></html>")
```

4. Validate the generated HTML for encoding issues:

```bash
python3 {plugins-dir}/jira/skills/status-analysis/scripts/validate_feature_updates.py \
  --html /tmp/feature-updates.html
```

If validation fails (missing charset, mojibake detected), regenerate the HTML using the template above before proceeding. **Do not serve HTML that fails this check.**

5. Start a local HTTP server in the background:

```bash
python3 -m http.server 8787 --directory /tmp --bind 127.0.0.1
```

6. Display the URL to the user:

```
Serving feature updates at: http://localhost:8787/feature-updates.html
Open in your browser, select all (Ctrl+A / Cmd+A), copy (Ctrl+C / Cmd+C), and paste into Google Docs.
The server will be stopped when you confirm you're done.
```

7. Wait for user confirmation, then stop the background server.

## Examples

1. **With project and component (recommended)**:

   ```bash
   /jira:generate-feature-updates OCPSTRAT --component "Hosted Control Planes"
   ```

   Output: Gathers data, analyzes all matching issues, presents feature updates section

2. **With label filter**:

   ```bash
   /jira:generate-feature-updates OCPSTRAT --label strategic-work
   ```

3. **With specific users**:

   ```bash
   /jira:generate-feature-updates OCPSTRAT --component "Hosted Control Planes" user@redhat.com
   ```

4. **Serve as HTML for Google Docs pasting**:

   ```bash
   /jira:generate-feature-updates OCPSTRAT --component "Hosted Control Planes" --serve
   ```

5. **Full example with all options**:

   ```bash
   /jira:generate-feature-updates OCPSTRAT --component "Control Plane" --label strategic-work user@redhat.com !manager@redhat.com --serve
   ```

**Example Output:**

```markdown
- 🟢 [OCPSTRAT-2426](https://issues.redhat.com/browse/OCPSTRAT-2426): Customer global pull secret in HCP for ROSA
    - Scope reduced to Managed OpenShift and platforms using node replacement strategy. E2E tests are already passing.
- 🟡 [OCPSTRAT-1409](https://issues.redhat.com/browse/OCPSTRAT-1409): Auto backup/restore for Hosted Clusters
    - A bug found in the implementation has highlighted a permission gap that we are going to cover with better UX.
- 🟢 [OCPSTRAT-1558](https://issues.redhat.com/browse/OCPSTRAT-1558): Shared ingress for HCP
    - Wei's PR #7143 landed this week, completing the core shared ingress controller. Integration tests are passing on AWS.
```

## Arguments

- `project-key` (optional): The Jira project key (e.g., `OCPSTRAT`, `OCPBUGS`). If not provided, prompts for selection
- `--component <name>` (optional): Filter by specific component name. If not provided, prompts for selection
- `--label <label-name>` (optional): Filter by specific label (e.g., `control-plane-work`, `strategic-work`)
- `user-filters` (optional): Space-separated list of user emails or display names
  - Prefix with exclamation mark to exclude specific users (example: !<manager@redhat.com>)
  - Display names without @ symbol will trigger user lookup with confirmation
- `--serve` (optional): Convert output to HTML and serve on localhost for copy/paste into Google Docs

## Notes

### Important Implementation Details

1. **Two-Phase Execution**:
   - Phase 1 (Data Gathering): Python script collects all data efficiently in parallel
   - Phase 2 (Processing): LLM analyzes all issues in batch with feature_markdown format

2. **Batch Processing** (key difference from update-weekly-status):
   - All issues are processed together, not one-by-one interactively
   - Complete section is assembled before presenting for review
   - No per-issue approve/skip workflow

3. **No Jira Writes**:
   - This command only reads from Jira (via pre-gathered data)
   - Output goes to stdout or localhost HTTP server — never back to Jira

4. **Significant Activity Filter**:
   - Issues with no noteworthy activity are automatically skipped
   - Prevents noise from issues that had only bot updates or trivial changes

5. **Error Handling**:
   - Invalid project key: Display error with available projects
   - Invalid component: Display available components
   - User lookup fails: Ask for email directly
   - Script execution failure: Display error and suggest checking environment variables
   - No significant activity found: Display message and exit

### Prerequisites

- **Python 3.8+** with `aiohttp` package installed
- **Jira MCP server** configured and accessible
- **Environment variables**:
  - `JIRA_TOKEN` or `JIRA_PERSONAL_TOKEN`: Jira API bearer token
  - `GITHUB_TOKEN` or authenticated `gh` CLI
- **For `--serve`**: Python `markdown` package (`pip install markdown`)

Check for required tools:

```bash
# Check Python and aiohttp
python3 -c "import aiohttp; print('aiohttp OK')"

# Check if the Jira token is defined
test -n "$JIRA_TOKEN"

# Check GitHub token (via gh CLI)
gh auth token &> /dev/null

# Check markdown library (for --serve)
python3 -c "import markdown; print('markdown OK')"
```

## Related

- **Shared skill**: `plugins/jira/skills/status-analysis/SKILL.md`
- **Data gatherer script**: `plugins/jira/skills/status-analysis/scripts/gather_status_data.py`
- **Validation script**: `plugins/jira/skills/status-analysis/scripts/validate_feature_updates.py`
- **Single-issue rollup**: `/jira:status-rollup` - Generate comprehensive status comment for one issue
- **Batch field updates**: `/jira:update-weekly-status` - Update Status Summary field for multiple issues
