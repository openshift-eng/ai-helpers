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

The plugin is defined in `plugins/macos-notifications/hooks/hooks.json`.
To customize the contents displayed by the notification, edit the script call:

```json
{
  "description": "Cross-platform desktop notifications (macOS, Linux desktop, Linux headless)",
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "if command -v osascript &>/dev/null; then osascript -e 'display notification \"Claude needs your input\" with title \"🔔 Claude Code\"'; elif command -v notify-send &>/dev/null && [ -n \"${DISPLAY:-}${WAYLAND_DISPLAY:-}\" ]; then notify-send '🔔 Claude Code' 'Claude needs your input'; else printf '\\a'; fi"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "if command -v osascript &>/dev/null; then osascript -e 'display notification \"Claude finished your task\" with title \"✅ Claude Code\"'; elif command -v notify-send &>/dev/null && [ -n \"${DISPLAY:-}${WAYLAND_DISPLAY:-}\" ]; then notify-send '✅ Claude Code' 'Claude finished your task'; else printf '\\a'; fi"
          }
        ]
      }
    ]
  }
}
```

