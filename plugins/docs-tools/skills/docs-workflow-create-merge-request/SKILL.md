---
name: docs-workflow-create-merge-request
description: Commit, push, and create a merge request (GitLab) or pull request (GitHub) for documentation changes. Creates a feature branch if the repo is on main/master. Replaces docs-workflow-prepare-branch, docs-workflow-commit, and docs-workflow-create-mr.
model: claude-haiku-4-5@20251001
argument-hint: <ticket> --base-path <path> [--draft] [--repo-path <path>]
allowed-tools: Bash, Read
---

# Create Merge Request Step

Step skill for the docs-orchestrator pipeline. After writing and reviews are complete, this step creates a feature branch (if needed), commits the manifest-listed files, pushes to the remote, and creates an MR/PR via `gh` (GitHub) or `glab` (GitLab).

**Skipped in draft mode** (`--draft` flag). When `--repo-path` is set, the script operates in the target repo but expects the user to have already switched to a feature branch.

## Arguments

- `$1` — JIRA ticket ID (required)
- `--base-path <path>` — Base output path (e.g., `.agent_workspace/proj-123`)
- `--draft` — If present, skip all git operations
- `--repo-path <path>` — Target documentation repository (must already be on a feature branch)

## Input

```
<base-path>/writing/step-result.json
```

Contains the `files` array of absolute paths to commit (written by the writing step).

## Output

```
<base-path>/create-merge-request/step-result.json
```

Combined sidecar with commit, push, and MR/PR metadata.

## Execution

Run the script, passing through all arguments:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/create_merge_request.sh <ticket> --base-path <base-path> [--draft] [--repo-path <path>]
```

The script handles:

1. **Skip mode** — writes a skip sidecar and exits if `--draft` is set
2. **Git context** — resolves repo root, current branch, remote URL, and platform (GitHub/GitLab)
3. **Branch creation** — if on `main` or `master` (and no `--repo-path`), creates `<ticket-lowercase>` branch from HEAD or switches to it if it already exists
4. **Safety** — refuses to proceed if on `main`/`master` with `--repo-path` (externally managed repos must be on a feature branch)
5. **Manifest reading** — reads file paths from `writing/step-result.json` and filters to files under the repo root
6. **Staging and commit** — stages manifest files and commits with `docs(<ticket>): add generated documentation`
7. **Push** — pushes with `--force-with-lease` to origin
8. **Title building** — derives MR/PR title from `requirements/step-result.json` title field or first heading in `requirements.md`
9. **Existing check** — searches for an open MR/PR from the feature branch before creating a new one
10. **MR/PR creation** — creates via `gh pr create` (GitHub) or `glab mr create` (GitLab), with fork detection for GitLab via the `upstream` remote
11. **Sidecar** — writes `step-result.json` with commit_sha, branch, pushed, url, action, platform, skipped, and skip_reason fields
