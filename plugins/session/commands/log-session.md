---
description: Save the current Claude Code session to a plain text file for later reference
argument-hint: "[filename]"
---

## Name
session:log-session

## Synopsis

```
/log-session
/log-session [filename]
```

## Description

Saves the current Claude Code session to a plain text file in `~/.claude/sessions/`. This command creates a complete session transcript containing the full conversation history along with session metadata and git information.

This provides a complete record of your session for later reference and review.

## Implementation

The command follows a three-phase process:

### Phase 1: Gather Session Metadata
Collect the following information using bash commands:
- Current date: `date -u '+%Y-%m-%d'`
- Current working directory: `pwd`
- Git branch: `git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A"`
- Determine output filename:
  - If argument $1 provided: `~/.claude/sessions/<filename>.txt`
  - If no argument: `~/.claude/sessions/session-<SESSION_ID>.txt`
- Ensure the `~/.claude/sessions/` directory exists: `mkdir -p ~/.claude/sessions`

### Phase 2: Build and Save Full Conversation Transcript
Use the **Write** tool to create a plain text file with this exact format:

```
================================================================================
CLAUDE CODE SESSION TRANSCRIPT
================================================================================
Session: <filename>
Date: <date>
Working Directory: <pwd>
Branch: <branch-name-or-NA>
================================================================================

USER:
<first user message>

A:
<first assistant response>

USER:
<second user message>

A:
<second assistant response>

[... complete conversation history ...]

================================================================================
END OF SESSION TRANSCRIPT
================================================================================
```

**How to implement:**
1. Create the header section with session metadata
2. Iterate through the entire conversation history in chronological order
3. For each message, format as:
   - User messages: Start with `USER:` followed by the message content
   - Assistant messages: Start with `A:` followed by the response content
   - Add blank lines between messages for readability
4. Close with the end-of-transcript footer
5. Use the Write tool to save the complete transcript to the file path

**CRITICAL**: Only Claude Code has direct access to the conversation history. The full conversation transcript MUST be saved using the Write tool. Bash scripts can only provide metadata - they cannot access the conversation content.

### Phase 3: Confirmation
- Display success message showing the full path to the saved file
- Format: `✓ Session saved to: <full-path>`

## Return Value

Creates a plain text file in `~/.claude/sessions/` containing the complete conversation transcript with filename:
- `<filename>.txt` (with custom filename)
- `session-<SESSION_ID>.txt` (auto-generated)

Terminal output:
```
✓ Session saved to: /home/user/.claude/sessions/session-abc123.txt
```

The saved file includes:
- Session metadata header (date, working directory, git branch)
- Complete conversation history (all USER and ASSISTANT messages)
- End-of-transcript footer

## Examples

**Basic usage with auto-generated filename:**
```
/log-session
```
Creates: `~/.claude/sessions/session-<SESSION_ID>.txt`

**With custom filename:**
```
/log-session my-bugfix-work
```
Creates: `~/.claude/sessions/my-bugfix-work.txt`

**Quick session snapshots:**
```
/log-session before-refactor
/log-session after-refactor
/log-session final-state
```

## Arguments

**filename** (optional)
- Custom name for the session log file (without .txt extension)
- The `.txt` extension is automatically added
- Good examples: `my-session-name`, `bugfix-123`, `feature-implementation`
- If not provided, defaults to `session-<SESSION_ID>`

## Notes

- All session logs are stored in `~/.claude/sessions/` directory
- The directory is created automatically if it doesn't exist
- Git information is only included if the working directory is inside a git repository
- This command saves the **complete conversation transcript** with full USER/ASSISTANT message history
- The conversation history can ONLY be accessed by Claude Code using the Write tool - bash scripts cannot access it
- Each session file includes a header with metadata, the full conversation, and an end-of-transcript footer
