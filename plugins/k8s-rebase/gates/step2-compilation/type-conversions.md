Run this check FIRST to decide if this gate applies:

```bash
REPO="<the absolute repo path from reviewer context>"
BASE=$(cd "$REPO" && git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
TYPE_CONV=$(cd "$REPO" && git diff "$BASE"..HEAD -- '*.go' ':(exclude,glob)**/vendor/**' | grep -E '^\+.*(\(\w+\)\(|\.(\w+)\{|type assertion|\.\(\*?[\w.]+\))' | head -20)
if [ -z "$TYPE_CONV" ]; then
  echo "No type conversions in fix commits — SKIP"
fi
```

If no fix commits touch struct conversions or type assertions,
write a SKIP report and stop immediately.

If type conversions ARE found: for each struct conversion or type
assertion, read the FULL struct/interface definition in vendor and
list ALL fields or methods. Compare against the conversion code.
Are any fields silently dropped? Could any conversion lose data?

Also scan the diff visually for bare named-type conversions that
the regex may miss — patterns like `NewType(oldVar)` or
`TypeName(expr)` where the type name appears at the start of the
expression. The regex only catches `.Type{...}` and `.(*Type)`
forms; direct named-type conversions are equally important to check.

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
