# Metrics Plugin

Anonymous usage metrics collection for ai-helpers slash commands.

## Overview

The `metrics` plugin provides anonymous usage tracking for slash commands. It helps the maintainers understand which commands are being used and how often, enabling data-driven decisions about feature development and improvements.

## How It Works

The plugin uses Claude Code's [hook system](https://docs.claude.com/en/docs/claude-code/hooks) to automatically track slash command usage:

1. **Hook Trigger**: When you submit a prompt that starts with `/`, the `UserPromptSubmit` hook fires
2. **Data Collection**: The `send_metrics.py` script extracts the command name and system information
3. **Background Transmission**: Metrics are sent asynchronously to the ai-helpers telemetry endpoint
4. **Local Logging**: If verbose mode is enabled, all activity is logged to `metrics.log`

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
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/send_metrics.py --verbose",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## What Data is Collected

The plugin collects the following **anonymous** data when you use a slash command:

| Field | Description | Example |
|-------|-------------|---------|
| `type` | Always "slash_command" | `"slash_command"` |
| `name` | The slash command name | `"jira:solve"` |
| `engine` | Always "claude" | `"claude"` |
| `version` | Plugin version | `"1.0"` |
| `timestamp` | UTC timestamp | `"2025-10-30T12:34:56Z"` |
| `session_id` | Claude session identifier | `"abc123..."` |
| `os` | Operating system | `"darwin"`, `"linux"`, `"windows"` |
| `mac` | SHA256 hash of session_id + timestamp | `"a1b2c3..."` |
| `prompt_length` | Character count of the prompt | `42` |

**Privacy Guarantees:**
- No command arguments or sensitive data are transmitted
- No personal identifying information (PII) is collected
- Session IDs are ephemeral and rotate between Claude sessions
- The MAC is used for data integrity verification only

**Example payload:**
```json
{
  "type": "slash_command",
  "name": "jira:solve",
  "engine": "claude",
  "version": "1.0",
  "timestamp": "2025-10-30T12:34:56Z",
  "session_id": "abc123...",
  "os": "darwin",
  "mac": "a1b2c3...",
  "prompt_length": 42
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

- **Endpoint**: `https://ai-helpers.dptools.openshift.org/api/v1/metrics`
- **Async**: Runs in a background thread so it doesn't delay command execution
- **Resilience**: Network failures are logged but don't interrupt your work

## Source Code

All metrics collection logic is open source and available in this repository:

- **Hook definition**: `plugins/metrics/hooks/hooks.json`
- **Collection script**: `plugins/metrics/scripts/send_metrics.py`
- **Plugin metadata**: `plugins/metrics/.claude-plugin/plugin.json`

## Data Usage

The collected metrics help us:

- Understand which commands are most valuable to users
- Prioritize bug fixes and feature development
- Identify commands that may need better documentation
- Make data-driven decisions about deprecations

**Aggregate metrics may be shared publicly** (e.g., "The most popular command is `/jira:solve` with 1,234 uses this month"), but individual usage data remains private.
