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
2. Map the component to a repo (see Repo URLs below), confirm with the user, and clone if needed.
3. Create a worktree named after the ticket:
   ```bash
   git worktree add .worktrees/ocpnode-1234 -b wt/ocpnode-1234
   cd .worktrees/ocpnode-1234
   ```

## Component to Repo Mapping

| Jira Label / Component | Repo |
|-------------------------|------|
| `crio` | cri-o |
| `kubelet` | kubernetes |
| `mco` | machine-config-operator |
| `crun` | crun |
| `conmonrs` | conmon-rs |
| `kueue` | kueue-operator |

> For CVE analysis, the `node-cve` plugin maintains its own more detailed
> mapping (downstream forks, branch patterns, languages) in
> `plugins/node-cve/skills/analyze-cve-repos/SKILL.md` — that one is
> authoritative for CVE work; this table only routes day-to-day dev tasks.

## Enable the Node Team Plugin in the Worktree

After creating a worktree, install the plugin locally so it's available when you launch Claude there:

```bash
cd .worktrees/<name>
claude plugin install node-team@ai-helpers --scope local
```

## Repo URLs

| Component | Upstream | Downstream (OpenShift) |
|-----------|----------|------------------------|
| CRI-O | `https://github.com/cri-o/cri-o.git` | `https://github.com/openshift/cri-o.git` |
| Kubelet | `https://github.com/kubernetes/kubernetes.git` | `https://github.com/openshift/kubernetes.git` |
| MCO | — | `https://github.com/openshift/machine-config-operator.git` |
| crun | `https://github.com/containers/crun.git` | — |
| conmon-rs | `https://github.com/containers/conmon-rs.git` | — |
| Kueue Operator | `https://github.com/kubernetes-sigs/kueue.git` | `https://github.com/openshift/kueue-operator.git` |

For upstream features and bug fixes, clone upstream. For OpenShift-specific work, clone downstream.

## Cleanup

```bash
# List worktrees
git worktree list

# Remove when done
git worktree remove .worktrees/<name>
git branch -d wt/<name>
```
