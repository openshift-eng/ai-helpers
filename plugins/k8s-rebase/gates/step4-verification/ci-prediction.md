Analyze whether the rebase changes will cause CI failures.
Only flag issues caused by or affected by the rebase diff —
pre-existing CI steps that were not modified are out of scope.
Could any test pass locally but fail in CI due to:
- Missing fixtures or CRDs?
- Wrong API versions in test expectations?
- Hardcoded assumptions about cluster behavior?
- e2e infrastructure incompatibilities (wrong KIND image,
  missing CRDs, stale FRR images, kubeadm format)?
- Feature gates not disabled in a test package that uses
  informers or watch-based patterns with fake clientsets?
  (Skip this check for repos whose unit tests use envtest
  or no informers — the pattern only applies to informer-based
  unit tests with fake clientsets.)
  Only flag packages that create informers AND lack gate
  setup. Do NOT flag packages that just use fake clientsets
  for simple CRUD operations. Search for test-go.sh at the
  repo root AND under subdirectories (e.g., hack/test-go.sh
  or go-controller/hack/test-go.sh). If it exports
  KUBE_FEATURE_* env vars, those cover ALL packages when
  run via `make test` — don't flag packages that are covered
  by test-go.sh exports.
- Stale codegen output? If hack/update-codegen.sh or a
  Makefile codegen/generate/manifests target exists, check
  that git log shows a codegen commit (i.e., a commit whose
  changed files include zz_generated*.go, */clientset/*,
  */informers/*, */listers/*, or pkg/generated/*, or whose
  message contains codegen, generate, or deepcopy). If no
  commit matches these patterns but the repo has a codegen
  script, flag as CONFIRMED stale-codegen risk. If the repo has a
  `verify-update-codegen` or `verify` CI job, stale output
  will fail `git diff --exit-code`. Look for controller-gen
  version annotations in CRD manifests matching the vendored
  controller-tools version.

Known ecosystem failures (report, may need manual fix):
- `ci/prow/security` (Snyk) — check if `.snyk` exists in the
  repo. If it uses per-file exclusions (not `vendor/**` glob),
  warn that Snyk rules may flag new vendor files. Repos with
  `vendor/**` glob exclusions are safe. Per-file repos may
  need manual `.snyk` updates or a switch to the glob approach.
- `ci/prow/verify-deps` may fail if library-go or other
  plumbing repos haven't merged their k8s bump yet. Verify
  the skill added a `replace` directive in go.mod pointing
  to a fork with the compatibility fix. If no replace was
  added and library-go hasn't merged, flag as a blocker.

Check e2e test files, CI config (.github/workflows/test.yml),
and KIND setup scripts. For each finding, classify as
CONFIRMED (verified from code or artifacts) or SPECULATIVE.
Only CONFIRMED findings should be rated above LOW risk.

MANDATORY pre-existing check — run for EVERY CONFIRMED finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <pattern>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<pattern>')
# If base_has > 0, the issue is PRE-EXISTING — do NOT count it
```

If base_has > 0, the issue is PRE-EXISTING. It is still pre-existing
even if the rebase modified the file — what matters is whether the
rebase introduced or changed the specific offending pattern. Check the
diff for the exact line: if the diff shows the offending export or sudo
line as unchanged (no + or - on that specific line), it is pre-existing
INFO. If the diff shows the pattern was added or modified, it is NEW FAIL.
If ALL findings are pre-existing INFO, verdict MUST be PASS.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific findings, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. For CONFIRMED findings, state the specific fix needed. Cite file:line for any issues.

VERDICT: FAIL if any NEW CONFIRMED issue would cause CI failure.
PASS if no confirmed issues. Speculative concerns are INFO,
not FAIL.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-ci-prediction PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
