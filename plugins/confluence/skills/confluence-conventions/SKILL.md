---
name: Confluence Conventions
description: Best practices for Confluence space organization, page hierarchy, labeling, and content formatting
---

## When to Use This Skill

Invoke this skill when making decisions about where to place a page, how to label it, or how to structure content within a Confluence space. It provides organizational conventions that keep spaces navigable and content discoverable.

## Space Organization

### Space Key Conventions
- Space keys are short uppercase codes (e.g., `DEV`, `TEAM`, `OPS`)
- Use space keys that match team or project identifiers
- When the user doesn't specify a space, ask — do not guess

### Page Hierarchy Best Practices
- Keep hierarchy depth to 3 levels maximum (Space Root > Section > Page)
- Group related pages under section pages (e.g., "Design Documents", "Meeting Notes", "Runbooks")
- Use the `mcp__mcp-atlassian__confluence_get_space_page_tree` tool to understand existing structure before creating pages
- Place new pages alongside similar content, not at the space root

### Common Section Pages
When placing content, look for existing section pages:
- **"Design Documents"** or **"Architecture"** - for design docs and decision records
- **"Meeting Notes"** - for meeting notes (often organized by date or team)
- **"Runbooks"** or **"Operations"** - for operational procedures
- **"Feature Specifications"** or **"Requirements"** - for feature specs

If the expected section page doesn't exist, ask the user whether to create it or place the page at the root.

## Labeling Standards

### Label Format Rules
- Labels must be lowercase with no spaces
- Use hyphens to separate words (e.g., `design-doc`, not `design_doc`)
- Keep labels concise (1-3 words)

### Standard Labels by Content Type
| Content Type | Required Labels | Optional Labels |
|-------------|----------------|-----------------|
| Design Document | `design-doc` | component name, team name |
| Feature Spec | `feature-spec` | component name, version |
| Meeting Notes | `meeting-notes`, `meeting-YYYY-MM` | team name, meeting type |
| Runbook | `runbook` | service name, severity |
| Decision Record | `decision-record` | status (`accepted`, `proposed`) |

### Jira-Derived Labels
When creating pages from Jira issues:
- Convert Jira components to lowercase labels (e.g., "API Gateway" -> `api-gateway`)
- Convert Jira labels directly (they're already label-friendly)
- Add the project key as a label (e.g., `proj`, `ocpbugs`)

## Content Formatting

### Headings
- `#` (H1): Page title only — never use more than one H1
- `##` (H2): Main sections
- `###` (H3): Subsections
- Avoid H4 and deeper — restructure content instead

### Linking Best Practices
- Always link back to the source Jira issue in the first line
- Use inline links `[text](url)` for references
- When referencing other Confluence pages, use the page title

### Tables
- Use tables for structured data: action items, comparisons, field descriptions
- Always include a header row
- Keep tables under 8 columns for readability

### Callouts
- Use `> **Note:**` for informational callouts
- Use `> **Warning:**` for critical information
- Use `> **Decision:**` to highlight decisions in meeting notes

## Page Naming Conventions

### Title Patterns by Type
| Type | Pattern | Example |
|------|---------|---------|
| Design Doc | `<ISSUE-KEY>: <Title> - Design Document` | `PROJ-100: SSO - Design Document` |
| Feature Spec | `<ISSUE-KEY>: <Title>` | `PROJ-101: API Rate Limiting` |
| Meeting Notes | `<Meeting Type> - YYYY-MM-DD` | `Sprint 42 Grooming - 2026-05-07` |
| Runbook | `Runbook: <Procedure Name>` | `Runbook: Database Failover` |
| Decision Record | `ADR-<NNN>: <Decision Title>` | `ADR-001: Use PostgreSQL` |

### Title Rules
- Include the Jira issue key when the page is derived from a Jira issue
- Include the date for time-sensitive content (meetings, reviews)
- Avoid generic titles like "Notes" or "Document" without context
- Keep titles under 80 characters
