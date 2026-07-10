---
description: Query open Node bugs, classify by priority and sub-team, suggest assignments, and generate a triage summary
argument-hint: "[--sub-team core|devices|kueue] [--sprint <name>] [--unassigned-only]"
---

## Name
node-bug:triage

## Synopsis
```text
/node-bug:triage [--sub-team core|devices|kueue] [--sprint "OCP Node Core Sprint 42"] [--unassigned-only]
```

## Description

Queries all open bugs in OCPBUGS for Node team components using the "Node Bugs" saved filter, classifies them into triage buckets (Release Blockers, Customer Escalations, Potential Blockers, Component Regressions, Untriaged), routes each bug to the correct sub-team, and suggests assignments based on current workload.

Designed for both interactive triage sessions and headless execution via `claude --print`.

## Implementation

### Phase 0: Setup and Argument Parsing

1. **Parse Arguments**
   - `--sub-team core|devices|kueue`: Filter results to one sub-team's components. Optional. Read sub-team component lists from the sub-teams table in [shared/components.md](../../node-team/skills/node/references/shared/components.md) rather than hardcoding names.
     - `core`: all Node components not listed under another sub-team
     - `devices`: components listed under DRA/Devices in the sub-teams table
     - `kueue`: components listed under Kueue in the sub-teams table
   - `--sprint <name>`: Filter to bugs in a specific sprint (e.g., "OCP Node Core Sprint 42"). Optional.
   - `--unassigned-only`: Show only untriaged or unassigned bugs. Optional.
2. **Validate Jira Credentials**

   Use the authentication chain from the [jira reference](../../node-team/skills/node/references/jira.md):

   ```bash
   JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
   JIRA_USER="${JIRA_EMAIL:-$(security find-generic-password -s "JIRA_API_TOKEN" -g 2>&1 | grep acct | sed 's/.*="//;s/"//')}"
   : "${JIRA_USER:=$(git config user.email)}"
   [[ "$JIRA_USER" != *@* ]] && JIRA_USER="${JIRA_USER}@redhat.com"
   ```

   Exit with error if `JIRA_API_TOKEN` is empty after the chain.

3. **Create work directory**: `mkdir -p .work/node-bug/triage-$(date +%Y-%m-%d)`

---

### Phase 1: Query Bugs

1. **Use the Jira saved filter** "Node Bugs" (ID 83963) for the base query. The filter defines which components are in scope.

2. **Build JQL**:

   ```text
   filter = "Node Bugs" AND status not in (Closed, Done, Verified)
   ```

   Apply optional filters (read sub-team component names from the sub-teams table in [shared/components.md](../../node-team/skills/node/references/shared/components.md)):
   - If `--sub-team devices`: append `AND component in (<DRA/Devices components>)`
   - If `--sub-team kueue`: append `AND component in (<Kueue components>)`
   - If `--sub-team core`: append `AND component not in (<DRA/Devices components>, <Kueue components>)`
   - If `--sprint <name>`: append `AND sprint = "<name>"`
   - If `--unassigned-only`: append `AND (assignee is EMPTY OR assignee in ("aos-node@redhat.com") OR priority = Undefined OR "Release Blocker" = Proposed)`

3. **Execute the query** using the POST search endpoint:

   ```bash
   curl -s -u "$JIRA_USER:$JIRA_API_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST "https://redhat.atlassian.net/rest/api/3/search/jql" \
     -d '{
       "jql": "<constructed JQL>",
       "maxResults": 100,
       "fields": [
         "key", "summary", "status", "priority", "assignee",
         "components", "labels",
         "customfield_10689",
         "customfield_10840",
         "customfield_10847",
         "customfield_10978",
         "customfield_10020"
       ]
     }'
   ```

   Custom field mapping:
   - `customfield_10689`: Customer Impact
   - `customfield_10840`: Severity
   - `customfield_10847`: Release Blocker
   - `customfield_10978`: SFDC Cases Counter
   - `customfield_10020`: Sprint

   Handle pagination via `nextPageToken`: while the response has `isLast: false`, repeat the request with `"nextPageToken": "<token from previous response>"` in the body. This endpoint does not return `total` and does not accept `startAt`.

4. **Print intermediate summary**: "Found N open bugs for Node team components."

**Decision Point:**
- IF 0 bugs found: print "No open bugs matching filters." and exit.
- IF bugs found: continue to Phase 2.

---

### Phase 2: Classify and Route

1. **Route each bug to its sub-team** using the sub-teams table from [shared/components.md](../../node-team/skills/node/references/shared/components.md):
   - DRA/Devices: bugs whose component appears in the DRA/Devices row of the sub-teams table
   - Kueue: bugs whose component appears in the Kueue row of the sub-teams table
   - Core: all remaining Node components

2. **Classify each bug into triage buckets** using the [Bug Triage Definitions](../../node-team/skills/node/references/jira.md):

   - **Release Blockers**: `"Release Blocker"` field value is "Approved", OR priority is "Blocker"
   - **Potential Blockers**: `"Release Blocker"` field value is "Proposed", OR (priority is "Blocker" AND `"Release Blocker"` is empty)
   - **Customer Escalations**: `customfield_10978` (SFDC Cases Counter) is not null/empty, OR `customfield_10689` (Customer Impact) value is "Customer Escalated"
   - **Component Regressions**: labels contain `component-regression`
   - **Untriaged**: priority is "Undefined", OR `"Release Blocker"` is "Proposed", OR assignee is `aos-node@redhat.com`
   - **Other**: all remaining bugs

   A bug can appear in multiple buckets (e.g., a release blocker that is also a customer escalation). Count it in each applicable bucket.

3. **Assignment suggestions** (when team roster files exist):

   Load team rosters from `~/.node-assistant/team-roster-{core,dra,kueue}.json`. If roster files do not exist, skip assignment suggestions and print "Roster files not found, skipping assignment suggestions."

   Query all team members' open bug counts in a single call:
   ```text
   filter = "Node Bugs" AND status not in (Closed, Done, Verified) AND assignee in (<all roster members>)
   ```
   Group results by assignee in code to build a workload map.

   For each unassigned or mailing-list-assigned bug:
   - Determine the correct sub-team from step 1
   - Exclude "Node Team Bot Account" from suggestions
   - Suggest the team member with the fewest open bugs from the appropriate sub-team roster

---

### Phase 3: Generate Triage Summary

1. **Print the triage summary** grouped by classification with counts:

   ```text
   Node Bug Triage (N bugs)

   Release Blockers: X
   Customer Escalations: X
   Potential Blockers: X
   Component Regressions: X
   Untriaged: X
   Other: X

   --- Release Blockers ---
   * OCPBUGS-XXXXX: <summary> (Component, Priority, Assignee)
   * OCPBUGS-XXXXX: <summary> (Component, Priority, Unassigned -> suggested: <name>)

   --- Customer Escalations ---
   * OCPBUGS-XXXXX: <summary> (Component, N support cases, Assignee)

   --- Potential Blockers ---
   * OCPBUGS-XXXXX: <summary> (Component, Priority, Assignee)

   --- Component Regressions ---
   * OCPBUGS-XXXXX: <summary> (Component, Assignee)

   --- Untriaged ---
   * OCPBUGS-XXXXX: <summary> (Component, Unassigned -> suggested: <name>)

   --- Other ---
   * OCPBUGS-XXXXX: <summary> (Component, Priority, Assignee)

   Workload Distribution:
   | Team Member | Open Bugs | Sub-team |
   |-------------|-----------|----------|
   | <name>      | N         | Core     |
   | <name>      | N         | DRA      |

   Filter: https://redhat.atlassian.net/issues/?filter=83963
   Dashboard: https://redhat.atlassian.net/jira/dashboards/12991
   ```

   Omit empty sections. Include the workload distribution table only when roster files are available. Show assignment suggestions inline for unassigned bugs.

2. **Save the report** to `.work/node-bug/triage-$(date +%Y-%m-%d)/report.md`.

## Return Value

Prints the triage summary to stdout. Saves a report file to `.work/node-bug/triage-$(date +%Y-%m-%d)/report.md`. No write operations are performed on Jira (read-only).

## Examples

1. **Full triage across all sub-teams**:
   ```text
   /node-bug:triage
   ```

2. **Core sub-team bugs in the current sprint**:
   ```text
   /node-bug:triage --sub-team core --sprint "OCP Node Core Sprint 42"
   ```

3. **Unassigned DRA/Devices bugs only**:
   ```text
   /node-bug:triage --sub-team devices --unassigned-only
   ```

4. **Headless run for CI/scheduled jobs**:
   ```bash
   claude --print "/node-bug:triage --unassigned-only"
   ```

## Arguments

- `--sub-team core|devices|kueue`: Filter to one sub-team's components. `core` includes all Node components not listed under another sub-team. `devices` includes only components listed under DRA/Devices. `kueue` includes only components listed under Kueue. Sub-team definitions are in the [sub-teams table](../../node-team/skills/node/references/shared/components.md). Optional.
- `--sprint <name>`: Filter to bugs in a specific sprint. Use the exact sprint name from Jira (e.g., "OCP Node Core Sprint 42"). Optional.
- `--unassigned-only`: Show only bugs that are untriaged or unassigned (priority Undefined, Release Blocker Proposed, assignee is the mailing list, or assignee is empty). Optional.

## Notes

- The Jira query uses the "Node Bugs" saved filter (ID 83963) as the base. This filter is maintained in Jira and defines which bugs are in scope. The "Node Bugs" dashboard (ID 12991) provides a visual overview at `https://redhat.atlassian.net/jira/dashboards/12991`.
- Sub-team routing uses the sub-teams table from the [node-team shared components reference](../../node-team/skills/node/references/shared/components.md). Core owns all Node components not listed under DRA/Devices or Kueue.
- Assignment suggestions require team roster files at `~/.node-assistant/team-roster-{core,dra,kueue}.json`. Sync these from Jira config issue OCPNODE-4230 (see [jira.md](../../node-team/skills/node/references/jira.md) Team Roster section).
- The command is read-only. It does not modify bugs, change assignments, or transition issues. All suggestions are advisory.
- Reports and artifacts are saved to `.work/node-bug/` (gitignored).
- For CVE-specific triage with reachability analysis, use `/node-cve:triage` instead.
