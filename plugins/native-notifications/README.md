# Cross-platform Notifications Plugin

This plugin enables Claude to notify the user via native system notifications when it is done with a prompt or requires user input.

## How It Works

The plugin uses Claude Code's [hook system](https://docs.claude.com/en/docs/claude-code/hooks) to send a notification when it is done.
It automatically detects the platform and uses the best available notification method:

| Platform | Method |
|---|---|
| macOS | `osascript` (native macOS notifications) |
| Linux with desktop session (`$DISPLAY` / `$WAYLAND_DISPLAY`) | `notify-send` (libnotify) |
| Linux headless / SSH (no display) | terminal bell (`\a`) |

### Hook Configuration

The plugin is defined in `plugins/native-notifications/hooks/hooks.json`.
To customize the notification messages, edit the title and message arguments to `notify.sh`:

```json
{
  "description": "Cross-platform desktop notifications (macOS, Linux desktop, Linux headless)",
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${PLUGIN_DIR}/scripts/notify.sh '🔔 Claude Code' 'Claude needs your input'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${PLUGIN_DIR}/scripts/notify.sh '✅ Claude Code' 'Claude finished your task'"
          }
        ]
      }
    ]
  }
}
```

