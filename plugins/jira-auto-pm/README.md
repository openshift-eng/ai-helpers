# Jira Auto PM Plugin

Automatically keeps JIRA cards in sync with implementation progress. As you work through tasks, the plugin posts plans, tracks PRs, manages status transitions, and validates card state -- all without manual intervention.

## Features

- **Automatic Plan Posting** - Posts your implementation plan to the JIRA card as a structured comment when work begins
- **PR Linking** - Links pull requests to the JIRA card as tasks complete
- **Status Transitions** - Moves cards through workflow states (In Progress, Code Review, Done) based on task progress
- **State Validation** - Validates card state before every transition and flags misalignment instead of forcing changes
- **Session Resumability** - Prefixed `[jira-auto-pm]` comments allow reconstructing plan progress from the JIRA card across sessions
- **JIRA Key Detection** - Automatically finds the relevant JIRA key from conversation context, git branch name, or recent commits

## Prerequisites

- Claude Code installed
- `jira@ai-helpers` plugin installed (`/plugin install jira@ai-helpers`)
- Atlassian MCP server configured (see [jira plugin README](../jira/README.md) for setup instructions)

## Installation

Ensure you have the ai-helpers marketplace enabled, via [the instructions here](/README.md).

```bash
# Install the jira plugin dependency first (if not already installed)
/plugin install jira@ai-helpers

# Install the plugin
/plugin install jira-auto-pm@ai-helpers
```

## How It Works

This plugin has no commands. It operates entirely through hooks, a skill, and a background PM agent that activate automatically during your workflow.

### Skill: Plan-Time JIRA Awareness

When you enter plan mode with a JIRA key in context, the `jira-auto-pm` skill auto-invokes. It detects the JIRA key, fetches card state, and ensures your plan clearly references the JIRA key. The plan will include PR tasks and a final verification task.

### TaskCompleted Hook: PM Agent

Each time a task completes, the hook spawns a lightweight PM agent (Haiku) that:

1. Finds the JIRA key in the task list
2. Posts the implementation plan to the card (on first task completion)
3. Links PRs mentioned in completed task descriptions
4. Transitions the card through workflow states as milestones are reached
5. Posts a completion summary when all tasks are done

### SessionStart Hook: Dependency Check

On session start, the hook verifies that the `jira` plugin dependency is available and the Atlassian MCP server is configured.

## Lifecycle

```
Session starts
  └── SessionStart hook injects jira-auto-pm context

User enters plan mode with JIRA key in context
  └── jira-auto-pm skill auto-invokes
      └── Detects JIRA key (from context, branch, or commits)
      └── Fetches card state
      └── Ensures plan clearly references JIRA key
      └── Plan includes: PR tasks, final verification task

User approves plan (context may clear, plan file re-loaded)
  └── Implementation begins, tasks created from plan

First task completes
  └── TaskCompleted hook -> PM agent
      └── Finds JIRA key in task list
      └── No plan comment on card yet -> posts plan, transitions to "In Progress"

Implementation task completes (with PR URL in description)
  └── TaskCompleted hook -> PM agent
      └── Links PR to JIRA card
      └── Posts progress comment with PR details

Last PR-related task completes
  └── TaskCompleted hook -> PM agent
      └── Detects all PR tasks done
      └── Transitions card to "Code Review"

Final task completes
  └── TaskCompleted hook -> PM agent
      └── All tasks done
      └── Posts completion summary
      └── Transitions card to "Done"

At ANY step, if card state is misaligned:
  └── PM agent flags to user with proposed remediation
  └── Does NOT take the action
```

## JIRA Key Detection

The plugin detects the relevant JIRA key using the following priority order:

1. **Conversation context** - JIRA key mentioned in the current conversation or task descriptions
2. **Git branch name** - Parsed from branch names like `PROJ-123-fix-something`
3. **Recent commits** - Extracted from commit messages referencing JIRA keys

## Comment Format

All comments posted to JIRA cards are prefixed with `[jira-auto-pm]`. This prefix serves two purposes:

- **Identification** - Clearly marks which comments were posted by the plugin
- **Session resumability** - When resuming work in a new session, the plugin reads these comments to reconstruct what has already been posted and which transitions have occurred

## State Validation

Before every status transition, the PM agent validates that the card is in an expected state. If the card state does not match expectations (for example, the card was manually moved), the agent flags the misalignment to the user with a proposed remediation rather than forcing the transition.

## Troubleshooting

### No JIRA key found

The plugin could not detect a JIRA key from the conversation, branch name, or recent commits. Make sure your plan or task list references a JIRA key (e.g., `PROJ-123`), or that your git branch includes one.

### Transition failures

JIRA workflow transitions may fail if the card is not in the expected status. Check the card's current status in JIRA and verify that the target transition is available. The PM agent will report the specific transition error.

### MCP tools unavailable

If the Atlassian MCP server is not running or not configured, the plugin cannot interact with JIRA. Verify that:

- The MCP server is running (see [jira plugin README](../jira/README.md) for setup)
- The server is registered with Claude Code (`claude mcp list` to verify)
- Your JIRA personal access token is valid and not expired

### Plugin dependency not detected

The `jira-auto-pm` plugin requires `jira@ai-helpers`. Install it with `/plugin install jira@ai-helpers` and restart your session.

## License

Apache-2.0
