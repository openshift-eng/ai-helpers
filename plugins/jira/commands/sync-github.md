---
description: Synchronize issues between JIRA and GitHub with bidirectional support and content sanitization
argument-hint: [--project <key> | --epic <key>] [--repo <org/repo>] [--since <date>] [--include-ignored] [--include-prs]
---

## Name
jira:sync-github

## Synopsis
```
/jira:sync-github [--project <key> | --epic <key>] [--repo <org/repo>] [--since <date>] [--include-ignored] [--include-prs]
```

## Description

The `jira:sync-github` command synchronizes issues between a JIRA project or epic and a GitHub repository. It identifies issues that exist in one system but not the other, allows selective syncing with user confirmation, and handles content sanitization appropriately for each direction.

**Key Features:**

- **Interactive UI**: Uses arrow-key navigation and multi-select for all user choices
- **Bidirectional sync**: Sync issues from JIRA to GitHub and vice versa
- **PR-Aware**: Discovers GitHub PRs, correlates them to JIRA issues, and updates status when merged
- **Orphan PR Handling**: Creates JIRA issues for merged PRs that have no linked issue
- **Incremental sync**: Optionally filter to only issues created/updated/closed after a specific date
- **Smart date filtering**: Automatically suggests date filter for large repositories (>50 items)
- **Semantic matching**: Identifies issues that exist in both systems based on similarity and existing links
- **Content sanitization**: Strips company-specific information when syncing JIRA→GitHub
- **Content cleanup**: Improves professionalism when syncing GitHub→JIRA
- **Remote linking**: Automatically adds JIRA remote links to synced GitHub issues/PRs
- **Status sync**: Updates JIRA status when linked GitHub issues are closed or PRs are merged
- **Persistent memory**: Remembers ignored issues and learned preferences across sessions
- **Learned preferences**: Suggests previously used projects, epics, and repos in prompts
- **Select-then-execute**: Each sync direction shows results immediately after selection
- **Label/Component mapping**: Learns and persists mappings across sessions

**Use Cases:**

1. Keep an open-source GitHub project in sync with internal JIRA tracking
2. Publish sanitized versions of internal issues to public issue trackers
3. Import community-reported issues into internal tracking systems
4. Update JIRA status based on GitHub issue resolution or PR merges
5. Track orphan PRs by creating JIRA issues for merged work without linked issues
6. Run incremental syncs to process only recent changes (e.g., weekly sync)
7. Resume syncing without re-reviewing previously ignored items

## Prerequisites

### Required Tools

This command requires the following tools to be configured:

#### 1. Atlassian MCP Server (for JIRA)

```bash
# Start the Atlassian MCP server
podman run -i --rm -p 8080:8080 \
  -e "JIRA_URL=https://issues.redhat.com" \
  -e "JIRA_USERNAME" \
  -e "JIRA_PERSONAL_TOKEN" \
  -e "JIRA_SSL_VERIFY=true" \
  ghcr.io/sooperset/mcp-atlassian:latest --transport sse --port 8080 -vv

# Add to Claude Code
claude mcp add --transport sse atlassian http://localhost:8080/sse
```

#### 2. GitHub CLI (gh)

```bash
# Install gh CLI (macOS)
brew install gh

# Install gh CLI (Fedora/RHEL)
sudo dnf install gh

# Authenticate with GitHub
gh auth login
```

**Required GitHub Scopes:**
- `repo` - Full control of private repositories (for issue read/write)
- `public_repo` - Access public repositories (minimum for public repos)

### Verification

- Use `/mcp` within Claude Code to verify the Atlassian MCP server is running
- Run `gh auth status` to verify GitHub CLI is authenticated

## Implementation

The command operates in five phases. **Invoke the `jira:sync-github` skill** for detailed step-by-step implementation guidance.

### Phase 1: Source Selection (with Learned Preferences)
- Use `AskUserQuestion` with interactive UI to prompt for JIRA source (project or epic)
- **Populate options from learned preferences** (recently used projects/epics from state)
- Use `AskUserQuestion` to prompt for GitHub repository
- **Suggest repos previously associated with selected project** from state
- Check repository size and **auto-suggest date filter** if >50 issues+PRs
- Validate access to both systems

### Phase 2: Data Collection and State Loading
- **First**, check Claude memory/CLAUDE.md for configured work directory
- If not found, prompt user with `AskUserQuestion` for work directory location
- After selection, **tell user how to persist**: run `/memory` and add `jira:sync-github work directory: {path}`
- Load existing state from `{work_directory}/state.json` (ignored issues, preferences, mappings)
- Display count of previously ignored items (hidden unless `--include-ignored`)
- Fetch JIRA issues using MCP `jira_search` with date filter if `--since` provided
- Fetch GitHub issues using `gh issue list --json ...`
- **Fetch GitHub PRs** using `gh pr list --json ...` (if `--include-prs` or by default)
- Extract existing JIRA→GitHub remote links for matching
- **Extract JIRA key mentions from PR titles, bodies, and branch names**
- Cache data to `{work_directory}/{timestamp}/`

### Phase 3: Semantic Matching & Gap Analysis
- Match issues by: existing remote links, JIRA key mentions, title similarity
- **Correlate PRs to JIRA issues** by: JIRA key mentions, linked GitHub issues, title similarity
- Categorize as:
  - **MATCHED**: Issues in both systems
  - **JIRA-ONLY**: Can sync to GitHub (filtered by ignored list)
  - **GITHUB-ONLY**: Open issues can sync to JIRA (filtered by ignored list)
  - **STATUS-SYNC-NEEDED**: Closed GitHub issues with open JIRA
  - **PR-STATUS-SYNC-NEEDED**: Merged PRs with open JIRA
  - **ORPHAN-PRS**: Merged PRs with no linked issue (can create JIRA, filtered by ignored list)

### Phase 4: Sync Execution (Interactive Select-Then-Execute)

Each sync direction uses `AskUserQuestion` for multi-select, then immediately executes:

1. **JIRA → GitHub Sync**
   - Use `AskUserQuestion` with multi-select to choose which JIRA-only issues to sync
   - For each selected issue: sanitize content, preview, confirm, create GitHub issue
   - Add remote link comment in JIRA after creation
   - **Track unselected items as ignored** for future runs
   - Display results immediately

2. **GitHub → JIRA Sync**
   - Use `AskUserQuestion` with multi-select to choose which open GitHub-only issues to sync
   - Note: Closed GitHub issues without a JIRA match are not shown (typically old/irrelevant)
   - For each selected issue: clean up formatting, preview, confirm, create JIRA issue
   - **Track unselected items as ignored** for future runs
   - Display results immediately

3. **Issue Status Sync**
   - Use `AskUserQuestion` with multi-select to choose which matched issues need status updates
   - Fetch available transitions from JIRA to show valid target statuses
   - Use `AskUserQuestion` to select target status (e.g., ON_QA, Verified, Closed)
   - Execute transitions and display results

4. **PR Status Sync**
   - Use `AskUserQuestion` with multi-select to choose which merged PRs should update JIRA status
   - Transition correlated JIRA issues to selected status
   - **Add remote link from JIRA to PR** if not already linked
   - Display results immediately

5. **Orphan PR → JIRA Sync**
   - Use `AskUserQuestion` with multi-select to choose which orphan PRs should create JIRA issues
   - For each selected PR: build issue from PR content, preview, confirm, create JIRA issue
   - Add remote link from new JIRA issue to PR
   - **Track unselected PRs as ignored** for future runs
   - Display results immediately

### Phase 5: Summary Report and State Persistence
- Display sync results with success/failure/ignored counts
- **Save updated state** to `{work_directory}/state.json` (ignored items, preferences, mappings)
- Save detailed report to `{work_directory}/{timestamp}/report.md`
- Offer retry for failed items

## Arguments

- **--project** *(optional)*
  JIRA project key to sync (e.g., `MYPROJECT`).
  Mutually exclusive with `--epic`.

- **--epic** *(optional)*
  JIRA epic key to sync (e.g., `MYPROJECT-123`).
  Syncs the epic and all child issues.
  Mutually exclusive with `--project`.

- **--repo** *(optional)*
  GitHub repository in `org/repo` format (e.g., `openshift/origin`).

- **--since** *(optional)*
  Only sync issues/PRs created, updated, or closed after this date.
  Accepts formats: `YYYY-MM-DD`, `last-week`, `last-month`, or relative like `7d`, `30d`.
  Useful for incremental syncs to avoid reprocessing old issues.
  **Note:** If not provided and the repository has >50 items, you'll be prompted to select a date filter.

- **--include-ignored** *(optional)*
  Include previously ignored issues and PRs in sync candidates.
  By default, items you've skipped in previous runs are hidden.
  Use this flag to reconsider all items.

- **--include-prs** *(optional, default: true)*
  Fetch and process GitHub pull requests in addition to issues.
  Enables PR→JIRA status sync and orphan PR handling.
  PRs are included by default; use `--no-include-prs` to disable.

If arguments are not provided, the command prompts interactively using learned preferences from previous runs.

## Return Value

- **Summary**: Count of issues and PRs synced in each direction
- **Created Issues**: List of newly created issue keys/URLs
- **Status Updates**: List of JIRA issues with updated status (from issues and PRs)
- **PR Links**: List of PRs linked to JIRA issues
- **Ignored Items**: Count of items added to ignore list
- **State Updates**: Confirmation that preferences and mappings were saved
- **Failures**: List of any sync failures with error details
- **Report File**: Path to detailed sync report

## Examples

1. **Interactive sync (recommended for first use):**
   ```
   /jira:sync-github
   ```
   Prompts for work directory, project/epic, and repository selection.
   On subsequent runs, uses learned preferences.

2. **Sync a specific project:**
   ```
   /jira:sync-github --project MYPROJECT --repo openshift/my-operator
   ```

3. **Sync issues under an epic:**
   ```
   /jira:sync-github --epic MYPROJECT-100 --repo myorg/myrepo
   ```

4. **Incremental sync (only recent changes):**
   ```
   /jira:sync-github --project MYPROJECT --repo openshift/my-operator --since 2025-12-01
   ```

5. **Weekly sync (last 7 days):**
   ```
   /jira:sync-github --project MYPROJECT --repo openshift/my-operator --since last-week
   ```

6. **Sync changes from last 30 days:**
   ```
   /jira:sync-github --epic MYPROJECT-100 --repo myorg/myrepo --since 30d
   ```

7. **Review previously ignored items:**
   ```
   /jira:sync-github --include-ignored
   ```
   Shows all items including those previously skipped.

8. **Sync without PR processing:**
   ```
   /jira:sync-github --project MYPROJECT --repo openshift/my-operator --no-include-prs
   ```
   Only syncs issues, skips PR correlation and orphan PR handling.

## Error Handling

### GitHub CLI Not Available

**Scenario:** GitHub CLI (gh) not installed or not authenticated.

**Action:**
```
GitHub CLI not available or not authenticated.

Please ensure gh is installed and authenticated:
  # Install (macOS)
  brew install gh

  # Install (Fedora/RHEL)
  sudo dnf install gh

  # Authenticate
  gh auth login

Then try again.
```

### Atlassian MCP Server Not Available

**Scenario:** Atlassian MCP server not running.

**Action:**
```
Atlassian MCP server not available.

Please ensure the server is running and configured.
Use /mcp in Claude Code to check status.
```

### Permission Denied

**Scenario:** Cannot create issue in target system.

**Action:**
- Log the failure
- Continue with remaining issues
- Report in summary
- Suggest checking token permissions

### Rate Limiting

**Scenario:** GitHub or JIRA API rate limit hit.

**Action:**
- Pause and wait for rate limit reset
- Inform user of delay
- Continue when limit resets

### No Issues Found

**Scenario:** Source has no issues to sync.

**Action:**
```
No issues found in JIRA project MYPROJECT.

Please verify:
1. The project key is correct
2. You have access to the project
3. The project contains issues
```

## Security Considerations

### Content Sanitization (JIRA → GitHub)

When syncing to public GitHub repositories, the following is automatically removed:

- Internal URLs (wikis, dashboards, internal tools)
- Employee names and email addresses
- Internal project codenames
- Confidential customer references
- Credentials, tokens, or secrets
- Internal component/team names (replaced with generic terms)

**Important:** Always review the sanitized preview before confirming creation.

### Access Control

- GitHub issues are created with your GitHub token's permissions
- JIRA issues include `security: Red Hat Employee` by default
- Remote links are only added from JIRA to GitHub (not vice versa)

## State Management

This command maintains persistent state across sessions in `{work_directory}/state.json`:

- **Ignored issues**: Items you've skipped are remembered and hidden in future runs
- **Recent projects/epics/repos**: Previously used values appear as quick-select options
- **Project-repo associations**: The command learns which repos you sync with which projects
- **Label/component mappings**: Mappings you establish are reused in future sessions

**To configure a persistent work directory**, run `/memory` and add:

```
jira:sync-github work directory: /path/to/your/preferred/location
```

**To clear ignored items**, manually edit the `state.json` file or run with `--include-ignored` to reconsider all items.

## See Also

- `jira:create` - Create individual JIRA issues
- `jira:solve` - Analyze and solve JIRA issues
- `jira:status-rollup` - Generate status rollup reports
- `jira:extract-prs` - Extract PR links from JIRA issues (used internally)

## Skills Reference

This command invokes the following skill:

- **sync-github** - Detailed implementation guide for the sync workflow

To view skill details:
```bash
cat plugins/jira/skills/sync-github/SKILL.md
```
