---
description: Analyze untriaged OCPBUGS bugs for a team and post AI triage comments directly on each issue before bug scrub meetings
argument-hint: "--team <team-name> [--team-docs <path>] [--since last-week] [--issue OCPBUGS-XXXXX] [--dry-run]"
---

## Name
bug-triage:scrub

## Synopsis
```text
/bug-triage:scrub --team <team-name> [--team-docs <path>] [--since last-week] [--issue OCPBUGS-XXXXX] [--dry-run]
```

## Description
The `bug-triage:scrub` command prepares OpenShift teams for bug scrub meetings by analyzing untriaged bugs and posting structured triage comments **directly on each Jira issue**. When someone opens a bug during the meeting, the AI triage comment is already there with routing checks, importance signals, duplicate candidates, and a recommended action.

This command is designed to:
- Reduce pre-meeting prep time from manual scanning to zero
- Catch misrouted bugs before the meeting
- Surface customer-impacting bugs with importance signals
- Flag possible duplicates and RFEs disguised as bugs
- Collapse CVE tracker clusters and ART Bot PRs into grouped summaries
- Never double-comment -- uses a team-specific label as an idempotency gate

The command integrates with the `teams` plugin's `team_component_map.json` for team identity (components, repos) and optionally reads team-specific documentation for richer analysis (sub-area taxonomy, routing rules, FAQs).

## Implementation

The command follows the detailed implementation in `plugins/bug-triage/skills/triage-comment/SKILL.md`. The high-level flow is:

### Phase 0: Load Team Context

1. **Look up team** in `plugins/teams/team_component_map.json` using the `--team` argument. Extract: components, repos, description, team size.

2. **Load team docs** (if `--team-docs` provided): Read `sub-areas.md`, `routing-guide.md`, and any files in `context/` from the specified directory. These provide team-specific knowledge for richer triage.

3. **Derive idempotency label**: If `sub-areas.md` contains a `Label:` line (e.g., `Label: nid-ai-triaged`), use that. Otherwise, derive from the team name: lowercase, drop filler words (`and`, `the`, `of`, `for`), join remaining words with hyphens, append `-ai-triaged` (e.g., "Network Ingress and DNS" becomes `network-ingress-dns-ai-triaged`). See `plugins/bug-triage/skills/triage-comment/SKILL.md` Idempotency section for the full specification.

### Phase 1: Query Untriaged Bugs

4. **Determine scope** based on arguments:
   - If `--issue OCPBUGS-XXXXX` is provided: operate on that single issue only (skip the JQL query). Useful for demos and testing.
   - Otherwise: query OCPBUGS for untriaged bugs owned by the team.

5. **Build and execute JQL query** (when not in single-issue mode):
   ```jql
   project = OCPBUGS
   AND component in ({team-components})
   AND status = New
   AND labels not in ({team-label})
   AND created >= {since-clause}
   ```
   Build `{team-components}` from the team's components array (e.g., `"Networking / router", "Networking / DNS"`).
   Build `{team-label}` from the idempotency label derived in Phase 0, step 3 (e.g., `nid-ai-triaged`).
   Build `{since-clause}` from the `--since` argument: relative values get a `-` prefix (e.g., `last-week` becomes `-1w`, `last-2-weeks` becomes `-2w`); absolute dates (YYYY-MM-DD) are passed as-is with no prefix (e.g., `"2026-04-01"`).

   Use `jira issue list --jql "<query>" --plain` to fetch matching issues.

   **Note on JQL syntax**: Do not quote `New` in the `status =` clause. Do not append `ORDER BY` -- the `jira` CLI handles sorting internally.

6. **Parse results** into a list of issue keys.
   - If no issues found, report "No untriaged bugs found for the given period" and exit.

### Phase 2: Classify and Group

Before analyzing individual bugs, scan all results and group special categories:

7. **Identify CVE/Security tracker clusters**:
   - Issues with labels matching `SecurityTracking`, `CVE-*`, or `Security`.
   - Group by CVE ID (extract from summary or labels).
   - These will get a single collapsed triage comment on the newest tracker in each group.

8. **Identify ART Bot reconciliation bugs**:
   - Issues where reporter is `ART Bot` or labels contain `art:reconciliation` or `art:package:*`.
   - Group all ART bugs together.
   - These will get a single summary comment on the newest ART issue.

9. **Remaining bugs** are processed individually (the main path).

### Phase 3: Analyze Each Bug

For each individual (non-CVE, non-ART) bug, perform the full triage analysis. Follow the detailed steps in `plugins/bug-triage/skills/triage-comment/SKILL.md`:

10. **Fetch full issue details** (Step 1 of SKILL.md)
11. **Sub-area classification** (Step 2) -- uses `sub-areas.md` if available
12. **Routing check** (Step 3) -- uses `routing-guide.md` if available
13. **Importance assessment** (Step 4) -- universal tiers
14. **Bug vs RFE classification** (Step 5) -- universal
15. **Age, completeness, versions, PR discovery** (Steps 5a-d)
16. **Duplicate detection** (Step 6) -- uses team components for JQL
17. **Related context** (Step 7)
18. **Confidence assessment** (Step 8) -- quality gate

### Phase 4: Post Triage Comments

19. **Format the triage comment** for each bug. Follow the comment template in `plugins/bug-triage/skills/triage-comment/SKILL.md`.

20. **Post the comment** (unless `--dry-run` is set). Use a template file to preserve URL formatting:
    ```bash
    # Write comment to temp file
    cat > /tmp/bug-triage-{ISSUE-KEY}.txt << 'EOF'
    {formatted-comment}
    EOF

    # Post using --template flag
    jira issue comment add {ISSUE-KEY} --template /tmp/bug-triage-{ISSUE-KEY}.txt --no-input

    # Clean up
    rm /tmp/bug-triage-{ISSUE-KEY}.txt
    ```
    **Important**: Do NOT pass the comment as an inline argument or `$'...'` string -- shell escaping breaks URLs at period characters.

21. **Add the idempotency label** to prevent double-commenting on subsequent runs:
    ```bash
    jira issue edit {ISSUE-KEY} -l "{team-label}" --no-input
    ```

22. **For CVE tracker clusters**, post a single collapsed comment on the newest tracker. Add the label to ALL trackers in the group.

23. **For ART Bot bugs**, post a single grouped comment on the newest ART issue. Add the label to ALL ART issues in the group.

### Phase 5: Terminal Summary

24. **Print a summary** to the terminal regardless of dry-run mode:
    ```text
    {team-name} Bug Scrub Complete
    ----------------------
    Period: {since}
    Total bugs analyzed: {N}
    - By sub-area: {sub-area counts}
    - Likely misrouted: {count}
    - Customer-impacting: {count}
    - Possible duplicates: {count}
    - Possible RFEs: {count}
    - CVE clusters: {count} ({total trackers} trackers)
    - ART reconciliation: {count}

    Comments posted: {N} (or "DRY RUN -- no comments posted")
    ```

## Return Value
- **Per-issue**: A structured triage comment posted directly on each Jira issue
- **Terminal**: Summary of all bugs analyzed with counts by category
- **Labels**: Team-specific idempotency label added to each processed issue

## Examples

1. **Triage all untriaged bugs for a team (last week)**:
   ```bash
   /bug-triage:scrub --team "Network Ingress and DNS" --team-docs ~/network-edge-tools/plugins/nid/team-docs
   ```

2. **Triage a single issue (demo/testing)**:
   ```bash
   /bug-triage:scrub --team "Core Networking" --issue OCPBUGS-83283 --dry-run
   ```

3. **Without team docs (basic triage only)**:
   ```bash
   /bug-triage:scrub --team "API Server" --since last-2-weeks
   ```

4. **Dry run to preview comments**:
   ```bash
   /bug-triage:scrub --team "Network Ingress and DNS" --team-docs ~/network-edge-tools/plugins/nid/team-docs --since last-week --dry-run
   ```

## Arguments

- **--team** *(required)*
  Team name as it appears in `plugins/teams/team_component_map.json`. Case-sensitive.
  Run `/teams:list-teams` to see available team names.
  Example: `--team "Network Ingress and DNS"`

- **--team-docs** *(optional)*
  Path to a directory containing team-specific documentation files (`sub-areas.md`, `routing-guide.md`, `context/`). See `plugins/bug-triage/reference/team-docs-spec.md` for the expected format.
  If omitted, the command performs basic triage without sub-area classification or routing checks.
  Example: `--team-docs ~/network-edge-tools/plugins/nid/team-docs`

- **--issue** *(optional)*
  A specific OCPBUGS issue key to triage. When provided, skips the JQL query and operates on this single issue only. Useful for demos and testing.
  Example: `--issue OCPBUGS-83283`

- **--since** *(optional)*
  Time window for querying untriaged bugs.
  Options: `last-week` (default) | `last-2-weeks` | `last-month` | `YYYY-MM-DD`
  Example: `--since last-2-weeks`

- **--dry-run** *(optional)*
  Preview triage comments in the terminal without posting them to Jira or adding labels. Use this to review output before enabling live posting.

## See Also
- `plugins/bug-triage/skills/triage-comment/SKILL.md` -- Detailed analysis logic and comment template
- `plugins/bug-triage/reference/team-docs-spec.md` -- Team documentation format specification
- `/teams:list-teams` -- List available team names
- `/teams:list-components` -- List components for a team
- `/jira:grooming` -- Generic Jira grooming agenda generator
