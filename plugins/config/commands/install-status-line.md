---
description: Install Claude Code custom status line with prompt display
---

## Name

config:install-status-line

## Synopsis

```
/config:install-status-line
```

## Description

The `config:install-status-line` command installs a custom status line script to `~/.claude/status_line.sh`.
This status line displays rich session information including:

- Claude Code version
- Active model name
- Git branch or current directory
- Output style
- Most recent user prompt (truncated to 50 characters)

The status line integrates with the session prompt hook to display contextual information about your current development session.

## Implementation

1. **Copy status line script to Claude Code config directory**
   - Source: `plugins/config/scripts/status_line.sh`
   - Destination: `~/.claude/status_line.sh`
   - Ensure the script is executable

2. **Configure Claude Code to use the status line**
   - The status line must be registered in Claude Code settings
   - Configuration can be done via `claude code config status-line` or by editing the settings file

3. **Verify installation**
   - Check that `~/.claude/status_line.sh` exists
   - Check that the script is executable
   - Verify that `jq` is installed (required dependency)
   - Verify that `git` is installed (for git branch display)

4. **Provide usage instructions**
   - Inform user how to configure the status line in Claude Code
   - Explain the visual format and color scheme
   - Note dependency on session-prompt-hook for prompt display

## Return Value

- **Success message**: Confirms the status line script has been installed and provides configuration instructions
- **Error message**: If the script cannot be copied or if required dependencies are missing

## Prerequisites

- **jq**: Required for JSON parsing
  - Check: `which jq`
  - Install (Fedora): `sudo dnf install jq`
  - Install (Arch Linux): `sudo pacman -S jq`
  - Install (macOS): `brew install jq`
- **git**: Optional, for git branch display
  - Check: `which git`
  - Install (Fedora): `sudo dnf install git`
  - Install (Arch Linux): `sudo pacman -S git`
  - Install (macOS): `brew install git`
- **session-prompt-hook**: Optional, for prompt display
  - Install via `/config:install-hooks`
  - Status line works without it, but won't show recent prompts

## Examples

1. **Basic installation**:
   ```
   /config:install-status-line
   ```
   Expected output:
   ```
   Installed status_line.sh to ~/.claude/

   To enable the status line, run:
   claude code config status-line ~/.claude/status_line.sh

   Or manually edit your Claude Code settings.

   Status line format:
   [version] | [model] | [branch/dir] | [style] | [last prompt...]
   ```

2. **Full setup with prompt hook**:
   ```
   /config:install-hooks
   /config:install-status-line
   ```
   Complete installation of both components for full functionality.

## Status Line Format

The status line displays information with color-coded sections:

- **Purple**: Claude Code version
- **Blue**: Active model display name
- **Green**: Git branch name or current directory
- **Yellow**: Output style name
- **Grey**: Last user prompt (truncated at 50 chars)

Example output:
```
v1.2.3 | Sonnet 4.5 | main | default | I would like to contribute ~/.clau...
```

## Notes

- The status line reads prompts from `/tmp/prompts-{session_id}.txt`
- Prompt display requires the session-prompt-hook to be installed and configured
- If no git repository is found, displays the current directory name
- Colors use matte ANSI codes for terminal compatibility
- Status line is updated on every prompt submission

## Arguments

None
