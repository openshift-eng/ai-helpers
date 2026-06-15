---
description: Clone a Node team repo and set up a worktree for development
argument-hint: "<component> [--ticket OCPNODE-1234] [--pr 456]"
---

## Name
node-team:setup

## Synopsis
```text
/node-team:setup <component> [--ticket OCPNODE-1234] [--pr 456]
```

## Description

Sets up a development environment for a Node team component. Clones the
appropriate downstream or upstream repo (based on the component-to-repo
mapping), creates a git worktree for the task, and installs the node-team
plugin locally in the worktree.

When given a Jira ticket or PR number, names the worktree after it and (for
tickets) fetches the issue summary to confirm the right component.

## Implementation

0. Run the checks from `/node-team:preflight` to confirm GitHub and Jira tokens
   are valid. If any required check fails, stop and show remediation steps
   before proceeding.
1. Read the component-to-repo mapping from
   [shared/components.md](../skills/node/references/shared/components.md).
   Match the `<component>` argument against the "Day-to-Day Dev Shorthand"
   table or the full component names (case-insensitive, partial match OK).
   If ambiguous, ask the user to clarify.
2. Determine the repo URL. For OpenShift-specific work, use the downstream
   fork. For upstream contributions, use the upstream repo. If unclear, ask
   the user.
3. Clone the repo if not already present in the current directory:
   ```bash
   git clone <repo-url>
   cd <repo-name>
   ```
4. Create a worktree following the workflow in
   [SETUP.md](../skills/node/references/SETUP.md):
   - `--ticket OCPNODE-1234`: name the worktree after the ticket
     (`wt/ocpnode-1234`), fetch issue details from Jira to confirm the
     component matches
   - `--pr 456`: fetch the PR and create a worktree for it
     (`pr-456`)
   - Neither: deduce a name from the task context
5. Install the node-team plugin in the worktree:
   ```bash
   claude plugin install node-team@ai-helpers --scope local
   ```
6. Print the worktree path and a short summary of what was set up.

## Return Value

- The path to the created worktree and confirmation of plugin installation

## Examples

1. **Set up CRI-O for a Jira ticket**:
   ```text
   /node-team:setup crio --ticket OCPNODE-5678
   ```

2. **Set up kubelet for PR review**:
   ```text
   /node-team:setup kubelet --pr 12345
   ```

3. **Set up MCO for general development**:
   ```text
   /node-team:setup mco
   ```

## Arguments

- `<component>`: Component short name (e.g., `crio`, `kubelet`, `mco`,
  `kueue`, `conmonrs`, `crun`). Required.
- `--ticket <key>`: Jira issue key to associate with the worktree. Optional.
- `--pr <number>`: PR number to fetch and review. Optional.
