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
minor version mismatches as a concern.

List each transformation category you checked and your finding.

VERDICT: FAIL if any autofix transformation is demonstrably wrong
(incorrect logic, wrong replacement, data loss). PASS if all
transformations are correct or cosmetic.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step3-autofix-diff-review PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
