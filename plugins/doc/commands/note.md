---
description: Generate professional engineering notes and append them to a log file
argument-hint: "[task description]"
---

## Name
doc:note

## Synopsis
```
/doc:note [task description]
```

## Description
The `doc:note` command generates professional engineering notes about completed tasks and appends them to a persistent log file (`~/engineering-notes.md`). It automatically searches for relevant context including GitHub PR URLs, issue numbers, and Jira ticket references in the conversation history and git repository.

This command helps engineers maintain a structured record of their daily work, making it easier to:
- Track accomplishments for performance reviews
- Generate status reports and weekly updates
- Maintain a searchable history of technical decisions
- Document completed work with proper attribution

## Implementation
The command performs the following steps:
1. **Context gathering**: Searches conversation history for GitHub PR URLs, issue numbers, or Jira ticket keys (e.g., PROJ-123)
2. **Git analysis**: If in a git repository, checks recent commits and current branch name for references
3. **Note generation**: Creates a 1-2 sentence note with:
   - Today's date in YYYY-MM-DD format
   - Accomplishment framed in past tense
   - Technical details and specific technologies used
   - Impact and value delivered
   - All relevant links inline
4. **File management**: Appends the note to `~/engineering-notes.md` (creates file if it doesn't exist) with proper spacing

If the task description argument is omitted, the command will attempt to discover a task description from relevant context (e.g. git repository status and conversation history). If no relevant context is discovered, or if more information is needed, the command will prompt for further context.

## Return Value
- **Success**: Confirmation message with the generated note
- **File created**: `~/engineering-notes.md` (if it didn't exist)
- **File updated**: Note appended with blank line separator

## Examples

1. **Basic usage with task description**:
   ```
   /doc:note Implemented user authentication with OAuth2
   ```
   Generates:
   ```
   2025-10-24 - Implemented user authentication using OAuth2. Integrated with Google and GitHub providers, added JWT token management, and secured API endpoints with role-based access control.

   ```

2. **Without task description (auto-discovers from context)**:
   ```
   /doc:note
   ```
   The command analyzes git repository and conversation history to generate a note. If insufficient context is available, it will prompt for details.

3. **With git context**:
   ```
   /doc:note Fixed critical bug in payment processor
   ```
   If on a branch named `fix/payment-timeout` with recent commits, generates:
   ```
   2025-10-24 - Fixed critical timeout bug in payment processor (PR #123). Optimized database queries and added connection pooling, reducing payment processing time by 60% and eliminating timeout errors.

   ```

## Arguments
- `[task description]`: Optional description of the completed task. If omitted, the command attempts to discover context automatically.
