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
2. **Locate shared data**

   The links to `node-team` files in this command are relative to a repo checkout. When the plugin is installed they do not resolve. In that case read the files from `"${CLAUDE_PLUGIN_ROOT}"/../../node-team/*/skills/node/references/` (glob the version directory), or invoke the `node-team:node` skill and read from its base directory.

3. **Resolve Jira Credentials**

   The canonical authentication chain is in the [jira reference](../../node-team/skills/node/references/jira.md). Shell variables do not persist between Bash tool calls, so put this block at the top of every invocation that talks to Jira (it is included in the query script in Phase 1):

   ```bash
   JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
   JIRA_USER="${JIRA_USER:-${JIRA_EMAIL:-$(security find-generic-password -s "JIRA_API_TOKEN" -g 2>&1 | grep acct | sed 's/.*="//;s/"//')}}"
   : "${JIRA_USER:=$(git config user.email)}"
   [ -n "$JIRA_API_TOKEN" ] || { echo "ERROR: JIRA_API_TOKEN not found (env, Keychain, secret-tool)" >&2; exit 1; }
   [ -n "$JIRA_USER" ] || { echo "ERROR: set JIRA_USER or JIRA_EMAIL" >&2; exit 1; }
   case "$JIRA_USER" in *@*) ;; *) JIRA_USER="${JIRA_USER}@redhat.com" ;; esac
   ```

   Never print the token and never pass it as a command-line argument. Credentials go to curl through a config on stdin (`curl -K -`), as shown in Phase 1.

4. **Create work directory**: `mkdir -p .work/node-bug/triage-$(date +%Y-%m-%d)`

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
   - If `--sprint <name>`: append `AND sprint = "<name>"`. Escape any `\` and `"` in the name with a backslash before inserting it.
   - If `--unassigned-only`: append `AND (assignee is EMPTY OR assignee = "Node Team Bot Account" OR priority = Undefined OR "Release Blocker" = Proposed)`

   Component names contain spaces and slashes, so quote each one: `component in ("Node / Device Manager", "Node / Instaslice-operator")`.

   The team mailing list `aos-node@redhat.com` is the email of the `Node Team Bot Account` user, so both names refer to the same assignee (verified with a read-only query on 2026-09-21: both forms return the same issues). Treat that account and an empty assignee as unassigned everywhere in this command.

3. **Execute the query** using the POST search endpoint. Run the credential block from Phase 0 and this script in a single Bash invocation. The JQL contains double quotes, so build the JSON body with `jq` instead of pasting the JQL into a JSON string:

   ```bash
   # <credential block from Phase 0 goes here>
   JQL='<constructed JQL>'
   OUT=".work/node-bug/triage-$(date +%Y-%m-%d)/bugs.jsonl"
   PAGE="${OUT%.jsonl}.page.json"
   PART="$OUT.partial"
   mkdir -p "$(dirname "$OUT")"
   # Collect into a partial file and publish it only after the last page, so a
   # failed run never leaves a truncated bugs.jsonl behind.
   rm -f "$OUT"
   : > "$PART"
   TOKEN=""
   PAGES=0
   while :; do
     # 50 pages are 5000 bugs. More than that means the pagination is broken.
     PAGES=$((PAGES + 1))
     [ "$PAGES" -le 50 ] || { echo "ERROR: more than 50 result pages, aborting" >&2; rm -f "$PART"; exit 1; }
     BODY=$(jq -n --arg jql "$JQL" --arg token "$TOKEN" '{
       jql: $jql,
       maxResults: 100,
       fields: ["key", "summary", "status", "priority", "assignee",
                "components", "labels", "customfield_10689",
                "customfield_10840", "customfield_10847",
                "customfield_10978", "customfield_10020"]
     } + (if $token == "" then {} else {nextPageToken: $token} end)')
     for attempt in 1 2 3 4 5; do
       CODE=$(printf 'user = "%s:%s"\n' "$JIRA_USER" "$JIRA_API_TOKEN" |
         curl -s -K - --connect-timeout 10 --max-time 60 -o "$PAGE" -w '%{http_code}' \
           -H "Content-Type: application/json" \
           -X POST "https://redhat.atlassian.net/rest/api/3/search/jql" \
           -d "$BODY")
       [ "$CODE" != "429" ] && break
       sleep $((attempt * 10))
     done
     if [ "$CODE" != "200" ]; then
       echo "ERROR: Jira search failed with HTTP $CODE" >&2
       jq -r '.errorMessages[]?, (.errors // {} | to_entries[] | "\(.key): \(.value)")' "$PAGE" >&2
       rm -f "$PAGE" "$PART"
       exit 1
     fi
     if ! jq -c '.issues[]' "$PAGE" >> "$PART" ||
        ! TOKEN=$(jq -r 'if .isLast == false then .nextPageToken // "" else "" end' "$PAGE"); then
       echo "ERROR: Jira returned a malformed search page" >&2
       rm -f "$PAGE" "$PART"
       exit 1
     fi
     rm -f "$PAGE"
     [ -z "$TOKEN" ] && break
   done
   mv "$PART" "$OUT"
   wc -l < "$OUT"
   ```

   If the JQL contains a single quote (for example in a sprint name), assign it with a quoted heredoc (`JQL=$(cat <<'EOF'` ... `EOF`) instead of `JQL='...'`.

   A non-200 response is an error, never "0 bugs found". See [Error Handling](#error-handling).

   Custom field mapping:
   - `customfield_10689`: Customer Impact
   - `customfield_10840`: Severity
   - `customfield_10847`: Release Blocker
   - `customfield_10978`: SFDC Cases Counter
   - `customfield_10020`: Sprint

   Pagination uses `nextPageToken`: while the response has `isLast: false`, the script repeats the request with the token from the previous response. This endpoint does not return `total` and does not accept `startAt`.

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
   - **Untriaged**: priority is "Undefined", OR `"Release Blocker"` is "Proposed", OR the bug is unassigned (assignee is empty, or assignee display name is `Node Team Bot Account`, which is the `aos-node@redhat.com` mailing-list account)
   - **Other**: all remaining bugs

   A bug can appear in multiple buckets (e.g., a release blocker that is also a customer escalation). Count it in each applicable bucket.

3. **Assignment suggestions** (when team roster files exist):

   Load team rosters from `~/.node-assistant/team-roster-{core,dra,kueue}.json`. This command only reads them. If roster files do not exist, skip assignment suggestions and print "Roster files not found, skipping assignment suggestions. Run /node-team:overview to sync them."

   Query all team members' open bug counts with one JQL, reusing the Phase 1 script (same credential block, `jq`-built body, HTTP code check, 429 backoff and `nextPageToken` pagination) with `fields: ["key", "assignee"]`:
   ```text
   filter = "Node Bugs" AND status not in (Closed, Done, Verified) AND assignee in ("<Display Name 1>", "<Display Name 2>", ...)
   ```
   The roster keys are Jira display names. Jira Cloud JQL resolves quoted display names and email addresses in `assignee in (...)` (verified with a read-only query on 2026-09-21), so the roster names can be used directly. If a name matches no user, Jira returns HTTP 400 with the name in `errorMessages`; drop that name, print a warning, and retry once.

   Group results by `assignee.displayName` in code to build a workload map. Roster members with no results have 0 open bugs.

   For each unassigned bug (empty assignee or `Node Team Bot Account`):
   - Determine the correct sub-team from step 1
   - Never suggest `Node Team Bot Account`, even if it appears in a roster
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

## Error Handling

- **Missing credentials**: the credential block exits with an error. Print which variable is missing and point to `/node-team:preflight`. Do not continue.
- **HTTP 401 or 403**: the token or user is wrong or expired. Print the status and stop. Do not report "0 bugs".
- **HTTP 400**: the JQL is invalid (for example an unknown sprint name or roster member). Print `errorMessages` from the response. For the roster query, drop the offending name and retry once; for the main query, stop.
- **HTTP 429**: wait and retry up to 5 times with increasing delay (10s, 20s, ...). If still rate limited, stop with an error.
- **Other non-200 or network failure**: print the status and stop.
- **Missing `jq` or `curl`**: stop and ask the user to install them.
- **Missing roster files**: not an error. Skip suggestions and the workload table.
- **Partial pagination failure**: discard the partial result file and stop, so a truncated list is never presented as complete.

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
- `--unassigned-only`: Show only bugs that are untriaged or unassigned (priority Undefined, Release Blocker Proposed, assignee is `Node Team Bot Account` (the mailing-list account), or assignee is empty). Optional.

## Notes

- The Jira query uses the "Node Bugs" saved filter (ID 83963) as the base. This filter is maintained in Jira and defines which bugs are in scope. The "Node Bugs" dashboard (ID 12991) provides a visual overview at `https://redhat.atlassian.net/jira/dashboards/12991`.
- Sub-team routing uses the sub-teams table from the [node-team shared components reference](../../node-team/skills/node/references/shared/components.md). Core owns all Node components not listed under DRA/Devices or Kueue.
- Assignment suggestions require team roster files at `~/.node-assistant/team-roster-{core,dra,kueue}.json`. This command only reads them; run `/node-team:overview` to sync them from the Jira config issue (see the Team Roster section of [jira.md](../../node-team/skills/node/references/jira.md)).
- The command is read-only. It does not modify bugs, change assignments, or transition issues. All suggestions are advisory.
- Reports and artifacts are saved to `.work/node-bug/` (gitignored).
- For CVE-specific triage with reachability analysis, use `/node-cve:triage` instead.
