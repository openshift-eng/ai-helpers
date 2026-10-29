Run this check FIRST to find candidate conversions:

```bash
REPO="<the absolute repo path from reviewer context>"
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$REPO") || exit 1
TYPE_CONV=$(cd "$REPO" && git diff "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep -E '^\+.*(\(\w+\)\(|\.(\w+)\{|type assertion|\.\(\*?[\w.]+\))' | head -20)
if [ -z "$TYPE_CONV" ]; then
  echo "No regex matches; inspect the Go diff before deciding applicability"
fi
```

Before deciding SKIP, scan the non-vendor Go diff for conversions the regex
may miss, including bare named-type calls such as `NewType(oldVar)`.
Write SKIP only if no fix commits involve struct conversions or type assertions.

If type conversions ARE found: for each struct conversion or type
assertion, read the FULL struct/interface definition in vendor and
list ALL fields or methods. Compare against the conversion code.
Are any fields silently dropped? Could any conversion lose data?

List each struct you checked and your finding. Do not just say
"no issues" -- show your work.

VERDICT criteria: FAIL if any struct conversion silently drops
fields or could lose data at runtime. SKIP if no fix commits
involve type conversions. PASS if all conversions are complete.

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
SCRIPT="$PLUGIN_ROOT/scripts/write-gate-report.sh"
bash "$SCRIPT" "$REPO" step2-type-conversions PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
