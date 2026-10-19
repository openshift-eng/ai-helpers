---
name: sync-pr-dashboard
description: "Maintain the NI&D PR dashboard in GitHub Project 28. Use when asked to populate PR authors, sync reviewers to assignees, add shared repo PRs, or classify ambiguous PR Area values."
---

# Sync the NI&D PR dashboard

Read and follow the [dashboard sync workflow](../../commands/sync-pr-dashboard.md).
Complete the script run, AI classification of ambiguous PR areas, and reporting
steps described there.

Resolve the plugin root from the actual location of this `SKILL.md`: two
directories above the directory containing the file. Substitute that absolute
path for `${CLAUDE_PLUGIN_ROOT}` in the workflow's commands. This also works
when the plugin is installed outside the ai-helpers repository.

Run the scripts bundled with this plugin. They load the adjacent
`scripts/pr-dashboard/config.sh` for the shared team and project configuration.
