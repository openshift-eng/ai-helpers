# Step 5: PR and Cleanup

**PROGRESS: 95% complete**

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

**CRITICAL: NEVER run `git push` or `gh pr create` yourself.**
Only print commands for the user to copy-paste.

## 5a. Gather data and detect downstream

```bash
PRIMARY_GOMOD=$(find . -name go.mod -not -path '*/vendor/*' -not -path '*/.claude/*' -exec grep -l 'k8s.io/' {} \; 2>/dev/null | head -1)
K8S_VER=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -oE 'v[0-9.]+' | head -1)
GO_VER=$(grep '^go ' "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}')
IS_DOWNSTREAM=$(git remote -v 2>/dev/null | grep -q 'openshift/' && echo true || echo false)
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
```

**OCP version mapping** (see rules.md for the full table):
k8s 1.N → OCP 4.(N-13) for k8s ≤1.35. OCP 5.0 = k8s 1.36+.

If `IS_DOWNSTREAM` is true, the PR title needs a Jira ticket key.
If interactive, ask. If background mode, use `REPLACE-WITH-JIRA-KEY:`.

## 5b. Generate `gh pr create` command

**Do NOT execute this.** Print for user to copy-paste.

Run `git log --oneline $BASE..HEAD` for the commit list. PR body:
- One-line summary: k8s version, Go version
- What changed: fix categories from commit subjects
- Commit table: git log output, note mechanical vs manual
- Verification: what passed locally
- Footer: "All commits carry `Assisted-by: Claude Code` trailers."

Output `gh pr create --title "..." --body "..."` using a heredoc.

## 5c. Suggest CI monitoring

Print: `/loop 5m check CI on the PR, explore any failures max carefully`

## 5d. Write rebase report

Write final report to `.rebase-tmp/rebase-report.json` with: repo,
versions, per-step
data (duration, error categories, patterns applied), discoveries,
unresolved items, and skill_improvements array.

For skill_improvements: concrete, actionable suggestions backed by
what you observed — not generic advice.

## 5e. Clean up

```bash
rm -rf .rebase-tmp/step*.log .rebase-tmp/step*.pid .rebase-tmp/*.log \
       .rebase-tmp/*.txt .rebase-tmp/*.pid \
       .rebase-tmp/crd-pre-codegen/
rm -f .rebase-tmp/.session-active

# Remove the pre-push hook installed by k8s-rebase.sh (restore backup if exists)
HOOK_DIR="$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/hooks"
if [[ -f "$HOOK_DIR/pre-push" ]] && grep -q 'k8s-rebase' "$HOOK_DIR/pre-push" 2>/dev/null; then
  rm -f "$HOOK_DIR/pre-push"
  [[ -f "$HOOK_DIR/pre-push.bak.k8s-rebase" ]] && mv "$HOOK_DIR/pre-push.bak.k8s-rebase" "$HOOK_DIR/pre-push"
fi
```

Do NOT delete `.rebase-tmp/gates/` or `.rebase-tmp/rebase-report.json`.

---

Step 5 is the final step — the rebase is complete after PR
generation. Do NOT run orchestrator advance (step 5 is not in the
orchestrator's step list).
