# Node Team Jira Reference

Red Hat Jira: `redhat.atlassian.net`. REST API v3. Use `curl` for this
skill's workflows: they need endpoints the `jira` CLI does not cover (Agile
boards and sprints, attachment downloads, ADF bodies, comment listing,
custom-field writes), and curl needs no extra install or config. The
skill's `allowed-tools: Bash(curl:*)` pre-approves curl calls; it does not
restrict other tools.

## Authentication

Inputs, in order of precedence:

| Value | Sources |
|-------|---------|
| Token | `$JIRA_API_TOKEN`, macOS Keychain item `JIRA_API_TOKEN`, Linux `secret-tool lookup service redhat key JIRA_API_TOKEN` |
| User (email) | `$JIRA_USER`, `$JIRA_EMAIL`, account of the macOS Keychain item, `git config user.email` |

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
JIRA_USER="${JIRA_USER:-${JIRA_EMAIL:-$(security find-generic-password -s "JIRA_API_TOKEN" -g 2>&1 | grep acct | sed 's/.*="//;s/"//')}}"
JIRA_USER="${JIRA_USER:-$(git config user.email)}"
[ -n "$JIRA_API_TOKEN" ] || { echo "ERROR: no Jira token (set JIRA_API_TOKEN or store it in the keychain)" >&2; exit 1; }
[ -n "$JIRA_USER" ] || { echo "ERROR: no Jira user (set JIRA_USER or JIRA_EMAIL)" >&2; exit 1; }
case "$JIRA_USER" in *@*) ;; *) JIRA_USER="${JIRA_USER}@redhat.com" ;; esac

jira_curl() {
  printf 'user = "%s:%s"\n' "$JIRA_USER" "$JIRA_API_TOKEN" \
    | curl -s -K - --connect-timeout 10 --max-time 60 -H "Content-Type: application/json" "$@"
}
```

Rules:

- **One invocation.** Shell variables and functions do not persist between
  Bash tool calls. Run the block above and the requests that use it in the
  same Bash invocation (or put them in one script file).
- **No tokens on the command line.** Never use `curl -u "user:token"` or
  `-H "Authorization: ..."` with a secret: arguments are visible in the process
  list. `jira_curl` feeds the credentials to curl through `-K -` on stdin, and
  `printf` is a shell builtin, so the token never appears in `ps`.
- Never echo the token or write it to a file. Test for presence with
  `[ -n "$JIRA_API_TOKEN" ]`.
- Check results: add `-w '\n%{http_code}'` (or `-o <file> -w '%{http_code}'`)
  and treat anything other than 2xx as a failure. 401 means a bad token or
  user, 403 missing permissions, 429 rate limiting (wait for `Retry-After`
  seconds, then retry). A failed request must never be reported as "0 results".
- Build JSON bodies with `jq -n --arg jql "$JQL" '{jql:$jql,...}'` so quotes in
  JQL are escaped correctly.

All requests below go through `jira_curl`.

## REST API Endpoints

Base: `https://redhat.atlassian.net`

| Method | Path | Use |
|--------|------|-----|
| POST | `/rest/api/3/search/jql` | Search. Body: `{"jql":"...","maxResults":50,"fields":["key","summary",...]}` |
| GET | `/rest/api/3/issue/{key}` | Get issue. Optional `?fields=summary,status,...` |
| POST | `/rest/api/3/issue` | Create. Body: `{"fields":{"project":{"key":"OCPNODE"},"issuetype":{"name":"Story"},"summary":"..."}}` |
| PUT | `/rest/api/3/issue/{key}` | Update fields. Body: `{"fields":{"customfield_10028":5}}` |
| PUT | `/rest/api/3/issue/{key}/assignee` | Assign. Body: `{"accountId":"..."}` |
| GET | `/rest/api/3/issue/{key}/comment` | List comments |
| POST | `/rest/api/3/issue/{key}/comment` | Add comment (body in ADF format, see below) |
| GET | `/rest/api/3/issue/{key}/transitions` | Available transitions |
| POST | `/rest/api/3/issue/{key}/transitions` | Transition. Body: `{"transition":{"id":"31"}}` |
| POST | `/rest/api/3/issue/{key}/remotelink` | Add link. Body: `{"object":{"url":"...","title":"..."}}` |
| GET | `/rest/api/3/user/search?query={name}` | Find user by name |
| GET | `/rest/agile/1.0/board/11478/sprint?state=active` | List sprints (board 11478 = Node) |
| GET | `/rest/agile/1.0/sprint/{id}/issue?maxResults=100&fields=...` | Sprint issues |
| POST | `/rest/agile/1.0/sprint/{id}/issue` | Move to sprint. Body: `{"issues":["KEY-1","KEY-2"]}` |

## ADF (Atlassian Document Format)

Jira Cloud uses ADF for rich text fields (description, comments, blocked reason). When **posting** comments or creating issues with descriptions:

```json
{
  "body": {
    "version": 1,
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Your text here"}]}]
  }
}
```

When **reading** ADF from responses: recursively walk `content` arrays, extract `text` from `type: "text"` nodes. Handle: `marks` with `type: "link"` (append URL), `type: "mention"` (extract `attrs.text`), `type: "blockCard"/"inlineCard"` (extract `attrs.url`). Paragraphs, headings, list items end with newlines.

**Exception (node-cve):** the `node-cve` helper script lists, adds and edits
its triage comments through the REST API **v2** comment endpoints, which
accept and return wiki markup strings. That is limited to those comments. All
other workflows in this reference use v3 with ADF.

## Projects

| Project | Tracks |
|---------|--------|
| OCPNODE | Node team epics, stories, tasks, spikes |
| OCPBUGS | Cross-team bugs (filter by Node components) |
| RHOCPPRIO | Red Hat OpenShift Priority List (escalations) |
| OCPKUEUE | Kueue-specific work |
| OCPSTRAT | Strategy/feature tracking |

## Components We Own

See [shared/components.md](shared/components.md) for the full component list,
repo mappings, and sub-team assignments.

Prefer `filter = "Node Components"` (ID 91645) in JQL over hardcoding the
list.

## Boards & Sprints

| ID | Board |
|----|-------|
| 11478 | Node board (scrum) |
| 4383 | Node-Epics (kanban) |
| 9874 | Node QE (scrum) |

Sprint naming: `OCP Node Core Sprint N`, `OCP Node Devices Sprint N`, `OCP Kueue Sprint N`, `CNF Compute Sprint N`

Filter sprints to Node-related by checking if `"Node"`, `"Kueue"` or `"CNF Compute"` appears in the sprint name.

Team mailing list: `aos-node@redhat.com`

## Team Roster

Team member lists live in `~/.node-assistant/team-roster-{core,dra,kueue}.json`. Format:

```json
{
  "description": "Node Core team roster: maps Jira display names to GitHub handles",
  "members": {
    "Jira Display Name": "github-handle",
    "Another Person": "their-github-handle"
  }
}
```

Rosters hold Jira display names and GitHub handles only (no email addresses).

**Source of truth:** the canonical rosters are attached to the config issue
`OCPNODE-4230` (override with `$NODE_ASSISTANT_CONFIG_ISSUE`).
`/node-team:overview` syncs them into `~/.node-assistant/`; other commands
(for example `/node-bug:triage`) only read them. Sync steps, in one Bash
invocation together with the auth block above:

```bash
CONFIG_ISSUE="${NODE_ASSISTANT_CONFIG_ISSUE:-OCPNODE-4230}"
mkdir -p ~/.node-assistant
jira_curl "https://redhat.atlassian.net/rest/api/3/issue/${CONFIG_ISSUE}?fields=attachment" \
  | jq -r '.fields.attachment[] | select(.filename | test("^team-roster-[a-z]+\\.json$")) | [.filename, .content] | @tsv' \
  | while IFS=$'\t' read -r name url; do
      tmp=$(mktemp)
      if jira_curl -f -L -o "$tmp" "$url" && jq -e 'type == "object" or type == "array"' "$tmp" >/dev/null 2>&1; then
        mv "$tmp" "$HOME/.node-assistant/$name"
      else
        echo "WARNING: download of $name failed, keeping the existing file" >&2
        rm -f "$tmp"
      fi
    done
```

The attachment `content` URL needs the same authentication and redirects to
the media store, hence `-L`. Each file is downloaded to a temporary file and
only replaces the existing roster after the request succeeded (`-f` turns an
HTTP error into a non-zero exit) and the content validated as JSON, so an error
page (401, 429, media store failure) never destroys a good roster.

Use these to resolve display names for assignment, filter team activity, and exclude external CVE assignees.

Bot account treated as unassigned: `Node Team Bot Account`.

## Sub-teams

See the Sub-teams table in [shared/components.md](shared/components.md) for
sprint filters, roster files and bug components per sub-team.

## Custom Field IDs

Use field names in JQL, IDs in REST API calls:

| ID | Name | Notes |
|----|------|-------|
| `customfield_10014` | Epic Link | String key, e.g. `"OCPNODE-1234"` |
| `customfield_10011` | Epic Name | |
| `customfield_10020` | Sprint | Array of objects with `state` field (`active`/`closed`/`future`) |
| `customfield_10028` | Story Points | Number |
| `customfield_10001` | Team | |
| `customfield_10855` | Target Version | |
| `customfield_10840` | Severity | Object: `{"value": "Critical"}` |
| `customfield_10847` | Release Blocker | Object: `{"value": "Approved"}` or `{"value": "Proposed"}` |
| `customfield_10517` | Blocked | Object: `{"value": "True"}` or `{"value": "False"}` |
| `customfield_10483` | Blocked Reason | ADF document |
| `customfield_10689` | Customer Impact | Object: `{"value": "Customer Escalated"}` |
| `customfield_10978` | SFDC Cases Counter | Number |
| `customfield_10979` | SFDC Cases Links | |

## Saved Filters

Use in JQL via `filter = "Name"`:

| Name | ID | Scope |
|------|-----|-------|
| Node Components | 91645 | Component list |
| Node Bugs | 83963 | Node component bugs |
| Node Core Team | 66331 | Core team members |
| Node Epics | 96318 | OCPNODE epics |
| Node CR bugs | 94401 | Component regression bugs |

## Workflow Statuses

Bug lifecycle: NEW → To Do → ASSIGNED → POST → Modified → ON_QA → Verified → CLOSED/Done

Feature/epic: New → Planning → To Do → In Progress → Code Review → Review → Dev Complete → Done/Closed

Status grouping for dashboards: map `statusCategory` key `"done"` → done, status name `"Code Review"` → codeReview, `"MODIFIED"` → modified, `statusCategory` `"indeterminate"` → inProgress, `statusCategory` `"new"` → toDo, else → other.

## Key Field Meanings

| Field Value | Meaning |
|-------------|---------|
| Priority: Undefined | Untriaged, needs prioritization |
| Release Blocker: Proposed | Someone thinks this blocks the release |
| Release Blocker: Approved | Confirmed release blocker |
| SFDC Cases Counter (not empty) | Has linked support cases |

## Bug Triage Definitions

Build every query from the template `filter = "Node Bugs" AND (<clause>)`.
The parentheses are mandatory: without them the `OR` branches escape the Node
filter and match issues across all of Jira.

| Category | JQL Clause (already parenthesized) |
|----------|-----------|
| Untriaged | `(priority = Undefined OR "Release Blocker" = Proposed OR assignee in ("aos-node@redhat.com"))` |
| Blocker? | `("Release Blocker" = Proposed OR (priority = Blocker AND "Release Blocker" is EMPTY))` |
| Blocker+ | `("Release Blocker" = Approved OR priority = Blocker)` |
| Customer Issues | `("Customer Impact" = "Customer Escalated" OR "SFDC Cases Counter" is not EMPTY)` |
| CVE | `(labels in (SecurityTracking) OR issuetype in (Vulnerability, Weakness))` |
| CR | `(labels = component-regression)` |

Example: `filter = "Node Bugs" AND ("Release Blocker" = Approved OR priority = Blocker)`.

> The CVE row is for counting/bucketing only. For actual CVE triage with
> reachability analysis, deduplication, and reporting, use the `node-cve`
> plugin (`/node-cve:triage`) instead.

## Carryover Detection

Count closed sprints in `customfield_10020` array to detect carryovers:
```text
sprints_carried = count of items in customfield_10020 where state == "closed"
```

## External CVE Filtering

Exclude from bug counts: bugs with "CVE" in summary AND status "ASSIGNED" AND assignee not in team roster AND assignee != "Unassigned". These are handled by other teams.

## Gotchas

- Epic children: use `"Epic Link" = EPIC-KEY` in JQL (not `parentEpic`).
- `issueFunction` does **not exist** on Jira Cloud. Workaround: `watcher = currentUser() AND comment ~ "keyword"`.
- Always confirm with the user before any write operation (create, edit, comment, transition).
- Release Blocker and Blocked fields are objects (`{"value":"True"}`), not strings. Check shape before accessing `.value`.
- When listing sprints, filter to Node-relevant by checking if sprint name contains "Node", "Kueue" or "CNF Compute", then sort by `startDate` descending.
