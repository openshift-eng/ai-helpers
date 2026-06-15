# Standard Repo Setup

All node team repos follow the same clone + worktree workflow for feature work.

## Clone

Clone into the current working directory (if not already present):

```bash
git clone <repo-url>
cd <repo-name>
```

## Worktree for Feature Work

Never work directly on the default branch. Create a worktree:

```bash
git worktree add .worktrees/<name> -b wt/<name>
cd .worktrees/<name>
```

Deduce `<name>` from the task description (e.g., "reflink feature" -> `reflink`, "fix cgroup leak" -> `fix-cgroup-leak`, "OCPNODE-1234" -> `ocpnode-1234`).

## Worktree for PR Work

To review or continue work on an existing PR:

```bash
git fetch origin pull/<number>/head:pr-<number>
git worktree add .worktrees/pr-<number> pr-<number>
cd .worktrees/pr-<number>
```

If resuming work on a PR you've already fetched, check `git worktree list` first — the worktree may already exist.

## Worktree for Jira Ticket Work

To investigate or fix a Jira issue:

1. Fetch the issue details to determine the component (see [jira.md](jira.md) for auth setup):
   ```bash
   curl -s -u "$JIRA_USER:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/issue/OCPNODE-1234?fields=summary,components"
   ```
2. Map the component to a repo (see [shared/components.md](shared/components.md)), confirm with the user, and clone if needed.
3. Create a worktree named after the ticket:
   ```bash
   git worktree add .worktrees/ocpnode-1234 -b wt/ocpnode-1234
   cd .worktrees/ocpnode-1234
   ```

## Component to Repo Mapping

See [shared/components.md](shared/components.md) for the full component list,
downstream fork URLs, branch patterns, and languages. The "Day-to-Day Dev
Shorthand" section there provides a quick lookup for common dev tasks.

For upstream features and bug fixes, clone upstream. For OpenShift-specific
work, clone downstream.

## Enable the Node Team Plugin in the Worktree

After creating a worktree, install the plugin locally so it's available when you launch Claude there:

```bash
cd .worktrees/<name>
claude plugin install node-team@ai-helpers --scope local
```

## Cleanup

```bash
# List worktrees
git worktree list

# Remove when done
git worktree remove .worktrees/<name>
git branch -d wt/<name>
```
