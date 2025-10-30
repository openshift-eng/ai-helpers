---
description: Install Claude Code prompt capture hook
---

## Name

config:install-hooks

## Synopsis

```
/config:install-hooks
```

## Description

The `config:install-hooks` command installs the session prompt capture hook script to `~/.claude/session-prompt-hook.sh`.
This hook captures every user prompt during a Claude Code session and saves them to a session-specific file in `/tmp/prompts-{session_id}.txt`.

The captured prompts are used by the status line to display the most recent prompt, providing context awareness during development sessions.

## Implementation

1. **Copy hook script to Claude Code config directory**
   - Source: `plugins/config/scripts/session-prompt-hook.sh`
   - Destination: `~/.claude/session-prompt-hook.sh`
   - Ensure the script is executable

2. **Configure Claude Code to use the hook**
   - The hook must be registered in Claude Code settings
   - Hook type: `UserPromptSubmit`
   - The configuration can be done via `claude code config hooks` or by editing the settings file

3. **Verify installation**
   - Check that `~/.claude/session-prompt-hook.sh` exists
   - Check that the script is executable
   - Verify that `jq` is installed (required dependency)

4. **Provide usage instructions**
   - Inform user how to verify the hook is working
   - Explain the `/tmp/prompts-{session_id}.txt` file location
   - Note that prompts persist until system reboot or manual cleanup

## Return Value

- **Success message**: Confirms the hook script has been installed and provides next steps for configuration
- **Error message**: If the script cannot be copied or if required dependencies are missing

## Prerequisites

- **jq**: Required for JSON parsing in the hook script
  - Check: `which jq`
  - Install (Fedora): `sudo dnf install jq`
  - Install (Arch Linux): `sudo pacman -S jq`
  - Install (macOS): `brew install jq`

## Examples

1. **Basic installation**:
   ```
   /config:install-hooks
   ```
   Expected output:
   ```
   Installed session-prompt-hook.sh to ~/.claude/

   To enable the hook, run:
   claude code config hooks --add UserPromptSubmit ~/.claude/session-prompt-hook.sh

   Or manually edit your Claude Code settings.
   ```

## Notes

- The hook script captures all prompts to `/tmp/prompts-{session_id}.txt`
- Prompt files are created per session and persist until system reboot
- Works in conjunction with the status line script to display recent prompts
- Captured prompts are single-line (newlines converted to spaces)

## Arguments

None
