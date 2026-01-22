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
This status line displays session information including:

- 📦 Claude Code version
- 🧬 Active model name
- 🗂️ Git branch with path context (parent/current directory)
- 🎨 Output style
- 💬 Most recent user prompt (only if session-prompt-hook is installed)

The status line works fully without the prompt hook.
The prompt hook is optional and only adds minimal extra context by showing your last prompt.

## Implementation

1. **Copy status line script to Claude Code config directory**
   - Source: `plugins/config/scripts/status_line.sh`
   - Destination: `~/.claude/status_line.sh`
   - Ensure the script is executable

2. **Configure Claude Code to use the status line**
   - Edit `~/.claude/settings.json` and add:
     ```json
     {
       "statusLine": {
         "type": "command",
         "command": "$HOME/.claude/status_line.sh"
       }
     }
     ```
   - Replace `$HOME` with the actual `$HOME` environment variable
   - If settings.json already has other content, merge this configuration
   - Restart Claude Code or start a new session for changes to take effect

3. **Verify installation**
   - Check that `~/.claude/status_line.sh` exists
   - Check that the script is executable
   - Verify that `jq` is installed (required dependency)
   - Verify that `git` is installed (for git branch display)

4. **Provide usage instructions**
   - Inform user how to configure the status line in Claude Code
   - Explain the visual format and color scheme
   - Clarify that the status line works without the prompt hook
   - Note that session-prompt-hook is optional for prompt display

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

   To enable the status line, add to ~/.claude/settings.json:

   {
     "statusLine": {
       "type": "command",
       "command": "$HOME/.claude/status_line.sh"
     }
   }

   Then restart Claude Code or start a new session.

   Status line format:
   📦 [version] | 🧬 [model] | 🗂️ [parent/current:branch] | 🎨 [style] | 💬 [last prompt...]
   ```

2. **Full setup with prompt hook**:
   ```
   /config:install-hooks
   /config:install-status-line
   ```
   Complete installation of both components for full functionality.

## Status Line Format

The status line displays information with emojis and color-coded sections:

- 📦 **Purple**: Claude Code version
- 🧬 **Blue**: Active model display name
- 🗂️ **Green (dark/light)**: Path context (parent/current directory) and git branch
  - Parent directory truncated to 10 chars, current folder to 20 chars
  - Format: `parent/current:branch` (if in git repo) or `parent/current` (if not)
- 🎨 **Yellow**: Output style name
- 💬 **Grey**: Last user prompt (truncated at 50 chars)

Example output:
```
📦 v1.2.3 | 🧬 Sonnet 4.5 | 🗂️ openshift/ai-helpers:config-plugin | 🎨 default | 💬 I would like to contribute ~/.clau...
```

## Notes

- The status line works fully without the session-prompt-hook installed
- If session-prompt-hook is installed, it reads prompts from `/tmp/claude-sessions/prompts-{session_id}.txt` for display
- If no git repository is found, displays the path context (parent/current directory)
- Colors use matte ANSI codes for terminal compatibility, with dark/light green variants for better visual hierarchy
- Directory truncation: parent directory to 10 chars, current folder to 20 chars
- Emojis provide quick visual scanning: 📦 version, 🧬 model, 🗂️ location, 🎨 style, 💬 prompt
- Status line is updated on every prompt submission
- The prompt hook is optional and provides minimal additional context

## Arguments

None
