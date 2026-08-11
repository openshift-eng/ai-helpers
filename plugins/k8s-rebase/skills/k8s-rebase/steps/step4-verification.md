# Step 4: Lint, Test, and Review

**PROGRESS: 80% complete**

Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` first.

## 4a. Lint iteration

```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-validate.sh" --no-test
```

Fix every reported issue. Run lint once, analyze ALL errors before
fixing any. Group by category and fix each in one commit.

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
- For errcheck: fix the code, not the linter.
  `defer f.Close()` → `defer func() { _ = f.Close() }()`
  `fmt.Fprintf(w, ...)` where the error is non-critical → `_, _ = fmt.Fprintf(w, ...)`
  Only use `exclude-functions` in `.golangci.yml` when the same pattern
  appears many times AND fixing each instance would obscure the real code.
  Never use per-line `//nolint:errcheck` for patterns that could be fixed in code.
- Staticcheck deprecated calls: use selective `//nolint:staticcheck`
  or `exclude-rules`, never disable entirely
- Nilness dead code: remove the entire dead block, do not restructure
- ST1005 error strings: lowercase first letter only, preserve
  acronyms. Grep for OLD string in all files (tests assert on it)

Iterate with `--quick` for build+vet, `--no-test` for lint. Repeat
until `--no-test` exits 0.

## 4b. Verification wave

Launch ALL gates immediately — do NOT wait for 4a to finish.
Gates run as parallel subagents while the main agent iterates
on lint fixes. In your first response, launch gate subagents
AND run the first lint command together. First, discover test
packages:

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
`--test-only` flag. For large packages (>20k test lines), use nohup.
Split by test line count, cap ~30k per agent. Check `free -h` first.

**Gate agents:** Run the orchestrator's gates command first:
```bash
bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" gates "$(pwd)" 4
```
Launch subagents only for PENDING gates. Gate files are at
`${PLUGIN_ROOT}/gates/step4-verification/`. Each subagent: repo path
+ module safety rule + "Read `<gate-file>` and follow instructions."
Let the subagent Read the gate file — do NOT cat it.

15 gates: cleanliness, correctness, version-completeness,
maintainer-review, ci-prediction, build-vet-recheck, skill-improvement,
logical-consistency, ci-readiness, gomod-diff-analysis,
deprecated-imports, go-version-check, k8s-changelog, dep-cve-check,
commit-messages.

## Gate-fix loop

If ANY gate reports FAIL: triage (check base branch), fix + commit,
re-validate with `--no-test`, re-run the orchestrator gates command
to refresh evidence, then delete ONLY that specific gate's report
(`rm .rebase-tmp/gates/step4-<gate>.report`) and re-run that gate.
**NEVER delete step2-*.report or step3-*.report from step 4** —
the orchestrator is forward-only. Prior-step reports cannot be
regenerated. The orchestrator's own HEAD-stamp check handles
staleness; you do not need to delete cross-step reports manually.
Step 4 override: always re-run `validate.sh --no-test` between fix
and gate re-run (catches regressions from fix commits).

If test agents report failures:
- **Timeout:** likely feature gate issue (informer hang)
- **Flaky:** re-run individual test with `-count=1 -run TestName`
- **Container timing:** check if test code changed in rebase
- **Pre-existing:** check merge-base diff — don't fix if unchanged

## 4c. Independent review

```bash
REVIEW=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-review.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
[ -n "$REVIEW" ] && bash "$REVIEW" "$(git rev-parse HEAD)" "k8s rebase"
```

APPROVE → proceed. REJECT → investigate the stated reason.

## 4d. Non-k8s Go module updates (--bump-tools only)

If `--bump-tools` was passed, discover and bump outdated non-k8s
direct Go dependencies. Skip deps in replace directives or pinned
to commit hashes. Verify k8s pins stay intact after each bump.
One commit per dep.

If `--bump-tools` was not passed, skip this section.

---

Run `bash "${PLUGIN_ROOT}/scripts/k8s-rebase-orchestrator.sh" advance "$(pwd)"`
