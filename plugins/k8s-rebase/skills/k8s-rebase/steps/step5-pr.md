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
k8s 1.N → OCP 4.(N-13) for k8s ≤1.35. k8s 1.N → OCP 5.(N-36) for k8s ≥1.36.

If `IS_DOWNSTREAM` is true, the PR title needs a Jira ticket key.
If interactive, ask. If background mode, use `REPLACE-WITH-JIRA-KEY:`.

## 5b. Adversarial pre-PR review

Before generating the PR command, run an independent juror over the full rebase diff:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
DIFF=$(git diff "$BASE"..HEAD -- . ':!.rebase-tmp' \
  ':(exclude,glob)**/vendor/**' ':(exclude,glob)**/go.sum' \
  ':(exclude,glob)**/*generated*' ':(exclude,glob)**/*deepcopy*' \
  2>/dev/null | head -c 200000)
# Use a quoted heredoc for the static instructions so $-signs in Go diff
# content aren't mangled, then append the diff separately.
_STATIC=$(cat <<'REVIEW_STATIC'
You are an adversarial reviewer for a k8s rebase. Review the diff below and output
exactly one of:
  APPROVE: <one-sentence reason>
  REJECT: <one-sentence reason>

Check for:
1. VERSION CONSISTENCY: are all k8s.io/* dependencies at the same minor version
   (no alpha/pre-release mixed with release)? If go.mod shows v0.35.x mixed with
   v0.36.x for direct deps, REJECT.
2. COMMIT COMPLETENESS: does the commit history include a rebase commit, codegen
   (if the repo has it), version refs update, and lint fixes? If a required commit
   type appears missing, REJECT.
3. REGRESSIONS: any obvious API removals, deleted test cases, or missing error
   handling that tests previously covered? If so, REJECT.
4. VERSION MATCH: does the diff content (API calls, import paths, version strings)
   appear consistent with the claimed k8s target version?

If in doubt, APPROVE — only REJECT on clear concrete evidence in the diff.
REVIEW_STATIC
)
VERDICT=$(claude -p --output-format text 2>/dev/null <<< "${_STATIC}

DIFF:
${DIFF}")
echo ":: Pre-PR review: $VERDICT"
```

If verdict is `REJECT:`, investigate the stated concern before proceeding.
`APPROVE:` (or no verdict from infrastructure failure) → continue to 5c.

## 5c. Generate `gh pr create` command

**Do NOT execute this.** Print for user to copy-paste.

Run `git log --oneline $BASE..HEAD` for the commit list. PR body:
- One-line summary: k8s version, Go version
- What changed: fix categories from commit subjects
- Commit table: git log output, note mechanical vs manual
- Verification: what passed locally
- Footer: "All commits carry `Assisted-by: Claude Code <noreply@anthropic.com>` trailers."

Output `gh pr create --title "..." --body "..."` using a heredoc.

## 5d. Suggest CI monitoring

Print: `/loop 5m check CI on the PR, explore any failures max carefully`

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

Do NOT delete `.rebase-tmp/gates/`.

---

Step 5 is the final step — the rebase is complete after PR
generation. Do NOT run orchestrator advance (step 5 is not in the
orchestrator's step list).
