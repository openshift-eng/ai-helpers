---
description: Generate a structured Confluence page from a Jira epic or story
argument-hint: "<issue-key> [--space <key>] [--parent-id <id>] [--type design-doc|feature-spec|runbook]"
---

## Name
confluence:create-from-jira

## Synopsis
```
/confluence:create-from-jira <issue-key> [--space <key>] [--parent-id <id>] [--type design-doc|feature-spec|runbook]
```

## Description
The `confluence:create-from-jira` command reads a Jira epic, story, or feature request and generates a well-structured Confluence page from it. It analyzes the issue's summary, description, acceptance criteria, linked issues, comments, and child issues to produce a comprehensive document — not a shallow copy of the Jira fields.

This command requires AI reasoning to:
- Decide which page template best fits the issue (design doc, feature spec, runbook, or decision record)
- Synthesize information scattered across linked issues and comments into a coherent narrative
- Identify gaps in the Jira issue and flag them as open questions in the generated page
- Structure the page hierarchy appropriately within the target Confluence space

## Key Features
- Automatically selects a page template based on issue type and content (or uses `--type` override)
- Fetches and incorporates context from linked/child issues
- Extracts action items and open questions from comments
- Adds labels based on Jira components and labels
- Links the generated page back to the source Jira issue

## Implementation

### Phase 1: Load Skills
Invoke the `confluence:page-templates` skill to load page structure guidance for the selected document type.

### Phase 2: Fetch Jira Context
1. Fetch the primary issue using `mcp__mcp-atlassian__jira_get_issue`:
   ```python
   mcp__mcp-atlassian__jira_get_issue(
       issue_key="<issue-key>",
       fields="summary,description,status,issuetype,components,labels,priority,assignee,reporter,created,updated",
       comment_limit=20
   )
   ```
2. If the issue is an Epic, fetch child issues:
   ```python
   mcp__mcp-atlassian__jira_search(
       jql="parent = <issue-key> ORDER BY rank ASC",
       fields="summary,status,issuetype,assignee,description",
       limit=50
   )
   ```
3. Fetch linked issues if present (from the issue's links field).

### Phase 3: Determine Page Type
If `--type` is provided, use it directly. Otherwise, analyze the issue to select:
- **Epic with multiple stories** -> `design-doc`
- **Story with acceptance criteria** -> `feature-spec`
- **Bug or incident-related** -> `runbook`
- **Decision or spike** -> `decision-record`

Ask the user to confirm the selected type before proceeding.

### Phase 4: Resolve Target Space and Parent
1. If `--space` is provided, use it. Otherwise, ask the user which space to publish to.
2. If `--parent-id` is provided, use it. Otherwise:
   - Use `mcp__mcp-atlassian__confluence_get_space_page_tree` to show the space structure
   - Ask the user to select a parent page or publish at the root

### Phase 5: Generate Page Content
Using the loaded template from Phase 1 and the Jira context from Phase 2:
1. Generate a page title from the Jira summary (prefix with issue key for traceability)
2. Compose the page body in Markdown format with appropriate sections
3. Include a "Source" section at the bottom linking back to the Jira issue
4. Include an "Open Questions" section for any gaps identified during analysis
5. Present the generated content to the user for review before publishing

### Phase 6: Publish to Confluence
1. Create the page:
   ```python
   mcp__mcp-atlassian__confluence_create_page(
       space_key="<space>",
       title="<generated-title>",
       content="<generated-markdown>",
       parent_id="<parent-id>",  # optional
       content_format="markdown"
   )
   ```
2. Add labels derived from Jira components and labels:
   ```python
   mcp__mcp-atlassian__confluence_add_label(
       page_id="<created-page-id>",
       name="<label>"
   )
   ```
3. Report the created page URL and ID to the user.

## Usage Examples

1. **Generate a design doc from an Epic:**
   ```
   /confluence:create-from-jira PROJ-100 --space DEV --type design-doc
   ```

2. **Auto-detect type, ask for space interactively:**
   ```
   /confluence:create-from-jira OCPBUGS-1234
   ```

3. **Create under a specific parent page:**
   ```
   /confluence:create-from-jira FEAT-50 --space TEAM --parent-id 123456789
   ```

## Arguments
| Argument | Required | Description |
|----------|----------|-------------|
| `<issue-key>` | Yes | Jira issue key (e.g., `PROJ-123`, `OCPBUGS-456`) |
| `--space <key>` | No | Target Confluence space key. If omitted, the user is prompted. |
| `--parent-id <id>` | No | Parent page ID. If omitted, the user chooses from the space tree. |
| `--type <type>` | No | Page template type: `design-doc`, `feature-spec`, `runbook`, or `decision-record`. Auto-detected if omitted. |

## Return Value
- The created Confluence page URL
- The page ID for future reference
- A summary of what was generated (title, template used, labels applied)

## Error Handling
| Error | Cause | Resolution |
|-------|-------|------------|
| Jira issue not found | Invalid issue key or no access | Verify the issue key and Jira authentication |
| Space not found | Invalid space key | List available spaces and ask user to choose |
| Permission denied | No write access to the target space | Ask user to specify a different space or check permissions |
| Page title conflict | A page with the same title already exists in the space | Offer to update the existing page or append a suffix |

## See Also
- `confluence:search` - Find existing docs before creating new ones
- `confluence:sync-meeting-notes` - Publish meeting notes to Confluence
- `jira:create` - Create Jira issues
- `jira:grooming` - Generate grooming agendas (output can be synced to Confluence)
