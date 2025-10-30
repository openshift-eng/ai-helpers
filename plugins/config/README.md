# Config Plugin

Claude Code configuration management for enhanced session awareness and customization.

## Overview

This plugin provides tools to customize your Claude Code experience with:

- **Session Prompt Hook**: Captures every prompt you submit, enabling context-aware features
- **Enhanced Status Line**: Displays rich session information including your recent prompt

Together, these tools provide better visibility into your development session and help maintain context across long interactions.

## Commands

### `/config:install-hooks`

Installs the session prompt capture hook that saves every prompt to a session-specific file.
This enables the status line to display your most recent prompt for quick context reference.

See [commands/install-hooks.md](commands/install-hooks.md) for full documentation.

### `/config:install-status-line`

Installs a custom status line that displays:
- Claude Code version
- Active model
- Git branch or directory name
- Output style
- Your most recent prompt (truncated)

See [commands/install-status-line.md](commands/install-status-line.md) for full documentation.

## Installation

```bash
/plugin install config@ai-helpers
```

## Quick Setup

To get the complete experience with both prompt tracking and enhanced status line:

```bash
# Install the prompt hook
/config:install-hooks

# Install the status line
/config:install-status-line

# Configure Claude Code (manual step)
claude code config hooks --add UserPromptSubmit ~/.claude/session-prompt-hook.sh
claude code config status-line ~/.claude/status_line.sh
```

## Requirements

- **jq**: JSON parsing utility
  - Fedora: `sudo dnf install jq`
  - Arch Linux: `sudo pacman -S jq`
  - macOS: `brew install jq`
- **git**: Optional, for git branch display in status line
  - Fedora: `sudo dnf install git`
  - Arch Linux: `sudo pacman -S git`
  - macOS: `brew install git`

## How It Works

1. **Prompt Hook**: When you submit a prompt, the hook script captures it to `/tmp/prompts-{session_id}.txt`
2. **Status Line**: Each time the status line renders, it reads the latest prompt from that file
3. **Context Awareness**: You can always see your last prompt in the status line, helping maintain context during long sessions

## Example Status Line

```
v1.2.3 | Sonnet 4.5 | main | default | I would like to contribute ~/.clau...
```

Color-coded for easy scanning:
- Purple: Version
- Blue: Model
- Green: Branch/Directory
- Yellow: Output style
- Grey: Last prompt
