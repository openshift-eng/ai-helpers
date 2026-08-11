MANDATORY FIRST STEP — run the companion gate script:

```bash
GATE_DIR=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -path "*/k8s-rebase/gates/step2-compilation" -type d 2>/dev/null | head -1)
bash "$GATE_DIR/version-consistency.sh" "$(pwd)"
```

Read the output carefully. Apply these rules in order:

RULE 1 — FAST-PATH: If NEW_ISSUES=0, set verdict=PASS immediately.
Write the PASS report and stop. Do NOT run the checks below.

RULE 2 — PER-ISSUE FILTER (when NEW_ISSUES>0): Only analyze issues
the script flagged as "MISMATCH" or "VENDOR-DRIFT". Determine if
each is a real problem requiring investigation.

If the companion script is not found, fall back to manual checks:

Count go.mod files where k8s.io/* dependency versions are
inconsistent (different minor versions across k8s.io packages
within the same go.mod). For each module with a vendor/ directory, verify
vendor is in sync with go.mod (check vendor/modules.txt).
Also run `go mod verify` in vendored modules to check vendor
consistency mechanically.
Report inconsistency count.

Also verify versions match the REBASE TARGET, not just that they
are consistent with each other. If `.rebase-tmp/target-k8s-api-version.txt`
exists, read the expected version (e.g. `v0.34.1`). Check that
`grep 'k8s.io/api ' go.mod` matches it. If ALL k8s deps are at a
DIFFERENT consistent version (e.g. all at v0.35.1 when target is
v0.34.1), that is a FAIL — the rebase was reverted or mis-targeted
by MVS. Count this as 1 inconsistency.

VERDICT criteria: FAIL if any k8s.io/* dependency version is
inconsistent with the target version or with each other. PASS if
all versions are consistent and match the target.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step2-version-consistency PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
