# Config Plugin

Claude Code configuration management for enhanced session awareness and customization.

## Overview

This plugin provides tools to customize your Claude Code experience with:

- **Enhanced Status Line**: Displays rich session information including Claude Code version, model, git branch, and output style
- **Session Prompt Hook**: Optional hook that captures prompts to display in the status line (the status line works fine without it)

The status line provides useful visibility into your development session.
The prompt hook adds minimal extra context by showing your last prompt in the status line.

## Commands

### `/config:install-hooks`

Installs the session prompt capture hook that saves prompts to a session-specific file.
This is specifically for use with the status line to display your most recent prompt.
The hook has no other functionality.

See [commands/install-hooks.md](commands/install-hooks.md) for full documentation.

### `/config:install-status-line`

Installs a custom status line that displays:
- Claude Code version
- Active model
- Git branch or directory name
- Output style
- Your most recent prompt (only if the prompt hook is installed)

See [commands/install-status-line.md](commands/install-status-line.md) for full documentation.

## Installation

```bash
/plugin install config@ai-helpers
```

## Quick Setup

Minimal setup (recommended):

```bash
# Install the status line
/config:install-status-line

# Configure Claude Code (manual step)
claude code config status-line ~/.claude/status_line.sh
```

Optional: Add prompt display to status line:

```bash
# Install the prompt hook (optional)
/config:install-hooks

# Configure the hook (manual step)
claude code config hooks --add UserPromptSubmit ~/.claude/session-prompt-hook.sh
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

1. **Status Line**: Displays session information (version, model, branch, output style) on every prompt
2. **Prompt Hook** (optional): If installed, captures prompts to `/tmp/prompts-{session_id}.txt` so the status line can display your last prompt

The status line works independently and provides useful context without the hook.

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
