#!/bin/bash
# Check if jira@ai-helpers plugin is installed
# Outputs a warning if not found, or context injection if present

if ! find "${HOME}/.claude/plugins" -path "*/jira/*" -name "plugin.json" 2>/dev/null | grep -q .; then
  echo '{"additionalContext": "WARNING: jira-auto-pm plugin requires jira@ai-helpers to be installed. Some features may not work correctly. Install with: /plugin install jira@ai-helpers"}'
else
  echo '{"additionalContext": "The jira-auto-pm plugin is active. When planning work related to a JIRA card, invoke the jira-auto-pm skill to ensure the plan references the JIRA key for automatic lifecycle tracking."}'
fi
