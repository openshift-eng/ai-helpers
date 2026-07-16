# GCP HCP Conventions

Team-specific conventions for GCP HCP (Hypershift on GKE) issues in the GCP project.

## Project Information

| Field | Value |
|-------|-------|
| **Project Key** | GCP |
| **Project Name** | GCP Hosted Control Planes (Hypershift on GKE) |
| **Issue Types** | Story, Epic, Task, Bug, Feature, Initiative, Feature Request |

## Custom Fields

| Field | Custom Field ID | Usage | Example |
|-------|-----------------|-------|---------|
| **Epic Name** | `customfield_10011` | Required for Epics | `"Multi-cluster metrics aggregation"` |
| **Story Points** | `customfield_10028` | Fibonacci scale: 0, 1, 2, 3, 5, 8, 13 | `3.0` |
| **Blocked** | `customfield_10517` | Mark issue as blocked | `{"value": "True"}` |

## Components

| Component | Usage |
|-----------|-------|
| `hypershift-operator-gcp` | HyperShift operator, control plane components |
| `gcp-hcp-automation` | Terraform, ArgoCD, infrastructure automation |
| `gcp-api-gateway` | API gateway work |
| `Retrospective action items` | Team retrospective tracking |

Components are **optional** — only specify if work clearly fits. Do not request new components.

## MCP Custom Fields by Issue Type

| Issue Type | Key Fields |
|---|---|
| Story / Task | `customfield_10028` (Story Points): float, auto-estimated per Sizing Guide; `priority`: `{"name": "Normal"}` (omit unless user specifies) |
| Epic | `customfield_10011` (Epic Name): must match summary |
| Feature | No type-specific custom fields required |
| Initiative | No type-specific custom fields required |

**Story Points:** Auto-estimate using the Sizing Guide below. Set `customfield_10028` as float. For estimates of 8+, recommend splitting.

**Priority:** Ask user before setting. Reference the Priority Scheme below. If unset, default is Normal.

## Team Standards

**All GCP project issues MUST conform to these templates.**

### Story Template

Source: [jira-story-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-story-template.md)

#### User Story

**As a** [platform user/developer/operations team/end user]
**I want** [goal/desire],
**so that** [benefit/reason].

#### Context / Background

[Current state, problem being solved, relevant history, links to related tickets/incidents]

#### Requirements

[Functional and non-functional requirements (performance, scalability, reliability, SLOs, compliance)]

#### Technical Approach

[Proposed solution, technologies/tools, major steps, alternatives considered]

#### Dependencies

[Blocking items: other teams/stories, external vendors, infrastructure/access needs, required approvals]

#### Acceptance Criteria

- [ ] [Specific testable outcome 1]
- [ ] [Specific testable outcome 2]
- [ ] [Specific testable outcome 3]

### Story Sizing Guide

| Points | Description |
|--------|-------------|
| **0** | Trivial task with stakeholder value but less risk/complexity than a 1-pointer |
| **1** | Smallest issue possible. One-line change, no risk, very low effort/complexity |
| **2** | Simple, well-understood change. Low risk, slightly more effort than 1 |
| **3** | Not necessarily complex but time consuming. Fairly straightforward, minor risks |
| **5** | Requires investigation, design, collaboration. Can be time consuming or complex. Risks involved |
| **8** | Big task. Requires investigation, design, collaboration. Challenging solution. Design doc required. **Consider splitting** |
| **13** | **Must be split into smaller stories** |

#### Story Point Examples (GCP HCP Context)

**1 Point**: Add env var to deployment, update GKE node pool version in terraform, fix API docs typo, add simple validation check

**2 Points**: New Prometheus metric for CPU usage, retry logic with exponential backoff, simple e2e test, update RBAC rules

**3 Points**: Health checks for all management cluster components, automated cleanup of orphaned GCP resources, refactor to structured logging, GCP service account impersonation

**5 Points**: New controller for GCP firewall rules, CMEK support for storage, automated backup/restore for management cluster, operator migration in-cluster → out-of-cluster

**8 Points (split)**: Full observability stack, VPC-native GKE clusters with IP aliasing and network policies, full CI/CD pipeline migration

#### When to Split Stories

**By scope**: >5 AC, >3 components/repos, contains both spike AND implementation, internal sequencing

**By layer**: API + controller + CLI → 3 stories; backend + frontend + docs → 3 stories

**By workflow**: CRUD operations → separate stories

**By component**: Changes across multiple operators → 1 story per operator

**By risk**: Separate PoC spike from production implementation

### Task Template

Source: [jira-task-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-task-template.md)

A finite piece of work. Great for post-meeting follow-ups and action items. Fits within a single sprint.

**Use a Task for:** Post-meeting follow-ups, finite work within a sprint, specific well-scoped items

**Use a Story instead for:** User-facing features requiring "As a... I want... so that..." format

Sections: Context/Background, Requirements, Technical Approach, Dependencies, Acceptance Criteria

### Epic Template

Source: [jira-epic-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-epic-template.md)

Epics represent a cohesive chunk of work within a Feature, typically 1-2 sprints, decomposing into multiple Stories.

**Hierarchy**: Feature → **Epic** → Story

**Title format**: [Action Verb] + [Specific Capability or Component]

Sections: Use Case/Context, Current State, Desired State/Goal, Scope (included + out of scope), Technical Details (optional), Dependencies, Story Breakdown Checklist, Acceptance Criteria, Metadata (Feature, Assignee, Priority, Sprint Target, Size Estimate)

### Feature Template

Source: [jira-feature-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-feature-template.md)

Features represent high-level capabilities spanning multiple sprints, decomposing into multiple Epics and Stories.

**Title format**: [Action Verb] + [Capability]

Sections: Context, Scope (included + not included), Technical Approach (optional), Dependencies, Acceptance Criteria, Metadata (Epics, Priority, Demo Critical, Size Estimate, DRI)

### Initiative Template

Source: [jira-initiative-template.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/jira-initiative-template.md)

Initiatives represent internal/architectural work at the same hierarchy as Features — non-customer-facing. Use for architectural improvements, process improvements, and engineering enablement.

**Hierarchy**: Outcome → **Initiative** → Epic → Story

**Title format**: [Action Verb] + [Capability]

Sections: Problem Statement, Proposed Approach, Internal Impact, Success Criteria, Scope and Epics, Timeline and Milestones, plus project-specific metadata

### Definition of Done

Source: [definition-of-done.md](https://github.com/openshift-online/gcp-hcp/blob/main/docs/definition-of-done.md)

#### Story DoD

1. Satisfies all acceptance criteria
2. Test automation: unit ≥85% coverage, integration tests, e2e tests — all passing
3. PR merged
4. AI-Assisted Development guidelines followed (commit conventions)
5. Architecture/design doc PR merged
6. Deployment to stage (when available)
7. Demo-able for end of sprint

#### Spike DoD

1. Findings documented
2. Decision documented in architecture docs
3. Resulting backlog items created

#### Bug DoD

1. Automated test verifying the fix (or documented why not feasible)
2. Root cause documented in PR description
3. All tests pass, no regressions
4. At least one code review approval
5. Link to merged PR added to bug ticket

### Priority Scheme (OJA-PRIS-001)

| Priority | Description |
|----------|-------------|
| **Blocker** | Work above all other priorities. Very high severity, no workaround, or low effort to fix. May generate significant media attention |
| **Critical** | Must do. Work immediately after Blocker issues |
| **Major** | Should do. High severity, low-to-moderate effort. Existing workaround but non-trivial implementation |
| **Normal** | Could do. Severity roughly matches effort. Easily implemented workaround may exist |
| **Minor** | Won't do until higher priorities resolved. Low severity or high effort. Known workarounds exist |
| **Undefined** | Not yet evaluated by the team |

<!-- maintainer notes — not used by the LLM during issue creation -->

## Maintenance

Sections of this reference file are sourced from upstream files in openshift-online/gcp-hcp.

### Upstream Sources

| Section | Upstream File |
|---------|---------------|
| Story Template + Sizing Guide | docs/jira-story-template.md |
| Task Template | docs/jira-task-template.md |
| Epic Template | docs/jira-epic-template.md |
| Feature Template | docs/jira-feature-template.md |
| Initiative Template | docs/jira-initiative-template.md |
| Definition of Done | docs/definition-of-done.md |
| Priority Scheme (OJA-PRIS-001) | Red Hat internal (team-agnostic) |

### Sync Instructions

1. Fetch latest from each upstream file at `https://raw.githubusercontent.com/openshift-online/gcp-hcp/main/docs/<file>`
2. Compare against embedded content
3. Update with changes
4. Run `make lint` to validate

### Intentional Omissions

- Feature Template worked example — focused on structure, not filled-in examples
- Epic Template worked example — same reason

## Related Conventions

- [HyperShift conventions](hypershift.md) — HyperShift on AWS/Azure
