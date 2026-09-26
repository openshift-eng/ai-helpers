# Step 4: Lint, Test, and Review

**PROGRESS: 80% complete**

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

## 4a. Lint iteration

```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-validate.sh" --no-test
```

**Scope rule (applies before fixing anything):** Only fix lint errors that
are caused by changes required for this rebase. Inspect the finding and the
merge-base diff, including dependencies and lint/toolchain configuration.
An unchanged line can fail against a changed API; a changed line does not by
itself prove the diagnostic is new. Use existing baseline evidence when
sufficient. If baseline execution is needed, use a separate disposable clone,
not a worktree; never stash, reset, or switch the active checkout for comparison.

With `REPO_ROOT` bound and `TMPDIR` pointing outside the target checkout:

```bash
LINT_BASE=$(git -C "$REPO_ROOT" merge-base HEAD master 2>/dev/null ||
            git -C "$REPO_ROOT" merge-base HEAD main) || {
  echo "ERROR: cannot resolve lint baseline from master/main" >&2
  exit 1
}
LINT_BASE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/k8s-rebase-lint-base.XXXXXX") || exit 1
git clone --no-hardlinks --no-checkout -- "$REPO_ROOT" "$LINT_BASE_DIR/repo" || exit 1
git -C "$LINT_BASE_DIR/repo" checkout --detach "$LINT_BASE" || exit 1
printf 'LINT_BASE: %s\nLINT_BASE_REPO: %s\n' "$LINT_BASE" "$LINT_BASE_DIR/repo"
```

Check success and retain the printed SHA/path for later calls. Run only the
relevant lint command in that clone, at the same module/package scope, with
its baseline dependencies/configuration. Record both runs' Go/linter versions
and configuration differences; reproduction only under new tooling does not
establish that a finding existed before the rebase. Do not run the full
validator there: it can build, generate files, and overwrite summaries.
If the baseline cannot run or the comparison is inconclusive, report that
limit; absence of a diagnostic in failed/truncated output is not evidence.
Keep comparison output separate from the active rebase's reports. Leave
pre-existing or unrelated findings unfixed, but retain them in the final
validation/gate results; scope exclusions do not turn failures into PASS/SKIP.

**Never fix these regardless of whether they appear new:**

- `QF1001` (De Morgan's law rewrites) — stylistic, not required by the k8s bump
- `QF1002`, `QF1003`, `QF1004` — similar staticcheck style suggestions
- `S1000`–`S1040` range — simplification suggestions unrelated to API changes
- `ST1001` (import ordering) — style only
- `revive` suggestions that don't reference a removed/changed API

Run lint once, analyze ALL errors before fixing any. Group by category
and fix each in one commit.

Key lint guidance:

- golangci-lint v2 defaults to 3 instances per error type — the
  validate script overrides with `--max-same-issues 0`

- Lint runs in a container (the repo's `make lint` uses docker/podman).
  If the first `--no-test` run produces "UNCLASSIFIED FAILURE (root lint)",
  check if the container pull is failing. Common fix: re-run once — the
  first run often pulls the image and the second run succeeds. If a tool
  is missing (operator-sdk, etc.), that is usually just a warning line
  in the Makefile — the actual lint result is in the container output.
  Make lint work; do not skip it or suppress the findings.
  If infrastructure still prevents lint from completing after the retry,
  report that blocker. If lint completes with findings, triage them under
  the scope rule above; a nonzero exit alone is not an infrastructure failure.
  Do not retry indefinitely or interpret incomplete output as successful lint.

- For errcheck: fix the code, not the linter.
  `defer f.Close()` → `defer func() { _ = f.Close() }()`
  `fmt.Fprintf(w, ...)` where the error is non-critical → `_, _ = fmt.Fprintf(w, ...)`
  Only use `exclude-functions` in `.golangci.yml` when the same pattern
  appears many times AND fixing each instance would obscure the real code.
  Never use per-line `//nolint:errcheck` for patterns that could be fixed in code.

- Staticcheck deprecated calls (SA1019): use selective `//nolint:staticcheck`
  or `exclude-rules`, never disable entirely

- Nilness dead code: remove the entire dead block, do not restructure
- ST1005 error strings: lowercase first letter only, preserve
  acronyms. Grep for OLD string in all files (tests assert on it)

Use `--quick` for build+vet feedback and `--no-test` after lint fixes.
Lint and gate-fix iterations share rules.md's three-iteration budget across
parent and workers; do not reset it at 4b or start a second fix loop.
Stop making fixes when the budget is exhausted or no in-scope fix remains.
Carry unresolved findings into 4b's evidence and the parent handoff, using
SKILL.md's existing blocked/force-advance protocol. Do not claim lint passed
unless the check actually completed successfully.

## 4b. Verification wave

Source-read-only tests and gates may run in parallel, with test workers writing
separate logs and gate reviewers writing only their own reports. Do not overlap
them with source mutations or full validation that replaces shared evidence.
Commit 4a's fixes before collecting their final evidence;
if HEAD changes, refresh every current-step review as in rules.md.
Use native workers when available, or run the same checks inline.
First, discover test packages:

```bash
TEST_GO_SH=$(find . -name "test-go.sh" -path "*/hack/*" -not -path "*/vendor/*" | head -1)
ROOT_PKGS=""
[ -n "$TEST_GO_SH" ] && ROOT_PKGS=$(sed -n '/root_pkgs=(/,/)/p' "$TEST_GO_SH" | grep -oE 'pkg/[^"]+' | tr '\n' '|')
for mod_dir in $(find . -name "go.mod" -not -path "*/vendor/*" -not -path "*/.claude/*" -exec dirname {} \; | sort); do
  echo "=== $mod_dir ==="
  for pkg in $(cd "$mod_dir" && find . -name "*_test.go" -not -path "*/vendor/*" -not -path "*/.claude/*" -exec dirname {} \; | sort -u); do
    [ -n "$ROOT_PKGS" ] && echo "$pkg" | grep -qE "^\./(${ROOT_PKGS%|})(/.+)?$" && continue
    echo "$pkg"
  done
done
```

**Test agents:** Use ONLY packages from discovery above (filters
out root_pkgs that need CAP_NET_ADMIN). Use the validate script's
`--test-only` flag. For large packages (>20k test lines), use native waiting.
Split by test line count, cap ~30k per agent. Check `free -h` first.

**Gate agents:** Run the orchestrator's gates command first:

```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" 4
```

Follow rules.md: delegate PENDING gates when available, or review inline.
Inspect cached non-PASS verdicts too. Gate files are at
`${PLUGIN_ROOT}/gates/step4-verification/`. Each subagent gets: repo path
plus module safety rule plus "Read `<gate-file>` and follow instructions."
Include the absolute plugin root and version in reviewer context.

15 gates: cleanliness, correctness, version-completeness,
maintainer-review, ci-prediction, build-vet-recheck, skill-improvement,
logical-consistency, ci-readiness, gomod-diff-analysis,
deprecated-imports, go-version-check, k8s-changelog, dep-cve-check,
commit-messages.

## Gate-fix loop

If ANY gate reports FAIL: triage against baseline and fix only in-scope issues
within the shared budget. After a fix commit, re-validate with `--no-test`,
then follow rules.md to refresh evidence and complete all stale/pending
current-step reviews, including old PASS reports.
Preserve prior-step reports and newly regenerated companion reports.
Step 4 override: always re-run `validate.sh --no-test` between fix
and gate re-run (catches regressions from fix commits).

If test agents report failures:

- **Timeout:** likely feature gate issue (informer hang)
- **Flaky:** re-run individual test with `-count=1 -run TestName`
- **Container timing:** check if test code changed in rebase
- **Pre-existing:** use 4a's baseline/evidence check; unchanged test code can
  fail because dependencies changed.

## 4c. Independent review

Select **only** the branch for the parent's host runtime from SKILL.md.
Delegating this step does not change that choice.

### Claude Code only

Run the existing nested reviewer. Do not use `--print-prompt` or substitute
a native review agent, even when native workers are available:

```bash
bash "$PLUGIN_ROOT/scripts/k8s-rebase-review.sh" "$(git rev-parse HEAD)" "k8s rebase"
```

Investigate `REJECT:` before continuing. Preserve the helper's existing
infrastructure fallback; Claude does not require a native independent reviewer.

### Codex only

Prepare the selected-commit evidence without invoking Claude. Capture the
complete prompt in a unique scratch file so tool-output limits cannot truncate
the handoff. Check the completed status; preparation success is not approval:

```bash
REVIEW_PROMPT=$(mktemp "$REPO_ROOT/.rebase-tmp/step4-review-XXXXXX") || exit 1
prep_rc=0
bash "$PLUGIN_ROOT/scripts/k8s-rebase-review.sh" --print-prompt "$(git rev-parse HEAD)" "k8s rebase" > "$REVIEW_PROMPT" || prep_rc=$?
printf '\nPreparation exit status: %s\n' "$prep_rc"
if [[ "$prep_rc" -eq 0 ]]; then
  printf 'Review prompt file: %s\n' "$REVIEW_PROMPT"
fi
exit "$prep_rc"
```

Only after successful preparation, give that invocation's prompt-file path,
repo path, and reviewed SHA to a fresh-context read-only native reviewer.
Require it to read the complete file, using bounded chunks if needed, including
the scope and any helper truncation warning. Do not substitute a tool preview
or a prior prompt file. Supply evidence,
not the parent's reasoning history. Require an explicit `APPROVE: <reason>`
or `REJECT: <reason>`; failed preparation, missing/malformed verdicts, or a
missing independent reviewer stop this path. Parent self-review is not a
substitute. Investigate rejection before continuing. On resume, repeat if
the decision for this SHA/scope is unavailable. Approval covers only that
scope, not subsequent changes; Step 5 reviews the full final branch.

## 4d. Non-k8s Go module updates (--bump-tools only)

If `--bump-tools` was passed, discover and bump outdated non-k8s
direct Go dependencies. Skip deps in replace directives or pinned
to commit hashes. Verify k8s pins stay intact after each bump.
One commit per dep.

If `--bump-tools` was not passed, skip this section.

---

If 4d changes HEAD, re-validate and refresh all current-step gates before
returning results. Only the parent advances, using the protocol in SKILL.md.
