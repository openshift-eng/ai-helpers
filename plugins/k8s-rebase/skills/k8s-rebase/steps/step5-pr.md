# Step 5: PR and Cleanup

PROGRESS: 95% complete

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

**CRITICAL: NEVER run `git push` or `gh pr create` yourself.**
Only print commands for the user to copy-paste.

## 5a. Gather data and detect downstream

```bash
PRIMARY_GOMOD=$(find . -name go.mod -not -path '*/vendor/*' -not -path '*/.claude/*' -exec grep -l 'k8s.io/' {} \; 2>/dev/null | head -1)
K8S_VER=$(grep 'k8s.io/api ' "$PRIMARY_GOMOD" 2>/dev/null | grep -oE 'v[0-9.]+' | head -1)
GO_VER=$(grep '^go ' "$PRIMARY_GOMOD" 2>/dev/null | awk '{print $2}')
IS_DOWNSTREAM=$(git remote -v 2>/dev/null | grep -q 'openshift/' && echo true || echo false)
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
PR_BASE=$(cat .rebase-tmp/start-branch 2>/dev/null)
[[ -n "$PR_BASE" ]] || PR_BASE=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
UPSTREAM=$(git remote get-url origin | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')
BRANCH=$(git branch --show-current)
printf 'PR_BASE=%s UPSTREAM=%s BRANCH=%s\n' "$PR_BASE" "$UPSTREAM" "$BRANCH"
gh pr list --repo "$UPSTREAM" --state merged --search 'rebase in:title' --limit 5 --json title --jq '.[].title'
```

The PR targets `PR_BASE`, the branch the rebase started from. Do not
substitute a release branch chosen from the OpenShift dependency mapping:
OpenShift release branches are often fast-forwarded copies of the default
branch. Model the title on the repository's previous rebase PR titles.
If `IS_DOWNSTREAM` is true, the PR title needs a Jira ticket key.
If interactive, ask. If background mode, use `REPLACE-WITH-JIRA-KEY:`.

## 5b. Draft the PR body

Write `.rebase-tmp/pr-body.md` for the independent review below. Do not
present the command until review completes.

Use a file-edit tool to retain a proposed publish command for review. The
publish guard conservatively rejects literal publish syntax in shell calls,
including quoted text and heredoc data. Keep the guard enabled; writing a
print-only proposal does not authorize executing it.

Before drafting verification claims, run this inventory from the expected
gate prompts, not just the reports that happen to exist:

```bash
# Bind PLUGIN_ROOT and REPO_ROOT to the verified paths in this call.
bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" reports "$REPO_ROOT"
```

Nonzero exit stops reporting; a successful inventory is not passing
validation. Copy its verdict totals and freshness warnings rather than
hand-counting. Copy the generated Markdown gate table into the PR body's
collapsed inventory verbatim: keep every exact gate name, verdict, reviewed HEAD, and freshness
label. Do not reconstruct names from memory, rename gates as test suites,
combine rows into "additional gates", or add rows for checks absent from
the inventory. Read each report's HEAD, exact VERDICT, and findings, and
`.rebase-tmp/status/INCOMPLETE` if present; quote its force-advance wording
and do not describe advance attempts as repairs or tests. INCOMPLETE records
only the latest force-advance, so list every unresolved or unverified check
from the inventory, including prior steps. Missing, unreadable, or malformed
reports are unverified, not PASS.

In the PR body, keep PASS, justified SKIP (with its reason), and unresolved
FAIL/INCONCLUSIVE distinct. A prior-step PASS is evidence at its recorded
SHA, not a retest of the final tip, and a stale final-step report does not
verify final HEAD. Never manufacture or relabel reports to fill gaps: DONE,
force-advancement, aggregate counts, and independent review approval change
no gate's verdict.

Report executed build, vet, lint, and test commands separately from the gate
table, using their actual outcomes. A PASS from a code-review or CI-prediction
gate does not establish that unit or integration tests passed. A test that
failed during environment setup remains failed/blocked, even when an isolated
base run reproduces that failure. Give the affected package or suite and
reason; mark skipped or unexecuted coverage unverified. Claim test PASS only
when that test command completed successfully at the stated revision.
Derive any package/test counts from complete output; a tail of the log cannot
establish totals. If the full output is unavailable, report the verified
command outcome and scope without inventing counts.
Include nonzero command exits and their failed/blocked scope. A successful
`validate --no-test` wrapper is not lint evidence when its output contains
no linter execution; label an absent lint configuration explicitly.
Do not rule out regressions solely because failing test source is unchanged.

Inspect `git diff "$BASE..HEAD"` and `git log --oneline "$BASE..HEAD"`.
Describe dependency bumps as old → new from removed/added lines, not unchanged
diff context. Confirm both versions in the base and result go.mod files:
moving an existing indirect requirement to the direct block is not adding a
new module. Commit subjects alone do not establish changes.

The PR body is for the repository's maintainers. Write it so a reviewer can
take it in within a minute, in this order:

- One-line summary: "Rebase to Kubernetes <version> (Go <version>)."
- Dependency changes: a short old → new table for the Kubernetes modules,
  controller-runtime, OpenShift modules, and the Go directive, plus one line
  for other notable module moves.
- Code changes: each manual or autofix commit and why the bump required it,
  or "None; mechanical dependency and vendor update."
- Verification: one bullet per executed command with its outcome and scope
  at the stated short SHA (build, vet, lint, unit tests executed vs compiled
  only, vulnerability scan), then one bullet naming what was not run locally
  (for example cloud e2e, race mode, image build).
- Unresolved gates: every FAIL, INCONCLUSIVE, or UNVERIFIED gate with its
  finding, outside any collapsed section. Omit the heading when there are none.
- A collapsed `<details><summary>Rebase gate inventory (…)</summary>` block
  holding the generated gate table, its totals and freshness warnings, and
  each SKIP reason.
- Footer: summarize the actual `Assisted-by` trailers from the branch's commit
  messages. Verify the whole range before claiming all commits share one value;
  a resumed branch may contain assistance from both hosts.

Keep local filesystem paths, `.rebase-tmp` names, and workflow narrative
(interruptions, resumes, retries, review attempts, models, cost) out of the
body. Put them in `.rebase-tmp/pr-evidence.md` instead: for each verification
bullet, the retained log path, actual argv, revision, scope, and completed
exit. The pre-PR review receives that file with the draft.

Reopen the retained logs before drafting: do not
reconstruct invocation details from memory or assume a linter was absent.
The validator retains each command in `.rebase-tmp/validation-*/command.txt`
with its own `HEAD`, command, and producer exit beside `output.log`. Use these
records for attribution; root-level convenience logs can be replaced by later
runs. Check its before/after worktree status and `HEAD_AFTER` too: dirty or
changing source is not verification of a committed SHA alone. A Dockerfile-only
follow-up does not move earlier tests to its new SHA.
Expected gates are not executed checks.

## 5c. Adversarial pre-PR review

Review the full rebase and the draft verification account before presenting
the PR command. The shared preparation and review rubric live in
`scripts/k8s-rebase-pr-review.sh`.

Select **only** the branch for the parent's host runtime from SKILL.md.
Delegating this step does not change that choice.

### Claude Code only

Preserve the nested reviewer and its existing failure policy. Do not use
`--print-prompt` or substitute a native review agent:

```bash
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
VERDICT=$(bash "$PLUGIN_ROOT/scripts/k8s-rebase-pr-review.sh" --verification "$REPO_ROOT/.rebase-tmp/pr-body.md" "$BASE" "$VERSION")
echo ":: Pre-PR review: $VERDICT"
```

Investigate `REJECT:` before proceeding. For Claude, `APPROVE:` or a missing
verdict from infrastructure failure retains the existing continuation policy;
report a missing verdict as review not performed.

### Codex only

Collect checked evidence without invoking Claude. Capture the complete prompt
in a unique scratch file, preserving it beyond tool-output limits. Check the
completed status; preparation success is not approval:

```bash
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
REVIEW_PROMPT=$(mktemp "$REPO_ROOT/.rebase-tmp/step5-review-XXXXXX") || exit 1
prep_rc=0
bash "$PLUGIN_ROOT/scripts/k8s-rebase-pr-review.sh" --print-prompt --verification "$REPO_ROOT/.rebase-tmp/pr-body.md" "$BASE" "$VERSION" > "$REVIEW_PROMPT" || prep_rc=$?
printf '\nPreparation exit status: %s\n' "$prep_rc"
if [[ "$prep_rc" -eq 0 ]]; then
  printf 'Review prompt file: %s\n' "$REVIEW_PROMPT"
fi
exit "$prep_rc"
```

Only after successful preparation, give that invocation's prompt-file path,
repo path, base, and HEAD to a fresh-context read-only native reviewer. Require
it to read the complete file, using bounded chunks if needed, including the
scope and any helper truncation warning. Do not substitute a tool preview or
a prior prompt file. Require an explicit
`APPROVE: <reason>` or `REJECT: <reason>`. Missing/malformed verdicts, failed
preparation, or no independent reviewer stop this path; do not substitute
parent self-review. Investigate rejection before proceeding. On resume,
repeat review if its decision for this SHA/scope is unavailable. Do not
reuse approval after changes; refresh affected gates and review the final tip.

## 5d. Present the reviewed command

After review, print the commands for the user. **Do not execute them.**
Name each review's actual scope: Step 4's selected-commit approval does not
approve the full branch. Step 5 may approve an accurately disclosed draft
with unresolved checks; that does not establish clean candidate readiness.
Report remaining FAIL/INCONCLUSIVE findings separately from review approval.
Use `<fork-remote>` and `<fork-owner>` placeholders unless a remote other than
`origin` clearly points to the user's fork. Copy the reviewed body
byte-for-byte into the heredoc:

```text
git push -u <fork-remote> <BRANCH>
gh pr create --repo <UPSTREAM> --base <PR_BASE> --head <fork-owner>:<BRANCH> \
  --title "<title>" --body-file - <<'K8S_REBASE_PR_BODY'
<reviewed body>
K8S_REBASE_PR_BODY
```

Investigate every rejection,
correct claims against raw evidence or complete the missing check, and repeat
review of the revised draft. Honest limitations may remain. Never change a
verification claim after approval without reviewing the amended draft.
Follow with cleanup status; do not add a second recap with new counts or claims.

## 5e. Suggest CI monitoring

For Claude when `/loop` is available, suggest:
`/loop 5m check CI on the PR, explore any failures max carefully`.
Otherwise suggest asking the agent to check CI after the user creates the PR;
do not configure automation.

## 5f. Clean up

Use host-approved file operations: restore the hook, remove scratch, then
remove the session marker last. Stop on any failure. The Bash block is an
example, not a required execution mechanism; keep its exact targets and order.
When using a shell tool, preserve the explicit Bash wrapper: the host shell
may be zsh, which rejects unmatched globs before `rm` runs. Such an error is
failed cleanup, not an ignorable warning or proof that scratch was removed.

```bash
bash <<'K8S_REBASE_CLEANUP'
# Remove the pre-push hook installed by k8s-rebase.sh (restore backup if exists)
HOOK_DIR="$(git rev-parse --git-common-dir)/hooks" || exit 1
if [[ -f "$HOOK_DIR/pre-push" ]]; then
  HOOK_CONTENT=$(cat "$HOOK_DIR/pre-push") || exit 1
  if [[ "$HOOK_CONTENT" == *k8s-rebase* ]]; then
    if [[ -f "$HOOK_DIR/pre-push.bak.k8s-rebase" ]]; then
      mv "$HOOK_DIR/pre-push.bak.k8s-rebase" "$HOOK_DIR/pre-push" || exit 1
    else
      rm -f "$HOOK_DIR/pre-push" || exit 1
    fi
  fi
fi
rm -rf .rebase-tmp/step*.pid .rebase-tmp/*.pid \
       .rebase-tmp/crd-pre-codegen/ || exit 1
rm -f .rebase-tmp/.session-active || exit 1
K8S_REBASE_CLEANUP
```

Preserve `.rebase-tmp/gates/`, `base-commit`, target-version records,
validation summaries, review prompts/results (including `step[45]-review-*`),
full `*.log` files, and `test-only-*` test output. These
are verification evidence needed to audit the PR's claims, not disposable
process scratch. If cleanup cannot be completed with allowed
tools/access, report incomplete cleanup; do not disable guards or change permissions.
Verify the original hook (including executable mode) and that the listed
scratch targets are gone before claiming cleanup is complete.

---

Step 5 completes after full-rebase review, PR command generation, and
verified cleanup, with unresolved checks retained in the PR body.
Do not call orchestrator `advance`; Step 5 is outside its gated steps.
