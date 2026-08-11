Final verification that no deprecated imports remain. This runs
AFTER step3 gates AND fix commits, so focus on what survived
the entire fix pipeline.

Promoted x/ packages:
  `grep -rn '"golang.org/x/' --include='*.go' . | grep -v vendor/ | grep -v .cache/`

For each hit, check if a stdlib equivalent is available in the Go
version this repo targets:
  `GO_MINOR=$(grep '^go ' go.mod | awk '{print $2}' | cut -d. -f2)`

Known stdlib promotions (require GO_MINOR at or above the listed value):
  golang.org/x/exp/slices → slices    (Go 1.21+)
  golang.org/x/exp/maps   → maps      (Go 1.21+)
  golang.org/x/exp/cmp    → cmp       (Go 1.21+)
  golang.org/x/net/context → context  (Go 1.7+)

k8s ecosystem deprecated packages (also check):
  `grep -rn '"k8s.io/utils/strings/slices"\|"k8s.io/utils/pointer"' --include='*.go' . | grep -v vendor/ | grep -v .cache/`
- `k8s.io/utils/strings/slices` -> stdlib `slices` (requires Go 1.21+)
- `k8s.io/utils/pointer` -> `k8s.io/utils/ptr` (no Go version floor)

If GO_MINOR is below the required floor for a given package, report
as INFO — the stdlib equivalent is not yet available for this repo's
Go version. Do NOT use `go doc` to check availability — the local
toolchain may differ from the go.mod directive and produce wrong verdicts.
Use the table above instead.

Do NOT re-run build, vet, or the vendor deprecated-symbol scan
— build-vet-recheck and step3's deprecated-api-remnants gates
already cover those.

MANDATORY pre-existing check — run for EVERY deprecated import finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <import-path>:
base_has=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<import-path>')
was_modified=$(git diff --name-only "$BASE"..HEAD -- "<file>" | wc -l)
```

Two tiers:
1. File WAS modified by the rebase (was_modified > 0):
   - If base_has==0 (import is NEW): FAIL — rebase introduced it
   - If base_has>0 (import pre-existing): check whether the diff touches
     the import block specifically (grep the diff for the import path):
     `git diff "$BASE"..HEAD -- "<file>" | grep '<import-path>'`
     If the diff shows the import line changed: FAIL (rebase touched the import)
     If the diff does NOT show the import changed (rebase modified other parts
     of the file only): INFO — out of scope, the deprecated import was already
     there and the rebase didn't cause it
2. File was NOT modified by the rebase (was_modified=0): INFO — out of scope.

If GO_MINOR is below the required floor for a given package: INFO
regardless of tier (can't migrate if stdlib equivalent doesn't exist yet).

Report count of FAIL-tier findings only. Cite file:line for each hit.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.
Note: `go doc` is prohibited — use the stdlib-promotion table above to check
package availability; the local toolchain version may differ from go.mod.

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
