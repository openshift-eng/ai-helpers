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
This hook captures user prompts during a Claude Code session and saves them to `/tmp/prompts-{session_id}.txt`.

**Purpose**: This hook exists solely to provide the status line with your last prompt for display.
It has no other functionality and provides no value on its own.
The status line works fine without it.

## Implementation

1. **Copy hook script to Claude Code config directory**
   - Source: `plugins/config/scripts/session-prompt-hook.sh`
   - Destination: `~/.claude/session-prompt-hook.sh`
   - Ensure the script is executable

2. **Configure Claude Code to use the hook**
   - Edit `~/.claude/settings.json` and add:
     ```json
     {
       "hooks": {
         "UserPromptSubmit": [
           {
             "hooks": [
               {
                 "type": "command",
                 "command": "/home/USERNAME/.claude/session-prompt-hook.sh"
               }
             ]
           }
         ]
       }
     }
     ```
   - Replace `USERNAME` with the actual username
   - If settings.json already has other content, merge this configuration
   - Restart Claude Code or start a new session for changes to take effect

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

   To enable the hook, add to ~/.claude/settings.json:

   {
     "hooks": {
       "UserPromptSubmit": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "/home/YOUR_USERNAME/.claude/session-prompt-hook.sh"
             }
           ]
         }
       ]
     }
   }

   Then restart Claude Code or start a new session.
   ```

## Notes

- This hook's only purpose is to enable prompt display in the status line
- The hook captures prompts to `/tmp/prompts-{session_id}.txt` (persist until reboot)
- The status line works fine without this hook installed
- Captured prompts are single-line (newlines converted to spaces)
- Installing this hook is optional and provides minimal additional value

## Arguments

None
