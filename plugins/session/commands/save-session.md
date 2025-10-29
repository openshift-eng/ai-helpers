---
description: Save current conversation session to markdown file for future continuation
argument-hint: [optional-description]
---

## Name
session:save-session

## Synopsis

```
/save-session
/save-session [description]
```

## Description

Saves the current conversation session to a comprehensive markdown file that enables seamless resumption of work after extended time intervals (days, weeks, or months).

This command addresses limitations of Claude Code's built-in session management by capturing:
- Complete conversation context and technical rationale
- Detailed file modification tracking with line numbers
- Key technical decisions and alternatives considered
- Commands executed during the session
- Clear resumption instructions

The generated session file is designed for engineers working across multiple projects with long gaps between sessions, providing all necessary context to continue work without losing momentum.

## Implementation

The command follows a five-phase process:

### Phase 0: Input Sanitization
If a description argument is provided, sanitize it for safe filename usage:
- Convert all spaces to hyphens
- Convert to lowercase
- Remove or replace special characters (keep only alphanumeric, hyphens, and underscores)
- Truncate to 100 characters maximum if longer
- Example: "investigating OCPBUGS-12345 regarding routes" → "investigating-ocpbugs-12345-regarding-routes"

### Phase 1: Context Analysis
- Summarizes main topics and goals discussed
- Lists all accomplishments and completed tasks
- Identifies all files that were read, modified, or created
- Extracts important technical decisions and their rationale
- Captures any error messages encountered and how they were resolved
- Notes any commands that were run (make, linter, tests, etc.)

### Phase 2: File Modification Tracking
- Reads and verifies current state of modified files
- Lists specific line numbers and code changes
- Includes before/after comparisons for critical changes
- Notes which files were created vs modified vs deleted
- Tracks any generated files (like bindata)

### Phase 3: Session File Creation
Creates a comprehensive markdown document with these sections:

1. **Session Summary** - Brief 1-2 paragraph overview
2. **Current State** - Status of work and modifications
3. **Accomplishments** - Detailed completion checklist
4. **Files Modified** - Organized by Created/Modified/Deleted
5. **Key Technical Decisions** - Rationale and implications
6. **Pending Tasks** - Unfinished work (checkbox format)
7. **Commands Used** - All executed commands
8. **Context for Resumption** - Critical continuation information
9. **Full Conversation Summary** - Key discussion points
10. **Next Steps** - Clear action items
11. **How to Resume This Session** - Step-by-step guide

### Phase 4: Verification and Output
- Confirms file was created successfully
- Displays file path and size
- Provides brief summary of what was saved
- Shows resumption instructions in terminal and saved file

## Return Value

Creates a markdown file in the repository root directory with filename:
- `session-YYYY-MM-DD-HHMM.md` (without description)
- `session-YYYY-MM-DD-<description>.md` (with custom description)

Terminal output:
```
✅ Session saved successfully!

File: session-YYYY-MM-DD-description.md (XX KB)
Location: /full/path/to/file

📖 To resume this session:
   Please read `/full/path/to/session-YYYY-MM-DD-description.md` and continue from where we left off
```

## Examples

**Basic usage with auto-generated timestamp:**
```
/save-session
```
Creates: `session-2025-10-16-1430.md`

**With custom description for easy identification:**
```
/save-session parallel-test-fixes
```
Creates: `session-2025-10-16-parallel-test-fixes.md`

**Multiple sessions in one project:**
```
/save-session initial-implementation
/save-session pr-review-feedback
/save-session final-testing
```

**With spaces and special characters (automatically sanitized):**
```
/save-session investigating OCPBUGS-12345 regarding routes
```
Creates: `session-2025-10-16-investigating-ocpbugs-12345-regarding-routes.md`

**Resuming a saved session:**
Open Claude Code and say:
```
Please read `/path/to/session-2025-10-16-parallel-test-fixes.md` and continue from where we left off
```

## Arguments

**description** (optional)
- Custom identifier appended to the filename
- Helps identify the session purpose when resuming after long intervals
- **Input handling**: Description is automatically sanitized for safe filename usage (spaces converted to hyphens, special characters removed, truncated to 100 chars if needed)
- **Good examples**: `feature-name`, `bug-fix`, `refactoring`, `investigating-ocpbugs-12345`
- Automatically added to filename: `session-YYYY-MM-DD-<description>.md`

If no description is provided, timestamp alone is used: `session-YYYY-MM-DD-HHMM.md`

**Note**: You can use spaces and special characters in your description - they will be automatically sanitized. For example, "investigating OCPBUGS-12345 regarding routes" becomes "investigating-ocpbugs-12345-regarding-routes".
