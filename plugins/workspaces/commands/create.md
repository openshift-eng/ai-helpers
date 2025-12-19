---
description: Create a workspace with git worktrees for multi-repository development
argument-hint: <short-description> <repo1|url> [repo2...]
---

## Name
workspaces:create

## Synopsis
```
/workspaces:create <short-description> <repo1|url> [repo2...]
```

## Description
The `workspaces:create` command creates a dedicated workspace directory with git worktrees for multi-repository development. It intelligently parses the workspace description to identify repositories, PR URLs, and JIRA keys, then sets up isolated git worktrees on a new feature branch or checks out a PR for review.

This command streamlines working on tasks that span multiple repositories by keeping all related code changes synchronized in a single workspace.

## Implementation

### Workflow

```
- [ ] Step 1: Gather info and check configuration
- [ ] Step 2: Parse workspace description
- [ ] Step 3: Ask user to confirm
- [ ] Step 4: Validate and execute
```

---

## Step 1: Gather info and check configuration

Run the gather script (which includes preflight check):

```bash
${CLAUDE_PLUGIN_ROOT}/commands/create/gather.sh
```

**If the output contains `STATUS: NOT_CONFIGURED`**:

1. Use AskUserQuestion to ask the user for:
   - **Git repositories root**: Full path to where git repos are cloned (e.g., `/home/user/git-repos` or `~/work/repos`)
   - **Workspaces root**: Full path to where workspaces will be created (e.g., `/home/user/workspaces` or `~/dev/workspaces`)

2. Run gather again with the user's paths:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/commands/create/gather.sh --repos-root <REPOS_PATH> --workspaces-root <WORKSPACES_PATH>
   ```

3. Verify the output shows `CONFIGURATION SAVED` before proceeding to Step 2

**If TEMPLATE is MISSING**: Abort with error.

---

## Step 2: Parse workspace description

**Check for custom rules**: From Step 1 output, check if `=== CUSTOM_PROMPT ===` section is present:

- **If present**: Apply the aliases and auto-detect rules defined in that section
- **If not present**: Use generic parsing without aliases or auto-detect

**Extract from workspace description:**
- **GitHub PR URLs**: `github.com/{org}/{repo}/pull/{number}`
- **Jira keys**: Pattern `[A-Z]+-[0-9]+` (e.g., TEAM-1234, PROJECT-567)
- **Repository names**: Match against repos listed in Step 1 REPOS section

**Apply custom rules** (if custom-prompt.md was found):
- Expand any aliases defined in the file
- Apply auto-detect rules to add dependent repositories

**Workspace directory name priority**:
1. Jira key (if found in description)
2. `review-{repo}-{pr}` (if PR URL found)
3. `feature-{summary}` (derive from description)

---

## Step 3: Ask user to confirm

Use AskUserQuestion for:
- **Repositories**: 1-3 specific combinations
- **Workspace name**: 1-3 actual suggestions

**If user picks "Other" for repositories**: Ask a second confirmation to verify their custom repo list before proceeding.

---

## Step 4: Execute workspace creation

**Use the workspace NAME (not full path)**.

For feature workspaces:
```bash
${CLAUDE_PLUGIN_ROOT}/commands/create/execute.sh {WORKSPACE_NAME} {BRANCH} feature {REPO1} {REPO2} ...
```

For PR review workspaces:
```bash
${CLAUDE_PLUGIN_ROOT}/commands/create/execute.sh {WORKSPACE_NAME} {BRANCH} review:{PR_NUM} {REPO1} {REPO2} ...
```

**Example**: Use `feature-azure-template-field` (not `/home/user/workspaces/feature-azure-template-field`).

The script will create the workspace with worktrees for each repository. If any issues are found, the script will abort with an error message.

Report the workspace location and worktrees created to the user.
