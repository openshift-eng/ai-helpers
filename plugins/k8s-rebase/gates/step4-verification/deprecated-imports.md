Final verification that no deprecated imports remain. This runs
AFTER step3 gates AND fix commits, so focus on what survived
the entire fix pipeline.

Promoted x/ packages:
  `grep -rn '"golang.org/x/' --include='*.go' . | grep -v vendor/ | grep -v .cache/`

Known promotions (check these first):
- `golang.org/x/exp/slices` -> `slices` (Go 1.21+)
- `golang.org/x/exp/maps` -> `maps` (Go 1.21+)
- `golang.org/x/net/context` -> `context` (Go 1.7+)
- `golang.org/x/sync/errgroup` -> still x/ (NOT promoted)

k8s ecosystem deprecated packages (also check):
  `grep -rn '"k8s.io/utils/strings/slices"\|"k8s.io/utils/pointer"' --include='*.go' . | grep -v vendor/ | grep -v .cache/`

- `k8s.io/utils/strings/slices` -> stdlib `slices` (Go 1.21+)
- `k8s.io/utils/pointer` -> `k8s.io/utils/ptr`

For each hit, derive the stdlib name and verify with:
  `go doc <stdlib-name> 2>/dev/null`
If available in stdlib, the x/ import is a FAIL finding — the
import must be replaced with the stdlib equivalent.

Ensure local Go matches the `go` directive in go.mod, or use
a container with the correct version. `go doc` results depend
on the local Go toolchain — a mismatch produces wrong verdicts.

Do NOT re-run build, vet, or the vendor deprecated-symbol scan
— build-vet-recheck and step3's deprecated-api-remnants gates
already cover those.

MANDATORY pre-existing check — run for EVERY deprecated import finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <import-path>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<import-path>')
# If base_has > 0, the x/ import is PRE-EXISTING — do NOT count it
```

If the deprecated import exists on the base branch, it is pre-existing —
report as "INFO (pre-existing)" but do NOT include in the ISSUES
count. Only imports NOT on the base branch are NEW and count
toward FAIL. If ALL findings are pre-existing, verdict MUST be
PASS.

Report count of NEW x/ imports that have stdlib equivalents.
Cite file:line for each hit. Zero new findings means PASS.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for each hit.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-deprecated-imports PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
