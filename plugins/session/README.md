# Session Plugin

Claude Code session management and persistence utilities.

## Commands

### `/session:save-session`

Save the current conversation session to a markdown file for future continuation.

This command captures the conversation context, allowing you to resume long-running tasks across multiple sessions.

See [commands/save-session.md](commands/save-session.md) for full documentation.

### `/session:log-session`

Save a snapshot of the current session to a plain text file for quick reference.

This command creates a lightweight session log with metadata and git information, stored in `~/.claude/sessions/`. It's a simpler alternative to `/save-session` when you only need basic session tracking.

See [commands/log-session.md](commands/log-session.md) for full documentation.

## Installation

```bash
/plugin install session@ai-helpers
```

