Read the autofix commit's diff. For each code change, verify it
is a correct transformation.

The autofix applies deterministic fix patterns. Any change from
the autofix script is expected — only flag changes that are
demonstrably WRONG (incorrect logic, wrong replacement, data
loss), not because they are unfamiliar.

Only flag a change as incorrect if the transformation itself is
WRONG (e.g., wrong format verb, missing field, wrong import
section), not because it's unfamiliar. K8S_VERSION patch-level
differences between go.mod and KIND/CI tooling are expected —
the autofix picks the latest available versions. Do not flag
patch-level differences (same major.minor, different patch) as a
concern. Do flag differences where the major or minor version changed
unexpectedly.

List each transformation category you checked and your finding.

VERDICT: FAIL if any autofix transformation is demonstrably wrong
(incorrect logic, wrong replacement, data loss). PASS if all
transformations are correct or cosmetic.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step3-autofix-diff-review PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
