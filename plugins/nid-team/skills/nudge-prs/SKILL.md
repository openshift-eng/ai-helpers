---
name: nudge-prs
description: "Review and send NI&D PR dashboard reminders for stale assigned High or Urgent PRs in GitHub Project 28. Use when asked to nudge reviewers or preview inactivity reminder comments."
---

# Nudge stale NI&D PRs

Read and follow the [PR reminder workflow](../../commands/nudge-prs.md), including
its dry-run preview before posting reminders. Preserve the requested inactivity
threshold and priorities.

Resolve the plugin root from the actual location of this `SKILL.md`: two
directories above the directory containing the file. Substitute that absolute
path for `${CLAUDE_PLUGIN_ROOT}` in the workflow's commands. This also works
when the plugin is installed outside the ai-helpers repository.

Run the script bundled with this plugin. It loads the adjacent
`scripts/pr-dashboard/config.sh` for the shared team and project configuration.
