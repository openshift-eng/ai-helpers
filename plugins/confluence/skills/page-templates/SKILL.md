---
name: Page Templates
description: Structured templates for common Confluence page types including design docs, feature specs, meeting notes, runbooks, and decision records
---

## When to Use This Skill

Invoke this skill when generating Confluence page content through the `confluence:create-from-jira` or `confluence:sync-meeting-notes` commands. It provides the structural skeleton for each page type so that generated pages are consistent and complete.

## Templates

### Design Document

Use for Epics, large features, or architectural changes that span multiple stories.

**Required sections:**
- **Overview** - One-paragraph summary of what is being designed and why
- **Goals and Non-Goals** - Explicit scope boundaries
- **Background** - Context and motivation (derived from Jira epic description)
- **Proposed Design** - Technical approach, architecture, key decisions
- **Alternatives Considered** - Other approaches and why they were rejected
- **Open Questions** - Unresolved items needing input (derived from Jira comments)

**Optional sections:**
- **Dependencies** - External teams, services, or upstream changes required
- **Rollout Plan** - Phased delivery strategy (derived from child stories)
- **Testing Strategy** - How the design will be validated
- **References** - Links to related Jira issues, PRs, existing docs

**Labels:** `design-doc`, component name from Jira

---

### Feature Specification

Use for individual stories or feature requests with clear acceptance criteria.

**Required sections:**
- **Summary** - What the feature does in user-facing terms
- **User Stories** - Who benefits and how (derived from Jira story description)
- **Acceptance Criteria** - Conditions for completion (extracted from Jira)
- **Technical Approach** - Implementation strategy
- **UI/UX** - User interface changes if applicable

**Optional sections:**
- **Edge Cases** - Boundary conditions and error scenarios
- **Performance Considerations** - Expected load, latency requirements
- **Security Considerations** - Authentication, authorization, data handling
- **References** - Links to related issues and docs

**Labels:** `feature-spec`, component name from Jira

---

### Meeting Notes

Use for grooming sessions, architecture reviews, standups, and team meetings.

**Required sections:**
- **Meeting Info** - Date, attendees, facilitator
- **Agenda** - Topics discussed (numbered list)
- **Discussion** - Key points per agenda item
- **Decisions** - Outcomes agreed upon (bulleted, each with owner)
- **Action Items** - Tasks with owner and due date (table format)

**Optional sections:**
- **Open Questions** - Items deferred to future meetings
- **Parking Lot** - Topics raised but not discussed
- **Next Meeting** - Date and preliminary agenda

**Action items table format:**
```markdown
| # | Action Item | Owner | Due Date | Status |
|---|------------|-------|----------|--------|
| 1 | Description | @name | YYYY-MM-DD | Open |
```

**Labels:** `meeting-notes`, `meeting-YYYY-MM` (date-based)

---

### Runbook

Use for operational procedures, incident response, or troubleshooting guides.

**Required sections:**
- **Purpose** - What this runbook addresses
- **Prerequisites** - Required access, tools, permissions
- **Symptoms** - How to identify the problem this runbook solves
- **Steps** - Numbered procedural steps with expected output at each step
- **Verification** - How to confirm the issue is resolved
- **Escalation** - Who to contact if the runbook doesn't resolve the issue

**Optional sections:**
- **Common Pitfalls** - Mistakes to avoid during execution
- **Related Alerts** - Monitoring alerts that trigger this runbook
- **History** - Past incidents where this runbook was used

**Labels:** `runbook`, component or service name

---

### Decision Record

Use for spikes, trade-off analyses, or technical decisions that need documentation.

**Required sections:**
- **Status** - Proposed, Accepted, Deprecated, or Superseded
- **Context** - What prompted this decision
- **Decision** - What was decided
- **Consequences** - Expected positive and negative outcomes
- **Alternatives** - Options considered with pros/cons

**Optional sections:**
- **Participants** - Who was involved in the decision
- **Review Date** - When to revisit this decision
- **References** - Related decisions, docs, or issues

**Labels:** `decision-record`, `adr`

## Formatting Guidelines

- Use Markdown format (`content_format="markdown"`) for all pages
- Use `##` for main sections, `###` for subsections
- Use tables for structured data (action items, comparisons, field lists)
- Use blockquotes (`>`) for callouts and important notes
- Include a horizontal rule (`---`) before the References section
- Always include the Jira issue key in the first line as a link back to the source

## Examples

### Example 1: Design Doc from Epic

Given an Epic "PROJ-100: Implement SSO for Admin Console" with 5 child stories:

```markdown
# PROJ-100: SSO for Admin Console - Design Document

> Source: [PROJ-100](https://jira.example.com/browse/PROJ-100)

## Overview
This document describes the design for adding Single Sign-On (SSO) support
to the Admin Console, replacing the current username/password authentication.

## Goals and Non-Goals
**Goals:**
- Support SAML 2.0 and OIDC identity providers
- Maintain backward compatibility with existing sessions

**Non-Goals:**
- Multi-factor authentication (tracked separately in PROJ-200)
...
```

### Example 2: Meeting Notes from Grooming

```markdown
# Sprint 42 Grooming - 2026-05-07

## Meeting Info
- **Date:** 2026-05-07
- **Attendees:** Alice, Bob, Carol
- **Facilitator:** Alice

## Agenda
1. Review PROJ-101: API rate limiting
2. Estimate PROJ-102: Dashboard redesign
3. Backlog prioritization

## Decisions
- PROJ-101 will use token bucket algorithm (decided by team consensus)
- PROJ-102 deferred to next sprint due to missing UX mocks

## Action Items
| # | Action Item | Owner | Due Date | Status |
|---|------------|-------|----------|--------|
| 1 | Create UX mockups for PROJ-102 | Carol | 2026-05-14 | Open |
| 2 | Spike on rate limiting libraries | Bob | 2026-05-09 | Open |
```
