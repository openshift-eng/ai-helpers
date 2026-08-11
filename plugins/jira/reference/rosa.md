# ROSA Conventions

Project-specific conventions for working with Jira issues in the ROSA and ROSAENG projects.

## When to Use

Use this file when:
- Creating or updating issues in the **ROSA** or **ROSAENG** projects
- Working with Features or Initiatives and their child execution work
- Running `/jira:update-weekly-status` for ROSA Features/Initiatives

## Project Information

| Field | Value |
|-------|-------|
| **ROSA Project Key** | ROSA |
| **ROSAENG Project Key** | ROSAENG |
| **Cloud Instance** | redhat.atlassian.net |
| **ROSA Issue Types** | Feature, Initiative, Risk |
| **ROSAENG Issue Types** | Epic, Story, Task, Sub-task, Spike, Bug, Risk, Vulnerability, Ticket |
| **Used By** | ROSA Product Management, Engineering Management, ~17 engineering teams |
| **Portfolio Plan** | [ROSA Portfolio Plan](https://issues.redhat.com/secure/PortfolioPlanView.jspa?id=3675&sid=3695&vid=16175#plan/backlog) |
| **Hygiene Dashboard** | [Features & Initiatives Hygiene](https://redhat.atlassian.net/jira/dashboards/21762) |

## Jira Hierarchy

```text
HPSTRAT       Outcome                          (strategic, multi-quarter)
                └── ROSA       Feature / Initiative      (release-scoped)
                                  └── ROSAENG    Epic                  (team execution)
                                                   ├── Story
                                                   ├── Task / Spike
                                                   ├── Bug / Vulnerability
                                                   └── Sub-task
```

- **Features** deliver value *to customers* — think release-notes line item.
- **Initiatives** deliver value *to Red Hat* — engineering-driven improvements (tech debt, tooling, infrastructure) with clear completion criteria.
- Both are parented under HPSTRAT Outcomes via the Parent Link field.
- Both parent Epics in the ROSAENG project.

Supplementary projects for specific workflows:
- **OCPBUGS** — Bug reports against OpenShift (ROSA HCP, OSD, ARO). See [OCPBUGS conventions](ocpbugs.md).
- **OHSS** — Customer-reported issues and incidents.

---

## ROSA Project (Features & Initiatives)

### Feature

A tangible customer-facing capability delivered in a release.

| Field | Required | Notes |
|-------|----------|-------|
| Summary | Yes | Clear, concise capability description |
| Description | Yes | Overview, Scope, Success Criteria |
| Assignee | Yes | Engineering Manager (default — accountable for technical execution) |
| Product Manager (`customfield_10469`) | Yes | PM accountable for customer value — listed in PM field, NOT Assignee |
| Architect (`customfield_10467`) | Yes | Technical lead for architectural direction |
| Priority | Yes | Blocker / Critical / Major / Minor / Trivial |
| Component | Yes | Functional area (e.g., "ROSA HyperFleet", "Clusters Service") |
| Security | Yes | `"Red Hat Employee"` |
| Parent Link | Yes | HPSTRAT Outcome key |

### Initiative

An engineering-driven improvement with clear completion criteria — not customer-facing.

Same fields as Feature. Initiatives and Features share a single ranked list in the [ROSA Portfolio Plan](https://issues.redhat.com/secure/PortfolioPlanView.jspa?id=3675&sid=3695&vid=16175#plan/backlog).

### Custom Fields (ROSA)

| Field | Custom Field ID | Usage | Format |
|-------|-----------------|-------|--------|
| Product Manager | `customfield_10469` | Single user — PM for the Feature | `{"accountId": "..."}` |
| Architect | `customfield_10467` | Single user — technical lead | `{"accountId": "..."}` |
| Activity Type | `customfield_10464` | Not required for Features/Initiatives | String value |
| Status Summary | `customfield_10814` | Weekly status narrative | Markdown text |
| Color Status | `customfield_10507` | On Track / At Risk / Off Track | `{"value": "On Track"}` |
| Blocked | `customfield_10517` | Whether the issue is blocked | `{"value": "True"}` |
| Blocked Reason | `customfield_10518` | Why it's blocked | Free text |
| Size | `customfield_10502` | T-shirt size per [HP sizing guide](https://docs.google.com/document/d/1WKXGPmBES3M6h3bfMSGRBqY3A2iTxM_dxi5Hac8W1qs/edit) | `{"value": "M"}` |
| Target Start | `customfield_10502` | Planned start date | `"YYYY-MM-DD"` |
| Target End | `customfield_10503` | Planned end date | `"YYYY-MM-DD"` |

### Feature & Initiative Workflow

```text
To Do → Refinement → Analysis → Backlog → In Progress → Release Pending → Closed
```

| Status | What Happens |
|--------|-------------|
| **To Do** | Reporter and Assignee (Engineering Manager) prepare the issue. Set Product Manager, Architect, description, priority, component. |
| **Refinement** | Review scope and acceptance criteria. |
| **Analysis** | Execute spikes if needed. Create ROSA Enhancement in GitHub. Generate Epics/Stories in ROSAENG. |
| **Backlog** | Ready for team assignment. Re-rank in Portfolio Plan if needed. Set Target Date. |
| **In Progress** | Active development. Weekly status updates in Status Summary. Set Color Status. |
| **Release Pending** | Verify acceptance criteria met. Prepare recorded demo. Close related Epics. |
| **Closed** | Delivered and complete. |

### Weekly Status Updates (`/jira:update-weekly-status`)

#### Status Summary Format

ROSA uses a **prepend** model — new updates go at the top, preserving history.

```text
{YYYY-MM-DD}: Color Status: {Green|Yellow|Red}
- {What happened this week}
- {Progress or blockers}
- Risks: {risk or "None at this time"}

```

**Rules:**
1. **Prepend, don't replace** — keep all previous entries intact
2. **Date stamp** each entry in `YYYY-MM-DD` format
3. **No duplication** — only include what changed since the last update
4. **Concise** — 2-4 bullets per update, one sentence per bullet

#### Updating via MCP

```javascript
editJiraIssue(
  cloudId: "redhat.atlassian.net",
  issueIdOrKey: "{ISSUE_KEY}",
  fields: {"customfield_10814": "{new_entry}\n\n{existing_text}"},
  contentFormat: "markdown"
)
```

Read the current value first, generate the new entry, prepend it with a blank line separator.

### Priority and Ranking

ROSA uses **positional rank** in the [Portfolio Plan](https://issues.redhat.com/secure/PortfolioPlanView.jspa?id=3675&sid=3695&vid=16175#plan/backlog) as the authoritative priority — not the Priority field. Items higher in the list are higher priority. Items above the **Ranked Line** have been actively prioritized.

Features and Initiatives share a single ranked list. To compare:
- Same list → higher position wins
- Both are Epics under different Features → compare parent Feature positions

Ranking is refined during the weekly Feature/Initiative Discovery meeting.

### MCP Tool Integration (ROSA)

Use `createJiraIssue` with `contentFormat: "markdown"`, project key `ROSA`:

```javascript
createJiraIssue(
  cloudId: "redhat.atlassian.net",
  projectKey: "ROSA",
  issueType: "Feature",
  summary: "Enhanced Observability for ROSA HCP",
  description: "Feature description...",
  security: {"name": "Red Hat Employee"},
  parent: "HPSTRAT-123",
  contentFormat: "markdown"
)
```

**Never set** `fixVersions` directly on ROSA issues unless coordinating a cross-project release plan.

---

## ROSAENG Project (Team Execution)

ROSAENG is the central execution project for all ROSA engineering teams. All Epics, Stories, Tasks, Bugs, and related work lives here.

### Workflow

All ROSAENG issue types follow the **OJA-WF-AG** workflow:

```text
New → Refinement → Backlog → In Progress → Review → Done
```

Teams choose which statuses to show on their boards.

### Required Fields

| Field | Required | Notes |
|-------|----------|-------|
| Security | Yes | `"Red Hat Employee"` |
| Activity Type (`customfield_10464`) | Yes | Values defined by [Sankey Capacity Allocation](https://docs.google.com/document/d/16Ooi8A_Qq-sK4epNT2rCpzjPeDk2_n0qEHOH2Cis-Zk/edit) |
| Team (`customfield_10001`) | Yes | Issues without Team are auto-closed after 30 days |
| Component | Strongly encouraged | Powers automation to auto-set the Team field |


### Custom Fields (ROSAENG)

| Field | Custom Field ID | Usage | Format |
|-------|-----------------|-------|--------|
| Team | `customfield_10001` | Mandatory — drives board routing, automation, reporting | UUID (see Team Directory) |
| Activity Type | `customfield_10464` | Mandatory — Sankey capacity categorization | String value |
| Story Points | `customfield_10028` | Strongly encouraged — Fibonacci scale | Float (e.g., `3.0`) |
| Epic Name | `customfield_10011` | Required for Epics — must match summary | String |
| Sprint | `customfield_10020` | Sprint assignment (Scrum teams) | Sprint object |
| Needs Info From | — | Triggers email notification to named person | User picker |
| Severity | — | Required for Bugs before leaving "New" | Critical / Important / Moderate / Low / Informational |
| Release Blocker | — | Flags bugs that block a release train | Proposed / Approved / Rejected |
| Regression | — | "Did this used to work?" — regressions get higher urgency | Yes / No |

### Components

Components in ROSAENG are synced from the [org repo component list](https://gitlab.cee.redhat.com/hybrid-platforms/org/-/tree/main/config/software/system/openshift/components). Key rules:

- **No component leads** — not all components are the same size
- **No default assignees** — routing is handled by the Team field + automation
- **Some components span multiple teams** (e.g., Clusters Service)
- To add a new component, it must first exist in the org repo — components are not created directly in Jira
- Do **not** create components for focus areas (Networking, CI/CD, Observability) — use Team, Activity Type, or Labels instead

### Team Directory

Each team has a dedicated board filtered by `project = ROSAENG AND Team = "[ROSA] <team>"`.

| Team | Board Type | Board ID | Jira Team ID |
|------|-----------|----------|-------------|
| AMS | scrum | 11887 | `971fb543-5d1b-4b9b-84f6-e70cb43e24b0` |
| Aurora | kanban | 11688 | `d82adfd4-85ef-442a-b3f7-1fb533082fdd` |
| CLI/Terraform | scrum | 11888 | `a23288d3-e663-4c68-8580-ce719fc78cfc` |
| Coffee | scrum | 11889 | `b1d72bb9-7e1c-4fc4-96f0-44eb3aebea7e` |
| FedRAMP Core | kanban | 11692 | `f9ad3210-48ec-40d0-b65a-068bc6f222f3` |
| Fleet Manager | kanban | 11693 | `bd8a0aae-863d-4ea3-a697-028b5043fc08` |
| Focaccia | scrum | 11890 | `461df7eb-f4e2-4492-84f4-b24ad53f3201` |
| GovCloud SRE | scrum | 11891 | `6c51c1cd-5997-4938-8bef-00cbb8168cd9` |
| HCP Platform | kanban | 11696 | `a5267ed5-eaa8-4cd6-90e3-d0ce145dbfbf` |
| Hulk | scrum | 11892 | `da409b64-3cdc-409c-939c-417b93001f22` |
| OSD GCP | scrum | 11893 | `1513346b-e10f-419a-925a-8da9e7e83369` |
| Operators | scrum | 11894 | `375bfc7d-06e7-492d-b1ca-f14d2e0145ea` |
| Orange | scrum | 11895 | `48d0de77-cfe4-424a-a34e-2800a9c44862` |
| Regionality | kanban | 5266 | `0c538cd9-152b-49f6-ad7c-e2fa2f865809` |
| Rocket | scrum | 11896 | `a0f44498-f22b-4cd4-a98f-f298cc375a94` |
| Service Lifecycle | scrum | 11897 | `16c10b5d-b9d1-4b9a-949d-39888ef9455a` |
| Thor | scrum | 11898 | `51fd486e-45a1-48de-955e-57899973d2b3` |

**JQL example:**
```jql
project = ROSAENG AND Team = "b1d72bb9-7e1c-4fc4-96f0-44eb3aebea7e" ORDER BY Rank ASC
```

The UI renders the friendly name (e.g., "[ROSA] Coffee") but JQL requires the UUID.

**Board URL pattern:**
```
https://redhat.atlassian.net/jira/software/c/projects/ROSAENG/boards/<BOARD_ID>
```

### Issue Type Details

#### Epic

Groups Stories, Tasks, and Bugs to show progress of a larger effort. Linked to ROSA Features or Initiatives via Parent Link.

- **Scope:** Larger than a sprint, smaller than a release
- **Sizing:** T-shirt sizes (S=2, M=3, L=4, XL=5)
- **Required:** Epic Name (`customfield_10011`) must match summary
- **Template:** Goal, acceptance criteria, open questions

#### Story

A description of a capability from the user's perspective. The smallest unit of end-user-facing work.

- **Scope:** Fits within a single sprint
- **Sizing:** Story points (Fibonacci)

#### Task

A unit of work that is not end-user facing. Good for follow-ups and action items.

- **Scope:** Fits within a single sprint
- **Sizing:** Story points (Fibonacci)

#### Spike

Time-boxed research. Produces decisions and future Stories, not deliverables.

- **Scope:** Fits within a single sprint
- **Description:** Questions to answer and decisions to make

#### Bug

An error, flaw, or fault in software. The primary signal for product quality health.

- **Scope:** Fits within a single sprint
- **Activity Type:** Must be "Quality / Stability / Reliability"
- **Triage gate** — before a Bug can leave "New" status, it must have:
  1. **Severity** — Critical / Important / Moderate / Low / Informational
  2. **Component** — what area of the product is affected
  3. **Team** — who owns it

**SLA targets:**

| Severity | Target to Close |
|----------|----------------|
| Critical | 21 days |
| Important | 30 days |
| Moderate / Low | Best effort, stale review at 60 days |

#### Vulnerability

Security issue (CVE) with mandatory SLA timelines — typically created by ProdSec.

- **Activity Type:** "Security & Compliance"
- **Due Date:** Pre-set by ProdSec SLA — non-negotiable
- **Priority:** Auto-set from CVSS score

**FedRAMP/GovCloud:** Monitor [PSHP project](https://redhat.atlassian.net/jira/software/c/projects/PSHP/summary) for issues labeled "ROSA-GovCloud". Triage via the [GovCloud SRE dashboard](https://redhat.atlassian.net/jira/dashboards/25817).

**General ROSA (ProdSec-opened):** ProdSec opens Vulnerability tickets directly in ROSAENG with summary format:
```text
[CVE Tracker ID] [Quay Image] [Vulnerable Package] [Description] [ProdSec Grouping]
```

### Triage and Routing

1. Issue is created (component set or unset)
2. If component is set, automation maps it to the correct Team
3. If Team is not set within 30 days, automation closes the issue

### MCP Tool Integration (ROSAENG)

#### Epic Creation

```javascript
createJiraIssue(
  cloudId: "redhat.atlassian.net",
  projectKey: "ROSAENG",
  issueType: "Epic",
  summary: "Implement API server monitoring improvements",
  description: "Epic description...",
  security: {"name": "Red Hat Employee"},
  parent: "ROSA-456",
  additional_fields: {
    "customfield_10011": "API Server Monitoring",
    "customfield_10464": {"value": "Product / Portfolio Work"},
    "customfield_10001": {"id": "<team-uuid>"}
  },
  contentFormat: "markdown"
)
```

#### Story/Task Creation

```javascript
createJiraIssue(
  cloudId: "redhat.atlassian.net",
  projectKey: "ROSAENG",
  issueType: "Story",
  summary: "Add retry logic to API client",
  description: "Story description...",
  security: {"name": "Red Hat Employee"},
  parent: "ROSAENG-123",
  additional_fields: {
    "customfield_10464": {"value": "Product / Portfolio Work"},
    "customfield_10001": {"id": "<team-uuid>"}
  },
  contentFormat: "markdown"
)
```

#### Bug Creation

```javascript
createJiraIssue(
  cloudId: "redhat.atlassian.net",
  projectKey: "ROSAENG",
  issueType: "Bug",
  summary: "API returns 500 on empty payload",
  description: "Bug description...",
  security: {"name": "Red Hat Employee"},
  parent: "ROSAENG-456",
  additional_fields: {
    "customfield_10464": {"value": "Quality / Stability / Reliability"},
    "customfield_10001": {"id": "<team-uuid>"}
  },
  contentFormat: "markdown"
)
```

---

## Related Conventions

- [OCPBUGS conventions](ocpbugs.md) — OpenShift bug reports
- [HyperShift conventions](hypershift.md) — HyperShift-specific component selection
