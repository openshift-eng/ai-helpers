# Metrics Plugin

Anonymous usage metrics collection for ai-helpers slash commands, skills, and sessions.

## Overview

The `metrics` plugin provides anonymous usage tracking for:
- **Events**: Individual slash commands and skill invocations
- **Sessions**: Aggregate session-level metrics (duration, tool usage, conversation patterns)

This helps maintainers understand usage patterns and make data-driven decisions about feature development and improvements.

## How It Works

The plugin uses Claude Code's [hook system](https://docs.claude.com/en/docs/claude-code/hooks) to automatically track usage:

### Event Tracking (Slash Commands & Skills)

1. **Hook Triggers**:
   - `UserPromptSubmit`: Fires when you submit a prompt that starts with `/` (slash commands)
   - `PreToolUse`: Fires when Claude invokes a Skill tool
2. **Data Collection**: The `send_metrics.py` script extracts the command/skill name and system information
3. **Background Transmission**: Events are sent asynchronously to the events endpoint
4. **Local Logging**: If verbose mode is enabled, all activity is logged to `metrics.log`

### Session Tracking (Session-Level Aggregates)

1. **Hook Trigger**: `SessionEnd` fires when your Claude Code session ends
2. **Transcript Parsing**: The `send_session_metrics.py` script parses the session transcript file
3. **Metrics Extraction**: Aggregates are calculated (tool usage, conversation turns, duration, etc.)
4. **Background Transmission**: Session metrics are sent asynchronously to the sessions endpoint
5. **Privacy**: Only counts and aggregates are collected - no command arguments, file paths, or message content

### Hook Configuration

The plugin is defined in `plugins/metrics/hooks/hooks.json`:

```json
{
  "description": "Anonymous Usage Metric Collection",
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/send_metrics.py",
            "timeout": 30
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": {
          "tool": "Skill"
        },
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/send_metrics.py",
            "timeout": 30
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/send_session_metrics.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## What Data is Collected

The plugin collects two types of anonymous data:

### Event Metrics (Slash Commands & Skills)

Collected when you use a slash command or invoke a skill:

| Field | Description | Example |
|-------|-------------|---------|
| `type` | Metric type | `"slash_command"` or `"skill"` |
| `name` | The command or skill name | `"jira:solve"` or `"prow-job:prow-job-analyze-install-failure"` |
| `engine` | Always "claude" | `"claude"` |
| `version` | Plugin version | `"1.0"` |
| `timestamp` | UTC timestamp | `"2025-10-30T12:34:56Z"` |
| `session_id` | Claude session identifier | `"abc123..."` |
| `user_id` | Persistent anonymous UUID | `"550e8400-e29b-41d4-a716-446655440000"` |
| `os` | Operating system | `"darwin"`, `"linux"`, `"windows"` |
| `mac` | SHA256 hash of session_id + timestamp | `"a1b2c3..."` |
| `prompt_length` | Character count of the prompt | `42` |

**Privacy Guarantees:**
- No command arguments or sensitive data are transmitted
- No personal identifying information (PII) is collected
- Session IDs are ephemeral and rotate between Claude sessions
- A persistent anonymous UUID is stored locally in `.anonymous_id`, used only to correlate events across sessions
- The `user_id` contains no PII and can be regenerated/cleared by deleting the `.anonymous_id` file
- The `user_id` is treated as anonymous for analytics and integrity purposes
- The MAC is used for data integrity verification only

**Example payloads:**

Slash command:
```json
{
  "type": "slash_command",
  "name": "jira:solve",
  "engine": "claude",
  "version": "1.0",
  "timestamp": "2025-10-30T12:34:56Z",
  "session_id": "abc123...",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "os": "darwin",
  "mac": "a1b2c3...",
  "prompt_length": 42
}
```

Skill invocation:
```json
{
  "type": "skill",
  "name": "prow-job:prow-job-analyze-install-failure",
  "engine": "claude",
  "version": "1.0",
  "timestamp": "2025-10-30T12:34:56Z",
  "session_id": "abc123...",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "os": "darwin",
  "mac": "a1b2c3...",
  "prompt_length": 0
}
```

### Session Metrics (Session-Level Aggregates)

Collected when your Claude Code session ends:

| Field | Description | Example |
|-------|-------------|---------|
| `session_id` | Session identifier | `"abc123..."` |
| `user_id` | Persistent anonymous UUID | `"550e8400-e29b-41d4-a716-446655440000"` |
| `os` | Operating system | `"darwin"`, `"linux"`, `"windows"` |
| `engine` | Always "claude" | `"claude"` |
| `start_timestamp` | Session start time (UTC) | `"2025-10-30T12:00:00Z"` |
| `end_timestamp` | Session end time (UTC) | `"2025-10-30T14:30:00Z"` |
| `session_duration` | Duration in seconds | `9000` |
| `exit_reason` | How session ended | `"clear"`, `"logout"`, `"prompt_input_exit"`, `"other"` |
| `turn_count` | User-assistant exchanges | `42` |
| `user_message_count` | Total user messages | `45` |
| `assistant_message_count` | Total assistant messages | `48` |
| `total_tool_calls` | Total tool invocations | `156` |
| `tool_error_count` | Failed tool calls | `3` |
| `bash_call_count` | Bash tool usage | `28` |
| `file_read_count` | Read tool usage | `42` |
| `file_edit_count` | Edit tool usage | `18` |
| `file_write_count` | Write tool usage | `5` |
| `grep_call_count` | Grep tool usage | `12` |
| `glob_call_count` | Glob tool usage | `8` |
| `web_fetch_call_count` | WebFetch tool usage | `2` |
| `web_search_call_count` | WebSearch tool usage | `1` |
| `total_input_tokens` | Total input tokens (nullable) | `50000` |
| `total_output_tokens` | Total output tokens (nullable) | `12000` |
| `cache_creation_tokens` | Cache creation tokens (nullable) | `15000` |
| `cache_read_tokens` | Cache read tokens (nullable) | `35000` |
| `had_errors` | Whether errors occurred | `true` or `false` |

**Privacy Guarantees for Session Metrics:**
- **Only aggregates**: Tool usage counts, not what tools were used for
- **No content**: Command arguments, file paths, or message content are never collected
- **No identifiable patterns**: Git operations, specific bash commands, or file names are excluded
- **Optional tokens**: Token metrics are only included if non-zero and can be omitted for privacy

**Example session payload:**
```json
{
  "session_id": "abc123...",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "os": "darwin",
  "engine": "claude",
  "start_timestamp": "2025-10-30T12:00:00Z",
  "end_timestamp": "2025-10-30T14:30:00Z",
  "session_duration": 9000,
  "exit_reason": "clear",
  "turn_count": 42,
  "user_message_count": 45,
  "assistant_message_count": 48,
  "total_tool_calls": 156,
  "tool_error_count": 3,
  "bash_call_count": 28,
  "file_read_count": 42,
  "file_edit_count": 18,
  "file_write_count": 5,
  "grep_call_count": 12,
  "glob_call_count": 8,
  "web_fetch_call_count": 2,
  "web_search_call_count": 1,
  "total_input_tokens": 50000,
  "total_output_tokens": 12000,
  "cache_creation_tokens": 15000,
  "cache_read_tokens": 35000,
  "had_errors": false
}
```

## Enabling the Plugin

The metrics plugin requires explicit configuration.

### Method 1: Repository Trust (Recommended)

If you clone and trust this repository locally, it will be automatically
installed by the included settings.json.

### Method 2: Manual Installation

If you've installed ai-helpers from the marketplace:

```bash
# Enable the plugin
/plugin enable metrics@ai-helpers

# Verify it's enabled
/plugin list
```

## Disabling the Plugin

If you wish to opt out of metrics collection:

```bash
/plugin disable metrics@ai-helpers
```

## Network Behavior

- **Event Endpoint**: `https://us-central1-openshift-ci-data-analysis.cloudfunctions.net/metrics-upload/events`
- **Session Endpoint**: `https://us-central1-openshift-ci-data-analysis.cloudfunctions.net/metrics-upload/sessions`
- **Async**: Runs in a background thread so it doesn't delay command execution
- **Resilience**: Network failures are logged but don't interrupt your work

## Source Code

All metrics collection logic is open source and available in this repository:

- **Hook definition**: `plugins/metrics/hooks/hooks.json`
- **Event collection script**: `plugins/metrics/scripts/send_metrics.py`
- **Session collection script**: `plugins/metrics/scripts/send_session_metrics.py`
- **Plugin metadata**: `plugins/metrics/.claude-plugin/plugin.json`

## Data Usage

The collected metrics help us:

**Event metrics:**
- Understand which commands and skills are most valuable to users
- Identify commands that may need better documentation
- Make data-driven decisions about feature prioritization and deprecations

**Session metrics:**
- Understand typical session patterns (duration, tool usage, conversation depth)
- Identify workflow bottlenecks and optimization opportunities
- Measure developer productivity patterns without revealing specific work content
- Optimize tool performance and caching strategies based on actual usage

**Aggregate metrics may be shared publicly** (e.g., "The average session uses 42 tool calls" or "The most popular command is `/jira:solve` with 1,234 uses this month"), but individual usage data remains private.
