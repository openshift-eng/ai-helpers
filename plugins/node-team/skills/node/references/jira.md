# Node Team Jira Reference

Red Hat Jira: `redhat.atlassian.net`. REST API v3. Use `curl` directly —
this skill's workflows need endpoints the `jira` CLI doesn't cover (Agile
boards/sprints, attachment downloads, ADF bodies, custom-field writes), and
curl needs no extra install/config and keeps `allowed-tools` narrow
(`Bash(curl:*)`). The node-cve plugin uses the `jira` CLI for its simpler
list/comment flows; both hit the same REST API.

## Authentication

API token from env, macOS Keychain, or Linux secret-tool:

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
JIRA_USER="${JIRA_EMAIL:-$(security find-generic-password -s "JIRA_API_TOKEN" -g 2>&1 | grep acct | sed 's/.*="//;s/"//')}"
[[ "$JIRA_USER" != *@* ]] && JIRA_USER="${JIRA_USER}@redhat.com"
: "${JIRA_USER:=$(git config user.email)}"
```

All requests: `curl -s -u "$JIRA_USER:$JIRA_API_TOKEN" -H "Content-Type: application/json"`.

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

The canonical definition is the Jira saved filter **"Node Components"** (ID
91645). Prefer `filter = "Node Components"` in JQL over hardcoding the list.
The team additionally owns **Driver Toolkit** and **Machine Config Operator**
for CVE triage; those are not in filter 91645.

## Boards & Sprints

| ID | Board |
|----|-------|
| 11478 | Node board (scrum) |
| 4383 | Node-Epics (kanban) |
| 9874 | Node QE (scrum) |

Sprint naming: `OCP Node Core Sprint N`, `OCP Node Devices Sprint N`, `OCP Kueue Sprint N`, `CNF Compute Sprint N`

Filter sprints to Node-related by checking if `"Node"` or `"Kueue"` appears in the sprint name.

Team mailing list: `aos-node@redhat.com`

## Team Roster

Team member lists live in `~/.node-assistant/team-roster-{core,dra}.json`. Format:

```json
{
  "description": "Node Core team roster — maps Jira display names to GitHub handles",
  "members": {
    "Jira Display Name": "github-handle",
    "Another Person": "their-github-handle"
  }
}
```

**Source of truth:** the canonical rosters are attached to the config issue `OCPNODE-4230` (override with `$NODE_ASSISTANT_CONFIG_ISSUE`). Sync them into `~/.node-assistant/`:

1. `GET /rest/api/3/issue/OCPNODE-4230?fields=attachment` and select attachments whose filename matches `team-roster-*.json`.
2. Download each attachment's `content` URL to `~/.node-assistant/<filename>`.

Use these to resolve display names for assignment, filter team activity, and exclude external CVE assignees.

Bot account treated as unassigned: `Node Team Bot Account`.

## Sub-teams

| Team | Sprint filter | Roster file | Bug components |
|------|--------------|-------------|----------------|
| Core | `Node Core` | `team-roster-core.json` | All Node components |
| DRA/Devices | `Node Devices` | `team-roster-dra.json` | Node / Device Manage, Node / Instaslice-operator |
| Kueue | `OCP Kueue` | `team-roster-core.json` | Node / Kueue |

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
| Priority: Undefined | Untriaged — needs prioritization |
| Release Blocker: Proposed | Someone thinks this blocks the release |
| Release Blocker: Approved | Confirmed release blocker |
| SFDC Cases Counter (not empty) | Has linked support cases |

## Bug Triage Definitions

Base all queries on `filter = "Node Bugs"` and append:

| Category | JQL Clause |
|----------|-----------|
| Untriaged | `priority = Undefined OR "Release Blocker" = Proposed OR assignee in ("aos-node@redhat.com")` |
| Blocker? | `"Release Blocker" = Proposed OR priority = Blocker AND "Release Blocker" is EMPTY` |
| Blocker+ | `"Release Blocker" = Approved OR priority = Blocker` |
| Customer Issues | `"Customer Impact" = "Customer Escalated" OR "SFDC Cases Counter" is not EMPTY` |
| CVE | `labels in (SecurityTracking) OR issuetype in (Vulnerability, Weakness)` |
| CR | `labels = component-regression` |

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
- When listing sprints, filter to Node-relevant by checking if sprint name contains "Node" or "Kueue", then sort by `startDate` descending.
