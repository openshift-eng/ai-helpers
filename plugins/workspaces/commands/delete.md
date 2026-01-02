---
description: Delete a workspace and its git worktrees
argument-hint: <workspace-name>
---

## Name
workspaces:delete

## Synopsis
```
/workspaces:delete <workspace-name>
```

## Description
The `workspaces:delete` command removes a workspace directory and its associated git worktrees. Before deletion, it checks the status of all repositories in the workspace to detect uncommitted changes or unpushed commits, prompting the user for confirmation when issues are found.

This command helps clean up task workspaces created by `/workspaces:create` while ensuring no work is accidentally lost.

## Implementation

### Workflow

```
- [ ] Step 1: Identify workspace and check configuration
- [ ] Step 2: Execute deletion
```

---

## Step 1: Identify workspace and check configuration

Get available workspaces (includes configuration check):

```bash
${CLAUDE_PLUGIN_ROOT}/commands/delete/list.sh
```

**If the output contains `STATUS: NOT_CONFIGURED`**:

1. Use AskUserQuestion to ask the user for:
   - **Git repositories root**: Full path to where git repos are cloned (e.g., `/home/user/git-repos` or `~/work/repos`)
   - **Workspaces root**: Full path to where workspaces will be created (e.g., `/home/user/workspaces` or `~/dev/workspaces`)

2. Run list again with the user's paths:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/commands/delete/list.sh --repos-root <REPOS_PATH> --workspaces-root <WORKSPACES_PATH>
   ```

3. Verify the output shows `CONFIGURATION SAVED` before proceeding to Step 2

Match user's input against the workspace list:
- **Exact match found**: Proceed to Step 2
- **Partial matches found**: Use AskUserQuestion to let user select from matches
- **No matches**: Use AskUserQuestion to let user select from all workspaces or cancel

---

## Step 2: Execute deletion

**Use the workspace NAME (not full path)** from Step 1.

**Example**: If the workspace is at `/home/user/workspaces/feature-azure-template-field`, use `feature-azure-template-field` (not the full path).

### Step 2.1: Attempt deletion

Execute the deletion script:
```bash
${CLAUDE_PLUGIN_ROOT}/commands/delete/execute.sh {WORKSPACE_NAME}
```

The script will:
1. **Check status** of all repositories in the workspace
2. **Display** the status to the user
3. **Proceed automatically** if workspace is clean
4. **Request user input** if there are uncommitted changes or unpushed commits

### Step 2.2: Handle the result

**Case A: Exit code 0** (success)

The workspace was clean and has been deleted successfully. Report completion to user.

---

**Case B: Exit code 2** (user input required)

The workspace has uncommitted changes or unpushed commits. The status has already been displayed to the user.

Use AskUserQuestion with these options:
1. **"Keep branches (Recommended)"** - Description: "Delete workspace but keep git branches. You can still access unpushed commits from the main repository."
2. **"Delete branches"** - Description: "Delete workspace AND branches. Warning: uncommitted changes and unpushed commits will be lost."
3. **"Abort"** - Description: "Cancel the deletion operation."

Then execute based on user's choice:

**If user chose "Keep branches"**:
```bash
${CLAUDE_PLUGIN_ROOT}/commands/delete/execute.sh {WORKSPACE_NAME} --keep-branches
```

**If user chose "Delete branches"**:
```bash
${CLAUDE_PLUGIN_ROOT}/commands/delete/execute.sh {WORKSPACE_NAME} --delete-branches
```

**If user chose "Abort"**:
- Do not execute deletion
- Inform user: "Deletion cancelled. Workspace remains intact."

---

**Case C: Exit code 1** (error)

An error occurred (e.g., workspace not found, configuration issue). Report the error to the user.
