Detect deprecated symbols, removed APIs, and stale imports
surfaced by the k8s dependency bump. Discover issues dynamically
— do NOT rely on a pre-existing list of known patterns.

First, find all module directories:
  `find . -name go.mod -not -path '*/vendor/*' -not -path '*/.cache/*' -exec dirname {} \;`

Step 1 — Build + vet check (catches compile-breaking changes):
  In each module directory, run:
  `go build ./... 2>&1` (add `-mod=vendor` if vendor/ exists)
  `go vet ./... 2>&1` (add `-mod=vendor` if vendor/ exists)
  Any error is a finding. If Go is unavailable, note as SKIPPED.

Step 2 — Discover deprecated symbols via web search:
  Read the Go version from go.mod (`go` directive) and the k8s
  version from the k8s.io/api dependency. Then search the web:
  - "Go <version> deprecated functions stdlib changes"
  - "kubernetes <version> breaking changes deprecated APIs"
  Build a list of deprecated symbols/imports from the results.
  For each, grep non-vendor Go files:
  `grep -rn '<pattern>' --include='*.go' . | grep -v vendor/ | grep -v .cache/`

Step 3 — Promoted x/ package check:
  `grep -rn '"golang.org/x/' --include='*.go' . | grep -v vendor/ | grep -v .cache/`
  For each x/ import, derive the stdlib name and check whether it is
  available in the Go version this repo targets. Extract the target:
  `GO_MINOR=$(grep '^go ' go.mod | awk '{print $2}' | cut -d. -f2)`
  Known stdlib promotions and their minimum Go minor version:
    golang.org/x/exp/slices → slices (Go 1.21+)
    golang.org/x/exp/maps   → maps   (Go 1.21+)
    golang.org/x/exp/cmp    → cmp    (Go 1.21+)
    golang.org/x/net/context → context (Go 1.7+)
  If GO_MINOR is below the required floor, report as INFO, not FAIL —
  the stdlib equivalent is not yet available for this repo's Go version.
  Otherwise the x/ import should be migrated (FAIL finding).

Report each finding with file:line AND the recommended fix
(e.g., math/rand -> math/rand/v2, golang.org/x/exp/slices ->
slices). FAIL if any NEW deprecated usage or build error
exists. PASS if clean or only pre-existing issues.

MANDATORY pre-existing check — run for EVERY finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each finding at <file> with <symbol>:
base_count=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<symbol>')
curr_count=$(grep -c '<symbol>' "<file>" 2>/dev/null)
net_new=$(( curr_count > base_count ? curr_count - base_count : 0 ))
# net_new > 0: that many occurrences are NEW and count toward FAIL
# net_new == 0: all occurrences are PRE-EXISTING — do NOT count
```

Count the delta: only `curr_count - base_count` net-new occurrences
count toward FAIL. Do NOT use "base_has > 0" as a simple binary —
a file with 3 occurrences on base and 5 on HEAD has 2 NEW ones. If
ALL findings net_new == 0, verdict MUST be PASS.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
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
  "$REPO" step3-deprecated-api-remnants PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
