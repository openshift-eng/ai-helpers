# Native macOS notifications Plugin

This plugin enables Claude to notify the user via native macOS system notifications when it is done with a prompt or requires user input.

## How It Works

The plugin uses Claude Code's [hook system](https://docs.claude.com/en/docs/claude-code/hooks) to send a notification when it is done.
The notification is sent using the native macOS notification system with `osascript`.


### Hook Configuration

The plugin is defined in `plugins/macos-notifications/hooks/hooks.json`.
To customize the contents displayed by the notification, edit the script call:

```json
{
  "description": "Native macOS Notifications",
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude needs your input\" with title \"🔔 Claude Code\"'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude finished your task\" with title \"✅ Claude Code\"'"
          }
        ]
      }
    ]
  }
}
```

