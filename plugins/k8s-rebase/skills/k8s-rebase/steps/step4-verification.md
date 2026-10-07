# Step 4: Lint, Test, and Review

PROGRESS: 80% complete

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

## 4a. Lint iteration

```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-validate.sh" --no-test
```

Inspect which commands actually ran. `--no-test` also builds and vets; its
exit zero does not prove lint ran. If no lint target is found, inspect the
repository's CI/configuration for its lint entrypoint. Run it if configured;
otherwise report lint as not configured, with no lint PASS claim.

**Scope rule (applies before fixing anything):** Only fix lint errors that
are caused by changes required for this rebase. Inspect the finding and the
merge-base diff, including dependencies and lint/toolchain configuration.
An unchanged line can fail against a changed API; a changed line does not by
itself prove the diagnostic is new. Use existing baseline evidence when
sufficient. If baseline execution is needed, use a separate disposable clone,
not a worktree; never stash, reset, or switch the active checkout for comparison.

With `PLUGIN_ROOT` and `REPO_ROOT` bound, and `TMPDIR` outside the target checkout:

```bash
LINT_BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$REPO_ROOT") || {
  echo "ERROR: cannot resolve lint baseline" >&2
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
  If mounting a host Go toolchain to reuse its cache, select its executable
  through `PATH` as well as its matching `GOROOT`. Read back `command -v go`,
  `go version`, and `go env GOROOT` inside the actual container before lint;
  setting `GOROOT` alone can leave the image's incompatible Go executable
  selected. Preserve failed attempts and use the existing shared retry budget.

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

Run tests and gates sequentially, with test workers writing separate logs and
gate reviewers writing only their own reports. Do not overlap them with source
mutations or full validation that replaces shared evidence. Parallel work is
allowed only on explicit user request under rules.md's execution constraints.
Commit 4a's fixes before collecting their final evidence;
if HEAD changes, refresh every current-step review as in rules.md.
Use native workers when available; run the same checks inline only when
the host exposes no worker tool.
First, discover test packages:

```bash
while IFS= read -r mod_dir; do
  TEST_GO_SH="$mod_dir/hack/test-go.sh"
  ROOT_PKGS=""
  [ -f "$TEST_GO_SH" ] && ROOT_PKGS=$(sed -n '/root_pkgs=(/,/)/p' "$TEST_GO_SH" | grep -oE 'pkg/[^"]+' || true)
  echo "=== $mod_dir ==="
  while IFS= read -r pkg; do
    [ -n "$ROOT_PKGS" ] && grep -Fxq -- "${pkg#./}" <<< "$ROOT_PKGS" && continue
    echo "$pkg"
  done < <(cd "$mod_dir" && find . -type d \( -name vendor -o -name .claude -o -name .git -o -name .rebase-tmp -o \( ! -path . -exec test -f '{}/go.mod' \; \) \) -prune -o -name "*_test.go" -exec dirname {} \; | sort -u)
done < <(find . -type d \( -name vendor -o -name .claude -o -name .git -o -name .rebase-tmp \) -prune -o -name "go.mod" -exec dirname {} \; | sort)
```

**Test agents:** Use ONLY packages from discovery above (filters
out exact root_pkgs that need CAP_NET_ADMIN). Retain each package's module
heading and execute the discovered unit-test packages, one module per
invocation. `--no-test` and compilation with `-run='^$'` do not execute them.
Keep the complete discovery output; `head` or a sample of subtrees can omit
changed-code consumers and entire nested modules. Before returning results,
reconcile every discovered package with a completed test result or a stated
infrastructure requirement. Wait for all launched validation/test/review jobs
and retain their real exits; refresh any verdict that used provisional output.
Retain each test command's exit status and log for the parent handoff and
Step 5; identify packages requiring unavailable infrastructure separately.
From `REPO_ROOT`, pass that
repo-relative module explicitly, for example:

```bash
bash "$PLUGIN_ROOT/scripts/k8s-rebase-validate.sh" --test-only --module ./test/e2e ./ipalloc
```

Do not combine packages from different modules or rely on the caller's cwd;
without `--module`, the helper uses the primary module. Discovery also finds
integration suites: inspect their runtime requirements and report missing
infrastructure as INCONCLUSIVE, never as a unit-test pass.
Inspect CI and each suite's setup for separate runtime modes. A package named
`e2e` may have both offline and live-cluster modes: account for each mode and
its actual prerequisites. A missing cluster does not explain omitted offline
coverage. Record concrete missing binaries, fixtures, privileges, or services
when a mode cannot run. Pass discovered package names as separate argv values
(for example a Bash array), never one quoted space-delimited string.
For large packages (>20k test lines), use native waiting.
Split by test line count, cap ~30k per agent. Check `free -h` first.
The validator preserves `GOMEMLIMIT`, `GOMAXPROCS`, `GOFLAGS`, and validation/lint
timeouts when it auto-containerizes. Set `K8S_REBASE_CONTAINER_MEMORY` to the
chosen hard container limit (for example `4g`) on constrained hosts; the Go
memory setting alone is soft. Choose limits from available memory and the
user's constraints, and keep validation invocations sequential.
If compilation reports space/quota errors under `/tmp/go-build*`, inspect
that filesystem separately from the checkout's disk. A tmpfs quota can fail
while the checkout still has space. Retain the failed attempt, then retry
with `GOTMPDIR` and `TMPDIR` bound to a task-owned directory on a filesystem
with sufficient space; do not delete unrelated temporary files or call an
unexecuted test successful.

Before dispatching `dep-cve-check`, the parent checks whether `govulncheck`
is available and collects its complete output and producer exit for each
affected module, sequentially. Follow that gate's resource limits and capture
block. Pass the log paths, module scope, and scanned SHA to the reviewer.
The OSV companion does not run govulncheck. If the scanner cannot run, pass
the actual availability/resource evidence so the gate retains that coverage
limit; do not describe OSV collection as a completed call-graph scan.

**Gate agents:** Run the orchestrator's gates command first:

```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" 4
```

Follow rules.md: delegate PENDING gates when available, or review inline.
Inspect cached non-PASS verdicts too. Supply the absolute repo and plugin
paths, version, module safety and verdict rules, and the gate prompt path
under `${PLUGIN_ROOT}/gates/step4-verification/`.

15 gates: cleanliness, correctness, version-completeness,
maintainer-review, ci-prediction, build-vet-recheck, skill-improvement,
logical-consistency, ci-readiness, gomod-diff-analysis,
deprecated-imports, go-version-check, k8s-changelog, dep-cve-check,
commit-messages.

## Gate-fix loop

Follow rules.md's shared loop within the budget carried from 4a.
Step 4 requires `validate.sh --no-test` after fix commits, before refreshing
current-step evidence and reviews, so lint regressions are checked too.

If test agents report failures:

- **Timeout:** likely feature gate issue (informer hang); see rules.md's
  Feature Gates
- **Flaky:** re-run individual test with `-count=1 -run TestName`
- **Container timing:** check if test code changed in rebase
- **Pre-existing:** use 4a's baseline/evidence check; unchanged test code can
  fail because dependencies changed.

For network-namespace permission failures, inspect the repository's container
test setup and try its isolated container path when a runtime is available.
The validator's `--full` mode requests a privileged container on nonroot hosts
even when local Go is current, preserving Go concurrency limits and caches.
Rootless containers can provide capabilities inside their own user/network
namespaces: a host permission failure does not prove container execution is
unavailable. Run the tests there and retain the actual result or blocker.
If container execution was not attempted, say so; do not claim the runtime
cannot support it. Root in a container alone is not evidence of passing tests.

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
A fallback `APPROVE:` for a missing CLI or template, or no verdict, means no
review ran: report it that way, not as approval.

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
direct Go dependencies, one at a time with
`bash "$PLUGIN_ROOT/scripts/k8s-rebase-depfix.sh" <module>@<version>` in
the module that requires it. Skip deps in replace directives or pinned
to commit hashes. Verify k8s pins stay intact after each bump.
One commit per dep.

If `--bump-tools` was not passed, skip this section.

---

If 4d changes HEAD, re-validate and refresh all current-step gates before
returning results. Only the parent advances, using the protocol in SKILL.md.
