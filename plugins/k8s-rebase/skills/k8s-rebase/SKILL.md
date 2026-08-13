---
name: k8s-rebase
description: Rebase a Go project to a new Kubernetes version by bumping all k8s.io/* dependencies, running codegen, updating version references, fixing build breakage with antagonistic review, and presenting a gh pr create command.
argument-hint: "[--bump-tools] <version> (e.g., 1.36.0 or --bump-tools 1.36.0)"
user-invocable: true
allowed-tools: Bash, Read, Agent
---

# Kubernetes Rebase

Automates k8s dependency rebases for Go projects. Steps 3-4 are where
you add unique value — the quality gates that prevent CI rejection. A
rebase that skips them will fail CI. **The rebase is NOT finished until
you present a `gh pr create` command to the user in Step 5.**

**Arguments:** $ARGUMENTS

**NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go mod edit`,
`go generate`, or `go run`.** These corrupt k8s version pins via MVS.

**NEVER run `git push` or `gh pr create`.** Only print commands for
the user.

## Bootstrap

Run from the current branch (do not switch branches).

```bash
PLUGIN_ROOT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -path "*/k8s-rebase" -name "scripts" -type d 2>/dev/null | head -1 | sed 's|/scripts$||')
ORCH="$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh"
REPO_ROOT=$(git rev-parse --show-toplevel)
VERSION=$(echo "$ARGUMENTS" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "PLUGIN_ROOT=$PLUGIN_ROOT"
echo "REPO_ROOT=$REPO_ROOT"
echo "VERSION=$VERSION"
bash "$ORCH" init "$REPO_ROOT" "$VERSION"
```

## Execute Current Step

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` —
   these rules apply to ALL steps. Internalize them.

2. The orchestrator printed the current step name and file. Read
   that step file using the Read tool:
   `${CLAUDE_PLUGIN_ROOT}/skills/k8s-rebase/steps/<step-file>.md`

3. Launch an Agent with the step file instructions + rules.md +
   repo context. Include in the Agent prompt: repo path, k8s
   version, PLUGIN_ROOT path, "Read rules.md first", the step
   file path, and the gate directory path.

4. When the step agent completes, run:
   ```bash
   bash "$ORCH" advance "$REPO_ROOT"
   ```
   - Exit 0 → read the next step file and continue
   - Exit 1 → gate-fix loop (fix, commit, re-run gates, retry advance)
   - Exit ≥2 → stop and include the error in your response

5. Repeat until the orchestrator prints `DONE: all steps complete`.

6. After DONE: read and execute
   `${CLAUDE_PLUGIN_ROOT}/skills/k8s-rebase/steps/step5-pr.md`
   (PR command generation + cleanup). Step 5 has no gates — it runs
   after the orchestrator confirms all gated steps are complete.

## Recovery

If resuming a crashed or interrupted session:
```bash
bash "$ORCH" status "$REPO_ROOT"
```
This shows the current step and gate progress. Continue from there.
