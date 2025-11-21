# Session Plugin

Claude Code session management and persistence utilities.

## Installation

```bash
/plugin install session@ai-helpers
```

## Commands

### `/session:save-session`

Save the current conversation session to a markdown file for future continuation.

This command captures the conversation context, allowing you to resume long-running tasks across multiple sessions.

See [commands/save-session.md](commands/save-session.md) for full documentation.


**Usage:**
```bash
/save-session                              # Auto mode: create new or update file for current session
/save-session <description>                # Create new named session (full conversation) file
/save-session -i <description>             # Create new session (incremental content only) file
/save-session --incremental <description>  # Same as -i (full syntax)
```

**What it does:**
- Saves conversation history to markdown files for continuity
- Supports incremental saves for topic separation to new file
- Enables resuming work by reading previous session files

**Arguments:**
- `description` (optional): Session description used for file naming
  - Provided: Creates new session file `session-YYYY-MM-DD-<description>.md`
  - Omitted: Auto-detects and updates the most recent session file or create new file for current session
  - Format: Spaces converted to hyphens, special characters removed
- `-i` or `--incremental` (optional): Save only new content since last save

**Key Usage Patterns:**

1. **Single Task with Multiple Updates** (Most Common)
   ```bash
   # First save: Create named session
   /save-session bug fix OCPBUGS 12345
   # → Creates: session-2025-10-22-bug-fix-ocpbugs-12345.md

   # Continue working...

   # Subsequent saves: Auto-update same session
   /save-session
   # → Updates: session-2025-10-22-bug-fix-ocpbugs-12345.md (Update #2)

   /save-session
   # → Updates: session-2025-10-22-bug-fix-ocpbugs-12345.md (Update #3)
   ```

2. **Evolving Discussion to New Session**
   ```bash
   # Save performance optimization work
   /save-session performance optimization
   # → Creates: session-2025-10-22-performance-optimization.md

   # Continue working...

   /save-session
   # → Updates: session-2025-10-22-performance-optimization.md (Update #2)

   # Continue discussion on error handling related to performance...

   # Create separate topic with "performance optimization" and "error handling"
   /save-session error handling improvements with  performance optimization
   # → Creates: session-2025-10-22-error-handling-improvements-with-performance-optimization.md
   # → Contains content from the beginning

   # Continue working...

   /save-session
   # → Updates: session-2025-10-22-error-handling-improvements-with-performance-optimization.md (Update #2)
   ```

3. **Task Switching**

   **Note:** Not recommended. For switching to a different task, exit Claude and start a new session for cleaner context separation.

   If you must switch tasks in the same conversation:
   ```bash
   # Working on bug fix
   /save-session bug fix OCPBUGS 12345
   # → Creates: session-2025-10-22-bug-fix-ocpbugs-12345.md

   /save-session
   # → Updates: session-2025-10-22-bug-fix-ocpbugs-12345.md

   # Switch to new task (not recommended - better to start new Claude session)
   /save-session -i add metrics support
   # → Creates: session-2025-10-22-add-metrics-support.md
   # Note: May contain minimal content if no discussion happened yet

   /save-session
   # → Updates: session-2025-10-22-add-metrics-support.md
   ```

   **Recommended approach for task switching:**
   ```bash
   # Save current work
   /save-session

   # Exit Claude
   /exit

   # Start new Claude session for new task
   claude

   # Work on new task with clean context
   # Save when ready
   /save-session new task
   ```

**Resuming Work:**

To continue previous work, read the session file in a new conversation:
```bash
# Start new Claude Code session
claude

# In the conversation:
User: Read session-2025-10-22-bug-fix-ocpbugs-12345.md and continue the work
Claude: [Reads file and understands previous context]

# Continue working...

# Save updates
/save-session
# → Automatically updates: session-2025-10-22-bug-fix-ocpbugs-12345.md
```

**Quick Reference:**

| Scenario | Command |
|----------|---------|
| Start new task | `/save-session task name` |
| Continue current task | `/save-session` |
| Switch to different task | `/save-session other task` |
| Separate new topic (incremental) | `/save-session -i new topic` |
| Resume previous work | Read file first, then `/save-session` |

## Additional Resources

- Command documentation: [commands/save-session.md](commands/save-session.md)
