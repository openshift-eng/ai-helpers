# Session Plugin

Claude Code session management and persistence utilities.

## Commands

### `/session:load-context`

Load and learn from recent conversation history to maintain context across sessions.

This command uses an AI agent to analyze your conversation history and generate a compact summary, allowing Claude to understand previous work without loading full message history into the main thread.

**Key features:**
- Agent-based analysis of `~/.claude/history.jsonl` in separate context
- Generates compact summaries (300-500 tokens) instead of loading full history
- Human-reviewed summaries before internalization
- Smart filtering by time range, project, and keywords
- Maintains context across days and weeks without context bloat

See [commands/load-context.md](commands/load-context.md) for full documentation.

### `/session:save-session`

Save the current conversation session to a markdown file for future continuation.

This command captures the conversation context, allowing you to resume long-running tasks across multiple sessions.

See [commands/save-session.md](commands/save-session.md) for full documentation.

## Usage Workflow

**Recommended daily workflow:**

```bash
# Morning: Load recent context
/session:load-context 3

# Work on your tasks...
# Claude remembers recent discussions

# Evening (optional): Save important milestones
/session:save-session feature-implementation
```

**Both commands work together:**
- Use `/session:load-context` for daily continuity (automatic)
- Use `/session:save-session` for important documentation (manual)

## Installation

```bash
/plugin install session@ai-helpers
```

