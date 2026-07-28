---
name: block-push
description: Prevent git push and gh pr create during k8s-rebase skill execution
event: PreToolUse
tools:
  - Bash
---

Check if the Bash command contains a git push or gh pr create operation.
The k8s-rebase skill must NEVER push to remotes or create PRs — the user
does this manually after reviewing the rebase result.

Block the command if it matches ANY of these patterns:
- `git push` (any arguments)
- `git send-pack`
- `gh pr create`
- `gh api` with `pulls` in the URL (PR creation via API)

If the command matches, respond with:

```
BLOCK: The k8s-rebase skill does not push or create PRs.
To push manually: git push origin <branch>
To create PR: gh pr create --title "..." --body "..."
```

If the command does NOT match any pattern, respond with:

```
ALLOW
```
