---
description: Publish meeting notes or agendas to Confluence with structured formatting
argument-hint: "<space-key> <title> [--parent-id <id>] [--update <page-id>]"
---

## Name
confluence:sync-meeting-notes

## Synopsis
```
/confluence:sync-meeting-notes <space-key> <title> [--parent-id <id>] [--update <page-id>]
```

## Description
The `confluence:sync-meeting-notes` command takes meeting context — a Jira grooming agenda, raw notes from the current conversation, or a file — and publishes it as a well-structured Confluence page. It transforms unstructured or semi-structured content into a proper meeting notes page with attendees, discussion topics, decisions, and action items.

This command requires AI reasoning to:
- Parse and restructure raw meeting content into a standard format
- Extract action items, decisions, and owners from unstructured notes
- Identify and tag attendees mentioned in the content
- Decide whether to create a new page or update an existing one
- Apply appropriate labels and page hierarchy

## Key Features
- Transforms raw notes, grooming agendas, or conversation context into structured meeting pages
- Extracts action items with owners and due dates
- Extracts key decisions made during the meeting
- Supports creating new pages or updating existing ones (`--update`)
- Applies date-based labels for easy filtering (e.g., `meeting-2026-05`)
- Works with output from `jira:grooming` and `agendas:outcome-refinement`

## Implementation

### Phase 1: Load Skills
Invoke the `confluence:page-templates` skill to load the meeting notes template structure.

### Phase 2: Gather Meeting Content
Determine the content source:
1. **Conversation context** (default): Look at the current conversation for meeting notes, grooming output, or agenda content that was generated earlier in the session.
2. **User provides content**: If no meeting content is found in context, ask the user to paste or describe the meeting notes.

### Phase 3: Parse and Structure Content
Using AI analysis, extract from the raw content:
- **Meeting title and date** (from `<title>` argument and current date)
- **Attendees** (names mentioned in the notes)
- **Agenda items / Discussion topics** (main sections)
- **Decisions made** (statements indicating agreement or resolution)
- **Action items** (tasks with owners, identified by patterns like "AI:", "@name will...", "TODO:")
- **Open questions** (unresolved items for follow-up)

Present the structured content to the user for review before publishing.

### Phase 4: Resolve Target Location
1. Use `<space-key>` as the target space.
2. If `--parent-id` is provided, use it as the parent page.
3. If not, search for a common meeting notes parent page:
   ```python
   mcp__mcp-atlassian__confluence_search(
       query="title = \"Meeting Notes\" AND space = \"<space-key>\"",
       limit=5
   )
   ```
4. If a meeting notes parent is found, suggest it. Otherwise, ask the user.

### Phase 5: Publish or Update
**Creating a new page:**
```python
mcp__mcp-atlassian__confluence_create_page(
    space_key="<space-key>",
    title="<title>",
    content="<structured-markdown>",
    parent_id="<parent-id>",
    content_format="markdown"
)
```

**Updating an existing page** (when `--update` is provided):
```python
mcp__mcp-atlassian__confluence_get_page(page_id="<page-id>")
# Use the existing title unless user provides a new one
mcp__mcp-atlassian__confluence_update_page(
    page_id="<page-id>",
    title="<title>",
    content="<structured-markdown>",
    content_format="markdown"
)
```

### Phase 6: Apply Labels and Report
1. Add date-based label:
   ```python
   mcp__mcp-atlassian__confluence_add_label(
       page_id="<page-id>",
       name="meeting-2026-05"
   )
   ```
2. Add a `meeting-notes` label for discoverability.
3. Report the page URL and summary of extracted items (action count, decision count).

## Usage Examples

1. **Publish grooming notes after running `/jira:grooming`:**
   ```
   /jira:grooming PROJ sprint-42
   /confluence:sync-meeting-notes TEAM "Sprint 42 Grooming - 2026-05-07"
   ```

2. **Create meeting notes under a specific parent:**
   ```
   /confluence:sync-meeting-notes DEV "Architecture Review - 2026-05-07" --parent-id 123456789
   ```

3. **Update an existing meeting page with new notes:**
   ```
   /confluence:sync-meeting-notes TEAM "Weekly Standup" --update 987654321
   ```

## Arguments
| Argument | Required | Description |
|----------|----------|-------------|
| `<space-key>` | Yes | Target Confluence space key (e.g., `TEAM`, `DEV`) |
| `<title>` | Yes | Page title for the meeting notes |
| `--parent-id <id>` | No | Parent page ID. Auto-detected if a "Meeting Notes" parent exists. |
| `--update <page-id>` | No | Page ID to update instead of creating a new page |

## Return Value
- The created or updated Confluence page URL
- Count of extracted action items, decisions, and attendees
- Labels applied to the page

## Error Handling
| Error | Cause | Resolution |
|-------|-------|------------|
| No meeting content found | No notes in conversation context | Ask user to paste or describe the meeting content |
| Space not found | Invalid space key | List available spaces for the user to choose |
| Page not found for update | Invalid `--update` page ID | Verify the page ID and suggest creating a new page instead |
| Title conflict | Page with same title exists in the space | Offer to update the existing page or use a different title |

## See Also
- `confluence:create-from-jira` - Generate documentation from Jira issues
- `confluence:search` - Find existing meeting notes pages
- `jira:grooming` - Generate grooming agendas (output works as input here)
- `agendas:outcome-refinement` - Generate outcome refinement agendas
