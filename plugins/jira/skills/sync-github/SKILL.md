---
name: JIRA-GitHub Issue Sync
description: Synchronize issues between JIRA and GitHub with bidirectional support and content sanitization
---

# JIRA-GitHub Issue Sync

This skill provides detailed implementation guidance for synchronizing issues between JIRA and GitHub. It handles bidirectional sync with appropriate content transformation for each direction.

**IMPORTANT FOR AI**: This is a **procedural skill** - when invoked, you should directly execute the implementation steps defined in this document. Follow the step-by-step instructions below, making MCP tool calls and using AskUserQuestion as specified.

**CRITICAL**: Do NOT proactively check prerequisites or validate access before starting Phase 1. Begin immediately with Step 1.1 (prompting the user for JIRA source). Prerequisites are only checked when an operation fails - see Error Handling section for recovery steps.

## When to Use This Skill

Use this skill when you need to:
- Sync issues from a JIRA project or epic to a GitHub repository
- Import GitHub issues into JIRA for internal tracking
- Update JIRA status based on linked GitHub issue state
- Maintain consistency between internal and public issue trackers

**Key Characteristics:**
- **Bidirectional**: Supports JIRA→GitHub and GitHub→JIRA sync
- **Incremental**: Optionally filter to only issues changed after a specific date
- **Sanitized**: Strips company-specific info from JIRA→GitHub sync
- **Professional**: Cleans up formatting for GitHub→JIRA sync
- **Interactive**: Confirms each sync operation with preview
- **Linked**: Adds JIRA remote links to track GitHub issues
- **Stateful**: Remembers ignored issues and learned preferences across sessions

## State Management

This skill maintains persistent state across sessions to remember user preferences and previously ignored issues.

### State File Location

The state file is stored at the configured work directory path. The default is `.work/jira/sync-github/state.json`.

### State Schema (v1.0)

```json
{
  "schema_version": "1.0",
  "last_updated": "2025-12-11T10:30:00Z",
  "ignored_issues": {
    "jira_to_github": {"PROJ-101": {"ignored_at": "...", "reason": "user_skip", "summary": "..."}},
    "github_to_jira": {"openshift/hypershift#42": {"ignored_at": "...", "reason": "user_skip", "summary": "..."}}
  },
  "sync_history": {
    "jira_to_github": [{"jira_key": "PROJ-100", "github_url": "...", "synced_at": "..."}],
    "github_to_jira": [{"github_number": 50, "github_repo": "...", "jira_key": "PROJ-102", "synced_at": "..."}]
  },
  "preferences": {
    "recent_projects": ["OCPMCP", "HOSTEDCP"],
    "recent_epics": ["OCPMCP-33"],
    "recent_repos": ["openshift/hypershift"],
    "project_repo_associations": {"OCPMCP": ["openshift/openshift-mcp-server"]},
    "label_mappings": {"openshift/hypershift": {"jira_to_github": {...}, "github_to_jira": {...}}},
    "component_mappings": {"OCPMCP": {"github_to_jira": {...}}}
  }
}
```

### State Operations

Load state at start (create empty if not exists), save after each operation, merge ignored issues and preferences with existing data.

## Implementation

### Phase 1: Source Selection

#### Step 1.1: Determine JIRA Source

If `--project` or `--epic` argument provided, use it. Otherwise, prompt user:

```
AskUserQuestion: "What would you like to sync from JIRA?" (header: "Source")
Options: "Project..." | "Epic..."
```

Handle custom responses (e.g., "project MYPROJECT", "MYPROJECT-123") by auto-detecting type.

If key not provided, prompt with options from `state.preferences.recent_projects` or `recent_epics`. After selection, update preferences (add to front, dedupe, keep 5 most recent).

#### Step 1.2: Determine GitHub Repository

If `--repo` argument provided, use it. Otherwise:

```
Use AskUserQuestion:
  question: "Which GitHub repository should sync with {project_key}?"
  header: "Repository"
  multiSelect: false
  options: (populated from state.preferences.project_repo_associations[project] first, then recent_repos)
```

Parse response to extract `org/repo`. Update `recent_repos` and `project_repo_associations` in state.

#### Step 1.3: Determine Date Filter (Optional)

If `--since` argument provided, parse it. Otherwise, check issue count with `gh issue list --repo {org}/{repo} --state all --limit 1 --json totalCount`.

**If count > 50 issues**, prompt:

```
Use AskUserQuestion:
  question: "This repository has many issues ({count}). Apply a date filter?"
  header: "Date Filter"
  multiSelect: false
  options:
    - label: "Last 30 days" (description: "Recommended")
    - label: "Last 90 days"
    - label: "Last 7 days"
    - label: "No filter (sync all)" (description: "Warning: Many items")
```

**Supported formats:** `YYYY-MM-DD`, `last-week`, `last-month`, `Nd` (e.g., `7d`, `30d`). Store as `since_date`.

#### Step 1.4: Validate Access

**JIRA:** Call `mcp__atlassian__jira_search` (project) or `mcp__atlassian__jira_get_issue` (epic) with minimal fields.

**GitHub:** Run `gh repo view {org}/{repo} --json name`

If JIRA fails, show Atlassian MCP setup (see Error Handling). If gh fails, show gh CLI setup (see Error Handling).

### Phase 2: Data Collection and State Loading

#### Step 2.1: Determine Work Directory

**This must happen BEFORE loading state or fetching data.**

First, check the user's CLAUDE.md (or Claude memory) for a configured work directory:
- Look for pattern: `jira:sync-github work directory: {path}`

**If not found, prompt the user:**

```
Use AskUserQuestion:
  question: "Where should sync-github store its state and reports?"
  header: "Work Dir"
  multiSelect: false
  options:
    - label: "~/.github-jira-sync" (description: "Persists across repos, recommended")
    - label: ".work/jira/sync-github" (description: "Project-local directory")
```

After the user selects (or provides a custom path via "Other"):

1. **Create the directory** if it doesn't exist: `mkdir -p {work_directory}`
2. **Tell the user how to persist this choice** by displaying:

```
To remember this location for future sessions, run `/memory` and add:
  jira:sync-github work directory: {selected_path}
```

Store the resolved path as `work_directory` for use throughout the session.

#### Step 2.2: Load Existing State

Load from `{work_directory}/state.json` or initialize empty state. Inform user of loaded ignored count and preferences.

#### Step 2.3: Check for --include-ignored Flag

Set `include_ignored = true` if provided (inform user), otherwise `false` (filter ignored issues from prompts).

#### Step 2.4: Fetch JIRA Issues

**JQL query:**
- Project: `project = {project_key} AND issuetype in (Story, Task, Bug, Epic)`
- Epic: `issue in childIssuesOf({epic_key})` (also fetch the epic itself)

If `since_date` set, append: `AND (created >= "{since_date}" OR updated >= "{since_date}" OR resolutiondate >= "{since_date}")`

Call `mcp__atlassian__jira_search` with fields: `key,summary,description,status,issuetype,components,labels`. For epic source, also call `mcp__atlassian__jira_get_issue` to get the epic itself.

#### Step 2.5: Extract Existing JIRA→GitHub Links

For each JIRA issue, fetch with `expand: "changelog"` and examine `changelog.histories[].items[]` where `field == "RemoteIssueLink"`. Extract GitHub issue URLs matching `https://github.com/{org}/{repo}/issues/{number}`. Store for matching in Phase 3.

#### Step 2.6: Fetch GitHub Issues

```bash
gh issue list --repo {org}/{repo} --state all --limit 500 \
  --json number,title,body,state,labels,createdAt,updatedAt,closedAt,url
```

If `since_date` set, add `--search "updated:>={since_date}"` or filter results post-fetch by `createdAt`, `updatedAt`, or `closedAt`.

#### Step 2.7: Cache Data

Save fetched data to `{work_directory}/{timestamp}/`: `jira-issues.json`, `github-issues.json`, `existing-links.json`. Allows fast iteration without re-fetching.

### Phase 3: Semantic Matching

#### Step 3.1: Build Issue Match Candidates

Compare each JIRA issue against GitHub issues. **Matching criteria (priority order):**
1. **Existing remote link** (score: 100) - JIRA has remote link to GitHub issue URL
2. **JIRA key in GitHub** (score: 50) - Key appears in GitHub title/body
3. **Title similarity** (score: 30) - 3+ common significant words between JIRA summary and GitHub title
4. **Body similarity** (score: 20) - 5+ common significant words between JIRA description and GitHub body

Match if score >= 50.

#### Step 3.2: Categorize Issues

Based on matching results, categorize:

- **MATCHED**: Issues in both systems (track JIRA keys ↔ GitHub numbers)
- **JIRA-ONLY**: JIRA issues with no GitHub match → candidates for sync TO GitHub (filter ignored unless `include_ignored`)
- **GITHUB-ONLY**: Open GitHub issues with no JIRA match → candidates for sync TO JIRA (filter ignored; skip closed issues)
- **STATUS-SYNC-NEEDED**: Matched issues where GitHub is closed but JIRA status not in (Done, Closed, Resolved)

### Phase 4: Sync Execution

User selection with immediate execution for each sync direction.

#### Step 4.1: Display Summary

```
Sync Analysis Complete{" (changes since {since_date})" if since_date}:
━━━━━━━━━━━━━━━━━━━━━━━
- Matched: {count} issues
- JIRA-only: {count} (can sync to GitHub)
- GitHub-only: {count} open issues (can sync to JIRA)
- Status updates needed: {count}
- Previously ignored: {count} hidden (use --include-ignored to show)
```

---

#### Step 4.2: JIRA → GitHub Sync

Handles **JIRA-ONLY** issues.

##### 4.2.1: Select JIRA Issues

```
Use AskUserQuestion:
  question: "Select JIRA issues to create in GitHub:"
  header: "JIRA→GitHub"
  multiSelect: true
  options: (label=JIRA key, description=summary truncated to 50 chars)
    - For >4 issues, batch into multiple rounds of 4
    - Include "[Skip all]" option
```

Track unselected issues in `state.ignored_issues.jira_to_github` for future filtering.

##### 4.2.2: Create GitHub Issues

For each selected JIRA issue:

**Sanitize content:**
- Remove internal URLs (`.redhat.com`, `.corp.`, `internal`, `wiki.`, `confluence.`) → `[internal link removed]`
- Remove emails → `[email removed]`
- Redact credentials (`token:`, `Bearer`, `password=`) → `[REDACTED]`
- Convert JIRA formatting (`{code}`, `{noformat}`) to Markdown backticks
- Do NOT include source JIRA key in GitHub issue

**Map components to labels:** If no obvious match, prompt:

```
Use AskUserQuestion:
  question: "Map JIRA component '{component_name}' to which GitHub label?"
  header: "Label"
  multiSelect: false
  options: (available GitHub labels, up to 4)
```

**Preview and confirm** sanitized content before creating. Create with `gh issue create`. Add comment in JIRA linking to new GitHub issue.

##### 4.2.3: Report Results

Display: `✓ PROJ-101 → #89` or `✗ PROJ-103 → Failed: {reason}`

---

#### Step 4.3: GitHub → JIRA Sync

Handles **GITHUB-ONLY** open issues (skip closed).

##### 4.3.1: Select GitHub Issues

```
Use AskUserQuestion:
  question: "Select GitHub issues to create in JIRA:"
  header: "GitHub→JIRA"
  multiSelect: true
  options: (label="#{number}", description=title truncated to 50 chars)
    - For >4 issues, batch into multiple rounds of 4
```

##### 4.3.2: Create JIRA Issues

For each selected GitHub issue:

**Clean content:**
- Capitalize title if needed
- Convert Markdown to JIRA format (`{code}` blocks, `[text|url]` links)
- Convert `#N` references to `[#N|https://github.com/{org}/{repo}/issues/N]`
- Clean excessive whitespace

**Determine issue type** from GitHub labels: "bug"→Bug, "enhancement"/"feature"→Story, else→Task

**Map labels to components:** If no obvious match, prompt:

```
Use AskUserQuestion:
  question: "Map GitHub label '{label_name}' to which JIRA component?"
  header: "Component"
  multiSelect: false
  options: (available JIRA components, up to 4)
```

**Link to parent epic:** Find Epic Link field ID via `mcp__atlassian__jira_search_fields` (keyword: "epic") or by inspecting an existing child issue. Include in `additional_fields`.

**Preview and confirm** before creating. Call `mcp__atlassian__jira_create_issue`. Do NOT set labels unless explicitly requested.

##### 4.3.3: Report Results

Display: `✓ #42 → PROJ-150` or `✗ #89 → Failed: {reason}`

---

#### Step 4.4: Status Sync

Handles **STATUS-SYNC-NEEDED** - matched issues where GitHub is closed but JIRA is still open.

##### 4.4.1: Select Issues

```
Use AskUserQuestion:
  question: "These JIRA issues are linked to closed GitHub issues. Select which to update:"
  header: "Status Sync"
  multiSelect: true
  options: (label=JIRA key, description="Linked to #{number} (closed) - {title}")
    - For >4 issues, batch into multiple rounds
```

##### 4.4.2: Select Target Status

Fetch transitions via `mcp__atlassian__jira_get_transitions`, then:

```
Use AskUserQuestion:
  question: "What status should these {N} JIRA issues be updated to?"
  header: "Target Status"
  multiSelect: false
  options: (up to 4 completion-related statuses: Done, Closed, Resolved, ON_QA, etc.)
```

##### 4.4.3: Execute Transitions

Call `mcp__atlassian__jira_transition_issue` with comment noting the linked GitHub issue. If transition unavailable for specific issue, fetch its transitions and retry or inform user.

##### 4.4.4: Report Results

Display: `✓ PROJ-101 → ON_QA (linked to #45)` or `✗ PROJ-103 → Failed: {reason}`

### Phase 5: Summary Report and State Persistence

#### Step 5.1: Track and Display Results

Track throughout Phase 4: successful syncs, status updates, ignored items, failures.

Display summary:
```
Sync Complete
━━━━━━━━━━━━━
JIRA → GitHub: ✓ PROJ-101 → #89, ✓ PROJ-102 → #90
GitHub → JIRA: ✓ #42 → PROJ-150
Status Updates: ✓ PROJ-104 → Done (linked to #45)
State: {N} items ignored, preferences saved
Summary: {sync_count} synced, {status_count} updated, {failure_count} failed
```

#### Step 5.2: Save State

Save to `{work_directory}/state.json`: ignored issues, sync history, preferences, label/component mappings.

#### Step 5.3: Save Report

Write to `{work_directory}/{timestamp}/report.md` with summary table (Direction | Success | Failed | Ignored), details for each sync direction, and state changes (newly ignored items, learned preferences).

#### Step 5.4: Offer Retry

If failures occurred, ask: "Some items failed. Retry failed items?" If yes, re-attempt only failures.

## Error Handling

### Atlassian MCP Server Not Available

Show setup instructions:
```
podman run -i --rm -p 8080:8080 -e "JIRA_URL=https://issues.redhat.com" -e "JIRA_USERNAME" -e "JIRA_PERSONAL_TOKEN" ghcr.io/sooperset/mcp-atlassian:latest --transport sse --port 8080 -vv
claude mcp add --transport sse atlassian http://localhost:8080/sse
```

### GitHub CLI Not Available

Check: `which gh`, `gh auth status`. Install: `brew install gh` (macOS) or `sudo dnf install gh` (Fedora). Auth: `gh auth login`

### Rate Limiting

Inform user, wait 60s, retry.

### Partial Failures

Continue processing; log failures; report all in summary.

## Security Considerations

**Sanitization (JIRA→GitHub):** Remove internal URLs, emails, employee names, credentials, codenames, customer info.

**Preview requirement:** NEVER create without user confirmation.

**Token security:** Never log tokens; use env vars; minimal scopes.

## Best Practices

- Use `--since 7d` for incremental syncs
- Review every sanitized preview before confirming
- Establish label/component mappings early
- For large projects, prefer epic-level syncing
- Use `--include-ignored` periodically to review skipped items
- Configure work directory in CLAUDE.md for persistence

## Anti-Patterns

- Syncing without preview
- Syncing credentials/internal URLs
- Assuming mappings without confirmation
- Adding JIRA labels without explicit request
- Running full syncs on large repos without date filtering

## Workflow Summary

1. **Phase 1**: Source selection (project/epic, repo, date filter) via AskUserQuestion prompts
2. **Phase 2**: Load state, validate access, fetch issues from both systems
3. **Phase 3**: Semantic matching (remote links, key mentions, title/body similarity)
4. **Phase 4**: Execute sync:
   - JIRA → GitHub: Select → sanitize → preview → create → link back
   - GitHub → JIRA: Select → clean → preview → create
   - Status sync: Select matched issues with closed GitHub → transition JIRA
5. **Phase 5**: Save state, display summary, offer retry
