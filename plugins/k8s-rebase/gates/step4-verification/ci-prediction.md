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
  that git log shows a codegen commit. If the repo has a
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

Rules: report specific findings, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
