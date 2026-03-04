---
name: JIRA Auto PM Plan Tracker
description: Ensures implementation plans reference a JIRA issue key for automatic lifecycle tracking
---

# JIRA Auto PM Plan Tracker

This skill ensures that implementation plans created during plan mode reference a JIRA issue key so that the PM agent hook can automatically track lifecycle events (status transitions, PR linking, verification) during implementation.

## When to Use This Skill

This skill is automatically invoked when:
- The user enters plan mode to create an implementation plan
- The user asks to implement work related to a JIRA issue
- A JIRA key is detected in the conversation context, git branch name, or recent commit messages

## JIRA Key Detection

The skill uses deterministic detection methods in the following priority order. The first match wins.

### 1. Conversation Context

The user explicitly mentions a JIRA key in their message (e.g., "implement GCP-123", "work on OCPBUGS-456").

Scan the user's message for patterns matching `[A-Z][A-Z0-9]+-\d+`.

### 2. Git Branch Name

Run `git branch --show-current` and extract a JIRA key using the regex `[A-Z]+-\d+`.

Common branch naming conventions that contain JIRA keys:
- `GCP-123-add-feature`
- `feature/GCP-123-description`
- `ocpbugs-456/fix-thing` (case-insensitive match, normalize to uppercase)

### 3. Recent Commit Messages

Scan recent commit messages (e.g., `git log --oneline -10`) for patterns matching `^[A-Z]+-\d+:` at the start of commit message subjects.

### 4. No Key Found

If no JIRA key is found from any of the above sources, ask the user:

> No JIRA issue key detected in the conversation, branch name, or recent commits. Would you like to associate this work with a JIRA card? If so, provide the issue key (e.g., GCP-123).

If the user declines, proceed without JIRA tracking. The PM agent hook will simply have no key to act on.

## Plan Requirements

Once a JIRA key is detected, the skill augments the implementation plan with the following elements.

### 1. Fetch Card State

Before finalizing the plan, fetch the current JIRA issue state using `mcp__atlassian__jira_get_issue` to retrieve:
- Current status
- Summary
- Description and acceptance criteria

Use this information to ensure the plan aligns with the card's requirements and definition of done.

### 2. Reference the JIRA Key in the Plan

The first task in the plan must clearly reference the JIRA key. For example:

```
1. Post implementation plan for GCP-123 to JIRA
```

This ensures the JIRA key is present in the plan file itself, which the PM agent hook uses to locate the associated card.

### 3. Identify Expected PRs

The plan must identify which tasks involve opening pull requests and what each PR covers. For example:

```
3. Implement the new controller logic
   - Open PR: "GCP-123: Add firewall rule controller"
5. Update documentation
   - Open PR: "GCP-123: Add firewall controller docs"
```

The PM agent uses this information to know when to link PRs to the JIRA card and when to transition the card status.

### 4. Include a Final Verification Task

The plan must end with a verification task that confirms all work is complete. For example:

```
7. Verify all work for GCP-123 is complete
   - All PRs merged
   - Acceptance criteria met
   - Definition of done satisfied
```

## What This Skill Does NOT Do

- **Add per-task tags** -- the JIRA key referenced in the plan is sufficient for the PM agent to track progress. Individual tasks do not need JIRA key annotations.
- **Add separate "JIRA update" tasks** -- the PM agent handles JIRA status transitions and comment updates transparently during implementation. The plan should not include explicit "update JIRA" steps beyond the initial plan posting and final verification.
- **Execute JIRA calls during planning** -- all JIRA interaction (status transitions, PR linking, comment updates) happens during implementation, not during plan creation. The only JIRA call during planning is the initial `mcp__atlassian__jira_get_issue` to fetch card context.

## Context Survival

The skill ensures the JIRA key survives across plan mode exit and context boundaries:

1. **Key in the plan file** -- the JIRA key is written directly into the plan file content (in the first task and verification task). When the user exits plan mode, the plan file is re-loaded with the JIRA key intact, even if conversation context is cleared.
2. **SessionStart hook re-injection** -- the SessionStart hook re-injects awareness of the jira-auto-pm plugin when a new session begins. If a plan file exists with a JIRA key, the PM agent can pick it up without requiring the user to re-state the key.
3. **No reliance on ephemeral state** -- the skill does not depend on conversation memory or session variables to preserve the JIRA key. The plan file is the single source of truth.
